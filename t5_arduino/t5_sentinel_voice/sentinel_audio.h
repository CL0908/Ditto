/* sentinel_audio.h —— T5AI Sentinel 板载真人声 PCM 声明
 * 16kHz/16bit/mono 裸 PCM，由 tools/wav_to_pcm_header.py 从 Artlist 真人声生成。
 */
#ifndef SENTINEL_AUDIO_H
#define SENTINEL_AUDIO_H

#ifdef __cplusplus
extern "C" {
#endif

extern const unsigned char g_pcm_spying[];
extern const unsigned int  g_pcm_spying_len;
extern const unsigned char g_pcm_malicious_control[];
extern const unsigned int  g_pcm_malicious_control_len;

#ifdef __cplusplus
}
#endif

#endif /* SENTINEL_AUDIO_H */
