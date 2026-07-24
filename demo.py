"""
Sentinel — full pipeline demo.

Two security layers on top of the existing T5 watchdog anomaly-detection
engine, feeding into one tamper-evident, blockchain-anchored alert trail:

  Layer 1 — Zero-trust device segmentation (qrng_entropy.py + device_segmentation.py)
    Every device's keypair is seeded from QRNG entropy; every inter-device
    request must carry a signature the sentinel can verify against that
    device's registered public key. A compromised device cannot forge
    another device's identity to move laterally — the sentinel rejects the
    request *before* it reaches its target, and logs the attempt.

  Layer 2 — Tamper-evident, blockchain-anchored history (alert_chain.py)
    Every alert — whether from the anomaly-detection engine or from a
    blocked lateral-movement attempt — goes into a local hash chain. Its
    Merkle root is periodically anchored on Injective EVM Testnet, so the
    alert history itself cannot be rewritten after the fact.
"""

import sys
from pathlib import Path

import qrng_entropy
from alert_chain import AlertChain, anchor_to_chain
from device_segmentation import Device, SentinelRegistry

BLOCKSCOUT_TX_URL = "https://testnet.blockscout.injective.network/tx/{tx_hash}"
INJSCAN_HOME = "https://injscan.com"


def load_env(path=".env"):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def main():
    env = load_env(Path(__file__).parent / ".env")
    rpc_url = env["RPC_URL"]
    private_key = env["PRIVATE_KEY"]
    contract_address = env["CONTRACT_ADDRESS"]

    print("=" * 70)
    print("SENTINEL — Full Pipeline Demo")
    print("Zero-Trust Device Segmentation + Tamper-Evident Chain Anchoring")
    print("=" * 70)

    print("\n[0/6] Priming QRNG entropy pool (seeds device keypairs)...")
    qrng_entropy.prime_pool()

    chain = AlertChain()

    # -----------------------------------------------------------------
    # T5 watchdog: existing anomaly-detection engine's alerts
    # -----------------------------------------------------------------
    simulated_events = [
        ("smart-camera-01", "normal", 0.02),
        ("smart-thermostat-03", "spying", 0.94),
        ("smart-lock-02", "malicious_control", 0.98),
        ("smart-plug-07", "normal", 0.05),
        ("smart-camera-01", "dos", 0.87),
    ]
    print(f"\n[1/6] T5 watchdog: {len(simulated_events)} behavioral anomaly-detection events...")
    for device_id, anomaly_type, score in simulated_events:
        record = chain.add_alert(device_id, anomaly_type, score)
        flag = "ANOMALY" if anomaly_type != "normal" else "normal "
        print(f"  #{record['index']} [{flag}] {device_id:22s} {anomaly_type:20s} "
              f"score={score:.2f} hash={record['hash'][:16]}...")

    # -----------------------------------------------------------------
    # Layer 1: zero-trust device segmentation
    # -----------------------------------------------------------------
    print("\n[2/6] Layer 1 — Zero-trust device segmentation")
    registry = SentinelRegistry(alert_chain=chain)

    camera = Device("smart-camera-01")
    light = Device("smart-light-04")
    plug = Device("smart-plug-07")
    for device in (camera, light, plug):
        registry.register_device(device.device_id, device.public_key_bytes)

    print("\n  Scenario A — legitimate: smart-light-04 -> smart-plug-07")
    message_a = b"FROM:smart-light-04|TO:smart-plug-07|CMD:turn_on"
    signature_a = light.sign(message_a)
    is_valid, _ = registry.verify_request("smart-light-04", message_a, signature_a)
    assert is_valid

    print("\n  Scenario B — attack: forged identity claiming smart-camera-01 -> smart-plug-07")
    print("  (attacker does not have smart-camera-01's real private key)")
    attacker = Device("attacker-forged-key")  # never registered
    message_b = b"FROM:smart-camera-01|TO:smart-plug-07|CMD:disable_motion_alerts"
    forged_signature = attacker.sign(message_b)
    is_valid, _ = registry.verify_request("smart-camera-01", message_b, forged_signature)
    assert not is_valid

    print(f"\n  QRNG pool stats: {qrng_entropy.pool_stats()}")

    # -----------------------------------------------------------------
    # Combined chain integrity
    # -----------------------------------------------------------------
    is_valid, error = chain.verify()
    print(f"\n[3/6] Combined chain integrity check ({len(chain.alerts)} alerts: "
          f"{len(simulated_events)} from T5 watchdog + 1 from segmentation layer): "
          f"{'OK' if is_valid else 'FAILED — ' + error}")
    if not is_valid:
        sys.exit(1)

    print("  Bonus check — tampering detection:")
    tampered = AlertChain()
    tampered.alerts = [dict(r) for r in chain.alerts]
    tampered.alerts[2]["score"] = 0.01  # silently alter an anomaly score after the fact
    tampered_valid, tampered_error = tampered.verify()
    print(f"    Tampered copy of alert #2's score -> verify() = {tampered_valid} ({tampered_error})")

    # -----------------------------------------------------------------
    # Layer 2: Merkle root + on-chain anchor
    # -----------------------------------------------------------------
    root = chain.merkle_root()
    print(f"\n[4/6] Layer 2 — Merkle root of all {len(chain.alerts)} alerts: {root}")

    print(f"\n[5/6] Anchoring to Injective EVM Testnet via SentinelAnchor @ {contract_address} ...")
    result = anchor_to_chain(
        rpc_url=rpc_url,
        private_key=private_key,
        contract_address=contract_address,
        merkle_root_hex=root,
        alert_count=len(chain.alerts),
    )

    status = "SUCCESS" if result["status"] == 1 else "FAILED"
    print(f"  Status:       {status}")
    print(f"  Tx hash:      {result['tx_hash']}")
    if result["block_number"] is not None:
        print(f"  Block:        {result['block_number']}")
        print(f"  Gas used:     {result['gas_used']}")
    else:
        print(f"  Block/gas:    unavailable — confirmed via on-chain state instead of tx receipt")
        print(f"                (this RPC's receipt index sometimes lags actual chain state)")
    print(f"  Submitter:    {result['submitter']}")
    print(f"  Checkpoint #: {result['checkpoint_index']}")

    print(f"\n[6/6] Verify this anchor on-chain:")
    print(f"  Blockscout (confirmed working):")
    print(f"    {BLOCKSCOUT_TX_URL.format(tx_hash=result['tx_hash'])}")
    print(f"  injscan.com (open the site, switch network to Testnet, paste the tx hash):")
    print(f"    {INJSCAN_HOME}  ->  search: {result['tx_hash']}")

    print("\n" + "=" * 70)
    print("Done.")
    print("Layer 1 stopped the forged request before it ever reached smart-plug-07.")
    print("Layer 2 means neither T5's original alerts nor the blocked-attack alert")
    print("can be rewritten after the fact without breaking the anchored Merkle root.")
    print("=" * 70)


if __name__ == "__main__":
    main()
