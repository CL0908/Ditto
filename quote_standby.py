"""Quote/0 无人值守布展 —— 把三屏内容各自锁进云端，之后不需要任何机器在场。

原理：MindReset 把每个 API 任务的内容**存在云端**，推一次就驻留。
设备的 Loop 会轮播这些任务，这个轮播由设备自己完成，不依赖你的 Mac。
所以：跑一次本脚本 → 关电脑 → 屏幕继续三屏轮播。

    .venv/bin/python quote_standby.py

三个任务各放一屏，合起来是完整叙事（每个任务只存最后推的那一份，所以一屏一个）：
    Canvas API → ① 平静：仪表盘（tito + 安全分 + 各设备流量柱）
    Image  API → ② 遭攻击：告警屏（流量波形冲顶，Image 的像素控制最能打）
    Text   API → ③ 已封存：证据上链（纯文字足够，也是断网时最稳的一层）

跑完还要去 Dot App 做一次（这步是 App 里的操作，脚本做不到）：
    Content Studio → 选设备 → Loop 任务里把 Text / Canvas / Image 三项都加上
    → 设好每屏停留时长 → 保存
只加了其中一项的话，就只会一直显示那一屏。

与 quote_loop.py 的区别：
    quote_loop.py  画面会动（有攻击发生的过程感），但必须有机器一直跑着
    quote_standby.py  推完即走，画面是静态三屏轮换，无需任何机器
现场建议两个都用：本脚本做保底，讲解时再开 quote_loop.py 加演。
"""
from __future__ import annotations

import sys
import time

import explain
import mindreset_quote as quote
import quote_image as qi
from preview_quote import load_env
from traffic_sim import HomeTraffic, spike_line

INCIDENT = "INC-0421"
DEVICE = "smart-camera-01"


def build_traffic() -> tuple[HomeTraffic, dict, float]:
    """造出"平稳一段时间后遭攻击"的真实时序，供波形使用。"""
    t = HomeTraffic()
    for _ in range(16):
        t.tick()
    kbps = t.observe(DEVICE, "spying", 0.94)
    for _ in range(5):
        t.tick()
    return t, t.snapshot(time.strftime("%H:%M")), kbps


def main() -> int:
    env = load_env()
    quote.configure(env.get("DOT_API_KEY", ""), env.get("DOT_DEVICE_ID", ""),
                    env.get("DASHBOARD_URL", ""),
                    image_api_key=env.get("DOT_IMAGE_API_KEY", ""))
    if quote.MOCK:
        print("⚠ 未配置 DOT_API_KEY / DOT_DEVICE_ID —— MOCK 模式，不会真发")

    traffic, snap, kbps = build_traffic()
    results = []

    # ① Canvas：平静态仪表盘。用攻击前的干净快照，别把异常状态带进去。
    calm = HomeTraffic()
    for _ in range(16):
        calm.tick()
    results.append(("① 平静  (Canvas)",
                    quote.push_dashboard_canvas(calm.snapshot(time.strftime("%H:%M")))))

    # ② Image：告警屏。Image API 有独立 key，绕开 mindreset_quote 的三层路由直接推，
    #    确保这一屏一定落在 Image 任务里（走路由的话可能被 canvas 抢走）。
    img = qi.render_anomaly(
        device_name=explain.device_name(DEVICE),
        event_type=explain.behavior_phrase("spying"),
        risk_score=94, severity_cn=quote.sev_cn("high"),
        incident_id=INCIDENT, timestamp=time.strftime("%H:%M:%S"),
        history=snap["history"])
    results.append(("② 遭攻击 (Image)",
                    qi.push(img, api_key=env.get("DOT_IMAGE_API_KEY", ""),
                            device_id=env.get("DOT_DEVICE_ID", ""))))

    # ③ Text：证据封存。同样绕开路由，直接打 text 端点。
    results.append(("③ 已封存 (Text)", quote._post(quote._text_url(), {
        "title": "证据已封存",
        "message": f"事件 {INCIDENT}\n哈希已验证 ✓\n链路完整 ✓",
        "signature": "已上链存证，不可篡改",
        "refreshNow": True,
    }, dedup=False, urgent=True)))

    print()
    for name, ok in results:
        print(f"  {name}  {'✓' if ok else '✗ 失败'}")

    failed = [n for n, ok in results if not ok]
    print(f"\n流量数据：常态 {sorted(snap['history'])[len(snap['history'])//2]:.0f} KB/s"
          f" → 峰值 {max(snap['history']):.0f} KB/s"
          f"（{spike_line(DEVICE, kbps, None)}）")

    if failed:
        print(f"\n⚠ {len(failed)} 屏没推上去，检查网络后重跑")
        return 1
    print("\n三屏已锁进云端，现在可以关电脑了。")
    print("最后一步（必须在 Dot App 里做）：")
    print("  Content Studio → 选设备 → Loop 里把 Text / Canvas / Image 三项都加上 → 保存")
    print("  只加一项的话就只会一直显示那一屏。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
