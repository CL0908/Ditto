#!/usr/bin/env python3
"""Ditto Mac 监听脚本(增强版)—— ESP32-S3 BOOT 键触发 → Mac 端 Ditto 全链输出。

原版只 `say`。增强版把 ESP32 的告警接进 Ditto 输出层:
  ESP32 BOOT 键 → 串口 "ALERT:<文案>" →
    ① 语音播报(优先 Artlist 真人声,否则系统 say)
    ② Quote/0 墨水屏:翻红告警 → 证据封存(REAL 或 MOCK)
    ③ (可选) gateway 签名,复用 ditto_alert(加 --sign)
各输出 fail-safe:任一挂掉不影响其余,也不影响串口监听。

独立可跑:缺 ditto 模块时自动退回纯 `say`(和原版一致)。
  pip install pyserial ；  python mac_listener.py [--sign]
"""
import subprocess
import sys
import time
from pathlib import Path

import serial
import serial.tools.list_ports

# 让 esp32_ditto/ 能 import 上一级 ditto-repo 的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BAUD_RATE = 115200
VOICE = "Tingting"

try:
    import voice_alert as _voice
    import mindreset_quote as _quote
    _HAVE_DITTO = True
except Exception:  # noqa: BLE001
    _HAVE_DITTO = False

_SIGN = "--sign" in sys.argv


def find_port():
    ports = list(serial.tools.list_ports.comports())
    cands = [p.device for p in ports
             if any(k in p.device for k in ("usbmodem", "usbserial", "wchusbserial"))]
    if len(cands) == 1:
        print(f"自动找到串口:{cands[0]}"); return cands[0]
    if len(cands) > 1:
        print("多个串口,请选择:")
        for i, c in enumerate(cands):
            print(f"  [{i}] {c}")
        return cands[int(input("序号:"))]
    for p in ports:
        print(f"  {p.device}  ({p.description})")
    return input("手动输入串口名:").strip()


def _guess_device(text: str) -> tuple[str, str]:
    """从中文文案猜设备类别 + clip 键(真人声/Quote0 脱敏展示用)。"""
    if "摄像头" in text:
        return "smart-camera-01", "dos"
    if "门锁" in text:
        return "smart-lock-02", "malicious_control"
    if "机器人" in text or "麦克风" in text:
        return "smart-robot-05", "spying"
    return "smart-device-00", "spying"


def _configure_ditto():
    if not _HAVE_DITTO:
        return
    env = {}
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("="); env[k.strip()] = v.strip()
    _quote.configure(env.get("DOT_API_KEY", ""), env.get("DOT_DEVICE_ID", ""),
                     env.get("DASHBOARD_URL", ""))
    _voice.configure(True, "zh")


def handle_alert(text: str):
    print(f"🚨 {text}")
    dev, clip = _guess_device(text)
    if not _HAVE_DITTO:
        subprocess.run(["say", "-v", VOICE, text]); return

    _voice.speak_anomaly(text, "high", clip)                 # ① 真人声优先,否则 say
    ts = time.strftime("%H:%M")
    inc = f"INC-{int(time.time()) % 10000:04d}"
    _quote.push_anomaly_alert(dev, text[:24], 96, "high", inc, ts)  # ② 墨水屏翻红
    if _SIGN:                                                 # ③ 可选 gateway 签名
        try:
            import ditto_alert as da
            key = da.load_private_key()
            signed = da.sign_alert(da.make_alert(dev, text), key)
            ok, reason = da.verify_alert(signed, key.public_key())
            print(f"   🔐 signed & verified: {ok} ({reason})  key_id={signed['key_id']}")
        except Exception as e:  # noqa: BLE001
            print(f"   签名跳过: {e}")
    time.sleep(1.0)
    _quote.push_evidence_sealed(inc)
    _voice.wait()


def main():
    _configure_ditto()
    print("Ditto 监听" + (" + 真人声/Quote0" if _HAVE_DITTO else "(纯 say 降级)")
          + (" + 签名" if _SIGN else ""))
    port = find_port()
    print(f"连接 {port} …")
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print(f"打不开串口:{e}(板子插着吗?被别的程序占用了吗?)"); return
    time.sleep(2)
    print("就绪,按板子 BOOT 键触发告警。Ctrl-C 退出。")
    while True:
        try:
            line = ser.readline().decode("utf-8", "replace").strip()
            if not line:
                continue
            if line.startswith("ALERT:"):
                handle_alert(line[len("ALERT:"):])
            elif line.startswith("READY:"):
                print(f"✅ {line[len('READY:'):]}")
            else:
                print(f"   [板] {line}")
        except KeyboardInterrupt:
            print("\n退出。"); break
        except Exception as e:  # noqa: BLE001
            print(f"出错: {e}"); time.sleep(1)
    ser.close()


if __name__ == "__main__":
    main()
