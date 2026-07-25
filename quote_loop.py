"""Quote/0 展台循环 —— 让墨水屏自己把一整个攻击故事循环演下去。

用途：路演/展台无人值守时，屏幕不停地走「平静 → 遭攻击 → 证据封存 → 恢复」
四幕，观众任何时候路过都能看到有内容。

    .venv/bin/python quote_loop.py                  # 默认每幕 30 秒，无限循环
    .venv/bin/python quote_loop.py --interval 20    # 加快
    .venv/bin/python quote_loop.py --cycles 3       # 只走三轮就退出
    .venv/bin/python quote_loop.py --once           # 只走一轮（等于 --cycles 1）

重要前提（别搞错了）：
  这个脚本必须**跑在一台联网的机器上**。Quote/0 不是连你的后端，而是连
  MindReset 云；你的进程停了，屏幕就定格在最后一幕不再变化（墨水屏断电也留字，
  所以"屏上有画面"不代表"还在循环"）。
  如果现场不能留一台机器，见 README 的「无人值守」一节：改用 Dot App 的 Loop
  轮播已推送的内容，那条路不需要任何机器在场，但画面是静态的三屏轮换。

对墨水屏的保护：
  每幕至少 15 秒（E-Ink 全刷 1~2 秒且会闪，刷太勤既难看又费屏）。
  网络抖动只记日志不退出——展台跑一整天，不能因为一次超时就黑屏。
"""
from __future__ import annotations

import argparse
import itertools
import logging
import signal
import sys
import time

import explain
import mindreset_quote as quote
from preview_quote import load_env
from traffic_sim import HomeTraffic, spike_line

log = logging.getLogger("quote_loop")

MIN_INTERVAL = 15          # 秒，低于这个值对 E-Ink 没好处
INCIDENT = "INC-0421"

_stop = False


def _handle_sigint(signum, frame):        # noqa: ARG001
    global _stop
    _stop = True
    print("\n收到中断，本幕结束后退出…")


def _sleep(seconds: float) -> None:
    """可被 Ctrl-C 立刻打断的等待。"""
    end = time.time() + seconds
    while time.time() < end and not _stop:
        time.sleep(0.2)


def run(interval: int, cycles: int) -> int:
    env = load_env()
    quote.configure(env.get("DOT_API_KEY", ""), env.get("DOT_DEVICE_ID", ""),
                    env.get("DASHBOARD_URL", ""),
                    image_api_key=env.get("DOT_IMAGE_API_KEY", ""))
    if quote.MOCK:
        print("⚠ 未配置 DOT_API_KEY / DOT_DEVICE_ID —— MOCK 模式，只打印不真发")
    print(f"展台循环启动：每幕 {interval}s，"
          f"{'无限循环' if cycles == 0 else f'{cycles} 轮后退出'}，Ctrl-C 停止")

    device = "smart-camera-01"
    ok_count = fail_count = 0

    for cycle in itertools.count(1):
        if _stop or (cycles and cycle > cycles):
            break

        traffic = HomeTraffic()
        for _ in range(16):               # 平稳期基线，让后面的尖峰有对比
            traffic.tick()

        scenes = [
            ("① 平静", lambda: quote.push_dashboard(
                traffic.snapshot(time.strftime("%H:%M")))),
            ("② 遭攻击", lambda: _attack(traffic, device)),
            ("③ 证据封存", lambda: quote.push_evidence_sealed(INCIDENT)),
            ("④ 已处置", lambda: _recovered(traffic, device)),
        ]

        for name, action in scenes:
            if _stop:
                break
            try:
                ok = action()
            except Exception as e:        # noqa: BLE001 —— 展台不能因一次异常就停
                log.warning("%s 推送异常: %s", name, e)
                ok = False
            ok_count, fail_count = (ok_count + 1, fail_count) if ok else (ok_count, fail_count + 1)
            print(f"  [第{cycle}轮] {name}  {'✓' if ok else '✗ 失败(已跳过,循环继续)'}")
            _sleep(interval)

    print(f"\n结束：成功 {ok_count} 次，失败 {fail_count} 次")
    return 0 if fail_count == 0 else 1


def _attack(traffic: HomeTraffic, device: str) -> bool:
    """第二幕：摄像头开始外传数据，流量冲顶。"""
    kbps = traffic.observe(device, "spying", 0.94)
    for _ in range(5):                    # 攻击持续期，波形维持高位
        traffic.tick()
    snap = traffic.snapshot(time.strftime("%H:%M"))
    return quote.push_anomaly_alert(
        device_name=explain.device_name(device),
        event_type=explain.behavior_phrase("spying"),
        risk_score=94,
        severity=explain.severity_of(0.94),
        incident_id=INCIDENT,
        timestamp=time.strftime("%H:%M:%S"),
        traffic_line=spike_line(device, kbps, None),
        rates=snap["rates"], history=snap["history"], device_id=device,
    )


def _recovered(traffic: HomeTraffic, device: str) -> bool:
    """第四幕：已封堵，流量回落到常态——屏上能看见波形从尖峰掉回基线。"""
    traffic.observe(device, "normal", 0.02)
    for _ in range(6):
        traffic.tick()
    return quote.push_dashboard(traffic.snapshot(time.strftime("%H:%M")))


def main() -> int:
    p = argparse.ArgumentParser(description="Quote/0 展台循环")
    p.add_argument("--interval", type=int, default=30, help="每幕停留秒数（默认 30）")
    p.add_argument("--cycles", type=int, default=0, help="循环轮数，0=无限（默认）")
    p.add_argument("--once", action="store_true", help="只走一轮")
    a = p.parse_args()

    interval = max(MIN_INTERVAL, a.interval)
    if interval != a.interval:
        print(f"⚠ 间隔已抬到 {MIN_INTERVAL}s —— E-Ink 刷太勤会闪且伤屏")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    signal.signal(signal.SIGINT, _handle_sigint)
    return run(interval, 1 if a.once else a.cycles)


if __name__ == "__main__":
    sys.exit(main())
