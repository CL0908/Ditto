"""t5_wifi_bridge 传输层测试(离线可跑的部分:信封 / ACK 关联 / fallback / 不抛异常)。

真机 WS/串口收发在实体联调阶段验证;这里保证逻辑与容错正确。
  pytest tests/test_t5_transport.py -q
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import t5_wifi_bridge as tb
import ditto_alert as da
from cryptography.hazmat.primitives.asymmetric import ec


def _signed():
    key = ec.generate_private_key(ec.SECP256R1())
    return da.sign_alert(da.make_alert("tp-link-camera-01", "test"), key)


def test_envelope_has_type_and_fields():
    a = _signed()
    env = json.loads(tb._envelope(a))
    assert env["type"] == tb.WS_TYPE
    for f in ("event_id", "signature", "nonce", "timestamp"):
        assert f in env


def test_ack_correlation_by_event_id():
    eid = "11111111-1111-4111-8111-111111111111"
    good = json.dumps({"type": "verified_ack", "event_id": eid, "verified": True, "played": True})
    other = json.dumps({"type": "verified_ack", "event_id": "other", "verified": True})
    assert tb._parse_ack(good, eid) is not None
    assert tb._parse_ack(other, eid) is None          # 不同 event_id 被忽略
    assert tb._parse_ack("not json", eid) is None
    assert tb._parse_ack(json.dumps({"type": "x"}), eid) is None


def test_send_never_raises_and_reports_structured():
    """无 host、无串口时,不抛异常,返回结构化失败并列出尝试过的传输。"""
    a = _signed()
    r = tb.send_signed_alert(a, host="", timeout=0.3)
    assert r["ok"] is False
    assert r["verified"] is False
    assert "tried" in r and len(r["tried"]) >= 1


def test_prefer_order_wifi_then_serial():
    a = _signed()
    r = tb.send_signed_alert(a, host="", timeout=0.3, prefer="wifi")
    keys = [list(t.keys())[0] for t in r["tried"]]
    assert keys[0] == "wifi"      # 主链优先


def test_no_fallback_only_tries_primary():
    a = _signed()
    r = tb.send_signed_alert(a, host="", timeout=0.3, prefer="wifi", allow_fallback=False)
    assert len(r["tried"]) == 1
