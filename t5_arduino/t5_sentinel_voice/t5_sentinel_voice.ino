/*
 * T5 Sentinel Voice —— T5AI-CORE 板载真人声告警(Arduino / arduino-tuyaopen)
 *
 * 串口(UART0 @115200)收到一行 clip 键 → 板载喇叭播放烧进固件的 Artlist 真人声 PCM。
 * clip 键与 Mac 侧 ditto-repo/t5_bridge.py / explain.clip_key() 完全一致。
 *
 * 协议:一行纯文本 clip 键 + 换行,如 "spying\n" / "malicious_control\n"。
 * Mac:  .venv/bin/python t5_bridge.py say spying
 *
 * 硬件:T5AI-CORE DevKit + 板载喇叭(GPIO39 使能),arduino-tuyaopen 的 Audio 库。
 */
#include "Audio.h"
#include "sentinel_audio.h"

Audio audio;
String line;

static void playClip(const String &key) {
  const uint8_t *pcm = nullptr;
  uint32_t len = 0;
  if (key == "spying") {
    pcm = g_pcm_spying;  len = g_pcm_spying_len;
  } else if (key == "malicious_control") {
    pcm = g_pcm_malicious_control;  len = g_pcm_malicious_control_len;
  } else {
    Serial.print("no clip: "); Serial.println(key);
    return;
  }
  Serial.print("playing: "); Serial.println(key);
  audio.play((uint8_t *)pcm, len);   // 16k/16bit/mono 裸 PCM
}

void setup() {
  Serial.begin(115200);
  AudioConfig cfg;
  cfg.micBufferSize = 0;   // 只播放,不录音
  cfg.volume = 80;
  audio.begin(&cfg);
  Serial.println("T5 Sentinel Voice ready. Send a clip key + newline (e.g. spying).");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      line.trim();
      if (line.length() > 0) playClip(line);
      line = "";
    } else if (line.length() < 64) {
      line += c;
    }
  }
}
