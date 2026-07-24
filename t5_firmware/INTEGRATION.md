# T5AI-CORE 板上真人声播报 —— 固件集成手册（B1）

目标:UART0 收到一行 clip 键(来自 Mac 的 `t5_bridge.py`)→ T5AI-CORE 用**自己的喇叭**
播放烧进固件的 Artlist 真人声(离线,不联云)。基于 TuyaOpen `apps/tuya.ai/your_serial_chat_bot`
改造(它已实现 UART0@115200/8N1 收文本,只需改 2 处 + 加 3 个文件)。

---

## 一、把这些文件放进 app

TuyaOpen 里进入 `apps/tuya.ai/your_serial_chat_bot/`,拷入本目录下的文件:

```
cp t5_firmware/app_local_audio.c            <SDK>/apps/tuya.ai/your_serial_chat_bot/src/
cp t5_firmware/audio_data_spying.c          <SDK>/apps/tuya.ai/your_serial_chat_bot/src/
cp t5_firmware/audio_data_malicious_control.c <SDK>/apps/tuya.ai/your_serial_chat_bot/src/
cp t5_firmware/app_local_audio.h            <SDK>/apps/tuya.ai/your_serial_chat_bot/include/
```

> `CMakeLists.txt` 用的是 `aux_source_directory(${APP_PATH}/src APP_SRCS)`,
> **放进 `src/` 的 .c 会自动编译,无需改 CMakeLists**;头文件目录 `include/` 已在 include 路径里。

## 二、改 `src/app_chat_bot.c`（2 处插入 + 1 个 include）

**① 文件顶部 include 区**加一行:
```c
#include "app_local_audio.h"
```

**② 加一个文件级全局句柄**(放在其它 `static` 变量附近):
```c
static TDL_AUDIO_HANDLE_T sg_audio = NULL;
```

**③ 在 `app_chat_bot_init()` 里**,`tal_uart_init(USER_CHAT_UART, &uart_cfg)` 成功之后、
创建 `uart_text_task` 线程之前,加一行初始化音频:
```c
    TUYA_CALL_ERR_RETURN(tal_uart_init(USER_CHAT_UART, &uart_cfg));
    app_local_audio_init(&sg_audio);        // ← 新增:打开板载喇叭 audio_codec
```

**④ 在 `__uart_text_scan_task()` 的 `if (need_upload) { ... }` 分支里**,
把原来的上传云端那一行换成本地派发(离线):
```c
        if (need_upload) {
            // ── 原来是: ai_agent_send_text(sg_serial_text_buf);
            app_local_cmd_dispatch(sg_serial_text_buf, sg_audio);   // ← 改成本地播放
            tal_uart_write(USER_CHAT_UART, (const uint8_t *)"ok:", 3);
            tal_uart_write(USER_CHAT_UART, (const uint8_t *)sg_serial_text_buf, text_len);
            tal_uart_write(USER_CHAT_UART, (const uint8_t *)"\r\n", 2);
            text_len = 0; need_upload = false;
        }
```
> 若想保留云端聊天能力,不删 `ai_agent_send_text`,而是:命中本地命令表就播、
> 未命中再走云端。`app_local_cmd_dispatch` 返回 `FALSE` 即未命中,可据此回退。

## 三、板级配置（无需额外开音频）

`boards/T5AI/TUYA_T5AI_CORE/Kconfig` 已 `select ENABLE_AUDIO_CODECS`(+AEC),
喇叭注册在 `tuya_t5ai_core.c::__board_register_audio()`(设备名 `"audio_codec"`,
16kHz/16bit/mono,喇叭使能脚 GPIO39)。**选 T5AI-CORE 板即自动带上 tdl_audio,不用改配置。**

## 四、构建 / 烧录 / 授权

```bash
cd <SDK>                       # TuyaOpen 根目录(IDE 里的 SDK 路径)
. ./export.sh                  # 激活 tos.py(每开新终端都要)
cd apps/tuya.ai/your_serial_chat_bot
tos.py config choice           # 选 TUYA_T5AI_CORE
tos.py build                   # → .build/bin/*_QIO_*.bin
tos.py flash                   # 选“烧录口”(两个串口里非日志口)
tos.py monitor -b 115200       # 看日志: "local_audio: ready, 2 clips embedded"
```

**授权码**(离线播放理论上不强依赖,但你已有码,照写更稳):
Chrome 打开 **https://tuyaopen.ai/tools/** →「连接授权串口」→「TuyaOpen 授权码写入」标签 →
填 UUID + AuthKey(取自你的 xlsx,已确认 2 组)→「写入授权」。

## 五、联调（与 Mac）

烧好后,板子 UART0 就是命令入口。Mac 侧:
```bash
cd ditto-repo
T5_PORT=/dev/cu.usbmodem5AAE1667591 .venv/bin/python t5_bridge.py say spying
# → T5 喇叭念出 Artlist 真人声「注意,温控器…疑似被植入监听…」
```
`demo.py` 跑时,每个异常会自动 `t5.speak_anomaly(clip_key)` 发命令,T5 亲口播报。
`t5_bridge.py::_frame()` 已改为发**一行纯 clip 键 + 换行**,与固件命令表严格对齐。

---

## 音频清单(已烧入 = 命令表里的)

| clip 键 | 音源 | 时长 | 文件 |
|---|---|---|---|
| `spying`            | **Artlist 真人声** | 10.7s | audio_data_spying.c |
| `malicious_control` | **Artlist 真人声** | 8.9s  | audio_data_malicious_control.c |

> 其余(`dos` / `evidence_sealed` / `normal` / `offline`)Artlist 免费额度用尽未渲染。
> 补法:在**图形登录终端**里 `say -v Ting-Ting -o x.aiff "文案"`(headless 沙箱里 say 出不了声),
> 或开 Artlist 订阅重渲染 → `python tools/wav_to_pcm_header.py x.aiff dos` →
> 新增 `audio_data_dos.c` + 在 `app_local_audio.h` 声明 + `app_local_audio.c::s_clips[]` 加一行 → 重 build/flash。
> 未烧入的 clip:T5 收到会日志 "no clip for 'xxx' (ignored)" 静默跳过,Mac `say` 兜底仍出声。

## 备选方案(若 tdl_audio 链接不通)

`your_chat_bot` 用的是高层 `ai_audio_play_data(AI_AUDIO_CODEC_MP3, mp3_bytes, len)`(直接吃 MP3,
更省 flash)。若 tdl_audio 路线在你的 SDK 版本有问题,可改用它:把 Artlist 的 `.mp3` 原样 `xxd -i`
成 C 数组,`app_local_cmd_dispatch` 里改调 `ai_audio_play_data(AI_AUDIO_CODEC_MP3, ...)`,
并在 app config 打开 `ENABLE_COMP_AI_AUDIO` / `ENABLE_MEDIA`。
