"""T5AI DevKit 串口桥 —— 让 T5 板子用自己的喇叭「开口播报」（B 档）。

Mac 上的检测流水线检测到入侵后，把**一句脱敏文案**通过 USB 串口发给 T5AI，
T5 侧 TuyaOpen 固件收到后走云端 TTS，用板载喇叭念出来。这才是字面意义的「T5 播报」。

两个用途：
  1) 读启动日志：先看板子当前刷的什么固件，决定发送帧格式
       .venv/bin/python t5_bridge.py log
  2) 发文案给 T5 播报：
       .venv/bin/python t5_bridge.py say "注意，门锁被远程控制"

设计（对齐项目容错哲学）：
  · pyserial 缺失 / 端口打不开 / 写失败 → 全部 no-op 返回 False，绝不抛异常、不阻塞检测
  · 只发脱敏摘要，绝不发原始包/IP/身份
  · 发送帧格式集中在 _frame() 一处，实测固件后只改这一个函数（对齐 README 里
    zilo_protocol「只改一行」的思路）

环境变量：
  T5_PORT  = /dev/cu.usbmodem5AAE1667591   （默认取第一个 usbmodem 口）
  T5_BAUD  = 115200                         （TuyaOpen 日志/控制台常用波特率）
  T5_ENABLED = 1|0                          （默认 1）
"""
from __future__ import annotations

import glob
import logging
import os
import time

log = logging.getLogger("t5_bridge")

try:
    import serial  # pyserial
except Exception:  # noqa: BLE001
    serial = None


def _default_port() -> str:
    env = os.environ.get("T5_PORT", "")
    if env:
        return env
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    return ports[0] if ports else ""


PORT = _default_port()
BAUD = int(os.environ.get("T5_BAUD", "115200"))
ENABLED = os.environ.get("T5_ENABLED", "1") not in ("0", "false", "")
WRITE_TIMEOUT = 2.0


def configure(port: str = "", baud: int = 0, enabled: bool | None = None) -> None:
    global PORT, BAUD, ENABLED
    if port:
        PORT = port
    if baud:
        BAUD = baud
    if enabled is not None:
        ENABLED = enabled


def _frame(text: str, severity: str) -> bytes:
    """把 clip 键打成一帧发给 T5。

    协议(与 T5 固件 app_local_audio.c::app_local_cmd_dispatch 对齐):
    一行纯文本 clip 键 + 换行,如 `spying\\n`。固件按行读、strcmp 命令表、播对应 PCM。
    demo 里传进来的 text 就是 explain.clip_key()(spying/malicious_control/dos/…)。
    severity 目前不上板(音色已烧在 PCM 里),保留形参供以后扩展。
    """
    return (text.strip() + "\n").encode("utf-8")


def send_alert(text: str, severity: str = "high") -> bool:
    """把一句脱敏文案发给 T5 播报。失败返回 False，绝不抛异常。"""
    if not ENABLED:
        log.info("[T5·off] %s", text)
        return True
    if serial is None:
        log.warning("pyserial 未安装，跳过 T5 播报（不影响检测）")
        return False
    if not PORT:
        log.warning("未找到 T5 串口，跳过（不影响检测）")
        return False
    try:
        with serial.Serial(PORT, BAUD, timeout=1, write_timeout=WRITE_TIMEOUT) as ser:
            ser.write(_frame(text, severity))
            ser.flush()
        log.info("已发送到 T5: %s", text[:24])
        return True
    except Exception as e:  # noqa: BLE001 —— 串口问题绝不拖垮检测
        log.warning("T5 发送失败（忽略）: %s", e)
        return False


def read_log(seconds: float = 5.0, port: str = "", baud: int = 0) -> str:
    """读一段串口输出，用于判断板子当前固件。返回原始文本（可能为空）。"""
    if serial is None:
        return "[pyserial 未安装]"
    p = port or PORT
    b = baud or BAUD
    if not p:
        return "[未找到串口]"
    buf = bytearray()
    deadline = time.time() + seconds
    try:
        with serial.Serial(p, b, timeout=0.5) as ser:
            while time.time() < deadline:
                chunk = ser.read(4096)
                if chunk:
                    buf.extend(chunk)
    except Exception as e:  # noqa: BLE001
        return f"[读取失败: {e}]"
    return buf.decode("utf-8", errors="replace")


# 语义化入口（demo/pipeline 直接调，和 voice_alert 同签名风格）
def speak_anomaly(text: str, severity: str = "high") -> bool:
    return send_alert(text, severity)


def speak_evidence_sealed(text: str = "证据已上链，无法篡改。") -> bool:
    return send_alert(text, "medium")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    print(f"PORT={PORT or '(none)'}  BAUD={BAUD}  pyserial={'yes' if serial else 'NO'}")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "log"
    if cmd == "log":
        secs = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
        print(f"读取串口 {secs:.0f}s（如无输出，试按板子 RESET 键触发启动日志）…\n" + "-" * 60)
        out = read_log(secs)
        print(out if out.strip() else "[静默——板子可能没在打印，或波特率不对，或是烧录口]")
        print("-" * 60)
    elif cmd == "say":
        text = sys.argv[2] if len(sys.argv) > 2 else "T5 播报测试"
        ok = send_alert(text, "high")
        print("发送", "成功" if ok else "失败")
    else:
        print("用法: t5_bridge.py [log [秒数] | say '文案']")
