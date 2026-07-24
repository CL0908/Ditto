"""MindReset Quote/0 电子墨水屏 —— 家庭安全哨兵的「实体告警输出」适配器。

Quote/0 不是传感器，是输出层：哨兵在 T5 本地检测到异常后，把**脱敏后的告警摘要**
推到这块 E-Ink 屏（Ambient Security Display），并作为 NFC 触碰进 Dashboard 的入口。

官方 API（已验证）：
  Text API :  POST https://dot.mindreset.tech/api/authV2/open/device/{DEVICE_ID}/text
  Canvas API: POST https://dot.mindreset.tech/api/authV2/open/device/{DEVICE_ID}/canvas
  认证: Authorization: Bearer {API_KEY}   限流: 10 req/s
  deviceId: 大写 12 位十六进制序列号(如 7CE8B17A3DF4)

配置（环境变量，绝不硬编码密钥）：
  DOT_API_KEY   = dot_app_xxx
  DOT_DEVICE_ID = 7CE8B17A3DF4
  DASHBOARD_URL = https://…（可选，NFC 触碰打开的事件详情页）
未配置 → 自动 MOCK 模式（打印不真发），本地 Demo 照跑。

设计约束（按项目要求）：
  ① API 失败绝不影响核心检测（全 catch，返回 bool）
  ② retry + timeout + 本地队列（离线自动补发）
  ③ 相同内容不重复刷新（dedup by hash）
  ④ E-Ink 是状态屏不是动画——最小刷新间隔守卫，不高频刷
  ⑤ 只发脱敏摘要，绝不发原始包/摄像头内容/完整 IP/拓扑/身份
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import deque

import httpx

log = logging.getLogger("mindreset_quote")

BASE = "https://dot.mindreset.tech"
API_KEY = os.environ.get("DOT_API_KEY", "")
DEVICE_ID = os.environ.get("DOT_DEVICE_ID", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
MOCK = not (API_KEY and DEVICE_ID)

USE_CANVAS = os.environ.get("QUOTE_CANVAS", "0") in ("1", "true", "True")  # 走 Canvas 富界面

MIN_REFRESH_INTERVAL = 15.0   # 秒：E-Ink 状态屏，别高频刷
TIMEOUT = 8.0
MAX_RETRY = 2

_last_hash: str | None = None
_last_push_ts = 0.0
_queue: deque = deque(maxlen=50)   # 本地补发队列 (url, payload)


def configure(api_key: str = "", device_id: str = "", dashboard_url: str = "") -> None:
    """运行时注入凭证（demo 从 .env dict 读出后调用）。都给了才退出 MOCK。"""
    global API_KEY, DEVICE_ID, DASHBOARD_URL, MOCK
    if api_key:
        API_KEY = api_key
    if device_id:
        DEVICE_ID = device_id
    if dashboard_url:
        DASHBOARD_URL = dashboard_url
    MOCK = not (API_KEY and DEVICE_ID and "replace_with" not in API_KEY)


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _text_url() -> str:
    return f"{BASE}/api/authV2/open/device/{DEVICE_ID}/text"


def _canvas_url() -> str:
    return f"{BASE}/api/authV2/open/device/{DEVICE_ID}/canvas"


def _hash(payload: dict) -> str:
    # text 用 title|message；canvas 无这俩字段时对整包哈希（去重仍生效）
    if "title" in payload or "message" in payload:
        key = payload.get("title", "") + "|" + payload.get("message", "")
    else:
        import json as _json
        key = _json.dumps(payload.get("windowData", payload), sort_keys=True,
                          ensure_ascii=False)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _post(url: str, payload: dict, dedup: bool = True, urgent: bool = False) -> bool:
    """带 dedup / 最小间隔 / retry / timeout / 队列的投递。失败返回 False，不抛异常。"""
    global _last_hash, _last_push_ts
    h = _hash(payload)
    if dedup and h == _last_hash:
        log.debug("跳过重复内容 %s", h)
        return True
    # 最小刷新间隔（E-Ink 保护）——太频繁则入队稍后补，不阻塞检测
    now = time.time()
    if not urgent and now - _last_push_ts < MIN_REFRESH_INTERVAL and dedup:
        log.info("刷新过快，入队稍后发")
        _queue.append((url, payload))
        return False

    if MOCK:
        _mock_print(payload)
        _last_hash, _last_push_ts = h, now
        return True

    for attempt in range(MAX_RETRY + 1):
        try:
            r = httpx.post(url, json=payload, headers=_headers(), timeout=TIMEOUT)
            # 4xx（除 429 限流）= 永久性错误(未绑定/参数错)，重试无用，直接放弃、不入队
            if 400 <= r.status_code < 500 and r.status_code != 429:
                log.warning("Quote/0 客户端错误 %d: %s（不重试/不入队）",
                            r.status_code, r.text[:120])
                return False
            r.raise_for_status()   # 5xx → 走 except 重试
            _last_hash, _last_push_ts = h, now
            log.info("Quote/0 已更新: %s", payload.get("title"))
            return True
        except Exception as e:   # 超时/网络/5xx/429 → 瞬时性，重试
            log.warning("Quote/0 投递失败(第%d次，将重试): %s", attempt + 1, e)
            time.sleep(0.5 * (attempt + 1))
    _queue.append((url, payload))   # 仍失败(瞬时性) → 入队补发
    return False


def flush_queue() -> int:
    """补发本地队列（哨兵主循环里定期调）。返回成功补发条数。"""
    sent = 0
    for _ in range(len(_queue)):
        url, payload = _queue.popleft()
        if _post(url, payload, dedup=False):
            sent += 1
        else:
            break   # 还是失败，留着下次
    return sent


def _mock_print(payload: dict):
    print("┌─ [Quote/0 · MOCK 未绑定/未配置] ──────────────")
    if payload.get("title"):
        print("│ " + payload["title"])
    for line in (payload.get("message", "")).split("\n"):
        print("│ " + line)
    if payload.get("signature"):
        print("│ — " + payload["signature"])
    if payload.get("link"):
        print("│ [NFC→ " + payload["link"] + "]")
    print("└──────────────────────────────────────────────")


# ============================================================
# 四个语义化推送（哨兵告警 pipeline 直接调）
# 只发脱敏摘要，绝不发原始流量/摄像头内容/完整IP/拓扑/身份
# ============================================================
def push_normal_status(device_count: int, security_score: int, last_checked: str) -> bool:
    return _post(_text_url(), {
        "title": "HOME SHIELD",
        "message": f"{device_count} Devices Protected\nSecurity Score: {security_score}\n\n✓ All devices normal",
        "signature": f"Last checked: {last_checked}",
        "refreshNow": True,
    })


def push_dashboard(snapshot: dict) -> bool:
    """实时安全仪表盘 —— 平时的 Quote/0 界面：设备数 / 安全分 / 实时流量 / 状态。

    snapshot 来自 traffic_sim.HomeTraffic.snapshot()（已聚合脱敏）：
      device_count, security_score, total_human, top_talker, top_talker_human,
      status, last_checked
    正常时刷（dedup 生效）；异常态下会被 push_anomaly_alert 的红屏盖过。
    """
    if USE_CANVAS:
        return push_dashboard_canvas(snapshot)
    status = snapshot.get("status", "正常")
    normal = snapshot.get("anomaly_count", 0) == 0
    icon = "🛡" if normal else "⚠"
    tag = "✓ 全部正常" if normal else f"⚠ {status}"
    return _post(_text_url(), {
        "title": f"{icon} HOME SHIELD",
        "message": (
            f"{snapshot.get('device_count', 0)} 台设备在线\n"
            f"安全分 {snapshot.get('security_score', 0)}/100\n"
            f"↕ 实时流量 {snapshot.get('total_human', '—')}\n"
            f"{tag}"
        ),
        "signature": (
            f"最忙 {snapshot.get('top_talker', '—')} "
            f"{snapshot.get('top_talker_human', '')} · {snapshot.get('last_checked', '')}"
        ),
        "refreshNow": True,
    })


def push_anomaly_alert(device_name: str, event_type: str, risk_score: int,
                       severity: str, incident_id: str, timestamp: str,
                       traffic_line: str = "") -> bool:
    if USE_CANVAS:
        return push_anomaly_canvas(device_name, event_type, risk_score, severity,
                                   incident_id, timestamp, traffic_line)
    sev = (severity or "").upper()
    # 异常翻红时补一行流量尖峰（脱敏聚合），让屏上“看得见被检测的流量”
    body = f"{device_name}\n{event_type}\n\nRisk: {sev} · {risk_score}/100"
    if traffic_line:
        body += f"\n{traffic_line}"
    return _post(_text_url(), {
        "title": f"⚠ {sev} ANOMALY",
        "message": body,
        "signature": f"{incident_id} · {timestamp}",
        "link": (f"{DASHBOARD_URL}/incident/{incident_id}" if DASHBOARD_URL else None),
        "refreshNow": True,
    }, urgent=True)


def push_evidence_sealed(incident_id: str) -> bool:
    if USE_CANVAS:
        return push_evidence_canvas(incident_id)
    return _post(_text_url(), {
        "title": "EVIDENCE SEALED",
        "message": f"Incident {incident_id}\nHash verified ✓\nChain intact ✓",
        "signature": "Tamper-proof on hash chain",
        "refreshNow": True,
    }, urgent=True)


def push_offline_status() -> bool:
    return _post(_text_url(), {
        "title": "SENTINEL OFFLINE",
        "message": "Local monitoring paused\nDevices unprotected",
        "signature": "Check T5 Core",
        "refreshNow": True,
    }, dedup=False, urgent=True)


# ============================================================
# Canvas 富界面（div/span/img + flex 布局）—— 比纯文字更清晰
# 需在 Dot App Content Studio 给设备 Loop 任务再加一个「Canvas API」项
# QUOTE_CANVAS=1 时，下面三个 text 函数自动改走 canvas
# ============================================================
def _el(type_: str, children=None, style: dict | None = None, tw: str = "") -> dict:
    props: dict = {}
    if tw:
        props["tw"] = tw
    if style:
        props["style"] = style
    if children is not None:
        props["children"] = children
    return {"type": type_, "props": props}


def _canvas_payload(root: dict, task_alias: str, link: str | None = None) -> dict:
    p = {"windowData": {"default": [root]}, "taskAlias": task_alias,
         "refreshNow": True, "border": 0}
    if link:
        p["link"] = link
    return p


def push_dashboard_canvas(snapshot: dict) -> bool:
    normal = snapshot.get("anomaly_count", 0) == 0
    accent = "#111" if normal else "#c62828"
    root = _el("div", style={
        "display": "flex", "flexDirection": "column", "width": "100%",
        "height": "100%", "padding": "14px", "backgroundColor": "#fff",
        "justifyContent": "space-between"}, children=[
        _el("div", style={"display": "flex", "justifyContent": "space-between",
                          "alignItems": "center"}, children=[
            _el("span", "🛡 HOME SHIELD", style={"fontSize": "26px", "fontWeight": "700", "color": "#111"}),
            _el("span", str(snapshot.get("security_score", 0)), style={
                "fontSize": "30px", "fontWeight": "800", "color": accent,
                "border": f"3px solid {accent}", "borderRadius": "10px", "padding": "2px 12px"}),
        ]),
        _el("div", style={"display": "flex", "flexDirection": "column", "gap": "4px"}, children=[
            _el("span", f"{snapshot.get('device_count', 0)} 台设备在线", style={"fontSize": "22px", "color": "#111"}),
            _el("span", f"↕ 实时流量 {snapshot.get('total_human', '—')}", style={"fontSize": "22px", "color": "#111"}),
            _el("span", ("✓ 全部正常" if normal else f"⚠ {snapshot.get('status', '')}"),
                style={"fontSize": "22px", "fontWeight": "700", "color": accent}),
        ]),
        _el("span", f"最忙 {snapshot.get('top_talker', '—')} {snapshot.get('top_talker_human', '')} · {snapshot.get('last_checked', '')}",
            style={"fontSize": "15px", "color": "#666"}),
    ])
    return _post(_canvas_url(), _canvas_payload(root, "sentinel-dash"))


def push_anomaly_canvas(device_name: str, event_type: str, risk_score: int,
                        severity: str, incident_id: str, timestamp: str,
                        traffic_line: str = "") -> bool:
    sev = (severity or "").upper()
    root = _el("div", style={
        "display": "flex", "flexDirection": "column", "width": "100%", "height": "100%",
        "padding": "14px", "backgroundColor": "#fff", "gap": "3px",
        "borderLeft": "10px solid #c62828"}, children=[
        _el("span", f"⚠ {sev} ANOMALY", style={"fontSize": "26px", "fontWeight": "800", "color": "#c62828"}),
        _el("span", device_name, style={"fontSize": "24px", "fontWeight": "700", "color": "#111"}),
        _el("span", event_type, style={"fontSize": "20px", "color": "#111"}),
        _el("span", f"Risk {sev} · {risk_score}/100", style={"fontSize": "20px", "fontWeight": "700", "color": "#c62828"}),
        _el("span", traffic_line or " ", style={"fontSize": "18px", "color": "#333"}),
        _el("span", f"{incident_id} · {timestamp}", style={"fontSize": "14px", "color": "#666"}),
    ])
    link = f"{DASHBOARD_URL}/incident/{incident_id}" if DASHBOARD_URL else None
    return _post(_canvas_url(), _canvas_payload(root, "sentinel-alert", link=link), urgent=True)


def push_evidence_canvas(incident_id: str) -> bool:
    root = _el("div", style={
        "display": "flex", "flexDirection": "column", "width": "100%", "height": "100%",
        "padding": "14px", "justifyContent": "center", "gap": "6px", "backgroundColor": "#fff"},
        children=[
        _el("span", "🔒 EVIDENCE SEALED", style={"fontSize": "26px", "fontWeight": "800", "color": "#1b5e20"}),
        _el("span", f"Incident {incident_id}", style={"fontSize": "20px", "color": "#111"}),
        _el("span", "Hash verified ✓  Chain intact ✓", style={"fontSize": "18px", "color": "#111"}),
        _el("span", "Tamper-proof on hash chain", style={"fontSize": "14px", "color": "#666"}),
    ])
    return _post(_canvas_url(), _canvas_payload(root, "sentinel-sealed"), urgent=True)


# 从脱敏告警字典一键推送（哨兵 alert pipeline 的统一入口）
def push_alert(alert: dict) -> bool:
    """alert = {device_name,event_type,risk_score,severity,incident_id,timestamp}（已脱敏）。"""
    return push_anomaly_alert(
        alert.get("device_name", "Unknown"),
        alert.get("event_type", "Anomaly detected"),
        int(alert.get("risk_score", 0)),
        alert.get("severity", "high"),
        alert.get("incident_id", "INC-0000"),
        alert.get("timestamp", ""),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("mode:", "MOCK" if MOCK else f"REAL (device {DEVICE_ID})")
    push_normal_status(5, 96, "12:42")
    time.sleep(0.1)
    push_anomaly_alert("Living Room Camera", "New external connection", 87, "high",
                       "INC-0042", "2026-07-24 12:45")
    push_evidence_sealed("INC-0042")
