/*
 * T5AI-Core minimal audio self-test.
 *
 * This deliberately bypasses Arduino-TuyaOpen's Audio::begin(): in core 1.2.5
 * that helper registers a second codec without assigning the speaker-enable
 * pin.  The TUYA_T5AI_CORE board registration below is the source of truth:
 * GPIO39, active-low, 16 kHz, signed 16-bit little-endian, mono PCM.
 */
#include <Arduino.h>
#include <stdarg.h>
#include <stdio.h>

extern "C" {
#include "board_com_api.h"
#include "tdl_audio_manage.h"
#include "tuya_kconfig.h"
}

#define TONE_SAMPLE_RATE_HZ 16000U
#define TONE_FREQUENCY_HZ   440U
#define TONE_DURATION_MS    2000U
#define TONE_REPEAT_MS      5000U
#define PCM_FRAME_MS        20U
#define PCM_FRAME_SAMPLES   ((TONE_SAMPLE_RATE_HZ * PCM_FRAME_MS) / 1000U)
#define TONE_AMPLITUDE      12000
#define OUTPUT_VOLUME       95U

static TDL_AUDIO_HANDLE_T s_audio = nullptr;
static bool s_audio_ready = false;

static void serialLog(const char *format, ...)
{
  char line[256];
  va_list args;
  va_start(args, format);
  vsnprintf(line, sizeof(line), format, args);
  va_end(args);
  Serial.print(line);
}

static void fillTrianglePcm(int16_t *samples, uint32_t count, uint32_t *phase)
{
  const uint32_t phaseStep =
      (uint32_t)(((uint64_t)TONE_FREQUENCY_HZ << 32) / TONE_SAMPLE_RATE_HZ);

  for (uint32_t i = 0; i < count; ++i) {
    const uint32_t quadrant = *phase >> 30;
    const uint32_t offset = (*phase >> 15) & 0x7fffU;
    int32_t triangle;

    if (quadrant == 0U) {
      triangle = (int32_t)offset;
    } else if (quadrant == 1U) {
      triangle = 32767 - (int32_t)offset;
    } else if (quadrant == 2U) {
      triangle = -(int32_t)offset;
    } else {
      triangle = -32767 + (int32_t)offset;
    }

    samples[i] = (int16_t)((triangle * TONE_AMPLITUDE) / 32767);
    *phase += phaseStep;
  }
}

static OPERATE_RET initAudio()
{
  TDL_AUDIO_INFO_T info = {};

  Serial.println("[AUDIO_TEST] target=TUYA_T5AI_CORE");
  Serial.println("[AUDIO_TEST] expected amp GPIO=39 active=LOW");

  OPERATE_RET rt = board_register_hardware();
  serialLog("[AUDIO_TEST] board_register_hardware rt=%d\n", (int)rt);
  if (rt != OPRT_OK) {
    return rt;
  }

  rt = tdl_audio_find((char *)AUDIO_CODEC_NAME, &s_audio);
  serialLog("[AUDIO_TEST] tdl_audio_find(%s) rt=%d handle=%p\n",
            AUDIO_CODEC_NAME, (int)rt, s_audio);
  if (rt != OPRT_OK) {
    return rt;
  }

  rt = tdl_audio_get_info(s_audio, &info);
  serialLog("[AUDIO_TEST] get_info rt=%d rate=%u channels=%u bits=%u "
            "frame_ms=%u frame_bytes=%u\n",
            (int)rt, info.sample_rate, info.sample_ch_num,
            info.sample_bits, info.sample_tm_ms, info.frame_size);
  if (rt != OPRT_OK) {
    return rt;
  }

  const uint32_t expectedFrameBytes = PCM_FRAME_SAMPLES * sizeof(int16_t);
  if (info.sample_rate != TONE_SAMPLE_RATE_HZ || info.sample_ch_num != 1U ||
      info.sample_bits != 16U || info.sample_tm_ms != PCM_FRAME_MS ||
      info.frame_size != expectedFrameBytes) {
    serialLog("[AUDIO_TEST] FORMAT_MISMATCH expected=16000/1/16/20/%u; "
              "refusing playback\n", expectedFrameBytes);
    return OPRT_INVALID_PARM;
  }

  rt = tdl_audio_open(s_audio, nullptr);
  serialLog("[AUDIO_TEST] tdl_audio_open rt=%d\n", (int)rt);
  if (rt != OPRT_OK) {
    return rt;
  }

  rt = tdl_audio_volume_set(s_audio, OUTPUT_VOLUME);
  serialLog("[AUDIO_TEST] volume=%u rt=%d\n", OUTPUT_VOLUME, (int)rt);
  if (rt != OPRT_OK) {
    return rt;
  }

  delay(300);
  return OPRT_OK;
}

static OPERATE_RET playToneOnce()
{
  static int16_t pcm[PCM_FRAME_SAMPLES];
  uint32_t phase = 0;
  const uint32_t frameCount = TONE_DURATION_MS / PCM_FRAME_MS;

  serialLog("[AUDIO_TEST] tone start hz=%u duration_ms=%u "
            "pcm=s16le/mono/%uHz bytes=%u\n",
            TONE_FREQUENCY_HZ, TONE_DURATION_MS, TONE_SAMPLE_RATE_HZ,
            frameCount * (uint32_t)sizeof(pcm));

  for (uint32_t frame = 0; frame < frameCount; ++frame) {
    fillTrianglePcm(pcm, PCM_FRAME_SAMPLES, &phase);
    OPERATE_RET rt = tdl_audio_play(s_audio, (uint8_t *)pcm, sizeof(pcm));
    if (rt != OPRT_OK) {
      serialLog("[AUDIO_TEST] play failed frame=%u rt=%d\n", frame, (int)rt);
      return rt;
    }
  }

  Serial.println("[AUDIO_TEST] tone queued successfully");
  return OPRT_OK;
}

void setup()
{
  Serial.begin(115200);
  delay(2000);
  Serial.println();
  Serial.println("================ T5 AUDIO SELFTEST ================");

  OPERATE_RET rt = initAudio();
  serialLog("[AUDIO_TEST] init result=%d\n", (int)rt);
  s_audio_ready = (rt == OPRT_OK);
  if (!s_audio_ready) {
    Serial.println("[AUDIO_TEST] FAIL_CLOSED: playback disabled");
  }
}

void loop()
{
  if (!s_audio_ready) {
    delay(TONE_REPEAT_MS);
    return;
  }

  OPERATE_RET rt = playToneOnce();
  serialLog("[AUDIO_TEST] playback cycle result=%d\n", (int)rt);
  delay(TONE_REPEAT_MS - TONE_DURATION_MS);
}
