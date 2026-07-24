"""
Sentinel Device Segmentation — standalone demo.

Registers 3 IoT devices (camera, light, plug) with the sentinel, then runs
two scenarios:
  A) legitimate:  light -> plug, correctly signed        -> allowed
  B) attack:      an attacker impersonates "camera" (no access to camera's
                   real private key) and targets plug     -> denied + alert

This module is self-contained (no blockchain calls) so it can be tested on
its own before wiring into the full demo.py pipeline.
"""

import qrng_entropy
from alert_chain import AlertChain
from device_segmentation import Device, SentinelRegistry


def main():
    print("=" * 70)
    print("SENTINEL — Zero-Trust Device Segmentation Demo")
    print("=" * 70)

    print("\n[0/3] Priming QRNG entropy pool (used to seed device keypairs)...")
    qrng_entropy.prime_pool()

    print("\n[1/3] Registering 3 devices with the sentinel...")
    chain = AlertChain()
    registry = SentinelRegistry(alert_chain=chain)

    camera = Device("camera-01")
    light = Device("light-01")
    plug = Device("plug-01")

    for device in (camera, light, plug):
        registry.register_device(device.device_id, device.public_key_bytes)

    print(f"\n  QRNG pool stats after keygen: {qrng_entropy.pool_stats()}")

    # --- Scenario A: legitimate request -----------------------------------
    print("\n[2/3] Scenario A — legitimate request: light-01 -> plug-01")
    message_a = b"FROM:light-01|TO:plug-01|CMD:turn_on"
    signature_a = light.sign(message_a)
    is_valid, reason = registry.verify_request("light-01", message_a, signature_a)
    print(f"  Result: {'ALLOWED' if is_valid else 'DENIED'}")
    assert is_valid

    # --- Scenario B: lateral-movement / impersonation attack ---------------
    print("\n[3/3] Scenario B — attack: forged identity claiming to be camera-01 -> plug-01")
    print("  (attacker does NOT have camera-01's real private key — it has its own forged keypair)")
    attacker = Device("attacker-forged-key")  # not registered anywhere
    message_b = b"FROM:camera-01|TO:plug-01|CMD:disable_motion_alerts"
    forged_signature = attacker.sign(message_b)  # valid signature, but from the WRONG key
    is_valid, reason = registry.verify_request("camera-01", message_b, forged_signature)
    print(f"  Result: {'ALLOWED' if is_valid else 'DENIED'}")
    assert not is_valid

    # --- Verify the alert chain recorded the attack, and is still intact ---
    print("\nAlert chain contents:")
    for record in chain.alerts:
        print(f"  #{record['index']} device={record['device_id']:20s} "
              f"type={record['anomaly_type']:24s} score={record['score']:.2f}")

    ok, error = chain.verify()
    print(f"\nChain integrity check: {'OK' if ok else 'FAILED — ' + error}")
    assert ok

    print("\n" + "=" * 70)
    print("Done. The forged request never reached plug-01: the sentinel")
    print("rejected it at the signature-verification step (before any device")
    print("action occurred) and recorded the attempt as a tamper-evident alert.")
    print("=" * 70)


if __name__ == "__main__":
    main()
