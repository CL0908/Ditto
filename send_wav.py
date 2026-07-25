#!/usr/bin/env python3
"""T5 TCP 音频播放协议（"TWAV"）—— 协议细节见 T5_ARCHITECTURE.md §1。

CLI 用法（手动测试，行为与原脚本一致）：
    python send_wav.py <host> <wav文件> [--port 9000]

其他模块（t5_voice.py）直接 `from send_wav import send_wav_bytes` 复用协议，
协议实现只在这一处，不重复。
"""
import argparse
import socket
import struct
from pathlib import Path
from typing import Callable, Optional


def recv_line(sock: socket.socket) -> str:
    data = bytearray()
    while not data.endswith(b"\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("device closed the connection")
        data.extend(chunk)
    return data.decode("utf-8", errors="replace").strip()


def send_wav_bytes(host: str, payload: bytes, port: int = 9000, timeout: float = 130,
                    on_status: Optional[Callable[[str], None]] = None) -> None:
    """把 WAV 字节流发给 T5 播放，走完整的 TWAV 协议。

    成功（收到 "DONE"）正常返回；失败（连不上/超时/"ERROR..."）抛异常，
    由调用方决定怎么兜底——这里不吞任何错误。
    """
    if payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(timeout)
        sock.sendall(b"TWAV" + struct.pack("!I", len(payload)))

        status = recv_line(sock)
        if on_status:
            on_status(status)
        if status != "READY":
            raise RuntimeError(f"T5 not ready: {status}")

        sock.sendall(payload)
        while True:
            status = recv_line(sock)
            if on_status:
                on_status(status)
            if status == "DONE":
                return
            if status.startswith("ERROR"):
                raise RuntimeError(f"T5 error: {status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a WAV file to the T5 TCP audio player")
    parser.add_argument("host", help="T5 IPv4 address")
    parser.add_argument("wav", type=Path, help="WAV file path")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    payload = args.wav.read_bytes()
    if payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise SystemExit(f"not a RIFF/WAVE file: {args.wav}")

    try:
        send_wav_bytes(args.host, payload, port=args.port, on_status=print)
    except Exception as e:  # noqa: BLE001 —— CLI 只需要打印错误并以非零退出
        print(f"ERROR: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
