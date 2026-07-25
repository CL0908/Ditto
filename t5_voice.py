"""T5 语音播报 —— 文本转语音（edge-tts · 晓晓）+ 送到 T5 板载喇叭播放。

跟 voice_alert.py（Mac 本地兜底）、t5_bridge.py（旧串口方案，当前固件已不吃这套）
是同一个容错哲学的第三条腿：T5 现在跑的是 TCP 裸音频流固件（见 T5_ARCHITECTURE.md），
只认 send_wav.py 里那套 TWAV 协议，所以播报文本必须先离线合成好 wav 再送过去。

两段能力：
  ① TTS 生成：edge-tts 在线合成 mp3 → ffmpeg 转 16kHz/16bit/单声道 → 落盘缓存
     （alert_cn.wav）。只在缓存不存在时才联网合成一次，现场没网也能用旧缓存播。
  ② 发送播放：复用 send_wav.py 的 TWAV 协议，后台线程送，不阻塞检测主流程。

台词只有一句（已定稿，不做多 clip 管理）：
  "家没啦主人，赶紧救救自己的家！我能帮你切断电源"

限流：整个进程生命周期内只真正播报一次——demo 一次跑 6 条告警，只在第一条
high severity 异常时触发，后续全部跳过，从根上避免播报重叠成噪音。

容错（两层，任何一层失败都不能拖垮检测主流程）：
  TTS 生成失败（在线服务不可达）→ 有缓存就用缓存；没缓存就打印警告跳过
  T5 播放失败/未配置 T5_IP     → 打印警告，降级到 Mac 本地 `say -v Ting-Ting`

环境变量：
  T5_IP   T5 板子的 IPv4 地址（DHCP 分配，换网络会变，不要硬编码）；未设置则跳过播报

独立测试：
  python t5_voice.py --generate          只跑 TTS 生成，检查 alert_cn.wav 时长/格式
  T5_IP=192.168.x.x python t5_voice.py --test   只测发送播放，用现有缓存，不联网
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import threading
import wave
from pathlib import Path
from typing import Optional

from send_wav import send_wav_bytes

log = logging.getLogger("t5_voice")

HERE = Path(__file__).parent
CACHE_WAV = HERE / "alert_cn.wav"
_TMP_MP3 = HERE / ".alert_cn.tmp.mp3"
_TMP_WAV = HERE / ".alert_cn.tmp.wav"

ALERT_TEXT = "家没啦主人，赶紧救救自己的家！我能帮你切断电源"
EDGE_VOICE = "zh-CN-XiaoxiaoNeural"

T5_PORT = 9000
FALLBACK_SAY_VOICE = "Ting-Ting"  # macOS 内置中文女声，T5 联系不上时兜底

_state_lock = threading.Lock()
_fired = False
_thread: Optional[threading.Thread] = None
_configured_ip: Optional[str] = None


def configure(t5_ip: str = "") -> None:
    """运行时注入配置（demo 从 .env 读出 T5_IP 后调用，跟 quote/voice/t5 同风格）。"""
    global _configured_ip
    _configured_ip = t5_ip.strip() or None


def _resolve_ip() -> str:
    if _configured_ip:
        return _configured_ip
    return os.environ.get("T5_IP", "").strip()


# ============================================================
# ① TTS 生成 + 缓存
# ============================================================
def _validate_16k_mono(path: Path) -> bool:
    """T5 固件按 16k 初始化 codec，喂别的采样率会让板子崩溃重启（实测过），
    发送前必须先本地校验，绝不能带着侥幸心理直接发。"""
    try:
        with wave.open(str(path), "rb") as w:
            return w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2
    except Exception:
        return False


def _wav_info(path: Path) -> str:
    with wave.open(str(path), "rb") as w:
        secs = w.getnframes() / float(w.getframerate())
        return f"{w.getframerate()}Hz {w.getsampwidth() * 8}bit {w.getnchannels()}ch 时长={secs:.2f}s"


def generate_and_cache(force: bool = False) -> Optional[Path]:
    """edge-tts 在线合成 → ffmpeg 转 16k/16bit/单声道 → 落盘为 alert_cn.wav。

    缓存已存在且 force=False 时直接返回缓存路径，不联网。
    生成失败返回 None（旧缓存不会被破坏——ffmpeg 先写临时文件，成功了才原地替换）。
    """
    if CACHE_WAV.exists() and not force:
        return CACHE_WAV

    if shutil.which("ffmpeg") is None:
        log.warning("ffmpeg 未安装（brew install ffmpeg），跳过 TTS 生成")
        return None

    try:
        subprocess.run(
            [sys.executable, "-m", "edge_tts", "--voice", EDGE_VOICE,
             "--text", ALERT_TEXT, "--write-media", str(_TMP_MP3)],
            check=True, capture_output=True, timeout=30,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(_TMP_MP3), "-ar", "16000", "-ac", "1",
             "-sample_fmt", "s16", str(_TMP_WAV)],
            check=True, capture_output=True, timeout=30,
        )
        if not _validate_16k_mono(_TMP_WAV):
            log.warning("ffmpeg 输出的 wav 格式校验没过，放弃这次生成")
            return None
        _TMP_WAV.replace(CACHE_WAV)
        log.info("TTS 生成成功: %s (%s)", CACHE_WAV, _wav_info(CACHE_WAV))
        return CACHE_WAV
    except Exception as e:  # noqa: BLE001 —— 在线服务不可达等，绝不抛给调用方
        log.warning("TTS 生成失败（%s），如有旧缓存会继续使用旧缓存", e)
        return None
    finally:
        _TMP_MP3.unlink(missing_ok=True)
        _TMP_WAV.unlink(missing_ok=True)


# ============================================================
# ② 发送播放（后台线程，不阻塞检测主流程）
# ============================================================
def _fallback_say() -> None:
    if shutil.which("say") is None:
        return
    try:
        subprocess.run(["say", "-v", FALLBACK_SAY_VOICE, ALERT_TEXT],
                       check=False, timeout=30)
    except Exception as e:  # noqa: BLE001
        log.warning("Mac say 兜底也失败（忽略）: %s", e)


def _run_alert() -> None:
    wav_path = generate_and_cache()
    if wav_path is None or not wav_path.exists():
        log.warning("没有可用的语音缓存（在线合成失败且无旧缓存），跳过播报")
        return
    if not _validate_16k_mono(wav_path):
        log.warning("缓存 wav 不是 16k/16bit/单声道，为避免把板子搞崩，跳过发送: %s", wav_path)
        return
    payload = wav_path.read_bytes()

    host = _resolve_ip()
    if not host:
        print("[t5_voice] 未设置 T5_IP，跳过 T5 播报，降级 Mac 本地兜底")
        _fallback_say()
        return

    try:
        send_wav_bytes(host, payload, port=T5_PORT, timeout=130,
                       on_status=lambda s: log.info("[T5] %s", s))
        log.info("T5 播报完成")
    except Exception as e:  # noqa: BLE001 —— T5 播放失败绝不能拖垮 demo
        log.warning("T5 播报失败（%s），降级 Mac 本地兜底", e)
        _fallback_say()


def trigger_alert(severity: str = "high") -> bool:
    """检测到异常时调用。整个进程生命周期只真正播报一次
    （第一条 high severity 异常），后续调用直接跳过——demo 一次产生 6 条告警，
    不能重叠成噪音。非阻塞：发送在后台线程里跑，本函数立即返回。

    返回是否**接管了本次播报**。调用方据此决定要不要走自己的播报路径——
    T5 只有一个喇叭，同一事件两条路径同时推会撞车（板子端表现为拒绝或崩溃重启）。
    """
    global _fired, _thread
    if severity != "high":
        return False
    with _state_lock:
        if _fired:
            return False
        _fired = True
        t = threading.Thread(target=_run_alert, name="t5-voice-alert", daemon=True)
        _thread = t
    t.start()
    return True


def wait(timeout: float = 30.0) -> None:
    """demo 收尾时调用，等播报线程跑完再退出，别把 T5 播放/say 兜底截断。"""
    t = _thread
    if t is not None:
        t.join(timeout=timeout)


# ============================================================
# 独立测试入口
# ============================================================
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="T5 语音播报：TTS 生成 / 发送测试")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate", action="store_true",
                       help="只跑 TTS 生成，刷新 alert_cn.wav 缓存（需要联网）")
    group.add_argument("--test", action="store_true",
                       help="只测发送播放，用现有缓存（需要 T5_IP，不联网）")
    args = parser.parse_args()

    if args.generate:
        print(f"合成: {ALERT_TEXT!r}  voice={EDGE_VOICE}")
        path = generate_and_cache(force=True)
        if path is None:
            print("生成失败，见上面的警告")
            raise SystemExit(1)
        print(f"OK -> {path}  {_wav_info(path)}")
        return

    if args.test:
        host = _resolve_ip()
        if not host:
            print("请设置 T5_IP，例如: T5_IP=192.168.x.x python t5_voice.py --test")
            raise SystemExit(1)
        if not CACHE_WAV.exists():
            print(f"没有缓存文件 {CACHE_WAV}，先跑: python t5_voice.py --generate")
            raise SystemExit(1)
        if not _validate_16k_mono(CACHE_WAV):
            print("缓存 wav 不是 16k/16bit/单声道，先重新 --generate 一次")
            raise SystemExit(1)
        payload = CACHE_WAV.read_bytes()
        print(f"发送到 T5 {host}:{T5_PORT} ...")
        try:
            send_wav_bytes(host, payload, port=T5_PORT, timeout=130, on_status=print)
        except Exception as e:  # noqa: BLE001
            print(f"失败: {e}")
            raise SystemExit(1)
        print("播放完成")
        return


if __name__ == "__main__":
    main()
