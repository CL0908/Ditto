/* app_local_audio.c —— T5AI 离线本地告警语音播放（命令表 + 分块播放）
 *
 * 见 app_local_audio.h。与 Mac 侧 t5_bridge.py 的协议:UART0 收一行文本 clip 键。
 */
#include "app_local_audio.h"
#include <string.h>
#include "tal_log.h"

/* 播放分块大小(字节)。16kHz/16bit/mono 下 640B = 20ms 一帧,稳妥喂给编解码器。 */
#define PCM_CHUNK 640

/* clip 键 → PCM 数组 的命令表。多一段音频就加一行(并在 .h 声明 + 加 audio_data_<key>.c)。 */
typedef struct {
    const char          *key;
    const unsigned char *pcm;
    const unsigned int  *len;
} local_clip_t;

static const local_clip_t s_clips[] = {
    { "spying",            g_pcm_spying,            &g_pcm_spying_len            },
    { "malicious_control", g_pcm_malicious_control, &g_pcm_malicious_control_len },
    /* 追加真人声后在此加行,例如:
     * { "dos",             g_pcm_dos,             &g_pcm_dos_len             },
     * { "evidence_sealed", g_pcm_evidence_sealed, &g_pcm_evidence_sealed_len }, */
};
#define CLIP_COUNT (sizeof(s_clips) / sizeof(s_clips[0]))


OPERATE_RET app_local_audio_init(TDL_AUDIO_HANDLE_T *out_handle)
{
    TDL_AUDIO_HANDLE_T h = NULL;
    OPERATE_RET rt = tdl_audio_find(AUDIO_CODEC_NAME, &h);   /* 默认 "audio_codec" */
    if (rt != OPRT_OK || h == NULL) {
        TAL_PR_ERR("local_audio: find audio_codec failed rt=%d", rt);
        return OPRT_COM_ERROR;
    }
    rt = tdl_audio_open(h, NULL);   /* NULL mic-cb = 仅播放 */
    if (rt != OPRT_OK) {
        TAL_PR_ERR("local_audio: open failed rt=%d", rt);
        return rt;
    }
    tdl_audio_volume_set(h, 80);
    if (out_handle) {
        *out_handle = h;
    }
    TAL_PR_INFO("local_audio: ready, %d clips embedded", (int)CLIP_COUNT);
    return OPRT_OK;
}


static BOOL_T play_pcm(TDL_AUDIO_HANDLE_T audio,
                       const unsigned char *pcm, unsigned int len)
{
    if (audio == NULL || pcm == NULL || len == 0) {
        return FALSE;
    }
    /* 分块喂,避免一次性大 buffer;末块可小于 PCM_CHUNK */
    unsigned int off = 0;
    while (off < len) {
        unsigned int n = (len - off > PCM_CHUNK) ? PCM_CHUNK : (len - off);
        if (tdl_audio_play(audio, (uint8_t *)(pcm + off), n) != OPRT_OK) {
            TAL_PR_WARN("local_audio: play chunk failed at %u", off);
            return FALSE;
        }
        off += n;
    }
    return TRUE;
}


BOOL_T app_local_cmd_dispatch(const char *line, TDL_AUDIO_HANDLE_T audio)
{
    if (line == NULL) {
        return FALSE;
    }
    /* 兼容 "PLAY:spying" 与 "spying" 两种;去掉可选前缀和首尾空白 */
    const char *key = line;
    if (strncmp(key, "PLAY:", 5) == 0) {
        key += 5;
    }
    while (*key == ' ' || *key == '\t') {
        key++;
    }

    for (unsigned int i = 0; i < CLIP_COUNT; i++) {
        if (strcmp(key, s_clips[i].key) == 0) {
            TAL_PR_INFO("local_audio: play clip '%s' (%u B)", key, *s_clips[i].len);
            return play_pcm(audio, s_clips[i].pcm, *s_clips[i].len);
        }
    }
    TAL_PR_INFO("local_audio: no clip for '%s' (ignored)", key);
    return FALSE;
}
