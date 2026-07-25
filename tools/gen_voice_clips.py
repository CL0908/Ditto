"""用 edge-tts 生成 audio/ 下的预渲染播报音频。

为什么是 edge-tts：
  完全免费、**不需要任何 API key**（走微软 Edge 的朗读服务）。
  Artlist 需要订阅才有 voiceover credits；现场断网时两者都用不了，
  所以真正的兜底始终是 voice_alert.py 里的 macOS `say`——这一层永远可用。

文案不在这里硬编码，全部从 explain.py 取：屏幕、语音、Quote/0 必须说同一套话，
一份文案改了三处都跟着变，不会出现"屏上写高危、喇叭念中危"。

    .venv/bin/python tools/gen_voice_clips.py            # 生成缺的
    .venv/bin/python tools/gen_voice_clips.py --force    # 全部重来
    .venv/bin/python tools/gen_voice_clips.py --pcm      # 另存 16k PCM(给 T5 烧固件用)

T5 板载播放需要 16kHz/16bit/mono 裸 PCM（见 t5_firmware/INTEGRATION.md），
--pcm 会顺手用 afconvert 转好，再交给 tools/wav_to_pcm_header.py 生成 .c。
"""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import explain  # noqa: E402

VOICE = "zh-CN-YunyangNeural"     # 男声新闻腔，告警场景比温柔女声更压得住
RATE = "-8%"                       # 稍慢一点，告警要听得清
AUDIO_DIR = Path(__file__).resolve().parent.parent / "audio"

# 现场固定事件（对应 demo.py 的模拟序列），可预渲染 → 零延迟
FIXED_EVENTS = [
    ("spying", "smart-thermostat-03", 0.94),
    ("malicious_control", "smart-lock-02", 0.98),
    ("dos", "smart-camera-01", 0.87),
]


def clips() -> dict[str, str]:
    """clip_key -> 播报文案。全部由 explain.py 生成，不在此处另写一份。"""
    out = {k: explain.explain_anomaly(dev, k, score) for k, dev, score in FIXED_EVENTS}
    out["evidence_sealed"] = explain.explain_evidence_sealed()
    out["normal"] = explain.explain_normal(5)
    out["offline"] = explain.explain_offline()
    return out


async def render(text: str, dest: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(dest))


def to_pcm(mp3: Path) -> Path | None:
    """转 16kHz/16bit/mono wav —— T5 固件要这个格式。"""
    wav = mp3.with_suffix(".16k.wav")
    r = subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                        str(mp3), str(wav)], capture_output=True)
    if r.returncode != 0:
        print(f"    ✗ 转 PCM 失败: {r.stderr.decode()[:120]}")
        return None
    return wav


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="已存在也重新生成")
    p.add_argument("--pcm", action="store_true", help="额外产出 16k wav（T5 固件用）")
    a = p.parse_args()

    AUDIO_DIR.mkdir(exist_ok=True)
    made = skipped = failed = 0
    for key, text in clips().items():
        dest = AUDIO_DIR / f"{key}.mp3"
        if dest.exists() and not a.force:
            print(f"  跳过 {key}.mp3（已存在，--force 可覆盖）")
            skipped += 1
            continue
        try:
            await render(text, dest)
            size = dest.stat().st_size
            print(f"  ✓ {key}.mp3  {size//1024}KB  「{text[:28]}…」")
            made += 1
            if a.pcm:
                w = to_pcm(dest)
                if w:
                    print(f"      └ {w.name}  {w.stat().st_size//1024}KB (16k PCM)")
        except Exception as e:                       # noqa: BLE001
            print(f"  ✗ {key}: {e}")
            failed += 1

    print(f"\n生成 {made}，跳过 {skipped}，失败 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
