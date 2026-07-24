"""Quote/0 界面预览 —— 不依赖区块链,直接把三种屏推给 Quote/0 + 语音播报。

用途:填好 .env 里的 DOT_API_KEY / DOT_DEVICE_ID 后,一条命令看全 Quote/0 界面:
  ① 平时:实时安全仪表盘(设备/安全分/流量)
  ② 异常:翻红告警 + 流量尖峰
  ③ 收尾:证据已封存
同时 Mac 语音播报(真人声优先);T5 已烧固件则板子也亲口播(发 clip 键)。

  .venv/bin/python preview_quote.py
未配 DOT_* → 自动 MOCK(终端打印屏内容,离线可演)。
"""
import time
from pathlib import Path

import mindreset_quote as quote
import voice_alert as voice
import t5_bridge as t5
import explain
from traffic_sim import HomeTraffic, spike_line


def load_env(path=".env"):
    env = {}
    p = Path(__file__).parent / path
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


def main():
    env = load_env()
    quote.configure(env.get("DOT_API_KEY", ""), env.get("DOT_DEVICE_ID", ""),
                    env.get("DASHBOARD_URL", ""))
    voice.configure(env.get("VOICE_ENABLED", "1") not in ("0", "false", ""),
                    env.get("VOICE_LANG", "zh"))
    t5.configure(env.get("T5_PORT", ""), int(env.get("T5_BAUD", "115200") or 115200),
                 env.get("T5_ENABLED", "1") not in ("0", "false", ""))

    traffic = HomeTraffic()
    print("mode:", "REAL Quote/0" if not quote.MOCK else "MOCK(未配 DOT_*,打印)")

    # ① 平时仪表盘
    print("\n[1/3] 实时安全仪表盘")
    quote.push_dashboard(traffic.snapshot("12:42"))
    time.sleep(3)

    # ② 异常:门锁被远程控制(真人声那句)
    print("\n[2/3] 异常告警 + 流量尖峰 + 语音")
    dev, atype, score = "smart-lock-02", "malicious_control", 0.98
    kbps = traffic.observe(dev, atype, score)
    line = spike_line(dev, kbps, None)
    quote.push_anomaly_alert(dev, atype.replace("_", " "), int(score * 100),
                             "high", "INC-0002", "12:45", traffic_line=line)
    clip = explain.clip_key(atype)
    spoken = explain.explain_anomaly(dev, atype, score)
    print("   🔊", spoken, " [", line, "]")
    t5.speak_anomaly(clip, "high")                 # T5 板子亲口(发 clip 键)
    voice.speak_anomaly(spoken, "high", clip)      # Mac 真人声/兜底
    time.sleep(4)

    # ③ 收尾:证据封存
    print("\n[3/3] 证据已封存")
    quote.push_evidence_sealed("INC-0002")
    t5.speak_evidence_sealed()
    voice.speak_evidence_sealed(explain.explain_evidence_sealed())
    voice.wait()
    print("\n完成。看 Quote/0 屏 + 听声音(Mac / T5)。")


if __name__ == "__main__":
    main()
