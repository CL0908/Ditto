"""Ditto → Supabase 事件写入(后端 / service_role)。

哨兵检测到异常时,把一条与前端同构的消息 insert 到 public.security_events,
前端仪表盘经 Supabase Realtime 实时更新。

密钥来自 .env(gitignored,绝不进 Git/前端):
  SUPABASE_URL=https://<ref>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=eyJ...   # 管理员密钥,只在后端用

用 httpx 直接打 PostgREST,不引额外依赖。失败返回 False,绝不抛异常。
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx


def _load_env() -> dict:
    env = dict(os.environ)
    p = Path(__file__).parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())
    return env


_ENV = _load_env()
URL = _ENV.get("SUPABASE_URL", "").rstrip("/")
KEY = _ENV.get("SUPABASE_SERVICE_ROLE_KEY", "")
ENABLED = bool(URL and KEY)


def emit(msg: dict) -> bool:
    """把一条消息写入 security_events(同时抽出 device/status/risk_score 冗余列)。"""
    if not ENABLED:
        return False
    row = {
        "payload": msg,
        "device": msg.get("device"),
        "status": msg.get("status"),
        "risk_score": msg.get("risk_score"),
    }
    try:
        r = httpx.post(
            f"{URL}/rest/v1/security_events",
            headers={
                "apikey": KEY,
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=row,
            timeout=8.0,
        )
        return r.status_code in (200, 201, 204)
    except Exception:  # noqa: BLE001
        return False


# 语义化封装(和前端消息类型对齐)
def emit_device(device: str, status: str, risk_score: float, reason: list | None = None) -> bool:
    return emit({"device": device, "status": status,
                 "risk_score": round(float(risk_score), 2), "reason": reason or []})


def emit_guardian(state: str, message: str, speak: bool = True) -> bool:
    return emit({"type": "guardian", "state": state, "message": message, "speak": speak})


def emit_alert(device: str, detections: list, confidence: float) -> bool:
    return emit({"type": "alert", "alert": {
        "device": device, "detections": detections, "confidence": round(float(confidence), 2)}})


def emit_network(mode: str, spike: int = 0) -> bool:
    return emit({"type": "network", "mode": mode, "spike": spike})


if __name__ == "__main__":
    # 自测:推一条攻击链(前端仪表盘应实时亮起)
    print("Supabase ingest:", "REAL" if ENABLED else "未配置(填 .env 的 SUPABASE_*)")
    import time
    emit_device("camera_01", "warning", 0.58, ["异常通信时间", "流量激增"])
    time.sleep(0.5)
    emit_network("attack", 420)
    emit_guardian("detecting", "检测到异常,正在与学习基线比对…", speak=False)
    time.sleep(0.5)
    emit_device("camera_01", "warning", 0.91, ["未知 IP", "流量激增", "异常通信时间"])
    emit_alert("客厅摄像头", ["未知目标 IP", "检测到流量异常", "行为偏离基线"], 0.91)
    emit_guardian("alert", "警告:客厅摄像头的行为偏离正常基线,检测到未知通信。")
    print("已推送攻击链到 Supabase。")
