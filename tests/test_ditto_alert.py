"""ditto_alert 单元测试 + golden vectors 验收(Priority 3 的 7 条硬标准)。

  pytest tests/test_ditto_alert.py -q
"""
import json
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ditto_alert as da

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def key():
    return ec.generate_private_key(ec.SECP256R1())


# ---- 基础签名/验签 ----
def test_sign_verify_roundtrip(key):
    a = da.sign_alert(da.make_alert("cam-1", "hello"), key)
    ok, reason = da.verify_alert(a, key.public_key())
    assert ok, reason


def test_reordered_keys_still_valid(key):
    a = da.sign_alert(da.make_alert("cam-1", "hello"), key)
    reordered = {k: a[k] for k in reversed(list(a.keys()))}
    assert da.verify_signature(reordered, key.public_key())


def test_message_tamper_fails(key):
    a = da.sign_alert(da.make_alert("cam-1", "hello"), key)
    a["message"] = "hellp"
    assert not da.verify_signature(a, key.public_key())


def test_signature_tamper_fails(key):
    import base64
    a = da.sign_alert(da.make_alert("cam-1", "hello"), key)
    raw = bytearray(base64.b64decode(a["signature"])); raw[5] ^= 0x02
    a["signature"] = base64.b64encode(bytes(raw)).decode()
    assert not da.verify_signature(a, key.public_key())


def test_wrong_key_fails(key):
    other = ec.generate_private_key(ec.SECP256R1())
    a = da.sign_alert(da.make_alert("cam-1", "hello"), key)
    assert not da.verify_signature(a, other.public_key())


# ---- 时间窗 ----
def test_timestamp_expired_fails(key):
    a = da.sign_alert(da.make_alert("cam-1", "hi", timestamp=int(time.time()) - 10000), key)
    ok, reason = da.verify_alert(a, key.public_key())
    assert not ok and "timestamp" in reason


def test_timestamp_future_fails(key):
    a = da.sign_alert(da.make_alert("cam-1", "hi", timestamp=int(time.time()) + 10000), key)
    ok, _ = da.verify_alert(a, key.public_key())
    assert not ok


# ---- 防重放 ----
def test_replay_event_id_fails(key, tmp_path):
    rg = da.ReplayGuard(tmp_path / "rp.log")
    a = da.sign_alert(da.make_alert("cam-1", "hi"), key)
    ok1, _ = da.verify_alert(a, key.public_key(), replay=rg)
    ok2, reason = da.verify_alert(a, key.public_key(), replay=rg)
    assert ok1 and not ok2 and "replay" in reason


def test_replay_nonce_fails(key, tmp_path):
    rg = da.ReplayGuard(tmp_path / "rp.log")
    a1 = da.sign_alert(da.make_alert("cam-1", "hi"), key)
    ok1, _ = da.verify_alert(a1, key.public_key(), replay=rg)
    # 不同 event_id 但复用 nonce
    a2 = da.sign_alert(da.make_alert("cam-1", "hi2", nonce=a1["nonce"]), key)
    ok2, reason = da.verify_alert(a2, key.public_key(), replay=rg)
    assert ok1 and not ok2 and "replay" in reason


def test_replay_persists_across_restart(key, tmp_path):
    p = tmp_path / "rp.log"
    a = da.sign_alert(da.make_alert("cam-1", "hi"), key)
    da.verify_alert(a, key.public_key(), replay=da.ReplayGuard(p))
    # 新 guard 从磁盘恢复 → 仍认得
    ok, reason = da.verify_alert(a, key.public_key(), replay=da.ReplayGuard(p))
    assert not ok and "replay" in reason


# ---- golden vectors(与 T5/C 端共享的跨语言验收) ----
def test_golden_vectors():
    gv = ROOT / "tests" / "golden_vectors.json"
    if not gv.exists():
        pytest.skip("run tools/gen_golden_vectors.py first")
    data = json.loads(gv.read_text())
    pub = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), bytes.fromhex(data["pubkey_uncompressed_hex"]))
    now = data["now_for_timestamp_checks"]
    for v in data["vectors"]:
        got = da.verify_signature(v["alert"], pub)
        assert got == v["expect_verify"], f"{v['name']}: sig verify {got} != {v['expect_verify']}"
        # 完整校验(时间/重放)按标注
        if v["name"] == "timestamp_expired":
            ok, _ = da.verify_alert(v["alert"], pub, now=now)
            assert not ok
        if v["name"].startswith("replay_"):
            rg = da.ReplayGuard(None)
            ok1, _ = da.verify_alert(v["alert"], pub, replay=rg, now=now)
            ok2, _ = da.verify_alert(v["alert"], pub, replay=rg, now=now)
            assert ok1 and not ok2
