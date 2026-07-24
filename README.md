<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Injective][injective-shield]][injective-url]
[![Tuya][tuya-shield]][tuya-url]
[![Python][python-shield]][python-url]
[![Solidity][solidity-shield]][solidity-url]
[![License: Unlicense][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <img src="img/logo.png" alt="Logo" width="88" height="88">

  <h1 align="center">Ditto · Sentinel</h1>

  <p align="center">
    <b>会开口说话的 AI 安全哨兵</b>
    <br />
    在攻击时间线的<b>三个不同时刻</b>分别设防 —— 攻击前阻止横向传播，攻击中检测异常，检测后让证据无法被篡改
    <br />
    <br />
    <a href="#系统架构"><strong>查看架构 »</strong></a>
    &middot;
    <a href="#运行-demo">运行 Demo</a>
    &middot;
    <a href="#赛道对应说明">赛道对应</a>
  </p>

  <p align="center">
    <sub>Built at AdventureX 2026 · Hangzhou</sub>
  </p>
</div>

---

<!-- TABLE OF CONTENTS -->
<details>
  <summary>目录</summary>
  <ol>
    <li><a href="#一句话说清">一句话说清</a></li>
    <li><a href="#我们在解决什么问题">我们在解决什么问题</a></li>
    <li><a href="#系统架构">系统架构</a></li>
    <li><a href="#layer-①--攻击前零信任设备分段">Layer ① — 攻击前</a></li>
    <li><a href="#layer-②--攻击中行为基线异常检测">Layer ② — 攻击中</a></li>
    <li><a href="#layer-③--检测后区块链锚定的不可篡改历史">Layer ③ — 检测后</a></li>
    <li><a href="#量子技术的优势">量子技术的优势</a></li>
    <li><a href="#交互层让系统开口说话">交互层</a></li>
    <li><a href="#技术栈">技术栈</a></li>
    <li><a href="#快速开始">快速开始</a></li>
    <li><a href="#运行-demo">运行 Demo</a></li>
    <li><a href="#赛道对应说明">赛道对应说明</a></li>
    <li><a href="#设计取舍">设计取舍</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#致谢">致谢</a></li>
  </ol>
</details>

---

## 一句话说清

> 2025 年，全球有 **15 亿台** IoT 设备被入侵。企业级安全方案家庭用不起，消费级方案检测不了新型攻击，就算检测到了，告警也只是一条没人看的 App 推送。
>
> **Ditto 做三件事**，对应攻击发生的三个不同时刻：

<div align="center">

| 时刻 | 防线 | 解决什么 |
|:---:|:---:|:---|
| 🛡️ **攻击前** | 零信任设备分段 | 一台设备被攻破，也无法横向传染给其他设备 |
| 🔍 **攻击中** | 行为基线异常检测 | 不靠特征库，靠"这台设备还像不像它自己"发现未知攻击 |
| 🔒 **检测后** | 区块链锚定存证 | 告警历史任何人都改不了，包括我们自己 |

</div>

最后由一个**会开口说话的语音 Agent** 把这一切讲给用户听——不是推送，是像家里多了个人一样告诉你：

> *"客厅那台摄像头刚开始向陌生地址发数据，这看起来不太对，要我帮你断开它吗？"*

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 我们在解决什么问题

这不是假设出来的威胁模型，是真实发生过的事：

- 一位加州母亲，通过被入侵的婴儿摄像头，听到陌生人说 **"I'm coming for your baby"**
- 2024 年，一台扫地机器人被黑客控制，对着屋主喊出种族歧视辱骂——而这台机器人早已绘制了整个户型图、记录了家人的日常路线
- 亚马逊因 Ring 摄像头的内部权限滥用，被 FTC 罚款 **560 万美元**，波及 **11.7 万名用户**——其中有些摄像头装在卧室和浴室
- **15 亿台** IoT 设备在 2025 年全球范围内被入侵

**三重痛点让这个问题至今无解：**

1. **买不起** —— 企业级方案（Palo Alto、Cisco、Fortinet）一年几万到几十万，家庭和小微企业从来不是它们的客户
2. **检测不了** —— 消费级方案靠已知攻击特征库比对，**真实攻击从不重复特征**，新型攻击一律漏检
3. **没人在听** —— 告警是一条 App 推送，而所有人都关掉了通知

结果是：**你家的设备正在被入侵，而你完全无感。**

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 系统架构

### 三条防线，对应攻击时间线上的三个时刻

大多数安全产品只做一件事：检测到异常，然后告警。我们把这个问题拆成攻击生命周期里的三个不同瞬间：

```
时间轴 ────────────────────────────────────────────────────────▶

  ① 攻击前                    ② 攻击中                     ③ 检测后
  阻止横向传播                  检测入侵行为                   保存证据
  ───────────────              ───────────────               ───────────────
  零信任设备分段                行为基线检测                   哈希链 + 链上锚定
  QRNG 量子熵源生成密钥          Isolation Forest              Merkle Root 锚定
  后量子签名（PQC）就绪          Z-Score（端侧，676 字节）       Injective EVM 测试网
```

**为什么不能只做检测？**

因为检测两边各有一个洞。检测之前：一台设备被攻破，就能感染同一网络里的所有其他设备——这正是 Mirai 类僵尸网络的传播方式。检测之后：如果告警记录本身能被篡改，"我们发现了入侵"这句话就没有任何证据效力。**检测只是中间那一环,前后都需要防线。**

### 系统拓扑

```
┌──────────────┐
│   摄像头(IP)  │──┐
└──────────────┘  │ WiFi
                   ▼
             ┌───────────┐      Zigbee      ┌────────────────────┐
             │   路由器   │◀───────────────▶│   Zigbee 子设备群    │
             │            │                  │  (灯 / 插座 / 传感器)│
             └─────┬──────┘                  └────────────────────┘
                   │ WiFi
                   ▼
        ┌─────────────────────┐
        │    哨兵主机           │  ← 流量采集 + 检测引擎跑在这里
        │  (Mac / ARM 主机)    │
        └──────────┬───────────┘
                   │
      ┌────────────┼─────────────┬──────────────────┐
      ▼            ▼             ▼                  ▼
 ┌──────────┐ ┌─────────┐ ┌──────────────┐ ┌──────────────┐
 │ T5 语音   │ │TuyaClaw │ │  Watchdog     │ │  Quote/0     │
 │ Agent    │ │ Agent   │ │ (多智能体编排) │ │  电子墨水屏   │
 └────┬─────┘ └─────────┘ └──────────────┘ └──────────────┘
      │
      ▼ 语音告警
   "客厅那台摄像头刚开始向陌生地址发数据，
    这看起来不太对，要我帮你断开它吗？"
```

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## Layer ① — 攻击前：零信任设备分段

**目标：即使一台设备被完全攻破，也无法触及网络里的任何其他设备。**

现实中的 IoT 攻击几乎都遵循同一个模式——先攻破最弱的一台（通常是最便宜的摄像头），再**横向跳板**控制其他所有设备，像僵尸病毒一样在局域网里扩散。

### 工作原理

每台设备持有自己独立的密钥对。设备之间的任何通信请求，都必须携带一个哨兵能够验证的签名——验证依据是该设备**登记过**的公钥。

```
 [灯] 想给 [插座] 下指令
        │
        ▼  用自己的私钥签名
   哨兵验证：这个签名能不能用"灯"登记的公钥验证通过？
        │
   ✅ 合法 → 放行            ❌ 伪造 → 拒绝 + 写入告警链
```

一台被攻破的摄像头，没有其他任何设备的私钥。**它无法伪造身份进行横向移动**——请求在到达目标之前就被拒绝，而这次尝试本身，也变成了告警链里的一条记录。

### 核心组件

| 文件 | 职责 |
|---|---|
| `qrng_entropy.py` | 量子熵源获取、本地池化、优雅降级 |
| `device_segmentation.py` | `Device`（身份 + Ed25519 签名）· `SentinelRegistry`（公钥注册表 + 验证 + 失败挂载点）|

`SentinelRegistry._on_verification_failure` 是为主动防御预留的扩展点——目前它只记录到告警链，未来这里就是自动化响应动作的接入位置。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## Layer ② — 攻击中：行为基线异常检测

**目标：在攻击正在发生的当下抓到它，包括从未见过的新型攻击。**

我们不问"这符不符合某个已知攻击特征"——新型攻击永远不会符合。我们问：**"这台设备还像不像它自己？"**

### 模型选型

在 **DS2OS** 数据集上完成验证——357,952 条真实 IoT 设备通信记录，覆盖 7 类攻击（DoS、扫描、恶意控制、恶意操作、窥探、数据探测、错误配置）。

| 模型 | 准确率 | F1 | 说明 |
|---|---:|---:|---|
| Random Forest | 100.0% | 1.000 | 有监督，主机端参考模型 |
| Gradient Boosting | 99.99% | 0.9999 | 有监督备选 |
| **Isolation Forest** | 98.1% | 0.981 | **无监督，不需要标注数据** |
| **Z-Score 基线** | 96.8% | 0.956 | **端侧模型仅 676 字节，7万条推理耗时 0.19 秒** |

### 一个决定产品形态的发现

特征重要性分析：

| 特征 | 重要性 |
|---|---:|
| `time_diff` — 通信时间间隔 | **30.6%** |
| `same_location` — 跨区域通信 | **21.7%** |
| `destinationServiceType` | 10.2% |
| `sourceType` | 8.9% |

排名前二的特征都是**纯元数据**，加起来贡献了一半以上的判别力。

**这意味着：我们完全不需要窥探通信内容。** 节奏和通信对象已经足够。隐私保护不是我们额外加的功能，是这条技术路线的天然结果。

### Watchdog：多智能体编排

检测不是一个模型单打独斗。**Watchdog** 系统把感知（流量采集）、评分（异常判断）、决策（是否值得打断用户、打断到什么程度）分给不同的智能体协同完成，再交给语音层输出。

不是每一次异常都值得开口说话——**什么时候该保持沉默，本身就是设计的一部分。**

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## Layer ③ — 检测后：区块链锚定的不可篡改历史

**目标：一条告警一旦产生，任何人——包括我们自己——都无法更改或抹除它。**

### 本地哈希链

无论是 Layer ② 检测到的异常，还是 Layer ① 拦截到的伪造身份攻击，每一条告警都会写入本地哈希链——每条记录包含上一条的哈希，改动任意一条，后面全部对不上。

```python
chain.add_alert(device_id, anomaly_type, score)  # 追加并链接
chain.verify()                                    # 检测任何篡改
chain.merkle_root()                               # 汇总用于锚定
```

### 为什么这还不够，以及锚定解决了什么

本地哈希链能做到**防篡改**，但有一个结构性漏洞：如果攻击者控制了哨兵本身，他可以把整条链重新算一遍，重算后的链条依然自洽，外部看不出破绽。

**锚定补上了这个洞。** 我们周期性地把告警链的 Merkle Root 提交到 Injective EVM 测试网上的 `SentinelAnchor` 合约。一旦提交，**连我们自己都无法修改。** 此后任何第三方——保险公司、执法机构、合规审计方——都可以独立验证：某条告警确实在某一时刻存在过，不是事后编造的。

```
告警 → 本地哈希链（防篡改）→ Merkle Root → 上链（第三方可独立验证）
```

### 为什么这是一个真实成立的区块链应用场景

我们很谨慎地控制这个说法的边界。这里的价值是**可验证性，不是"用区块链所以更安全"**。

三个真实需要它的场景：

1. **保险理赔** —— 证明入侵确实发生过、发生在哪一刻
2. **法律取证** —— 证据链的时间完整性
3. **合规审计** —— 安全事件记录不能被内部人员悄悄删除

**为什么选 Injective**：亚秒级出块和接近零 Gas，让高频锚定在经济上真正可行——如果每次锚定要花几美元，这个产品形态根本不成立。原生 EVM 支持让我们直接用 Solidity + Foundry 完成部署。

### 核心组件

| 文件 | 职责 |
|---|---|
| `alert_chain.py` | 哈希链构建、完整性校验、Merkle Root、链上锚定 |
| `src/SentinelAnchor.sol` | 锚定合约（Injective EVM 测试网）|
| `SentinelAnchor.abi.json` | Python 客户端调用用的合约 ABI |

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 量子技术的优势

> 我们对"量子"这个词很谨慎——**Ditto 里没有任何一步是用量子计算机跑检测或推理的**。量子技术在这个系统里，扮演的是两个具体、诚实、能被验证的角色：**真随机数的来源**，以及**面向未来的签名安全**。下面把这两点讲清楚，而不是简单地贴标签。

### 1. QRNG 真量子随机数 —— 密钥生成的熵源

**问题所在**：嵌入式设备在刚开机的那一刻，熵池几乎是空的。真实世界里有大量安全漏洞的根源，就是 IoT 设备用了一个"不够随机"的伪随机数生成器（PRNG）去生成密钥——密钥可预测,意味着攻击者能够提前算出来。

**我们的做法**：Layer ① 的每一把设备密钥，其生成熵源来自 **ANU（澳大利亚国立大学）量子随机数发生器**——这是从真空量子涨落里测量出来的**物理真随机数**,不是任何算法伪造出来的"看起来随机"的数字。

```python
# qrng_entropy.py
get_quantum_bytes(n)   # 从 ANU QRNG 请求真随机字节
                       # → 网络失败时自动降级为 secrets.token_bytes()
                       #   并打印明确警告，保证会场网络抖动
                       #   也不会拖垮 demo
prime_pool()           # 启动时预取一批随机字节存入本地队列
                       # 避免每次生成密钥都要等一次网络请求
```

**这为什么重要**：整个零信任分段层的安全性，最终都建立在"密钥不可预测"这一个假设之上。而这些密钥恰恰要在一块资源受限的嵌入式芯片上生成——**用真量子熵源填充，是一个针对具体风险的工程决策，不是往简历上加一个热词。**

### 2. 后量子签名（PQC）—— 让证据活得比签名算法更久

**问题所在**：我们的存证系统要解决的问题，往往是**多年之后**才需要验证的（保险理赔、法律诉讼）。但如果今天用 ECDSA 签这份 Merkle Root，而十年后量子计算机真正破解了 ECDSA，那这份"不可篡改的证据"就能被追溯性地伪造——**一份为长期存证设计的系统，用一个已知会在其生命周期内失效的签名算法，这在逻辑上是自相矛盾的。**

**我们的做法**：对于需要长期保存的存证（Merkle Root 锚定之前），使用 **NIST 标准化的后量子签名方案**（ML-DSA / Dilithium 一类）先行签名，确保这份证据的可信度不依赖于"量子计算机什么时候成熟"这个变量。

**这个思路不是装饰性的**，它直接回答了一个具体问题：*这份证据要保持不可伪造多久，你的签名算法能撑多久？*

### 3. 这两点为什么恰好是我们说得清楚的话题

这套"设备本身不完美的情况下，如何依然证明系统是安全的"方法论，来自团队在 **Fraunhofer Singapore** 正在进行的**量子密钥分发（QKD）协议安全评估研究**——评估光学器件的不完美如何影响 QKD 的安全边界，和评估一块几十块钱的摄像头能不能被信任，本质上是**同一类问题**，只是换了一层。

**诚实的边界**：我们没有，也不需要在 72 小时的黑客松里去实现量子密钥分发（QKD）本身——那需要专用的量子光学硬件。我们做的是把量子技术里已经能落地、已经有开放 API 和标准化算法的那两块——**QRNG 熵源**与**PQC 签名**——用在了它们真正解决问题的地方。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 交互层：让系统"开口说话"

检测和防护都是沉默的后台逻辑，真正让用户"感知"到这套系统存在的，是这一层。

| 组件 | 角色 |
|---|---|
| **T5 语音 Agent** | 涂鸦 T5 Core —— 板载麦克风与扬声器，把告警说出来 |
| **TuyaClaw** | Agent 层 —— 把结构化的告警信号翻译成自然语言，处理语音交互 |
| **Quote/0 电子墨水屏** | 常驻可见的告警展示面（`mindreset_quote.py`）—— 脱敏后的事件摘要、严重程度、事件编号、存证完成确认 |

### 设计原则：只监控，不控制

哨兵**只观察、只汇报，不持有任何设备的控制权限。**

这是一个刻意的约束。把全家设备的监控能力集中到一台哨兵上，会带来一个显而易见的质疑：*这不就让哨兵自己变成了最有价值的攻击目标吗？*

我们的回答是：**把爆炸半径压到最小，而不是假装哨兵刀枪不入。** 即使它被攻破，攻击者拿到的也只是元数据和验证权限——**不是任何一把门锁的控制权，也改不了已经锚定上链的历史记录。**

我们诚实地说明这个边界：**信任根被压缩到了最小,但没有被消除。** 一个门限签名注册表（需要多方共同签署才能修改信任根）是自然的下一步,目前放在 Roadmap 里,不假装已经做到。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 技术栈

<div align="center">

**检测与安全**

![Python][python-shield] ![scikit-learn][sklearn-shield] ![Cryptography][cryptography-shield]

**区块链**

![Solidity][solidity-shield] ![Foundry][foundry-shield] ![Injective][injective-shield]

**硬件与嵌入式**

![Tuya][tuya-shield]

**前端**

![Qoder][qoder-shield]

</div>

| 分类 | 具体技术 |
|---|---|
| 检测与安全 | Python 3 · scikit-learn（Isolation Forest, Random Forest）· cryptography（Ed25519）· ANU QRNG API · NumPy |
| 区块链 | Solidity · Foundry · web3.py · eth-account · Injective EVM 测试网（chainId **1439**）|
| 硬件与嵌入式 | 涂鸦 **T5 Core**（T5-E1 模组，WiFi 2.4G + BLE 5.4，板载麦克风/扬声器）· 涂鸦 **Zigbee 网关 THP10-Z** · TuyaOpen / TuyaClaw · Quote/0 电子墨水屏 |
| 前端 | 基于 **Qoder**（阿里云）的多智能体协作开发 Dashboard |

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 快速开始

### 环境要求

- Python 3.9+
- [Foundry](https://book.getfoundry.sh/)（用于合约构建/部署）
- 一个持有测试网 INJ 的 Injective EVM **测试网**账户（[水龙头](https://testnet.faucet.injective.network/)）

### 安装

```bash
git clone https://github.com/CL0908/Ditto.git
cd Ditto
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
```

填入：

```ini
RPC_URL=https://injectiveevm-testnet-rpc.polkachu.com   # chainId 1439 — 测试网
PRIVATE_KEY=0x...                                        # 仅限测试网私钥
CONTRACT_ADDRESS=0x...                                   # 已部署的 SentinelAnchor

# 可选 — Quote/0 电子墨水屏。留空则为 MOCK 模式（只打印，不真发）
DOT_API_KEY=
DOT_DEVICE_ID=
DASHBOARD_URL=
```

> ⚠️ **仅限测试网。** `chainId 1439` 是 Injective EVM 测试网；`sentry.evm-rpc.injective.network`（chainId **1776**）是**主网**——不要用demo私钥指向它。

### 部署合约（可选 —— 已配置好一个部署实例）

```bash
forge build
forge create src/SentinelAnchor.sol:SentinelAnchor \
  --rpc-url $RPC_URL \
  --private-key $PRIVATE_KEY
```

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 运行 Demo

```bash
python demo.py
```

### 它做了什么

```
[0/6]  预热 QRNG 熵源池（真实量子随机数，用于生成设备密钥）
[1/6]  T5 Watchdog —— 5 条行为异常事件 → 写入哈希链
[2/6]  Layer ① 零信任设备分段
         · 3 台设备注册（摄像头 / 灯 / 插座），密钥来自 QRNG 熵源
         · 合法场景：灯 → 插座，签名通过 → 验证成功
         · 攻击场景：伪造身份冒充摄像头 → 插座
                    → 签名验证失败
                    → 拦截 + 写入同一条哈希链
[3/6]  合并后的链完整性校验（6 条告警：5 条检测 + 1 条拦截攻击）
         → OK，篡改检测独立验证有效
[4/6]  Layer ③ 计算全部 6 条告警的 Merkle Root
[5/6]  锚定到 Injective EVM 测试网的 SentinelAnchor 合约
[6/6]  打印可独立验证的交易链接
```

### 链上核对

Demo 会打印一个实时交易链接。`getCheckpoint` 读回来的 `merkleRoot` 和 `alertCount`，跟本地计算的**完全一致**——这是对照真实链上状态确认的，不是本地假装成功。

```
Blockscout:  https://testnet.blockscout.injective.network/tx/<tx_hash>
injscan：    https://injscan.com  → 切换到 Testnet → 粘贴 tx hash
```

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 🏆 赛道对应说明

Ditto 是同一个系统，每条赛道看到的是它不同的侧面。

---

### 涂鸦智能 · 破界者 —— *用 AI 重写生活脚本*

**涂鸦硬件是交互层的脊柱，不是一个打勾的checklist项。**

| 涂鸦资产 | 具体用途 |
|---|---|
| **T5 Core** | 哨兵的嘴巴。跑本地 Agent 循环，通过板载麦克风扬声器说出告警 |
| **Zigbee 网关 THP10-Z** | Zigbee 类设备（传感器、插座、灯）的感知入口——传统网络安全工具完全看不到的盲区 |
| **TuyaOpen / TuyaClaw** | Agent 框架——主动、常驻监听，不是"喊一声才应答"的被动交互 |

**为什么必须是 T5**：能跑本地推理的板子有很多。但同时具备"本地 Agent 框架 + 麦克风扬声器 + 涂鸦生态原生兼容"三者的，是它让这个产品核心创意成立的原因。**没有它，这就退化成一个只会发推送的检测脚本——而"没人看推送"正是我们要解决的问题本身。**

**AI 是真智能，不是噱头**：35.7 万条记录的验证、四个模型的完整对比、直接改变产品设计的特征重要性分析、676 字节的端侧模型——完整记录在 `sentinel_anomaly_detection.py`。

---

### 清闲智能 · Desktop Daemon —— *陪你一起创造的桌面常驻精灵*

> *"Agent 最好的家不是云，而是一台离你最近、一直醒着的小主机。"*

这句话，就是 Ditto 的产品哲学，一字不差。

**它是谁，它替你守住了什么？**
**一只住在你桌上的守护精灵——它不看你的屏幕、不听你说话，它盯着的是你家里每一台联网设备有没有在偷偷做坏事。**

**本地/云端切分与理由：**

| 跑在本地 | 调用云端 |
|---|---|
| 通信元数据采集与解析 | 告警的自然语言表达（**可降级** —— 断网时回落到本地模板）|
| 异常推理（676字节模型，亚毫秒级） | |
| 每台设备的行为基线学习 | |
| 告警决策 + 本地哈希链 | |
| 7×24 Agent 心跳循环 | |

**理由**：一个安全产品如果把用户家里的全部流量传上云端分析，它自己就成了系统里最有价值的攻击目标、最大的隐私泄露面。**做一个用来防止别人窥探你家的东西，第一件事却是把你家的一切都传出去，这在逻辑上是自相矛盾的。**

我们的原则是：**任何能推断出"你家发生了什么"的数据，一步都不出门。** 只有数据被抽象成一句不含原始信号的话之后，才允许它接触外部网络。

这件事之所以能做到，正是因为 Layer ② 的那个发现——纯元数据就贡献了一半以上的判别力，内容检查从来就不是必需的。

---

### Injective × AI

**已部署并可在 Injective EVM 测试网（chainId 1439）验证。**

- **合约**：`SentinelAnchor.sol` —— `anchor()` / `getCheckpoint()` / `checkpointCount()`
- **集成**：`alert_chain.py` 中的 web3.py 客户端，按周期锚定 Merkle Root
- **验证**：`getCheckpoint` 读回的 root 和告警数与本地计算完全一致——对照链上真实状态确认，不是本地自我感觉良好

**关于"为什么需要区块链"的诚实回答**：我们不宣称区块链让系统"更安全"。防篡改本地哈希链已经做到了。锚定解决的是另一个具体问题——**控制了哨兵的攻击者可以重算出一条自洽的本地链**。一旦 Root 上链，**连我们自己也改不了**——这正是第三方愿意信任它的原因。

**为什么选 Injective**：亚秒级最终性和接近零 Gas，让周期性锚定在经济上真正可行。原生 EVM 意味着可以直接用 Solidity + Foundry，不用绕道桥接。

**用户体验**：用户完全不需要知道区块链的存在。他们看到的是"证据已封存"，需要时是一个可以交给保险公司或调查人员的链接。

---

### Alibaba Cloud · Qoder —— 前端

Dashboard 用 **Qoder** 开发，用的是它的多智能体协作工作流,而不是把它当成普通代码补全工具。

**前端要解决的问题**：检测引擎输出的是 `device_id=cam_01, z_score=4.2, dst_ip=unknown` 这样的信号。真正的挑战从这里才开始——**一个完全没有安全背景的人，怎么在 3 秒内看懂发生了什么、该做什么？**

**分工：**

| 智能体负责 | 人负责 |
|---|---|
| 组件结构、状态管理、图表渲染、mock 数据联调、响应式布局 | 前后端数据契约、首屏该出现什么信息、告警的视觉层级与打断强度 |

**原则：智能体管"怎么做"，人管"为什么"。** 这个界面最难的部分从来不是画出来，而是判断一个惊慌的非专业用户最先需要看到什么。

---

### 智能少年 · 未来火种教育

**为什么是我们——三圈交集。**

团队负责人目前正在 **Fraunhofer Singapore** 进行量子密钥分发（QKD）安全评估研究，隶属于 NRF 资助的 QUASAR-CREATE 项目。每天在想的问题只有一个：

> **当设备本身是不完美的、有缺陷的，你还能不能证明这个系统是安全的？**

在实验室里，这是一道数学题。直到看到那条新闻——一位母亲通过被入侵的婴儿摄像头，听到陌生人说"我要来抓你的孩子"——才意识到**家里那些几十块钱的智能摄像头，就是最典型的"不完美设备"，而没有任何人在为它们做这个安全证明。**

一个研究量子安全的人，拦不住自己家的摄像头被陌生人看。这件事我们过不去。

**这不是我们挑了一个热门赛道，是我们每天在研究的那个问题，追到了我们家里。**

---

### 小红书 · Build in Public（副赛道）

全程公开构建——立项初衷、踩过的坑（收到的"摄像头"是一根裸排线、差点把部署指向了主网而不是测试网）、改过的方向、深夜的突破、以及第一条真实用户反馈。

**活动之外的内容规划：**
- **恐怖故事系列** —— 一个案例一条笔记
- **自检指南系列** —— 不花钱教你检查自家摄像头
- **开源硬件系列** —— 自己做一台 Sentinel
- **构建日志** —— 把读者变成共创者

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 设计取舍

**用准确率换本地化。** 完整版 Random Forest 达到 100%，但依赖 sklearn 运行时和 1.8MB 模型。端侧 Z-Score 基线是 676 字节、96.8%。我们花了 **3.2 个百分点**换取完全的端侧本地化——因为"数据不出门"是产品原则，不是性能指标。

**只用元数据，是设计而非局限。** 不检查通信内容不是我们被迫接受的限制，是被验证为"足够"的结论——`time_diff` + `same_location` 两项加起来就贡献了 52.3% 的判别力。

**只监控，不控制。** 哨兵刻意不持有任何设备的控制权限，缩小自身被攻破后的伤害半径。

**先本地哈希链，再上链锚定。** 每条告警都单独上链会太慢太贵。周期性的 Merkle Root 检查点，用极小的交易量换来第三方可验证性。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## Roadmap

- [ ] **门限签名信任根** —— 修改设备注册表需要多方共识，单独攻破哨兵无法伪造注册
- [ ] **主动防御挂载** —— 在 `SentinelRegistry._on_verification_failure` 接入自动化响应动作
- [ ] **端侧持续学习** —— 每台设备的行为基线在边缘主机上持续自适应
- [ ] **全面 PQC 迁移** —— 后量子签名覆盖到设备层，而不只是长期存证

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 团队

Built at AdventureX 2026, Hangzhou —— 一支横跨安全研究、嵌入式硬件、机器学习工程与产品的四人团队。

<a href="https://github.com/CL0908/Ditto/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=CL0908/Ditto" alt="contrib.rocks image" />
</a>

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

## 致谢

* **DS2OS** 数据集 —— Distributed Smart Space Orchestration System 流量记录
* **ANU 量子随机数发生器** —— 澳大利亚国立大学
* **涂鸦智能** —— T5 Core、Zigbee 网关、TuyaOpen 框架
* **Injective** —— EVM 测试网基础设施与 Foundry 起始模板

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

---

<div align="center">
<i>15 亿台设备已经被入侵。<br>
我们要做的，是让下一台，会先开口告诉你。</i>
</div>

<!-- MARKDOWN LINKS & IMAGES -->
[injective-shield]: https://img.shields.io/badge/Injective-EVM_Testnet-00D2FF?style=for-the-badge
[injective-url]: https://injective.com
[tuya-shield]: https://img.shields.io/badge/Tuya-T5_Core-FF5C00?style=for-the-badge
[tuya-url]: https://tuyaopen.ai
[python-shield]: https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white
[python-url]: https://python.org
[solidity-shield]: https://img.shields.io/badge/Solidity-Foundry-363636?style=for-the-badge&logo=solidity&logoColor=white
[solidity-url]: https://soliditylang.org
[license-shield]: https://img.shields.io/badge/License-Unlicense-blue.svg?style=for-the-badge
[license-url]: LICENSE.txt
[sklearn-shield]: https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white
[cryptography-shield]: https://img.shields.io/badge/cryptography-Ed25519-4B8BBE?style=for-the-badge
[foundry-shield]: https://img.shields.io/badge/Foundry-FF3B3B?style=for-the-badge
[qoder-shield]: https://img.shields.io/badge/Qoder-Alibaba_Cloud-FF6A00?style=for-the-badge
