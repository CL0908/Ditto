#!/usr/bin/env python3
"""生成跨语言 golden vectors —— Python 签,Python 与 T5(C/mbedTLS)都要能一致验证。

产出 tests/golden_vectors.json:含公钥、canonical 预览、一组签名消息 + 期望结果。
T5 端读取同一文件(或编译进固件)逐条验证,必须与 Python 结论一致。

固定 timestamp/event_id/nonce → 结果可复现(不用随机、可提交)。
"""
import base64
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ditto_alert as da
from cryptography.hazmat.primitives.asymmetric import ec

# 固定测试私钥(仅测试用,非生产;生产私钥在 Mac keys 目录)
TEST_PRIV_HEX = "7f3e1c2a4d5f6987012345678909abcdef0123456789abcdef0123456789abcd"
BASE_TS = 1784890000


def test_key():
    d = int(TEST_PRIV_HEX, 16)
    return ec.derive_private_key(d, ec.SECP256R1())


def main():
    key = test_key()
    pub = da.public_key_uncompressed(key.public_key())

    base = da.make_alert(
        device_id="tp-link-camera-01",
        message="Suspicious outbound traffic detected from the smart home camera",
        timestamp=BASE_TS,
        event_id="11111111-1111-4111-8111-111111111111",
        nonce="AAAAAAAAAAAAAAAAAAAAAA",
    )
    signed = da.sign_alert(base, key)

    vectors = []

    # 1) 正确签名 → 通过并播放
    vectors.append({"name": "valid", "expect_verify": True, "alert": signed})

    # 2) JSON 字段顺序变化 → 仍通过(canonical 与顺序无关)
    reordered = {k: signed[k] for k in reversed(list(signed.keys()))}
    vectors.append({"name": "reordered_keys", "expect_verify": True, "alert": reordered})

    # 3) message 改一个字符 → 失败
    m = dict(signed); m["message"] = m["message"][:-1] + "X"
    vectors.append({"name": "message_tampered", "expect_verify": False, "alert": m})

    # 4) signature 改一个字节 → 失败
    raw = bytearray(base64.b64decode(signed["signature"])); raw[10] ^= 0x01
    s = dict(signed); s["signature"] = base64.b64encode(bytes(raw)).decode()
    vectors.append({"name": "signature_tampered", "expect_verify": False, "alert": s})

    # 5) timestamp 过期(相对 now=BASE_TS 的 ±120s 判定,这条给 now 用) —— 标注 verify_now
    old = da.sign_alert(da.make_alert(
        device_id="tp-link-camera-01", message="old alert", timestamp=BASE_TS - 10000,
        event_id="22222222-2222-4222-8222-222222222222", nonce="BBBBBBBBBBBBBBBBBBBBBB"), key)
    vectors.append({"name": "timestamp_expired", "expect_verify": True,
                    "expect_full": False, "reason": "timestamp", "alert": old})

    # 6) 相同 event_id 重放 → 第二次失败(replay);签名本身有效
    replay_eid = da.sign_alert(da.make_alert(
        device_id="tp-link-camera-01", message="replay eid", timestamp=BASE_TS,
        event_id="33333333-3333-4333-8333-333333333333", nonce="CCCCCCCCCCCCCCCCCCCCCC"), key)
    vectors.append({"name": "replay_same_event_id", "expect_verify": True,
                    "expect_full_first": True, "expect_full_second": False,
                    "reason": "replay", "alert": replay_eid})

    # 7) 相同 nonce 重放 → 第二次失败
    replay_nonce = da.sign_alert(da.make_alert(
        device_id="tp-link-camera-01", message="replay nonce", timestamp=BASE_TS,
        event_id="44444444-4444-4444-8444-444444444444", nonce="DDDDDDDDDDDDDDDDDDDDDD"), key)
    vectors.append({"name": "replay_same_nonce", "expect_verify": True,
                    "expect_full_first": True, "expect_full_second": False,
                    "reason": "replay", "alert": replay_nonce})

    out = {
        "curve": "P-256", "hash": "SHA-256", "sig_encoding": "DER-base64",
        "canonical": "DITTO-ALERT-v1 + fixed-order key=value lines (see ditto_alert.canonical_bytes)",
        "now_for_timestamp_checks": BASE_TS,
        "timestamp_window": da.TIMESTAMP_WINDOW,
        "pubkey_uncompressed_hex": pub.hex(),
        "canonical_of_valid_utf8": da.canonical_bytes(base).decode("utf-8"),
        "vectors": vectors,
    }
    dst = Path(__file__).resolve().parent.parent / "tests" / "golden_vectors.json"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("wrote", dst, "with", len(vectors), "vectors")


if __name__ == "__main__":
    main()
