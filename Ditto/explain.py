"""异常 → 一句「人话」解释 —— 让哨兵开口时不是干念 "DoS detected"，
而是告诉你「发生了什么、为什么可疑」。

设计：
  · 纯模板、确定性、可复现，断网照跑（附录A：LLM 不参与判定，只在录入/文案阶段）。
  · 只用脱敏字段（设备类别 + 行为类型 + 风险分），绝不带原始包/IP/拓扑/身份。
  · 输出同时给出 clip_key，供 voice_alert 优先播放预渲染的真人音色 audio/{clip_key}.mp3。
"""
from __future__ import annotations

# 设备 id 前缀 → 中文类别名（只做类别归一，不暴露具体位置/身份）
_DEVICE_ALIAS = {
    "smart-camera": "摄像头",
    "smart-thermostat": "温控器",
    "smart-lock": "智能门锁",
    "smart-plug": "智能插座",
    "smart-speaker": "智能音箱",
    "smart-tv": "智能电视",
    "smart-sensor": "传感器",
}

# DS2OS 攻击类型 → (行为短语, 为什么可疑)
_ANOMALY_PHRASE = {
    "spying":            ("正在悄悄采集并向外发送数据", "疑似被植入监听"),
    "malicious_control": ("正在被远程恶意控制", "行为已不受你掌控"),
    "malicious_operation": ("执行了异常操作", "与它平时的行为不符"),
    "dos":               ("出现异常大流量", "疑似被劫持发起攻击"),
    "scan":              ("正在被人扫描探测", "有人在摸你的家庭网络"),
    "data_probing":      ("正在被探测数据类型", "疑似入侵前的试探"),
    "wrong_setup":       ("配置被异常改动", "可能被人动过手脚"),
}


def _device_name(device_id: str) -> str:
    for prefix, alias in _DEVICE_ALIAS.items():
        if device_id.startswith(prefix):
            num = device_id[len(prefix):].lstrip("-")
            return f"{alias}{num}" if num else alias
    return device_id


def severity_of(score: float) -> str:
    """与 demo.py 保持一致：>=0.9 high / >=0.7 medium / else low。"""
    return "high" if score >= 0.9 else "medium" if score >= 0.7 else "low"


def clip_key(anomaly_type: str) -> str:
    """预渲染音频文件名（audio/{clip_key}.mp3）。按攻击类型固定，便于 Artlist 提前渲染。"""
    return anomaly_type.strip().lower().replace(" ", "_")


def explain_anomaly(device_id: str, anomaly_type: str, score: float) -> str:
    """一句中文播报文案（已脱敏）。未知类型走通用兜底，绝不抛异常。"""
    name = _device_name(device_id)
    behavior, why = _ANOMALY_PHRASE.get(
        anomaly_type, ("出现了异常行为", "与平时明显不同")
    )
    pct = int(round(float(score) * 100))
    return f"注意，{name}{behavior}，{why}。风险{pct}分，已为你封存证据。"


def explain_evidence_sealed() -> str:
    return "证据已上链，无法篡改。"


def explain_normal(device_count: int) -> str:
    return f"家庭防护正常，{device_count}台设备在线。"


def explain_offline() -> str:
    return "哨兵已离线，本地监控暂停。"


if __name__ == "__main__":
    for d, a, s in [
        ("smart-thermostat-03", "spying", 0.94),
        ("smart-lock-02", "malicious_control", 0.98),
        ("smart-camera-01", "dos", 0.87),
    ]:
        print(f"[{clip_key(a):18s}] {explain_anomaly(d, a, s)}")
    print("[evidence_sealed  ]", explain_evidence_sealed())
