"""
Sentinel Device Segmentation — zero-trust, signature-based device identity.

Every IoT device holds its own Ed25519 keypair (seeded from the QRNG entropy
pool); only the public key is ever shared, via registration with the
sentinel's SentinelRegistry. Any inter-device request must be signed by the
sender's private key. A signature that doesn't match the claimed device's
registered public key — e.g. a compromised device trying to impersonate
another device to move laterally — is rejected and logged as an alert into
the tamper-evident alert chain (see alert_chain.py), rather than silently
dropped.
"""

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from qrng_entropy import get_quantum_bytes

LATERAL_MOVEMENT_ANOMALY_TYPE = "lateral_movement_attempt"
LATERAL_MOVEMENT_SCORE = 1.0  # cryptographic proof of forgery, not a probabilistic guess


class Device:
    """A simulated IoT device. Holds its own Ed25519 private key in memory —
    on real hardware this would live in a secure element and never leave it.
    Only the public key is ever handed out, via registration.
    """

    def __init__(self, device_id):
        self.device_id = device_id
        seed = get_quantum_bytes(32)
        self._private_key = Ed25519PrivateKey.from_private_bytes(seed)

    @property
    def public_key_bytes(self):
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def sign(self, message: bytes) -> bytes:
        """Signs `message` with this device's private key. The key itself
        never leaves the Device instance."""
        return self._private_key.sign(message)


class SentinelRegistry:
    """The sentinel's central registry of trusted device public keys. Every
    inter-device request passes through here before being allowed to reach
    its target — a device cannot act as another device without a signature
    matching that device's registered public key.
    """

    def __init__(self, alert_chain=None):
        self._public_keys = {}
        self.alert_chain = alert_chain

    def register_device(self, device_id, public_key_bytes):
        self._public_keys[device_id] = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        print(f"[sentinel] registered device '{device_id}' (pubkey {public_key_bytes.hex()[:16]}...)")

    def verify_request(self, device_id, message: bytes, signature: bytes):
        """Verifies that `signature` over `message` was produced by the
        private key registered for `device_id`.

        Returns (is_valid: bool, reason: str | None). On failure, prints a
        lateral-movement alert and — if an alert_chain was supplied — writes
        it into the tamper-evident alert chain.
        """
        public_key = self._public_keys.get(device_id)
        if public_key is None:
            reason = f"unknown device_id '{device_id}' (not registered with sentinel)"
            self._on_verification_failure(device_id, message, reason)
            return False, reason

        try:
            public_key.verify(signature, message)
            print(f"[sentinel] VERIFIED: signature from '{device_id}' is valid -> request allowed")
            return True, None
        except InvalidSignature:
            reason = f"signature does not match the public key registered for '{device_id}'"
            self._on_verification_failure(device_id, message, reason)
            return False, reason

    def _on_verification_failure(self, device_id, message, reason):
        print("[sentinel] ALERT: possible lateral-movement attempt detected!")
        print(f"           claimed identity : '{device_id}'")
        print(f"           reason           : {reason}")
        print(f"           message payload  : {message!r}")
        print("           action           : request DENIED")

        if self.alert_chain is not None:
            record = self.alert_chain.add_alert(
                device_id=device_id,
                anomaly_type=LATERAL_MOVEMENT_ANOMALY_TYPE,
                score=LATERAL_MOVEMENT_SCORE,
            )
            print(f"           -> logged to alert chain as alert #{record['index']} "
                  f"(hash {record['hash'][:16]}...)")
