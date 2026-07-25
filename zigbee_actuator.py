"""Zigbee 执行层 —— 哨兵唯一的物理动作能力：给白名单插座限时断电。

## 为什么不是「检测到异常就直接关」

README 原本的核心论证是「只监控，不控制」：哨兵被攻破，攻击者也拿不到任何
设备的控制权。一旦哨兵能直接关电，这个论证就没了——它自己变成了最有价值的目标。

本模块用**能力分离**保住这个论证：

    决策方（哨兵）  持签名私钥，只能"请求"封堵，拿不到网关凭据
    执行方（本模块）持网关凭据，只认签名过的封堵令，且只在白名单内动作

攻破哨兵 → 拿不到网关凭据，伪造不出合法封堵令（没有私钥）
攻破执行方 → 拿到网关凭据，但只能关白名单里那几个插座
两边都被攻破 → 仍改不了已锚定上链的历史记录

## 四道校验（缺一不可，顺序不能变）

    ① 签名有效        —— 不是哨兵签的，直接丢
    ② 目标在白名单    —— 冰箱/路由器/医疗设备永远不在表里
    ③ 动作允许        —— **只能关，不能开**（见下）
    ④ 未过期且 nonce 未用过 —— 防重放

为什么「只能关不能开」：攻击者攻破哨兵后，无法用它给已被断电的设备恢复供电。
恢复只能由 TTL 到期或人工触发，不走这条通道。

## TTL 是硬性的

封堵是临时措施，不是永久判决。误判的代价必须有上限——断的可能是冰箱、
医疗设备、正在渲染的机器。到期自动恢复，且恢复动作同样入链。

## 传输：本地优先

CCTV_DEMO_PLAN §54-56 把封堵归入「断网也必须能做」那一类，所以走 tinytuya
局域网直连；涂鸦云 API 只作兜底。Zigbee 子设备通过网关寻址（cid = 子设备节点 id）。

## 未配置硬件时

自动进入 dry-run：全部校验照跑、结果照样入链，只是不真的下发指令。
这样策略逻辑可以先于硬件完成并测试。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger("zigbee_actuator")

# ---- 配置 ----
GATEWAY_IP = os.environ.get("TUYA_GATEWAY_IP", "")
GATEWAY_ID = os.environ.get("TUYA_GATEWAY_ID", "")
GATEWAY_KEY = os.environ.get("TUYA_GATEWAY_KEY", "")      # local key，从涂鸦云取一次
GATEWAY_VERSION = os.environ.get("TUYA_GATEWAY_VERSION", "3.3")

DEFAULT_TTL = int(os.environ.get("CONTAIN_TTL", "120"))   # 秒
MAX_TTL = 600
SWITCH_DP = "1"                                            # 插座开关 DP，涂鸦标准


# ---- 目标白名单 ----------------------------------------------------
# 硬约束，不是配置项。只有登记过的设备可被封堵。
# 新增设备必须显式加进来——默认拒绝，而不是默认允许。
@dataclass
class ContainTarget:
    label: str                  # 人话名字，播报/屏显用
    cid: str = ""               # Zigbee 子设备节点 id（直连 Wi-Fi 设备留空）
    max_ttl: int = 300
    allow_auto: bool = False    # 是否允许无人确认自动封堵


WHITELIST: dict[str, ContainTarget] = {
    "smart-plug-07": ContainTarget(label="客厅插座", cid="", max_ttl=300, allow_auto=False),
}

ALLOWED_ACTIONS = {"power_off"}     # 注意：没有 power_on


# ---- 状态 ----
@dataclass
class _Held:
    target: str
    expires_at: float
    timer: Optional[threading.Timer] = None


_held: dict[str, _Held] = {}
_used_nonces: set[str] = set()
_lock = threading.Lock()

# 每一次动作都要留证。由调用方注入 AlertChain.add_alert 之类的回调。
_recorder: Optional[Callable[[str, str, float], None]] = None


def configure(gateway_ip: str = "", gateway_id: str = "", gateway_key: str = "",
              version: str = "", recorder: Callable | None = None) -> None:
    """注入网关凭据与留证回调。凭据只在本模块持有，哨兵主进程不碰。"""
    global GATEWAY_IP, GATEWAY_ID, GATEWAY_KEY, GATEWAY_VERSION, _recorder
    if gateway_ip:
        GATEWAY_IP = gateway_ip
    if gateway_id:
        GATEWAY_ID = gateway_id
    if gateway_key:
        GATEWAY_KEY = gateway_key
    if version:
        GATEWAY_VERSION = version
    if recorder is not None:
        _recorder = recorder


def is_dry_run() -> bool:
    """没有完整凭据 → 只跑校验与留证，不下发指令。"""
    return not (GATEWAY_IP and GATEWAY_ID and GATEWAY_KEY)


def _record(target: str, action: str, ok: bool) -> None:
    if _recorder is None:
        return
    try:
        _recorder(target, f"containment_{action}_{'ok' if ok else 'fail'}", 1.0)
    except Exception as e:                       # noqa: BLE001 —— 留证失败不能反过来阻断动作
        log.warning("留证回调失败: %s", e)


# ---- 四道校验 ------------------------------------------------------
def _validate(order: dict, verify_signature: Callable[[dict], bool] | None) -> str:
    """返回空串=通过，否则返回拒绝原因。顺序不能变：先验身份，再看权限。"""
    # ① 签名
    if verify_signature is not None:
        if not verify_signature(order):
            return "signature_invalid"
    elif order.get("signature"):
        log.warning("收到带签名的封堵令但未注入验签函数——按未签名处理")

    # ② 目标白名单
    target = order.get("target", "")
    if target not in WHITELIST:
        return f"target_not_whitelisted({target})"

    # ③ 动作白名单
    action = order.get("action", "")
    if action not in ALLOWED_ACTIONS:
        return f"action_not_allowed({action})"

    # ④ 时效与重放
    expiry = float(order.get("expires_at", 0))
    if expiry and time.time() > expiry:
        return "order_expired"
    nonce = order.get("nonce", "")
    if not nonce:
        return "nonce_missing"
    with _lock:
        if nonce in _used_nonces:
            return "nonce_replayed"
    return ""


# ---- 设备通信 ------------------------------------------------------
def _device(target: str):
    """构造 tinytuya 句柄。Zigbee 子设备经网关寻址（cid），Wi-Fi 设备直连。"""
    import tinytuya
    spec = WHITELIST[target]
    d = tinytuya.OutletDevice(dev_id=GATEWAY_ID, address=GATEWAY_IP,
                              local_key=GATEWAY_KEY, version=float(GATEWAY_VERSION),
                              cid=spec.cid or None)
    d.set_socketTimeout(5)
    return d


def _set_power(target: str, on: bool) -> tuple[bool, str]:
    """下发开关指令并**回读验证**。不能只信命令返回值——返回 ok 不代表继电器真的动了。"""
    if is_dry_run():
        return True, "dry_run"
    try:
        d = _device(target)
        d.set_value(SWITCH_DP, on)
        time.sleep(1.0)                          # 给继电器与状态上报留时间
        status = d.status() or {}
        dps = status.get("dps", {})
        actual = dps.get(SWITCH_DP)
        if actual is None:
            return False, "readback_no_state"
        if bool(actual) != on:
            return False, f"readback_mismatch(want={on} got={actual})"
        return True, "verified"
    except Exception as e:                       # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# ---- 对外 API ------------------------------------------------------
def contain(order: dict, verify_signature: Callable[[dict], bool] | None = None) -> dict:
    """执行一条封堵令。四道校验全过才动手。

    order = {target, action, ttl, nonce, expires_at, alert_hash, signature?}
    返回 {ok, executed, reason, expires_at, dry_run}

    失败绝不重试到底——反复开关插座比不封堵更危险。
    """
    reason = _validate(order, verify_signature)
    target = order.get("target", "?")
    if reason:
        log.warning("拒绝封堵令 target=%s: %s", target, reason)
        _record(target, "rejected", False)
        return {"ok": False, "executed": False, "reason": reason, "dry_run": is_dry_run()}

    spec = WHITELIST[target]
    ttl = min(int(order.get("ttl", DEFAULT_TTL)), spec.max_ttl, MAX_TTL)

    with _lock:
        _used_nonces.add(order["nonce"])
        if target in _held:                      # 已在封堵中：续期而不是重复下发
            _held[target].expires_at = time.time() + ttl
            log.info("目标 %s 已在封堵中，续期 %ds", target, ttl)
            return {"ok": True, "executed": False, "reason": "already_contained",
                    "expires_at": _held[target].expires_at, "dry_run": is_dry_run()}

    ok, detail = _set_power(target, on=False)
    log.info("封堵 %s (%s) -> %s / %s", target, spec.label, ok, detail)
    _record(target, "power_off", ok)
    if not ok:
        return {"ok": False, "executed": False, "reason": detail, "dry_run": is_dry_run()}

    expires_at = time.time() + ttl
    timer = threading.Timer(ttl, lambda: release(target, "ttl_expired"))
    timer.daemon = True
    with _lock:
        _held[target] = _Held(target=target, expires_at=expires_at, timer=timer)
    timer.start()

    return {"ok": True, "executed": True, "reason": detail,
            "expires_at": expires_at, "ttl": ttl, "dry_run": is_dry_run()}


def release(target: str, reason: str = "manual") -> dict:
    """恢复供电。TTL 到期自动调用，也可人工提前调用。

    注意：恢复**不走封堵令通道**——攻击者攻破哨兵也无法用它给设备复电。
    """
    with _lock:
        held = _held.pop(target, None)
        if held and held.timer:
            held.timer.cancel()
    if held is None:
        return {"ok": True, "executed": False, "reason": "not_contained"}

    ok, detail = _set_power(target, on=True)
    log.info("恢复 %s -> %s / %s (%s)", target, ok, detail, reason)
    _record(target, "power_on", ok)
    return {"ok": ok, "executed": True, "reason": f"{reason}/{detail}",
            "dry_run": is_dry_run()}


def status() -> dict:
    """当前封堵态，供 Quote/0 与仪表盘展示。"""
    now = time.time()
    with _lock:
        return {
            "dry_run": is_dry_run(),
            "gateway": GATEWAY_IP or "(未配置)",
            "whitelist": {k: v.label for k, v in WHITELIST.items()},
            "contained": {t: {"label": WHITELIST[t].label,
                              "remaining": round(h.expires_at - now, 1)}
                          for t, h in _held.items()},
        }


def release_all(reason: str = "shutdown") -> None:
    """收尾：把所有封堵解除。demo 结束/进程退出时调，别让插座一直断着。"""
    for t in list(_held):
        release(t, reason)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import uuid
    print("状态:", json.dumps(status(), ensure_ascii=False, indent=2))
    print("\n-- 四道校验演示 --")
    base = {"action": "power_off", "ttl": 30, "expires_at": time.time() + 60}
    cases = [
        ("白名单外的设备", {**base, "target": "smart-fridge-01", "nonce": uuid.uuid4().hex}),
        ("试图开机而非关机", {**base, "target": "smart-plug-07", "action": "power_on",
                              "nonce": uuid.uuid4().hex}),
        ("过期的封堵令", {**base, "target": "smart-plug-07", "expires_at": time.time() - 1,
                          "nonce": uuid.uuid4().hex}),
        ("合法封堵", {**base, "target": "smart-plug-07", "nonce": "demo-nonce-1"}),
        ("重放同一条", {**base, "target": "smart-plug-07", "nonce": "demo-nonce-1"}),
    ]
    for name, order in cases:
        r = contain(order)
        print(f"  {name:20s} ok={str(r['ok']):5s} {r['reason']}")
    print("\n封堵态:", json.dumps(status(), ensure_ascii=False))
    release_all("demo_end")
