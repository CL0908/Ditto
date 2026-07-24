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
import mindreset_quote as quote
import voice_alert as voice
import explain
import t5_bridge as t5
from traffic_sim import HomeTraffic, spike_line


def _severity(score):
    return "high" if score >= 0.9 else "medium" if score >= 0.7 else "low"

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

    # 告警输出屏（Quote/0）：未配置 DOT_* 时自动 MOCK（打印不真发）
    quote.configure(env.get("DOT_API_KEY", ""), env.get("DOT_DEVICE_ID", ""),
                    env.get("DASHBOARD_URL", ""))
    # 语音播报：预渲染真人音色优先，缺则 say 兜底；VOICE_ENABLED=0 则静音
    voice.configure(env.get("VOICE_ENABLED", "1") not in ("0", "false", ""),
                    env.get("VOICE_LANG", "zh"))
    # T5 DevKit 板载喇叭：串口发 clip 键→板子播烧入的真人声；未连/未就绪自动 no-op
    t5.configure(env.get("T5_PORT", ""), int(env.get("T5_BAUD", "115200") or 115200),
                 env.get("T5_ENABLED", "1") not in ("0", "false", ""))

    # 家庭流量态势（确定性模拟；接真设备时换数据源即可）
    traffic = HomeTraffic()

    print("=" * 70)
    print("SENTINEL — Tamper-Evident Alert Anchoring Demo")
    print("=" * 70)

    # 平时的 Quote/0 界面：实时安全仪表盘（设备/安全分/流量）
    quote.push_dashboard(traffic.snapshot("start"))

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
        # 每个事件都更新流量态势；正常事件顺带刷新仪表盘
        kbps = traffic.observe(device_id, anomaly_type, score)
        if anomaly_type == "normal":
            quote.push_dashboard(traffic.snapshot(str(record.get("timestamp", ""))))
            continue

        # 异常 → 同一瞬间四路扇出（都只发脱敏摘要）：
        #   ①墨水屏红色告警+流量尖峰 ②刷新流量仪表盘 ③T5 板载喇叭真人声 ④Mac say 兜底
        sev = _severity(score)
        clip = explain.clip_key(anomaly_type)
        traffic_line = spike_line(device_id, kbps, None)
        quote.push_anomaly_alert(
            device_name=device_id,
            event_type=anomaly_type.replace("_", " "),
            risk_score=int(score * 100),
            severity=sev,
            incident_id=f"INC-{record['index']:04d}",
            timestamp=str(record.get("timestamp", "")),
            traffic_line=traffic_line,
        )
        quote.push_dashboard(traffic.snapshot(str(record.get("timestamp", ""))))
        spoken = explain.explain_anomaly(device_id, anomaly_type, score)
        print(f"       🔊 {spoken}  [{traffic_line}]")
        t5.speak_anomaly(clip, sev)          # T5 板子亲口播（发 clip 键）
        voice.speak_anomaly(spoken, sev, clip)  # Mac 兜底（T5 没就绪时也有声）

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
    if result["status"] == 1:
        # 哈希锚链成功 → Quote/0 显示存证完成 + 语音收尾
        quote.push_evidence_sealed(f"chk-{result.get('checkpoint_index', 0)}")
        voice.speak_evidence_sealed(explain.explain_evidence_sealed())
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

    voice.wait()   # 等语音播完再退出，别截断最后一句


if __name__ == "__main__":
    main()
