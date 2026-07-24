#!/usr/bin/env python3
"""把音频（Artlist mp3 / say aiff / 任意 wav）转成 T5AI 能烧进固件、离线播放的
16kHz/16bit/mono 裸 PCM 的 C 数组源文件。

T5 的 tdl_audio_play() 只吃裸 PCM（16k/16bit/mono，无 WAV 头）。本工具:
  ffmpeg 重采样成 16k 单声道 s16le → 生成 src/audio_data_<key>.c + include 声明。

用法:
  python tools/wav_to_pcm_header.py audio/spying.mp3 spying
  python tools/wav_to_pcm_header.py audio/dos.aiff   dos
输出:
  t5_firmware/audio_data_<key>.c   (const unsigned char g_pcm_<key>[] + g_pcm_<key>_len)
一次转全部 6 个:见 tools/gen_all_pcm.sh
"""
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "t5_firmware"


def to_pcm(src: str) -> bytes:
    """ffmpeg → 16kHz mono s16le 裸 PCM。"""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", src, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
        check=True, capture_output=True).stdout
    return out


def emit_c(key: str, pcm: bytes) -> Path:
    var = f"g_pcm_{key}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"audio_data_{key}.c"
    lines = [
        f'/* 自动生成: audio_data_{key}.c —— 16kHz/16bit/mono 裸 PCM，供 tdl_audio_play 离线播放 */',
        f'#include "app_local_audio.h"',
        "",
        f"const unsigned int {var}_len = {len(pcm)}u;",
        f"const unsigned char {var}[] = {{",
    ]
    body = []
    for i in range(0, len(pcm), 16):
        chunk = pcm[i:i + 16]
        body.append("  " + ",".join(f"0x{b:02x}" for b in chunk) + ",")
    lines.extend(body)
    lines.append("};")
    path.write_text("\n".join(lines) + "\n")
    return path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, key = sys.argv[1], sys.argv[2]
    pcm = to_pcm(src)
    path = emit_c(key, pcm)
    secs = len(pcm) / (16000 * 2)
    print(f"  {key:18s} {len(pcm):>7d} B PCM ({secs:.1f}s) → {path.relative_to(OUT_DIR.parent)}")


if __name__ == "__main__":
    main()
