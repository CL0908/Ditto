"""Ditto gateway-attested alert —— 签名 / 验签 / 防重放（Mac Edge Agent 侧）。

架构:TP-Link 摄像头 → Ditto Edge Gateway(Mac,持私钥)→ 对告警签名 →
     T5AI-Core 验签成功才播报。私钥只在 Mac,T5 只存对应公钥。

密码学(不自行实现算法):
  · ECDSA P-256 + SHA-256(Python cryptography ↔ T5 mbedTLS)
  · 签名对象是**canonical 字节串**(不是原始 JSON 字符串),Python/C 逐字节一致,
    JSON 字段顺序变化不影响结果。签名为 DER 编码后 base64。

Canonical 规则(v1,C 端用 snprintf 可完全复现):
  行1: 固定域分隔头 "DITTO-ALERT-v1"
  之后按**固定顺序**每字段一行 "key=value":
    schema_version, attestation_type, signer_id, key_id, event_id,
    device_id, severity, message, timestamp, nonce
  值内禁止出现 '\n'/'\r'(否则拒绝),防止分隔符注入。
  UTF-8 编码 → SHA-256 → ECDSA 签名。
"""
from __future__ import annotations

import base64
import os
import time
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils

SCHEMA_VERSION = 1
CANON_HEADER = "DITTO-ALERT-v1"
# 参与签名的字段(固定顺序)——增删字段必须同步改 C 端与 golden vectors
SIGNED_FIELDS = [
    "schema_version", "attestation_type", "signer_id", "key_id", "event_id",
    "device_id", "severity", "message", "timestamp", "nonce",
]
TIMESTAMP_WINDOW = 120     # ±秒
NONCE_BYTES = 16           # 128-bit

DEFAULT_KEY_PATH = (
    Path.home() / "Library" / "Application Support" / "Ditto" / "keys"
    / "gateway-private.pem"
)


# ---------------- canonical serialization ----------------
def canonical_bytes(alert: dict) -> bytes:
    """从告警字段构造 canonical 字节串(顺序无关,可跨语言逐字节复现)。"""
    lines = [CANON_HEADER]
    for f in SIGNED_FIELDS:
        if f not in alert:
            raise ValueError(f"missing signed field: {f}")
        v = alert[f]
        s = str(v)
        if "\n" in s or "\r" in s:
            raise ValueError(f"field {f} contains newline (illegal)")
        lines.append(f"{f}={s}")
    return ("\n".join(lines)).encode("utf-8")


# ---------------- keys ----------------
def generate_keypair(path: Path = DEFAULT_KEY_PATH) -> ec.EllipticCurvePrivateKey:
    """生成 P-256 私钥并写到 Mac 本地(0600),返回私钥对象。绝不进 Git。"""
    key = ec.generate_private_key(ec.SECP256R1())
    path.parent.mkdir(parents=True, exist_ok=True)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return key


def load_private_key(path: Path = DEFAULT_KEY_PATH) -> ec.EllipticCurvePrivateKey:
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def public_key_uncompressed(pub: ec.EllipticCurvePublicKey) -> bytes:
    """65 字节未压缩点(0x04 || X || Y)——mbedTLS/T5 端最易加载的格式。"""
    return pub.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


# ---------------- build / sign / verify ----------------
def new_nonce() -> str:
    return base64.urlsafe_b64encode(os.urandom(NONCE_BYTES)).decode().rstrip("=")


def make_alert(device_id: str, message: str, severity: str = "critical",
               signer_id: str = "ditto-edge-01", key_id: str = "ditto-gw-p256-2026-01",
               timestamp: int | None = None, event_id: str | None = None,
               nonce: str | None = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "attestation_type": "gateway",
        "signer_id": signer_id,
        "key_id": key_id,
        "event_id": event_id or str(uuid.uuid4()),
        "device_id": device_id,
        "severity": severity,
        "message": message,
        "timestamp": timestamp if timestamp is not None else int(time.time()),
        "nonce": nonce or new_nonce(),
    }


def sign_alert(alert: dict, private_key: ec.EllipticCurvePrivateKey) -> dict:
    """对 canonical 字节串签名,返回带 signature(base64-DER)的完整告警。"""
    sig = private_key.sign(canonical_bytes(alert), ec.ECDSA(hashes.SHA256()))
    out = dict(alert)
    out["signature"] = base64.b64encode(sig).decode()
    return out


def verify_signature(alert: dict, public_key: ec.EllipticCurvePublicKey) -> bool:
    """只验签名本身(不含时间/重放)。True=有效。"""
    sig_b64 = alert.get("signature")
    if not sig_b64:
        return False
    try:
        sig = base64.b64decode(sig_b64)
        public_key.verify(sig, canonical_bytes(alert), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


def check_timestamp(alert: dict, now: int | None = None,
                    window: int = TIMESTAMP_WINDOW) -> bool:
    now = now if now is not None else int(time.time())
    try:
        ts = int(alert["timestamp"])
    except (KeyError, ValueError, TypeError):
        return False
    return abs(now - ts) <= window


def verify_alert(alert: dict, public_key: ec.EllipticCurvePublicKey,
                 replay=None, now: int | None = None) -> tuple[bool, str]:
    """完整验证:签名 + 时间窗 + 防重放。返回 (ok, reason)。

    fail closed:任一步失败即拒绝,reason 说明。replay 为可选 ReplayGuard。
    调用方在 ok=True 后才可播报;replay marker 必须在播报前持久化(见 ReplayGuard)。
    """
    if alert.get("schema_version") != SCHEMA_VERSION:
        return False, "bad schema_version"
    if alert.get("attestation_type") != "gateway":
        return False, "bad attestation_type"
    if not verify_signature(alert, public_key):
        return False, "signature invalid"
    if not check_timestamp(alert, now=now):
        return False, "timestamp expired/out of window"
    if replay is not None:
        if replay.seen(alert.get("event_id"), alert.get("nonce")):
            return False, "replay detected (event_id/nonce reused)"
        if not replay.remember(alert.get("event_id"), alert.get("nonce")):
            return False, "replay store write failed (fail closed)"
    return True, "ok"


class ReplayGuard:
    """持久化防重放:记住用过的 event_id 与 nonce。

    fail closed:remember() 若持久化写入失败返回 False,调用方必须拒绝播报。
    Mac 侧用文件;T5 侧对应用 KV(tal_kv),同一语义。
    """

    def __init__(self, path: str | Path | None = None, maxlen: int = 4096):
        self.path = Path(path) if path else None
        self.maxlen = maxlen
        self._ids: set[str] = set()
        self._nonces: set[str] = set()
        self._order: list[str] = []
        if self.path and self.path.exists():
            for line in self.path.read_text().splitlines():
                kind, _, val = line.partition(":")
                if kind == "e":
                    self._ids.add(val)
                elif kind == "n":
                    self._nonces.add(val)

    def seen(self, event_id, nonce) -> bool:
        return (event_id in self._ids) or (nonce in self._nonces)

    def remember(self, event_id, nonce) -> bool:
        """先持久化再返回;写失败返回 False(fail closed)。"""
        try:
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a") as f:
                    f.write(f"e:{event_id}\nn:{nonce}\n")
                    f.flush()
                    os.fsync(f.fileno())
            self._ids.add(event_id)
            self._nonces.add(nonce)
            self._order.extend([f"e:{event_id}", f"n:{nonce}"])
            return True
        except Exception:
            return False


if __name__ == "__main__":
    # 自测:生成密钥→签名→验签
    key = ec.generate_private_key(ec.SECP256R1())
    a = make_alert("tp-link-camera-01",
                   "Suspicious outbound traffic detected from the smart home camera")
    signed = sign_alert(a, key)
    ok, reason = verify_alert(signed, key.public_key())
    print("verify:", ok, reason)
    print("pubkey(65B hex):", public_key_uncompressed(key.public_key()).hex()[:32], "...")
