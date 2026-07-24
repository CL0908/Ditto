# Ditto · Sentinel

> **An AI security sentinel that speaks.**
> Three lines of defense across the attack timeline — stopping lateral movement *before* a breach spreads, detecting anomalies *during* an attack, and anchoring the evidence *after*, where no one can rewrite it.

<p align="center">
  <b>Built at AdventureX 2026 · Hangzhou</b><br>
  Tuya T5 Core · Injective EVM Testnet · ANU QRNG · Ed25519 · Post-Quantum Ready
</p>

---

## TL;DR（中文速览）

家里那些几十块钱的智能摄像头、插座、灯泡，正在被入侵——2025 年全球有超过 **15 亿台 IoT 设备**被攻破，而普通家庭对此完全无感。

企业级安全方案一年几万到几十万，家庭市场是真空的。少数消费级方案依赖"已知攻击特征库"比对，**新型攻击一律漏检**。而即使检测到了，告警只是一条没人看的 App 推送。

**Ditto 做三件事**：

| 阶段 | 防线 | 解决什么 |
|---|---|---|
| **攻击前** | 零信任设备分段 | 一台设备被攻破，也无法横向传染给其他设备 |
| **攻击中** | 行为基线异常检测 | 不靠特征库，靠"这台设备还像不像它自己"发现未知攻击 |
| **检测后** | 区块链锚定存证 | 告警历史任何人都改不了，包括我们自己 |

最后由一个**会开口说话的语音 Agent** 把这一切讲给用户听——不是推送，是像家里多了个人一样告诉你："客厅那台摄像头刚开始向陌生地址发数据，要我帮你断开它吗？"

---

## The Problem

This is not a hypothetical threat model.

- A mother in California heard a stranger's voice through her baby monitor: *"I'm coming for your baby."*
- In 2024, a robot vacuum was hijacked and shouted racial slurs at its owner — the same device that had already mapped her floor plan and daily routine.
- Amazon was fined **$5.6M by the FTC** over Ring camera access abuse, affecting **117,000 customers** — some of those cameras were in bedrooms and bathrooms.
- **1.5 billion IoT devices** were compromised globally in 2025.

**Three gaps keep this unsolved for ordinary users:**

1. **Price.** Enterprise IoT security (Palo Alto, Cisco, Fortinet) runs tens of thousands per year. Households and small offices were never the target market.
2. **Detection method.** Consumer solutions match against known-attack signatures. Real attacks don't repeat signatures — anything novel slips through.
3. **Delivery.** Alerts arrive as push notifications. Everyone has those muted.

The result: **your devices are being compromised, and you have no idea.**

---

## Architecture

### Three lines of defense, mapped to the attack timeline

Most security products do exactly one thing: detect an anomaly, then alert. We split the problem across three distinct moments in an attack's lifecycle.

```
TIMELINE ──────────────────────────────────────────────────────────────▶

  ① BEFORE                  ② DURING                    ③ AFTER
  Prevent lateral spread    Detect the intrusion        Preserve the evidence
  ─────────────────────     ─────────────────────       ─────────────────────
  Zero-Trust Segmentation   Behavioral Baseline         Hash Chain + On-Chain
  QRNG-seeded Ed25519       Isolation Forest            Merkle Anchoring
  PQC-ready signatures      Z-Score (edge, 676 B)       Injective EVM Testnet
```

**Why not just detection?**

Because detection alone leaves two holes. Before it: one compromised device can infect every other device on the same network — this is exactly how Mirai-class botnets propagate. After it: if the alert log itself can be rewritten, *"we detected an intrusion"* carries no evidentiary weight at all.

Detection is the middle link. It needs a layer on each side.

### System topology

```
┌──────────────┐
│   IP Camera  │──┐
└──────────────┘  │ WiFi
                   ▼
             ┌───────────┐      Zigbee      ┌────────────────────┐
             │   Router   │◀───────────────▶│  Zigbee Sub-devices │
             │            │                  │  (lights / plugs /  │
             └─────┬──────┘                  │   sensors)          │
                   │ WiFi                     └────────────────────┘
                   ▼
        ┌─────────────────────┐
        │   Sentinel Host      │  ← traffic capture + detection engine
        │   (Mac / ARM SBC)    │
        └──────────┬───────────┘
                   │
      ┌────────────┼─────────────┬──────────────────┐
      ▼            ▼             ▼                  ▼
 ┌──────────┐ ┌─────────┐ ┌──────────────┐ ┌──────────────┐
 │ T5 Voice │ │TuyaClaw │ │  Watchdog     │ │ Quote/0      │
 │ Agent    │ │ Agent   │ │  (multi-agent │ │ E-ink Display│
 │          │ │         │ │  orchestration)│ │              │
 └────┬─────┘ └─────────┘ └──────────────┘ └──────────────┘
      │
      ▼  Spoken alert
  "The living-room camera just started sending data to an unknown
   address. That's not how it normally behaves. Want me to cut it off?"
```

---

## Layer ① — Before: Zero-Trust Device Segmentation

**Goal: even if one device is fully compromised, it cannot reach any other device on the network.**

Real-world IoT attacks almost universally follow the same pattern — compromise the weakest device (usually the cheapest camera), then **pivot laterally** to control everything else. It spreads like a zombie virus across the LAN.

### How it works

Every device holds its own keypair. Every inter-device request must carry a signature that the sentinel can verify against that device's *registered* public key.

```
 [Light] wants to command [Plug]
        │
        ▼  signs the request with its own private key
   Sentinel verifies: does this signature validate
   against the public key registered for "light"?
        │
   ✅ valid → forward        ❌ forged → reject + log to alert chain
```

A compromised camera does not hold any other device's private key. **It cannot forge an identity to move laterally** — the request is rejected *before* it reaches its target, and the attempt itself becomes an alert in the chain.

### Why QRNG for key generation

Embedded devices are notorious for shallow entropy pools at boot. There is a well-documented history of real-world vulnerabilities caused by IoT devices generating **predictable keys** from weak PRNG seeds at first power-on.

We seed keypair generation from the **ANU Quantum Random Number Generator** — genuine quantum entropy from vacuum fluctuations, not a software PRNG.

```python
# qrng_entropy.py
get_quantum_bytes(n)   # fetches true random bytes from ANU QRNG
                       # → falls back to secrets.token_bytes() on network failure,
                       #   with an explicit warning, so a flaky venue network
                       #   can never brick the demo
prime_pool()           # pre-fetches a buffer at startup so key generation
                       # never blocks on a network round-trip
```

This is an engineering decision with a concrete justification, not a buzzword: **the entire security of the segmentation layer rests on keys being unpredictable, and those keys are generated on constrained hardware.**

### Components

| File | Responsibility |
|---|---|
| `qrng_entropy.py` | Quantum entropy sourcing, local pooling, graceful degradation |
| `device_segmentation.py` | `Device` (identity + Ed25519 signing) · `SentinelRegistry` (public-key registry + verification + failure hook) |

`SentinelRegistry._on_verification_failure` is the designed extension point for active response — currently it logs to the alert chain; it is where an automated defense action would attach.

---

## Layer ② — During: Behavioral Anomaly Detection

**Goal: catch the intrusion while it is happening, including attacks nobody has seen before.**

We do not ask *"does this match a known attack signature?"* — novel attacks never will. We ask **"does this device still behave like itself?"**

### Model selection

Validated on the **DS2OS** dataset — 357,952 real IoT service-communication records spanning 7 attack classes (DoS, scan, malicious control, malicious operation, spying, data probing, misconfiguration).

| Model | Accuracy | F1 | Notes |
|---|---:|---:|---|
| Random Forest | 100.0% | 1.000 | Supervised; host-side reference model |
| Gradient Boosting | 99.99% | 0.9999 | Supervised alternative |
| **Isolation Forest** | 98.1% | 0.981 | **Unsupervised — no labels required** |
| **Z-Score baseline** | 96.8% | 0.956 | **676 bytes · 0.19 s per 71k records · edge-deployable** |

### The finding that shaped the product

Feature importance analysis:

| Feature | Importance |
|---|---:|
| `time_diff` — inter-message interval | **30.6%** |
| `same_location` — cross-zone communication | **21.7%** |
| `destinationServiceType` | 10.2% |
| `sourceType` | 8.9% |

The top two features — both **pure metadata** — account for over half the discriminative power.

**Implication: we never need to inspect packet contents.** Rhythm and counterparty are sufficient. Privacy preservation isn't a feature we bolted on; it falls out of the technical approach itself.

### Watchdog: multi-agent orchestration

Detection is not a single model running in isolation. The **Watchdog** system orchestrates separate agents for sensing (traffic capture), scoring (anomaly evaluation), and decision (whether an anomaly warrants interrupting the user, and at what severity) — before handing off to the voice layer.

Not every anomaly deserves to be spoken aloud. Deciding *when to stay quiet* is part of the design.

---

## Layer ③ — After: Tamper-Evident, Blockchain-Anchored History

**Goal: once an alert exists, no one — including us — can alter or erase it.**

### Local hash chain

Every alert enters a local hash chain, whether it originated from Layer ② detection or from a Layer ① blocked lateral-movement attempt. Each record embeds the hash of its predecessor — modify any single entry and every subsequent hash breaks.

```python
chain.add_alert(device_id, anomaly_type, score)  # append + link
chain.verify()                                    # detect any tampering
chain.merkle_root()                               # roll up for anchoring
```

### Why that isn't enough, and what anchoring adds

A local hash chain is **tamper-evident**, but it has a structural limit: an attacker who controls the sentinel itself can recompute the entire chain, and the recomputed version is internally consistent. Nothing looks wrong from the outside.

**Anchoring closes that gap.** We periodically commit the chain's Merkle root to the `SentinelAnchor` contract on Injective EVM Testnet. Once committed, **not even we can change it.** Any third party — an insurer, law enforcement, a compliance auditor — can independently verify that a given alert existed at a given moment and was not fabricated after the fact.

```
alerts → hash chain (tamper-evident) → Merkle root → on-chain (third-party verifiable)
```

### Why this is a genuine blockchain use case

We are careful to make the correct claim. The value here is **verifiability, not secrecy or security-by-blockchain**.

Three scenarios where it is a hard requirement:

1. **Insurance claims** — proving an intrusion occurred, and precisely when
2. **Legal evidence** — chain-of-custody and temporal integrity
3. **Compliance audit** — security events that insiders cannot quietly delete

**Why Injective**: sub-second block times and near-zero gas make frequent anchoring economically viable — at a few dollars per anchor the product form simply would not exist. Native EVM support let us build and deploy directly with Solidity and Foundry.

### Post-quantum consideration

Evidence intended to survive for years should not be signed with an algorithm expected to fall within that horizon. For long-lived attestations, the Merkle root is signed with a **post-quantum signature scheme** (NIST-standardized ML-DSA / Dilithium class) before anchoring.

This is not decoration. It answers a specific question: *how long must this evidence remain unforgeable, and does the signature outlast that window?* The reasoning comes directly from our team's ongoing QKD security-evaluation research at Fraunhofer Singapore — **evaluating whether a protocol remains provably secure when the underlying devices are imperfect** is the same problem, one layer down.

### Components

| File | Responsibility |
|---|---|
| `alert_chain.py` | Hash chain construction, integrity verification, Merkle root, on-chain anchoring |
| `src/SentinelAnchor.sol` | Anchor contract (Injective EVM Testnet) |
| `SentinelAnchor.abi.json` | Contract ABI for the Python client |

---

## Interaction Layer

Detection and defense are silent background processes. This layer is what makes the system *present* to the user.

| Component | Role |
|---|---|
| **T5 Voice Agent** | Tuya T5 Core — on-device microphone/speaker, speaks the alert aloud |
| **TuyaClaw** | Agent layer — translates structured alert signals into natural language, handles voice interaction |
| **Quote/0 E-ink Display** | Ambient, always-visible alert surface (`mindreset_quote.py`) — redacted incident summary, severity, incident ID, evidence-sealed confirmation |

### Design principle: monitor, don't control

The sentinel **observes and reports. It does not hold control authority over any device.**

This is a deliberate constraint. Centralizing visibility over every device on a network creates an obvious question: *doesn't that make the sentinel itself the highest-value target?*

Our answer is to **minimize blast radius rather than pretend the sentinel is unbreakable**. If it is compromised, an attacker gains metadata and verification authority — **not the keys to your locks, not control of your cameras**, and no ability to rewrite history already anchored on-chain.

We state the boundary honestly: **the trust root is compressed to a minimum, not eliminated.** A threshold-signature registry (requiring multiple parties to modify the trust root) is the natural next step, and is on the roadmap rather than claimed as done.

---

## Tech Stack

**Detection & Security**
`Python 3` · `scikit-learn` (Isolation Forest, Random Forest) · `cryptography` (Ed25519) · ANU QRNG API · NumPy

**Blockchain**
`Solidity` · `Foundry` · `web3.py` · `eth-account` · Injective EVM Testnet (chainId **1439**)

**Hardware & Embedded**
Tuya **T5 Core** (T5-E1 module, WiFi 2.4G + BLE 5.4, on-board mic/speaker) · Tuya **Zigbee Gateway THP10-Z** · `TuyaOpen` / `TuyaClaw` · Quote/0 e-ink display

**Frontend**
Dashboard built with **Qoder** (Alibaba Cloud) — multi-agent assisted development

---

## Repository Structure

```
Ditto/
├── src/
│   └── SentinelAnchor.sol          # On-chain anchor contract
├── test/                            # Foundry contract tests
├── qrng_entropy.py                  # Layer ① — quantum entropy sourcing
├── device_segmentation.py           # Layer ① — zero-trust segmentation
├── sentinel_anomaly_detection.py    # Layer ② — model training & evaluation
├── alert_chain.py                   # Layer ③ — hash chain + Merkle + anchoring
├── mindreset_quote.py               # Quote/0 e-ink alert display integration
├── demo.py                          # End-to-end pipeline demo
├── SentinelAnchor.abi.json          # Contract ABI
├── foundry.toml                     # Foundry config
├── Makefile
├── requirements.txt
└── .env.example                     # Config template
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- [Foundry](https://book.getfoundry.sh/) (for contract build/deploy)
- An Injective EVM **Testnet** account with test INJ ([faucet](https://testnet.faucet.injective.network/))

### Install

```bash
git clone https://github.com/CL0908/Ditto.git
cd Ditto
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Fill in:

```ini
RPC_URL=https://injectiveevm-testnet-rpc.polkachu.com   # chainId 1439 — TESTNET
PRIVATE_KEY=0x...                                        # testnet key only
CONTRACT_ADDRESS=0x...                                   # deployed SentinelAnchor

# Optional — Quote/0 e-ink display. Unset = MOCK mode (prints, does not push)
DOT_API_KEY=
DOT_DEVICE_ID=
DASHBOARD_URL=
```

> ⚠️ **Testnet only.** `chainId 1439` is Injective EVM Testnet. `sentry.evm-rpc.injective.network` (chainId **1776**) is **mainnet** — do not point a demo key at it.

### Deploy the contract (optional — a deployed instance is already configured)

```bash
forge build
forge create src/SentinelAnchor.sol:SentinelAnchor \
  --rpc-url $RPC_URL \
  --private-key $PRIVATE_KEY
```

---

## Running the Demo

```bash
python demo.py
```

### What it does

```
[0/6]  Prime QRNG entropy pool (real quantum randomness, seeds device keypairs)
[1/6]  T5 Watchdog — 5 behavioral anomaly events → written to hash chain
[2/6]  Layer ① Zero-Trust Segmentation
         · Register 3 devices (camera / light / plug), keys from QRNG entropy
         · Legitimate:  light → plug, signed → verification passes
         · Attack:      forged identity claiming camera → plug
                        → signature verification FAILS
                        → blocked + logged to the same hash chain
[3/6]  Combined chain integrity check (6 alerts: 5 detection + 1 blocked attack)
         → OK, and tamper-detection independently verified
[4/6]  Layer ③ Compute Merkle root over all 6 alerts
[5/6]  Anchor to SentinelAnchor on Injective EVM Testnet
[6/6]  Print independently verifiable transaction links
```

### Verify it on-chain

The demo prints a live transaction link. `getCheckpoint` reads back the **same** `merkleRoot` and `alertCount` that were computed locally — this is confirmed against actual chain state, not a local success message.

```
Blockscout:  https://testnet.blockscout.injective.network/tx/<tx_hash>
injscan:     https://injscan.com  → switch to Testnet → paste tx hash
```

---

## 🏆 Sponsor Track Alignment · 赛道对应说明

Ditto is a single system. Each track sees a different face of it.

---

### 涂鸦智能 · 破界者 — *用 AI 重写生活脚本*

**Tuya hardware is the spine of the interaction layer, not a checkbox.**

| Tuya asset | How it is used |
|---|---|
| **T5 Core** | The sentinel's voice. Runs the local agent loop and speaks alerts through the on-board mic/speaker. |
| **Zigbee Gateway THP10-Z** | Sensing entry point for Zigbee-class devices (sensors, plugs, lights) — a segment traditional network security tooling treats as a blind spot entirely. |
| **TuyaOpen / TuyaClaw** | Agent framework — proactive, always-on monitoring rather than a wake-word request/response loop. |

**Why it has to be T5:** plenty of boards can run local inference. The board that also carries an on-device agent framework, a microphone and speaker, *and* native Tuya IoT ecosystem compatibility is the one that makes the core product idea possible. **Without it, this degrades into a detection script that fires push notifications — and "nobody reads push notifications" is the exact problem we set out to solve.**

**AI: substance over gimmick.** 357,952-record validation, four models benchmarked, feature-importance analysis that materially changed the product design, and a 676-byte edge model — the full record is in `sentinel_anomaly_detection.py`.

---

### 清闲智能 · Desktop Daemon — *陪你一起创造的桌面常驻精灵*

> *"Agent 最好的家不是云，而是一台离你最近、一直醒着的小主机。"*

That line is Ditto's product thesis, verbatim.

**Who is this machine, and what does it guard?**
**一只住在你桌上的守护精灵——它不看你的屏幕、不听你说话，它盯着的是你家里每一台联网设备有没有在偷偷做坏事。**

**Local / cloud split — and why:**

| Runs locally | Calls cloud |
|---|---|
| Traffic metadata capture & parsing | Natural-language phrasing of an alert (**degradable** — falls back to local templates offline) |
| Anomaly inference (676 B model, sub-ms) | |
| Per-device behavioral baseline learning | |
| Alert decisioning + local hash chain | |
| 7×24 agent heartbeat loop | |

**The reasoning:** a security product that ships every packet of your home traffic to a cloud analyzer **becomes the single highest-value target in the system and the largest privacy surface in it.** Building something to stop others from watching your home, whose first act is to export everything about your home, is self-contradictory.

Our rule: **anything from which "what happened in this house" can be inferred never leaves the house.** Only after data has been abstracted into a statement containing no raw signal is it allowed to touch an external network.

This is achievable precisely *because* of the Layer ② finding — pure metadata carries over half the discriminative power, so content inspection was never required.

---

### Injective × AI

**Deployed and verifiable on Injective EVM Testnet (chainId 1439).**

- **Contract**: `SentinelAnchor.sol` — checkpoint anchoring with `anchor()` / `getCheckpoint()` / `checkpointCount()`
- **Integration**: `web3.py` client in `alert_chain.py`, Merkle root anchoring at configurable intervals
- **Verification**: `getCheckpoint` reads back a root and alert count matching local computation exactly — confirmed against chain state, not local optimism

**On "why blockchain" — the honest answer.** We do not claim blockchain makes the system *more secure*. Tamper-evidence is already handled locally by the hash chain. Anchoring solves a different, specific problem: **an attacker who controls the sentinel can recompute a self-consistent local chain.** Once a root is anchored, *we* cannot change it either — and that is exactly why a third party can trust it.

**Why Injective specifically:** sub-second finality and near-zero gas make periodic anchoring economically viable. Native EVM meant Solidity + Foundry with no bridging detours.

**User experience:** the user never learns a blockchain is involved. They see *"evidence sealed"* and, if they ever need it, a link they can hand to an insurer or investigator.

---

### Alibaba Cloud · Qoder — 前端

The Dashboard is built with **Qoder**, using its multi-agent workflow rather than treating it as autocomplete.

**Problem the frontend solves:** the detection engine emits `device_id=cam_01, z_score=4.2, dst_ip=unknown`. The real challenge starts there — **how does someone with zero security background understand, in three seconds, what is wrong and what to do about it?**

**Division of labour:**

| Agents handled | Humans decided |
|---|---|
| Component structure, state management, chart rendering, mock-data integration, responsive layout | The front-end data contract · what belongs above the fold · alert visual hierarchy and interruption threshold |

**Principle: agents own *how*, humans own *why*.** The hard part of this interface was never drawing it — it was deciding what a frightened non-expert needs to see first.

---

### 智能少年 · 未来火种教育

**Why us — the three-circle intersection.**

Our team lead currently conducts **quantum key distribution security-evaluation research at Fraunhofer Singapore**, under the NRF-funded QUASAR-CREATE programme. The question there, every day, is a single one:

> **When the devices themselves are imperfect and flawed, can you still prove the system is secure?**

In the lab, that is mathematics. Then came the news story about a mother hearing a stranger through her baby monitor — and the realization that **the cheap smart cameras and plugs in every home are the canonical "imperfect device," and nobody is running that proof for them.**

A person who researches quantum security, unable to stop a stranger from watching their own home. That is the gap this project exists to close.

**This is not a chosen trend. It is the question we already work on, followed home.**

---

### 小红书 · Build in Public *(side track)*

Building in the open throughout AdventureX — origin story, the pitfalls (a "camera" that arrived as a bare FPC ribbon cable; nearly pointing a deploy at mainnet instead of testnet), direction changes, late-night breakthroughs, and first real user feedback.

**Planned content lines beyond the event:**
- **Horror stories** — one real smart-home intrusion case per post
- **Self-check guides** — how to inspect your own camera's behavior, buying nothing
- **Open hardware** — build your own Sentinel
- **Build logs** — turning readers into co-builders

---

## Design Decisions & Trade-offs

**Accuracy traded for locality.** The full Random Forest reaches 100% but needs a scikit-learn runtime and a 1.8 MB model. The edge Z-Score baseline is 676 bytes at 96.8%. We spent **3.2 percentage points** to keep inference fully on-device — because *data never leaves the house* is a product principle, not a performance target.

**Metadata only, by design.** Not inspecting packet contents was not a limitation we accepted; it was validated as sufficient. `time_diff` + `same_location` alone carry 52.3% of discriminative power.

**Observe, don't control.** The sentinel deliberately holds no device control authority. It shrinks the consequences of its own compromise.

**Local hash chain first, chain anchoring second.** Anchoring every alert individually would be slow and costly. Periodic Merkle-root checkpoints give third-party verifiability at a fraction of the transaction volume.

---

## Roadmap

- [ ] **Threshold-signature trust root** — require multi-party consensus to modify the device registry, so compromising the sentinel alone cannot forge a registration
- [ ] **Active defense hook** — automated response attached at `SentinelRegistry._on_verification_failure`
- [ ] **On-device baseline learning** — continuous per-device model adaptation on the edge host
- [ ] **Full PQC migration** — post-quantum signatures across the device layer, not only long-lived attestations

---

## Team

Built at AdventureX 2026, Hangzhou — a four-person team across security research, embedded hardware, ML engineering, and product.

**Contributors**: see [Contributors](https://github.com/CL0908/Ditto/graphs/contributors)

---

## Acknowledgements

- **DS2OS** dataset — Distributed Smart Space Orchestration System traffic traces
- **ANU Quantum Random Number Generator** — Australian National University
- **Tuya Smart** — T5 Core, Zigbee gateway, TuyaOpen framework
- **Injective** — EVM testnet infrastructure and Foundry starter template

---

<p align="center">
<i>1.5 billion devices have already been compromised.<br>
We're making sure the next one speaks up first.</i>
</p>
