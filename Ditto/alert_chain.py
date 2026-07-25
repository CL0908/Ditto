"""
Sentinel Alert Chain — tamper-evident local hash chain for IoT anomaly alerts,
periodically anchored to Injective EVM Testnet via the SentinelAnchor contract.
"""

import hashlib
import json
import time
from pathlib import Path

from web3.exceptions import TimeExhausted

from web3 import Web3

GENESIS_HASH = "0" * 64
ABI_PATH = Path(__file__).parent / "SentinelAnchor.abi.json"


def _record_digest(device_id, anomaly_type, score, timestamp, prev_hash):
    payload = f"{device_id}|{anomaly_type}|{score:.6f}|{timestamp}|{prev_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AlertChain:
    """A local hash-linked chain of IoT anomaly alerts."""

    def __init__(self):
        self.alerts = []

    def add_alert(self, device_id, anomaly_type, score):
        prev_hash = self.alerts[-1]["hash"] if self.alerts else GENESIS_HASH
        timestamp = time.time()
        record = {
            "index": len(self.alerts),
            "device_id": device_id,
            "anomaly_type": anomaly_type,
            "score": round(float(score), 6),
            "timestamp": timestamp,
            "prev_hash": prev_hash,
        }
        record["hash"] = _record_digest(
            record["device_id"], record["anomaly_type"], record["score"],
            record["timestamp"], record["prev_hash"],
        )
        self.alerts.append(record)
        return record

    def verify(self):
        """Returns (is_valid, error_message). error_message is None when valid."""
        expected_prev = GENESIS_HASH
        for record in self.alerts:
            if record["prev_hash"] != expected_prev:
                return False, f"alert #{record['index']}: prev_hash link broken"
            recomputed = _record_digest(
                record["device_id"], record["anomaly_type"], record["score"],
                record["timestamp"], record["prev_hash"],
            )
            if recomputed != record["hash"]:
                return False, f"alert #{record['index']}: hash mismatch (tampered)"
            expected_prev = record["hash"]
        return True, None

    def merkle_root(self):
        """Returns the Merkle root of all alert hashes as a 0x-prefixed bytes32 hex string."""
        if not self.alerts:
            return "0x" + GENESIS_HASH

        level = [bytes.fromhex(record["hash"]) for record in self.alerts]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            level = [
                hashlib.sha256(level[i] + level[i + 1]).digest()
                for i in range(0, len(level), 2)
            ]
        return "0x" + level[0].hex()


def load_abi():
    with open(ABI_PATH) as f:
        return json.load(f)


def anchor_to_chain(rpc_url, private_key, contract_address, merkle_root_hex, alert_count,
                     receipt_wait=8, state_poll_timeout=45, poll_interval=2):
    """Calls SentinelAnchor.anchor(merkleRoot, alertCount) on Injective EVM Testnet.

    Injective's public testnet RPC (polkachu) has been observed to update
    contract state (eth_call) within ~2s of broadcast, but its transaction
    receipt index (eth_getTransactionReceipt) can lag far behind — sometimes
    never catching up within several minutes for a given node in its
    load-balanced pool. So: try the normal receipt wait only briefly, then
    confirm success the reliable way, by polling checkpointCount() (a state
    read) until it increments.

    Returns dict with tx_hash, block_number, gas_used, status, submitter,
    and checkpoint_index. block_number/gas_used are None if confirmation came
    from the state-polling fallback rather than a receipt.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"could not connect to RPC: {rpc_url}")

    account = w3.eth.account.from_key(private_key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=load_abi(),
    )

    prior_index = contract.functions.checkpointCount(account.address).call()

    tx = contract.functions.anchor(merkle_root_hex, alert_count).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 300_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash_hex = tx_hash.hex()
    if not tx_hash_hex.startswith("0x"):
        tx_hash_hex = "0x" + tx_hash_hex

    receipt = None
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=receipt_wait, poll_latency=poll_interval)
    except TimeExhausted:
        deadline = time.time() + state_poll_timeout
        while time.time() < deadline:
            if contract.functions.checkpointCount(account.address).call() > prior_index:
                break
            time.sleep(poll_interval)
        else:
            raise TimeoutError(
                f"anchor tx {tx_hash_hex} confirmed neither via receipt nor on-chain state "
                f"within {receipt_wait + state_poll_timeout}s"
            )

    return {
        "tx_hash": tx_hash_hex,
        "block_number": receipt["blockNumber"] if receipt else None,
        "gas_used": receipt["gasUsed"] if receipt else None,
        "status": receipt["status"] if receipt else 1,
        "submitter": account.address,
        "checkpoint_index": prior_index,
    }
