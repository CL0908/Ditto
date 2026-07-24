"""流量/数据指标模拟器 —— 为 Quote/0 安全仪表盘提供「检测到的流量」。

检测事件是模拟的，所以流量也由事件流**确定性派生**：每台设备有稳定基线，
异常时对应设备流量尖峰。纯字典 + 确定性算术，可复现、断网可跑、不含随机数
（对齐项目红线：确定性、无 LLM 参与）。

后续接 TuyaClaw / 真实设备遥测时，只需把 `HomeTraffic.observe()` 的数据源换成
真实字节计数，Quote/0 与 demo 上层无需改动。

只输出**聚合脱敏指标**（每设备类别的 KB/s、总吞吐、当前 top talker、安全分），
绝不输出原始包 / IP / 端口 / 拓扑。
"""
from __future__ import annotations

# 每台设备的正常基线吞吐（KB/s）—— 与 demo.py 的模拟设备对齐
_BASELINE = {
    "smart-camera-01": 220.0,   # 摄像头常态码流最高
    "smart-thermostat-03": 3.5,
    "smart-lock-02": 1.2,
    "smart-plug-07": 0.8,
    "smart-speaker-05": 40.0,
}

# 异常类型 → 相对基线的流量倍数（尖峰强度，脱敏后的“行为强度”）
_SPIKE = {
    "dos": 18.0,                 # 被劫持发起攻击 → 流量暴涨
    "spying": 6.0,               # 悄悄外传数据 → 明显上行
    "malicious_control": 3.0,
    "malicious_operation": 2.5,
    "scan": 4.0,
    "data_probing": 2.0,
    "wrong_setup": 1.5,
    "normal": 1.0,
}


def _fmt_rate(kbps: float) -> str:
    """KB/s 人类可读：>=1024 显示 MB/s。"""
    if kbps >= 1024:
        return f"{kbps / 1024:.1f}MB/s"
    return f"{kbps:.0f}KB/s"


class HomeTraffic:
    """维护每台设备的当前吞吐，随事件更新，产出仪表盘快照。"""

    def __init__(self, devices: dict | None = None):
        self.rates = dict(devices or _BASELINE)      # device_id -> KB/s
        self.baseline = dict(self.rates)
        self._anomaly_devices: set[str] = set()

    def observe(self, device_id: str, anomaly_type: str, score: float) -> float:
        """喂入一个检测事件，更新该设备当前吞吐，返回该设备最新 KB/s。"""
        base = self.baseline.get(device_id, 5.0)
        mult = _SPIKE.get(anomaly_type, 1.0)
        # 尖峰强度按风险分微调（score 越高越猛），确定性
        rate = base * mult * (1.0 + 0.5 * float(score))
        self.rates[device_id] = round(rate, 1)
        if anomaly_type != "normal":
            self._anomaly_devices.add(device_id)
        else:
            self._anomaly_devices.discard(device_id)
        return self.rates[device_id]

    def total_kbps(self) -> float:
        return round(sum(self.rates.values()), 1)

    def top_talker(self) -> tuple[str, float]:
        """当前吞吐最高的设备（脱敏：只回类别名 + 速率）。"""
        if not self.rates:
            return ("—", 0.0)
        dev, rate = max(self.rates.items(), key=lambda kv: kv[1])
        return (dev, rate)

    def security_score(self) -> int:
        """安全分 0-100：每个处于异常的设备扣分（确定性）。"""
        return max(0, 100 - 12 * len(self._anomaly_devices))

    def device_count(self) -> int:
        return len(self.rates)

    def snapshot(self, last_checked: str = "") -> dict:
        """给 Quote/0 仪表盘的一屏脱敏快照。"""
        dev, rate = self.top_talker()
        anomalies = len(self._anomaly_devices)
        return {
            "device_count": self.device_count(),
            "security_score": self.security_score(),
            "total_kbps": self.total_kbps(),
            "total_human": _fmt_rate(self.total_kbps()),
            "top_talker": dev,
            "top_talker_human": _fmt_rate(rate),
            "anomaly_count": anomalies,
            "status": "正常" if anomalies == 0 else f"{anomalies} 台异常",
            "last_checked": last_checked,
        }


# 便捷格式化：给单台设备的流量尖峰做一行摘要（异常时补在告警下）
def spike_line(device_id: str, kbps: float, baseline_kbps: float | None) -> str:
    base = baseline_kbps if baseline_kbps is not None else _BASELINE.get(device_id, 5.0)
    x = (kbps / base) if base > 0 else 0
    return f"流量 {_fmt_rate(kbps)}（≈{x:.0f}× 常态）"


if __name__ == "__main__":
    t = HomeTraffic()
    print("初始快照:", t.snapshot("12:42"))
    for d, a, s in [("smart-thermostat-03", "spying", 0.94),
                    ("smart-camera-01", "dos", 0.87)]:
        r = t.observe(d, a, s)
        print(f"  {d} {a} → {r}KB/s | {spike_line(d, r, None)}")
    print("异常后快照:", t.snapshot("12:45"))
