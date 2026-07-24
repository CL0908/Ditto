# Artlist 真人音色 —— 预渲染脚本

把下面每一句用 **Artlist AI Voiceover**（中文女声，沉稳/略带警示语气）渲染成音频，
文件名**必须**与下表 `文件名` 一致，放进本 `audio/` 目录即可。
运行时 `voice_alert.py` 会自动优先播放它（`afplay`），没有对应文件才降级到系统 `say`。

> 命名规则：`audio/{clip_key}.mp3`（也支持 .wav/.m4a/.aiff）。
> `clip_key` = 攻击类型（见 `explain.py::clip_key`）。

| 文件名 | 触发时机 | 播报文案（现场固定事件） |
|---|---|---|
| `spying.mp3`            | 温控器被监听  | 注意，温控器03正在悄悄采集并向外发送数据，疑似被植入监听。风险94分，已为你封存证据。 |
| `malicious_control.mp3` | 门锁被控     | 注意，智能门锁02正在被远程恶意控制，行为已不受你掌控。风险98分，已为你封存证据。 |
| `dos.mp3`               | 摄像头被劫持 | 注意，摄像头01出现异常大流量，疑似被劫持发起攻击。风险87分，已为你封存证据。 |
| `evidence_sealed.mp3`   | 上链成功收尾 | 证据已上链，无法篡改。 |
| `normal.mp3`（可选）     | 正常状态     | 家庭防护正常，五台设备在线。 |
| `offline.mp3`（可选）    | 哨兵离线     | 哨兵已离线，本地监控暂停。 |

## 怎么生成（两种）

**A. 用 Claude Code + Artlist MCP（推荐，我来渲染）**
1. 你先把 Artlist MCP 连上 Claude Code：
   ```bash
   claude mcp add --transport http artlist https://mcp.artlist.io/mcp
   ```
   （首次会走 OAuth，用你的 Artlist 账号授权一次）
2. 重开会话后叫我：「用 Artlist 把 VOICEOVER_SCRIPT 里的 6 句渲染进 audio/」
   我会逐句调 Artlist 的 voiceover 工具生成并落盘。

**B. 手动**
在 artlist.io 后台用 AI Voiceover 逐句渲染、下载、按上表改名放进本目录。

## 说明
- 现场事件是**固定**的（demo.py 里 5 个模拟事件），所以每句可预渲染、零延迟。
- 任何**动态/未预渲染**的告警（换设备、换分数、新攻击类型）会自动用系统 `say` 念，
  绝不哑火。真人音色只是「锦上添花」，不是「命门」。
