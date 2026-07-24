/* app_local_audio.h —— T5AI 离线本地告警语音播放
 *
 * UART0 收到 clip 键(来自 Mac 的 t5_bridge.py)→ 查表 → tdl_audio_play 播放
 * 烧进固件的 16kHz/16bit/mono 裸 PCM。纯离线,不联云。
 *
 * clip 键与 Mac 侧 explain.clip_key() / voice_alert 完全对齐:
 *   spying / malicious_control / dos / evidence_sealed / normal / offline
 * 每个 clip 的 PCM 数组由 tools/wav_to_pcm_header.py 生成为 audio_data_<key>.c。
 */
#ifndef APP_LOCAL_AUDIO_H
#define APP_LOCAL_AUDIO_H

#include "tuya_cloud_types.h"
#include "tdl_audio_manage.h"

#ifdef __cplusplus
extern "C" {
#endif

/* 已烧入的真人声/占位 PCM(每多一段音频,加一个 audio_data_<key>.c 并在此声明) */
extern const unsigned char g_pcm_spying[];
extern const unsigned int  g_pcm_spying_len;
extern const unsigned char g_pcm_malicious_control[];
extern const unsigned int  g_pcm_malicious_control_len;

/* 初始化:找到并打开板载 "audio_codec"。成功返回 OPRT_OK。可在 app_chat_bot_init 里调。
 * 若传入的 handle 指针非空,会把打开的句柄回填,供后续直接复用。 */
OPERATE_RET app_local_audio_init(TDL_AUDIO_HANDLE_T *out_handle);

/* 派发一行 UART 文本命令。支持 "spying" 或 "PLAY:spying" 两种格式。
 * 命中命令表 → 播放对应 PCM,返回 TRUE;未命中 → 不播,返回 FALSE(不阻塞、不报错)。 */
BOOL_T app_local_cmd_dispatch(const char *line, TDL_AUDIO_HANDLE_T audio);

#ifdef __cplusplus
}
#endif

#endif /* APP_LOCAL_AUDIO_H */
