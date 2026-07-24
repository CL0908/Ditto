"""Ditto → T5 统一传输层 —— Wi-Fi WebSocket 主链 + 签名 Serial fallback。

Primary:  Ditto Edge Agent → Wi-Fi WebSocket(TuyaOpenClaw 内置 server, port 18789)
          → T5 验签 → 播报 → verified ACK
Fallback: Ditto Edge Agent → USB Serial → 相同签名信封 → T5 相同验签逻辑 → ACK

只传**已签名**的告警信封(ditto_alert.sign_alert 的输出)。T5 端在进入任何 Agent loop /
调用 MCP / 更新 Quote/0 之前必须先验签(fail closed)。本层负责:
  · 主链优先、失败自动切 fallback   · 重连 / 超时
  · 按 event_id 关联 ACK            · 清晰错误上报(返回结构化结果,不抛异常)

依赖:websocket-client(WS)、pyserial(串口,经 t5_bridge)。缺库自动降级并报告。
"""
from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("t5_wifi_bridge")

WS_TYPE = "ditto_alert"            # WebSocket 入口识别的消息 type
WS_PORT = int(os.environ.get("DITTO_T5_WS_PORT", "18789"))
WS_HOST = os.environ.get("DITTO_T5_HOST", "")          # T5 的 Wi-Fi IP(配网后填)
DEFAULT_TIMEOUT = float(os.environ.get("DITTO_ACK_TIMEOUT", "6"))

try:
    import websocket  # websocket-client
except Exception:      # noqa: BLE001
    websocket = None


def _envelope(alert_signed: dict) -> str:
    """WS/串口共用的一行 JSON 信封:{type, ...签名告警}。"""
    msg = {"type": WS_TYPE}
    msg.update(alert_signed)
    return json.dumps(msg, ensure_ascii=False)


def _parse_ack(raw: str, event_id: str) -> dict | None:
    """解析并按 event_id 关联 ACK。T5 回:
       {"type":"verified_ack","event_id":..,"verified":bool,"played":bool,"reason":..}"""
    try:
        d = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    if d.get("type") not in ("verified_ack", "ack"):
        return None
    if event_id and d.get("event_id") not in (None, event_id):
        return None    # 不是这条的 ACK,忽略
    return d


# ---------------- Wi-Fi WebSocket 主链 ----------------
def _send_ws(alert_signed: dict, host: str, port: int, timeout: float) -> dict:
    if websocket is None:
        return {"ok": False, "transport": "wifi", "error": "websocket-client 未安装"}
    if not host:
        return {"ok": False, "transport": "wifi", "error": "DITTO_T5_HOST 未配置"}
    url = f"ws://{host}:{port}"
    event_id = alert_signed.get("event_id")
    try:
        ws = websocket.create_connection(url, timeout=timeout)
        try:
            ws.send(_envelope(alert_signed))
            deadline = time.time() + timeout
            while time.time() < deadline:
                ws.settimeout(max(0.2, deadline - time.time()))
                ack = _parse_ack(ws.recv(), event_id)
                if ack is not None:
                    return {"ok": True, "transport": "wifi",
                            "verified": bool(ack.get("verified")),
                            "played": bool(ack.get("played")),
                            "reason": ack.get("reason", ""), "ack": ack}
            return {"ok": False, "transport": "wifi", "error": "ACK 超时"}
        finally:
            ws.close()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "transport": "wifi", "error": f"WS 失败: {e}"}


# ---------------- Serial fallback(签名信封)----------------
def _send_serial(alert_signed: dict, timeout: float) -> dict:
    """经 t5_bridge 的串口发签名信封,读回 ACK 行。"""
    try:
        import t5_bridge
        import serial  # noqa: F401  确认 pyserial 在
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "transport": "serial", "error": f"依赖缺失: {e}"}
    port = t5_bridge.PORT
    if not port:
        return {"ok": False, "transport": "serial", "error": "未找到串口"}
    event_id = alert_signed.get("event_id")
    line = (_envelope(alert_signed) + "\n").encode("utf-8")
    try:
        import serial as _pyserial
        with _pyserial.Serial(port, t5_bridge.BAUD, timeout=0.5, write_timeout=2.0) as ser:
            ser.reset_input_buffer()
            ser.write(line)
            ser.flush()
            deadline = time.time() + timeout
            buf = b""
            while time.time() < deadline:
                buf += ser.read(256)
                while b"\n" in buf:
                    raw, _, buf = buf.partition(b"\n")
                    ack = _parse_ack(raw.decode("utf-8", "replace").strip(), event_id)
                    if ack is not None:
                        return {"ok": True, "transport": "serial",
                                "verified": bool(ack.get("verified")),
                                "played": bool(ack.get("played")),
                                "reason": ack.get("reason", ""), "ack": ack}
            return {"ok": False, "transport": "serial", "error": "ACK 超时"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "transport": "serial", "error": f"串口失败: {e}"}


# ---------------- 统一入口 ----------------
def send_signed_alert(alert_signed: dict, host: str = "", port: int = 0,
                      timeout: float = DEFAULT_TIMEOUT, prefer: str = "wifi",
                      allow_fallback: bool = True) -> dict:
    """发送已签名告警,返回结构化结果(绝不抛异常)。

    result: {ok, transport, verified, played, reason} 或 {ok:False, error, tried:[...]}
    只有 verified=True 才代表 T5 验签通过并播报;调用方据此才更新 Quote/0。
    """
    host = host or WS_HOST
    port = port or WS_PORT
    tried = []
    order = (["wifi", "serial"] if prefer == "wifi" else ["serial", "wifi"])
    if not allow_fallback:
        order = order[:1]
    for tp in order:
        r = _send_ws(alert_signed, host, port, timeout) if tp == "wifi" \
            else _send_serial(alert_signed, timeout)
        tried.append({tp: r.get("error") or ("verified" if r.get("verified") else "not-verified")})
        if r.get("ok"):
            r["tried"] = tried
            return r
        log.warning("%s 传输失败: %s", tp, r.get("error"))
    return {"ok": False, "verified": False, "error": "所有传输失败", "tried": tried}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import ditto_alert as da
    key = da.load_private_key()
    alert = da.sign_alert(da.make_alert(
        "tp-link-camera-01",
        "Suspicious outbound traffic detected from the smart home camera"), key)
    print("发送签名告警(WS 未配 host 会自动降级 serial)…")
    print(json.dumps(send_signed_alert(alert), ensure_ascii=False, indent=2))
