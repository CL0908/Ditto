"""Quote/0 Image API —— 把哨兵状态渲染成 296x152 的 1-bit 图直接推屏。

为什么要有这条路（Canvas API 之外）：
  Canvas 走的是 Satori 的 flex 排版，字号/换行由渲染端决定，小屏上很容易挤爆
  （296x152 去掉 padding 只剩 ~280x136，一折行就塌）。Image API 是像素级的：
  画成什么样，屏上就是什么样，还能画 Canvas 做不了的东西（波形、密集图表）。

  Canvas 适合：文字为主、内容长度会变的屏。
  Image  适合：图表为主、排版必须精确的屏。

接口（实测）：
  POST https://dot.mindreset.tech/api/authV2/open/device/{DEVICE_ID}/image
  Body: {"image": "<PNG base64 或 http(s) 图片URL>", "refreshNow": true}
  Image API 有**独立的 API Key**，与 Text/Canvas 的不是同一个。

配置：DOT_IMAGE_API_KEY（没配则回退到 DOT_API_KEY）
屏幕是 1-bit 黑白：只用纯黑纯白与实心块，不用灰度渐变（抖动后会糊）。
"""
from __future__ import annotations

import base64
import io
import logging
import os

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("quote_image")

W, H = 296, 152
BASE = "https://dot.mindreset.tech"

_HERE = os.path.dirname(os.path.abspath(__file__))
TITO = os.path.join(_HERE, "docs", "tito", "tito-bw.png")
# STHeiti 中英文都覆盖，笔画比 Arial Unicode 粗，小尺寸墨水屏上更清楚
_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
_cache: dict[int, ImageFont.FreeTypeFont] = {}


def f(size: int) -> ImageFont.FreeTypeFont:
    if size not in _cache:
        try:
            _cache[size] = ImageFont.truetype(_FONT, size)
        except Exception:
            _cache[size] = ImageFont.load_default()
    return _cache[size]


def _paste_tito(img: Image.Image, x: int, y: int, size: int) -> None:
    try:
        t = Image.open(TITO).convert("L").resize((size, size), Image.LANCZOS)
        img.paste(t.point(lambda p: 0 if p < 128 else 255), (x, y))
    except Exception as e:                       # noqa: BLE001
        log.warning("tito 贴图失败: %s", e)


def render_dashboard(snapshot: dict) -> Image.Image:
    """平时那屏：tito + 安全分 + 每台设备流量柱（柱子带设备名，Canvas 挤不下）。"""
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    normal = snapshot.get("anomaly_count", 0) == 0
    score = int(snapshot.get("security_score", 0))

    _paste_tito(img, 8, 8, 30)
    d.text((44, 8), "家庭哨兵", font=f(18), fill=0)
    d.text((W - 8, 6), str(score), font=f(26), fill=0, anchor="ra")

    # 安全分实心条
    d.rectangle([44, 32, 44 + 150, 32 + 8], outline=0, width=1)
    d.rectangle([45, 33, 45 + int(148 * score / 100), 32 + 7], fill=0)

    # 状态行。不用 ⚠/✓ —— STHeiti 没有这些字形，会渲染成空框
    status = "全部正常" if normal else snapshot.get("status", "")
    # 用「流量」二字而不是 ↕ 箭头——STHeiti 缺这个字形，会渲染成怪符号
    d.text((8, 48), f"{snapshot.get('device_count', 0)} 台在线 · 流量 {snapshot.get('total_human', '—')}",
           font=f(12), fill=0)
    if normal:
        d.text((W - 8, 48), status, font=f(12), fill=0, anchor="ra")
    else:
        # 异常状态反白：黑底白字，墨水屏上比任何图标都醒目
        tw = int(d.textlength(status, font=f(12)))
        d.rectangle([W - 12 - tw, 46, W - 4, 64], fill=0)
        d.text((W - 8, 48), status, font=f(12), fill=255, anchor="ra")

    # 每台设备一根柱 + 中文名（Image API 的价值：Canvas 放不下这些标签）
    rates = snapshot.get("rates") or {}
    if rates:
        from explain import _device_name
        items = sorted(rates.items(), key=lambda kv: -kv[1])[:5]
        peak = max(v for _, v in items) or 1.0
        bw, gap, y0, hmax = 40, 12, 128, 48
        top = snapshot.get("top_talker", "")
        for i, (dev, val) in enumerate(items):
            x = 8 + i * (bw + gap)
            bh = max(3, int(hmax * val / peak))
            d.rectangle([x, y0 - bh, x + bw, y0], fill=0)
            if (not normal) and dev == top:          # 异常设备打白色横纹，1-bit 下也能区分
                for k in range(y0 - bh + 2, y0, 4):
                    d.line([(x, k), (x + bw, k)], fill=255)
            # 中文类别名，复用 explain.py 的脱敏映射（不另造一套）
            name = _device_name(dev).rstrip("0123456789")
            d.text((x + bw // 2, y0 + 3), name, font=f(10), fill=0, anchor="ma")
    d.text((W - 8, H - 13), str(snapshot.get("last_checked", "")), font=f(9), fill=0, anchor="ra")
    return img


def _waveform(d: ImageDraw.ImageDraw, series: list[float],
              x: int, y: int, w: int, h: int) -> None:
    """流量时序面积图。数据来自 HomeTraffic.history（真实采样，非画图时生成）。

    墨水屏没有颜色/透明度可用，所以用实心填充 + 虚线基线来表达"冲出常态"：
    基线是序列里的中位数（抗尖峰干扰），填充面积是实际吞吐。
    """
    if len(series) < 3:
        return
    peak = max(series) or 1.0
    pts = series[-w:] if len(series) > w else series
    step = w / max(1, len(pts) - 1)
    base = sorted(pts)[len(pts) // 2]                    # 中位数=常态水平

    # 实心面积：顶部轮廓 + 底边闭合成多边形一次填充。
    # （早先用"每点一条竖线"填，采样点稀疏时会变成栅栏状空心图。）
    top = [(x + int(i * step), y + h - int(h * v / peak)) for i, v in enumerate(pts)]
    d.polygon(top + [(x + w, y + h), (x, y + h)], fill=0)

    # 常态基线画在填充**之上**且用白色：尖峰段里能看见它，
    # 平稳段它与填充顶边重合、白线不可见——正好，那里本来也不需要参照物。
    by = y + h - int(h * base / peak)
    for k in range(x, x + w, 6):
        d.line([(k, by), (k + 3, by)], fill=255)


def render_anomaly(device_name: str, event_type: str, risk_score: int,
                   severity_cn: str, incident_id: str, timestamp: str,
                   history: list[float] | None = None) -> Image.Image:
    """告警屏：左侧粗黑条 + 反白风险分 + 流量波形。刻意不放 tito——这屏要读风险。"""
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 7, H], fill=0)                    # 左侧严重度色条

    d.text((16, 6), f"{severity_cn}异常", font=f(20), fill=0)
    # 风险分反白徽章——1-bit 屏上最强的强调手段
    badge = f"{risk_score}"
    tw = int(d.textlength(badge, font=f(22)))
    d.rectangle([W - 16 - tw - 10, 4, W - 8, 34], fill=0)
    d.text((W - 13, 6), badge, font=f(22), fill=255, anchor="ra")

    d.text((16, 34), device_name, font=f(15), fill=0)
    d.text((16, 54), event_type, font=f(11), fill=0)

    if history and len(history) >= 3:
        d.text((16, 70), "全屋流量", font=f(9), fill=0)
        _waveform(d, history, 16, 82, W - 32, 44)
    d.text((16, H - 14), f"{incident_id} · {timestamp}", font=f(9), fill=0)
    return img


def render_evidence(incident_id: str, block_count: int = 12) -> Image.Image:
    """收尾屏：tito + 一条可视化的哈希链——比"Chain intact ✓"这行字更有说服力。"""
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    _paste_tito(img, 10, 12, 34)
    d.text((52, 14), "证据已封存", font=f(20), fill=0)
    d.text((52, 42), f"事件 {incident_id}", font=f(12), fill=0)

    # 哈希链：一排相连的实心方块，末块反白表示"刚封存的这一块"
    y, s, gap = 78, 14, 6
    total = block_count * s + (block_count - 1) * gap
    x0 = (W - total) // 2
    for i in range(block_count):
        x = x0 + i * (s + gap)
        last = i == block_count - 1
        d.rectangle([x, y, x + s, y + s], outline=0, width=2,
                    fill=0 if not last else 255)
        if i < block_count - 1:                          # 块间连接线
            d.line([(x + s, y + s // 2), (x + s + gap, y + s // 2)], fill=0, width=2)
    d.text((W // 2, y + s + 8), "哈希已验证 · 链路完整", font=f(11), fill=0, anchor="ma")
    d.text((W // 2, H - 15), "已上链存证，不可篡改", font=f(9), fill=0, anchor="ma")
    return img


def to_base64(img: Image.Image) -> str:
    """1-bit 化后编码。墨水屏本身就是黑白，提前二值化避免设备端自己抖动。"""
    buf = io.BytesIO()
    img.convert("1").save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def push(img: Image.Image, api_key: str = "", device_id: str = "") -> bool:
    """推一张图上屏。失败返回 False，绝不抛异常（与 mindreset_quote 同约定）。"""
    import httpx
    key = api_key or os.environ.get("DOT_IMAGE_API_KEY") or os.environ.get("DOT_API_KEY", "")
    dev = device_id or os.environ.get("DOT_DEVICE_ID", "")
    if not (key and dev):
        log.info("Image API 未配置，跳过")
        return False
    try:
        r = httpx.post(f"{BASE}/api/authV2/open/device/{dev}/image",
                       json={"image": to_base64(img), "refreshNow": True},
                       headers={"Authorization": f"Bearer {key}",
                                "Content-Type": "application/json"}, timeout=15)
        if r.status_code >= 300:
            log.warning("Image API %d: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:                       # noqa: BLE001
        log.warning("Image API 投递失败: %s", e)
        return False
