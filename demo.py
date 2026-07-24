"""
Sentinel Alert Chain — end-to-end demo.

Simulates 5 IoT anomaly-detection events (normal + attack types drawn from the
DS2OS taxonomy used by sentinel_anomaly_detection.py), stores them in a local
tamper-evident hash chain, computes the Merkle root, and anchors it on
Injective EVM Testnet via the deployed SentinelAnchor contract.
"""

import os
import sys
from pathlib import Path

from alert_chain import AlertChain, anchor_to_chain

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
    print("SENTINEL — Tamper-Evident Alert Anchoring Demo")
    print("=" * 70)

    # 1. Simulate 5 anomaly-detection events (mix of normal + attack types)
    simulated_events = [
        ("smart-camera-01", "normal", 0.02),
        ("smart-thermostat-03", "spying", 0.94),
        ("smart-lock-02", "malicious_control", 0.98),
        ("smart-plug-07", "normal", 0.05),
        ("smart-camera-01", "dos", 0.87),
    ]

    print(f"\n[1/4] Generating {len(simulated_events)} simulated alerts and adding to local hash chain...")
    chain = AlertChain()
    for device_id, anomaly_type, score in simulated_events:
        record = chain.add_alert(device_id, anomaly_type, score)
        flag = "ANOMALY" if anomaly_type != "normal" else "normal "
        print(f"  #{record['index']} [{flag}] {device_id:22s} {anomaly_type:20s} "
              f"score={score:.2f} hash={record['hash'][:16]}...")

    is_valid, error = chain.verify()
    print(f"\n  Chain integrity check: {'OK' if is_valid else 'FAILED — ' + error}")
    if not is_valid:
        sys.exit(1)

    # Bonus: prove the chain actually detects tampering (doesn't affect the real chain)
    print("\n  Bonus check — tampering detection:")
    tampered = AlertChain()
    tampered.alerts = [dict(r) for r in chain.alerts]
    tampered.alerts[2]["score"] = 0.01  # silently alter an anomaly score after the fact
    tampered_valid, tampered_error = tampered.verify()
    print(f"    Tampered copy of alert #2's score -> verify() = {tampered_valid} ({tampered_error})")

    # 2. Compute Merkle root
    root = chain.merkle_root()
    print(f"\n[2/4] Merkle root of {len(chain.alerts)} alerts: {root}")

    # 3. Anchor to Injective testnet
    print(f"\n[3/4] Anchoring to Injective EVM Testnet via SentinelAnchor @ {contract_address} ...")
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

    # 4. Print verifiable links
    print(f"\n[4/4] Verify this anchor on-chain:")
    print(f"  Blockscout (confirmed working):")
    print(f"    {BLOCKSCOUT_TX_URL.format(tx_hash=result['tx_hash'])}")
    print(f"  injscan.com (open the site, switch network to Testnet, paste the tx hash):")
    print(f"    {INJSCAN_HOME}  ->  search: {result['tx_hash']}")

    print("\n" + "=" * 70)
    print("Done. The Merkle root above commits to all 5 alerts above;")
    print("any modification to any alert changes the root and breaks verify().")
    print("=" * 70)


if __name__ == "__main__":
    main()
