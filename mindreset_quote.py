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
# QUOTE_IMAGE=1 → 走 Image API（像素级渲染，图表最清楚）。优先级：image > canvas > text。
# 三者都是同一份脱敏数据的不同呈现，任何一层失败都会向下回退，绝不让告警丢失。
USE_IMAGE = os.environ.get("QUOTE_IMAGE", "0") in ("1", "true", "True")
IMAGE_API_KEY = os.environ.get("DOT_IMAGE_API_KEY", "")   # Image API 用独立的 key

MIN_REFRESH_INTERVAL = 15.0   # 秒：E-Ink 状态屏，别高频刷
TIMEOUT = 8.0
MAX_RETRY = 2

_last_hash: str | None = None
_last_push_ts = 0.0
_queue: deque = deque(maxlen=50)   # 本地补发队列 (url, payload)


def configure(api_key: str = "", device_id: str = "", dashboard_url: str = "",
              image_api_key: str = "", use_image: bool | None = None) -> None:
    """运行时注入凭证（demo 从 .env dict 读出后调用）。都给了才退出 MOCK。

    image_api_key 单独传：Image API 在 Dot 后台是独立的一项内容，用的不是同一个 key。
    只要给了 image key 就默认打开 Image 分支（除非 use_image 显式指定）。
    """
    global API_KEY, DEVICE_ID, DASHBOARD_URL, MOCK, IMAGE_API_KEY, USE_IMAGE
    if api_key:
        API_KEY = api_key
    if device_id:
        DEVICE_ID = device_id
    if dashboard_url:
        DASHBOARD_URL = dashboard_url
    if image_api_key:
        IMAGE_API_KEY = image_api_key
        if use_image is None:
            USE_IMAGE = True
    if use_image is not None:
        USE_IMAGE = use_image
    MOCK = not (API_KEY and DEVICE_ID and "replace_with" not in API_KEY)


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


# ---- Image API 分支 -------------------------------------------------
# 放在这里而不是 demo.py：让所有调用方（demo / alert_chain / 未来的实时管线）
# 都自动走上，不用各自记得调 quote_image。
def _image_push(render, *args, **kwargs) -> bool:
    """渲染并推图。PIL 缺失 / 渲染出错 / 投递失败都返回 False，由调用方回退到
    canvas 或 text——三层任何一层挂了，告警都不会丢。"""
    if not (USE_IMAGE and not MOCK):
        return False
    try:
        import quote_image
        img = render(quote_image, *args, **kwargs)
        return quote_image.push(img, api_key=IMAGE_API_KEY or API_KEY,
                                device_id=DEVICE_ID)
    except Exception as e:                       # noqa: BLE001
        log.warning("Image API 分支失败，回退: %s", e)
        return False


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
        "title": "家庭哨兵",
        "message": f"{device_count} 台设备受保护\n安全分 {security_score}/100\n\n✓ 全部正常",
        "signature": f"最近检查 {last_checked}",
        "refreshNow": True,
    })


def push_dashboard(snapshot: dict) -> bool:
    """实时安全仪表盘 —— 平时的 Quote/0 界面：设备数 / 安全分 / 实时流量 / 状态。

    snapshot 来自 traffic_sim.HomeTraffic.snapshot()（已聚合脱敏）：
      device_count, security_score, total_human, top_talker, top_talker_human,
      status, last_checked
    正常时刷（dedup 生效）；异常态下会被 push_anomaly_alert 的红屏盖过。
    """
    if _image_push(lambda qi: qi.render_dashboard(snapshot)):
        return True
    if USE_CANVAS:
        return push_dashboard_canvas(snapshot)
    status = snapshot.get("status", "正常")
    normal = snapshot.get("anomaly_count", 0) == 0
    icon = "🛡" if normal else "⚠"
    tag = "✓ 全部正常" if normal else f"⚠ {status}"
    return _post(_text_url(), {
        "title": f"{icon} 家庭哨兵",
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
                       traffic_line: str = "", rates: dict | None = None,
                       history: list | None = None, device_id: str = "") -> bool:
    """rates / history 是可选的：给了就画流量柱/波形，没给就退回纯文字描述。
    调用方不传也能工作，老代码无需改动。"""
    sev = sev_cn(severity)
    if _image_push(lambda qi: qi.render_anomaly(
            device_name, event_type, risk_score, sev, incident_id, timestamp,
            history=history)):
        return True
    if USE_CANVAS:
        return push_anomaly_canvas(device_name, event_type, risk_score, severity,
                                   incident_id, timestamp, traffic_line,
                                   rates=rates, device_id=device_id)
    # 异常翻红时补一行流量尖峰（脱敏聚合），让屏上“看得见被检测的流量”
    body = f"{device_name}\n{event_type}\n\n风险 {sev} · {risk_score}/100"
    if traffic_line:
        body += f"\n{traffic_line}"
    return _post(_text_url(), {
        "title": f"⚠ {sev}异常",
        "message": body,
        "signature": f"{incident_id} · {timestamp}",
        "link": (f"{DASHBOARD_URL}/incident/{incident_id}" if DASHBOARD_URL else None),
        "refreshNow": True,
    }, urgent=True)


def push_evidence_sealed(incident_id: str) -> bool:
    if _image_push(lambda qi: qi.render_evidence(incident_id)):
        return True
    if USE_CANVAS:
        return push_evidence_canvas(incident_id)
    return _post(_text_url(), {
        "title": "证据已封存",
        "message": f"事件 {incident_id}\n哈希已验证 ✓\n链路完整 ✓",
        "signature": "已上链存证，不可篡改",
        "refreshNow": True,
    }, urgent=True)


def push_offline_status() -> bool:
    return _post(_text_url(), {
        "title": "哨兵离线",
        "message": "本地监控已暂停\n设备暂无保护",
        "signature": "请检查 T5 Core",
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


# ---- 复用组件 ------------------------------------------------
# 屏幕是 296x152（实测：真机预览里渲染框宽高比 1.89）。
# 这块屏很小——去掉 padding 只剩约 280x136，字号预算必须算着来：
#   行高 ≈ 字号 x 1.3，四行 20/15/13/11 加间距 ≈ 100px，正好留出余量。
# 之前用 25/20/18/14 排四行 ≈ 149px 超框，Satori 不裁剪而是让文字重叠——就是翻车的原因。
# 标题也必须能单行放下，否则一折行就再吃掉一整行高度。
PANEL_W, PANEL_H = 296, 152

# E-Ink 是 1-bit 抖动屏：只用纯黑/纯白与实心块，不用渐变、不用浅色。
# tito 标记是为此专门画的单色版（docs/tito/tito-bw.png，365 字节）；
# 原版 tito-icon.png 是浅紫粉渐变，抖动后平均亮度 232/255，糊成噪点，不能直接用。
_TITO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "docs", "tito", "tito-bw.png")
_tito_uri: str | None = None


def tito_data_uri() -> str:
    """内嵌成 data URI —— 不依赖 Vercel 部署、不需要渲染端联网抓图。取不到就返回空串。"""
    global _tito_uri
    if _tito_uri is None:
        try:
            import base64
            with open(_TITO_PATH, "rb") as f:
                _tito_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()
        except Exception as e:                       # noqa: BLE001
            log.warning("tito 图标读取失败，改用纯文字版: %s", e)
            _tito_uri = ""
    return _tito_uri


# 严重程度中文映射。屏幕文案一律中文；技术标识符（事件编号/哈希/时间）保持原样。
_SEV_CN = {"critical": "严重", "high": "高危", "medium": "中危", "low": "低危"}


def sev_cn(severity: str) -> str:
    return _SEV_CN.get((severity or "").lower(), severity or "")


def _img(src: str, size: int) -> dict:
    return {"type": "img", "props": {"src": src, "width": size, "height": size}}


def _bar(pct: int, width: int = 150, height: int = 12, color: str = "#111") -> dict:
    """实心进度条。外框描边 + 内部填充，墨水屏上比任何渐变都清楚。"""
    pct = max(0, min(100, int(pct)))
    fill = _el("div", style={"display": "flex", "width": f"{int(width * pct / 100)}px",
                             "height": "100%", "backgroundColor": color})
    return _el("div", [fill], style={
        "display": "flex", "width": f"{width}px", "height": f"{height}px",
        "border": f"2px solid {color}", "padding": "1px"})


def _bars(rates: dict, highlight: str = "", height: int = 30, count: int = 8) -> dict:
    """每台设备一根柱子的实时流量图——攻击设备那根会明显冲出来。
    数据来自 traffic_sim.HomeTraffic.rates（真实值，不编造）。"""
    items = sorted(rates.items(), key=lambda kv: -kv[1])[:count]
    peak = max((v for _, v in items), default=1.0) or 1.0
    bars = []
    for dev, val in items:
        h = max(3, int(height * val / peak))
        bars.append(_el("div", style={
            "display": "flex", "width": "9px", "height": f"{h}px",
            "backgroundColor": "#c62828" if dev == highlight else "#111"}))
    return _el("div", bars, style={"display": "flex", "alignItems": "flex-end",
                                   "gap": "3px", "height": f"{height}px"})


def push_dashboard_canvas(snapshot: dict) -> bool:
    """平时那屏：tito 标记 + 安全分进度条 + 每台设备流量柱。"""
    normal = snapshot.get("anomaly_count", 0) == 0
    accent = "#111" if normal else "#c62828"
    score = int(snapshot.get("security_score", 0))
    uri = tito_data_uri()

    left = [_img(uri, 34)] if uri else []
    head = _el("div", left + [
        _el("div", [
            _el("span", "家庭哨兵", style={"fontSize": "17px", "fontWeight": "800", "color": "#111"}),
            _bar(score, width=104, height=8, color=accent),
        ], style={"display": "flex", "flexDirection": "column", "gap": "3px"}),
        _el("span", str(score), style={
            "fontSize": "26px", "fontWeight": "800", "color": accent,
            "border": f"2px solid {accent}", "borderRadius": "7px", "padding": "0px 7px"}),
    ], style={"display": "flex", "alignItems": "center", "gap": "8px",
              "justifyContent": "space-between"})

    body = [_el("span",
                f"{snapshot.get('device_count', 0)} 台在线 · ↕ {snapshot.get('total_human', '—')}"
                + ("" if normal else f" · {snapshot.get('status', '')}"),
                style={"fontSize": "13px", "fontWeight": "700" if not normal else "400",
                       "color": accent if not normal else "#111"})]
    rates = snapshot.get("rates") or {}
    if rates:
        body.append(_bars(rates, highlight="" if normal else snapshot.get("top_talker", ""),
                          height=22))

    root = _el("div", [
        head,
        _el("div", body, style={"display": "flex", "flexDirection": "column", "gap": "3px"}),
        _el("span", f"最忙 {snapshot.get('top_talker', '—')} {snapshot.get('top_talker_human', '')} · {snapshot.get('last_checked', '')}",
            style={"fontSize": "10px", "color": "#666"}),
    ], style={"display": "flex", "flexDirection": "column", "width": "100%",
              "height": "100%", "padding": "8px 10px", "backgroundColor": "#fff",
              "justifyContent": "space-between"})
    return _post(_canvas_url(), _canvas_payload(root, "sentinel-dash"))


def push_anomaly_canvas(device_name: str, event_type: str, risk_score: int,
                        severity: str, incident_id: str, timestamp: str,
                        traffic_line: str = "", rates: dict | None = None,
                        device_id: str = "") -> bool:
    """告警屏：刻意不放 tito——这一屏要一眼读到风险等级，图标只会抢注意力。
    rates 给了就画流量柱，攻击设备那根标红冲高；没给就退回原来的文字行。"""
    children = [
        _el("span", f"⚠ {sev_cn(severity)}异常", style={"fontSize": "19px", "fontWeight": "800", "color": "#c62828"}),
        _el("span", device_name, style={"fontSize": "16px", "fontWeight": "700", "color": "#111"}),
        _el("span", event_type, style={"fontSize": "12px", "color": "#111"}),
        _el("div", [
            _bar(risk_score, width=96, height=9, color="#c62828"),
            _el("span", f"{risk_score}/100", style={"fontSize": "13px", "fontWeight": "800", "color": "#c62828"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "6px"}),
    ]
    if rates:
        children.append(_bars(rates, highlight=device_id or device_name, height=18))
    elif traffic_line:
        children.append(_el("span", traffic_line, style={"fontSize": "12px", "color": "#333"}))
    children.append(_el("span", f"{incident_id} · {timestamp}",
                        style={"fontSize": "10px", "color": "#666"}))

    root = _el("div", children, style={
        "display": "flex", "flexDirection": "column", "width": "100%", "height": "100%",
        "padding": "8px 10px", "backgroundColor": "#fff", "gap": "2px",
        "borderLeft": "7px solid #c62828"})
    link = f"{DASHBOARD_URL}/incident/{incident_id}" if DASHBOARD_URL else None
    return _post(_canvas_url(), _canvas_payload(root, "sentinel-alert", link=link), urgent=True)


def push_evidence_canvas(incident_id: str) -> bool:
    """收尾屏：tito 回来了——事情处理完，品牌感放在这里不抢信息。"""
    uri = tito_data_uri()
    left = [_img(uri, 34)] if uri else []
    root = _el("div", [
        _el("div", left + [
            # 去掉 🔒——emoji 在这块屏上又宽又重，会把标题挤到折行
            _el("span", "证据已封存",
                style={"fontSize": "19px", "fontWeight": "800", "color": "#1b5e20"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
        # 事件编号不翻译——它是技术标识符，要能跟链上记录对得上
        _el("span", f"事件 {incident_id}", style={"fontSize": "14px", "color": "#111"}),
        _el("span", "哈希已验证 ✓   链路完整 ✓", style={"fontSize": "13px", "color": "#111"}),
        _el("span", "已上链存证，不可篡改", style={"fontSize": "10px", "color": "#666"}),
    ], style={"display": "flex", "flexDirection": "column", "width": "100%", "height": "100%",
              "padding": "10px 12px", "justifyContent": "center", "gap": "4px",
              "backgroundColor": "#fff"})
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
