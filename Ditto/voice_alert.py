"""语音播报 —— 家庭安全哨兵的「实体声音输出」适配器。

哨兵在 T5 本地检测到入侵后，把**脱敏后的一句人话**播报出来。
与 mindreset_quote.py（墨水屏）同一套容错哲学，只是输出到扬声器。

三级音源（自动降级，现场绝不哑火）：
  ① 预渲染真人音色  audio/{clip_key}.mp3   —— Artlist 提前渲染，afplay 秒播，离线零延迟（首选）
  ② 系统 TTS        macOS `say`            —— 离线兜底，任何动态文案都能念，永远可用
  ③ 关闭            VOICE_ENABLED=0        —— 纯打印（无声环境/CI）

设计约束（对齐项目红线）：
  · 播报在后台线程队列里跑，**绝不阻塞检测主循环**（失败全 catch，返回 bool）
  · 相同内容不重复念（dedup by hash）＋ 最小间隔守卫（防轰炸）
  · high/medium 用不同语速语气；只念脱敏摘要，绝不念原始包/IP/身份

环境变量：
  VOICE_ENABLED = 1|0     （默认 1；置 0 只打印不发声）
  VOICE_LANG    = zh|en   （默认 zh）
  AUDIO_DIR     = audio   （预渲染 mp3 目录，相对本文件）
  VOICE_ZH / VOICE_EN     （覆盖默认音色，如 Ting-Ting / Samantha）
"""
from __future__ import annotations

import hashlib
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

log = logging.getLogger("voice_alert")

ENABLED = os.environ.get("VOICE_ENABLED", "1") not in ("0", "false", "False", "")
LANG = os.environ.get("VOICE_LANG", "zh")
AUDIO_DIR = Path(__file__).parent / os.environ.get("AUDIO_DIR", "audio")
VOICE_ZH = os.environ.get("VOICE_ZH", "Ting-Ting")   # macOS 内置中文女声
VOICE_EN = os.environ.get("VOICE_EN", "Samantha")

MIN_INTERVAL = 3.0       # 秒：同一路播报的最小间隔，防轰炸
CLIP_EXTS = (".mp3", ".wav", ".m4a", ".aiff")
_HAVE_SAY = shutil.which("say") is not None
_HAVE_AFPLAY = shutil.which("afplay") is not None

# 语速（say -r，词/分钟）：级别越高越沉稳有力
_RATE = {"high": 165, "medium": 180, "low": 190}

_q: "queue.Queue[tuple]" = queue.Queue(maxsize=32)
_worker: threading.Thread | None = None
_last_hash: str | None = None
_last_ts = 0.0
_lock = threading.Lock()


def configure(enabled: bool | None = None, lang: str = "") -> None:
    """运行时注入配置（demo 从 .env 读出后调用）。"""
    global ENABLED, LANG
    if enabled is not None:
        ENABLED = enabled
    if lang:
        LANG = lang


def _voice() -> str:
    return VOICE_ZH if LANG == "zh" else VOICE_EN


def _find_clip(clip_key: str | None) -> Path | None:
    if not clip_key:
        return None
    for ext in CLIP_EXTS:
        p = AUDIO_DIR / f"{clip_key}{ext}"
        if p.exists():
            return p
    return None


def _ensure_worker() -> None:
    global _worker
    if _worker and _worker.is_alive():
        return
    _worker = threading.Thread(target=_run, name="voice-alert", daemon=True)
    _worker.start()


def _run() -> None:
    """后台顺序播放，语音不重叠；任何异常都不会拖垮哨兵。"""
    while True:
        text, clip_key, severity = _q.get()
        try:
            clip = _find_clip(clip_key)
            if clip and _HAVE_AFPLAY:                       # ① 预渲染真人音色
                subprocess.run(["afplay", str(clip)], check=False,
                               timeout=30)
            elif _HAVE_SAY:                                 # ② 系统 TTS 兜底
                subprocess.run(
                    ["say", "-v", _voice(), "-r", str(_RATE.get(severity, 180)), text],
                    check=False, timeout=30)
            else:                                           # ③ 无 TTS 环境
                print(f"[VOICE] {text}")
        except Exception as e:  # noqa: BLE001 —— 播报出错绝不影响检测
            log.warning("语音播报失败（忽略）: %s", e)
        finally:
            _q.task_done()


def _enqueue(text: str, clip_key: str | None, severity: str,
             dedup: bool = True) -> bool:
    """入队播报。失败返回 False，绝不抛异常。"""
    global _last_hash, _last_ts
    if not ENABLED:
        print(f"[VOICE·off] {text}")
        return True
    try:
        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        now = time.time()
        with _lock:
            if dedup and h == _last_hash and now - _last_ts < MIN_INTERVAL:
                log.debug("跳过重复播报 %s", h)
                return True
            _last_hash, _last_ts = h, now
        _ensure_worker()
        _q.put_nowait((text, clip_key, severity))
        log.info("已入队播报: %s", text[:24])
        return True
    except queue.Full:
        log.warning("语音队列已满，丢弃本条（不阻塞检测）")
        return False
    except Exception as e:  # noqa: BLE001
        log.warning("入队失败（忽略）: %s", e)
        return False


def wait(timeout: float = 20.0) -> None:
    """等队列播完再退出（demo 结尾调，防止最后一句被截断）。"""
    if not ENABLED:
        return
    deadline = time.time() + timeout
    while not _q.empty() and time.time() < deadline:
        time.sleep(0.1)
    time.sleep(0.3)  # 给正在播放的最后一段留点尾巴


# ============================================================
# 语义化播报（哨兵 alert pipeline 直接调）——只念脱敏摘要
# ============================================================
def speak_anomaly(text: str, severity: str = "high",
                  clip_key: str | None = None) -> bool:
    return _enqueue(text, clip_key, severity, dedup=True)


def speak_evidence_sealed(text: str = "证据已上链，无法篡改。") -> bool:
    return _enqueue(text, "evidence_sealed", "medium", dedup=False)


def speak_normal(text: str) -> bool:
    return _enqueue(text, "normal", "low", dedup=True)


def speak_offline(text: str = "哨兵已离线，本地监控暂停。") -> bool:
    return _enqueue(text, "offline", "high", dedup=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import explain
    print("VOICE_ENABLED =", ENABLED, "| LANG =", LANG,
          "| say =", _HAVE_SAY, "| afplay =", _HAVE_AFPLAY)
    print("试听三种告警（有 audio/*.mp3 则播真人音色，否则 say 兜底）…")
    speak_anomaly(explain.explain_anomaly("smart-camera-01", "spying", 0.94),
                  "high", explain.clip_key("spying"))
    speak_anomaly(explain.explain_anomaly("smart-lock-02", "malicious_control", 0.98),
                  "high", explain.clip_key("malicious_control"))
    speak_evidence_sealed(explain.explain_evidence_sealed())
    wait()
    print("完成。")
