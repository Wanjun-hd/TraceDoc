from __future__ import annotations

import math
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "TraceDoc_动态演示视频.mp4"
W, H = 720, 1280
FPS = 24
DURATION = 44
TOTAL = FPS * DURATION

FONT = Path(r"C:\Windows\Fonts\simhei.ttf")
FONT_REG = Path(r"C:\Windows\Fonts\Deng.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT if bold else FONT_REG
    return ImageFont.truetype(str(path), size=size)


F_TITLE = font(54, True)
F_H1 = font(42, True)
F_H2 = font(32, True)
F_BODY = font(25)
F_SMALL = font(20)
F_TINY = font(16)


def dataset_count(name: str) -> int:
    p = ROOT / "data" / name
    if not p.is_file():
        return 0
    return sum(1 for line in p.open("r", encoding="utf-8") if line.strip())


def kb_count() -> int:
    p = ROOT / "核心三库"
    return len(list(p.glob("*.txt"))) if p.is_dir() else 0


STATS = {
    "samples": dataset_count("dataset_samples.jsonl"),
    "pseudo": dataset_count("pseudo_labeled_pairs.jsonl"),
    "pubmed": dataset_count("pubmed_literature.jsonl"),
    "kb": kb_count(),
}


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def draw_bg(draw: ImageDraw.ImageDraw, frame: int) -> Image.Image:
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    pulse = 0.5 + 0.5 * math.sin(frame / 45)
    r = np.broadcast_to(8 + 12 * y + 4 * pulse, (H, W)).astype(np.uint8)
    g = np.broadcast_to(20 + 34 * y + 10 * x, (H, W)).astype(np.uint8)
    b = np.broadcast_to(42 + 86 * (1 - y) + 18 * pulse, (H, W)).astype(np.uint8)
    bg = np.dstack([r, g, b])
    img = Image.fromarray(bg, "RGB")
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(22):
        px = (i * 89 + frame * (0.7 + i % 3)) % (W + 160) - 80
        py = (i * 137 + frame * (0.35 + i % 5 * 0.08)) % (H + 160) - 80
        radius = 1 + (i % 4)
        d.ellipse((px - radius, py - radius, px + radius, py + radius), fill=(74, 212, 255, 70))
    for i in range(9):
        y0 = 80 + i * 130 + math.sin(frame / 40 + i) * 18
        d.line((30, y0, W - 30, y0 + math.sin(frame / 33 + i) * 22), fill=(92, 199, 255, 22), width=1)
    return img


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, fnt, fill=(238, 248, 255, 255), anchor=None):
    draw.text(xy, s, font=fnt, fill=fill, anchor=anchor)


def rounded(draw, box, fill, outline=None, width=1, radius=22):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap_text(s: str, max_chars: int) -> list[str]:
    lines, cur = [], ""
    for ch in s:
        cur += ch
        if len(cur) >= max_chars:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return lines


def draw_phone(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str):
    rounded(draw, (x, y, x + w, y + h), (238, 247, 255, 245), (116, 199, 255, 160), 2, 34)
    rounded(draw, (x + 18, y + 18, x + w - 18, y + 62), (20, 48, 80, 255), radius=18)
    text(draw, (x + w // 2, y + 40), title, F_SMALL, (235, 248, 255, 255), "mm")
    draw.ellipse((x + w // 2 - 32, y + 24, x + w // 2 + 32, y + 30), fill=(210, 230, 244, 70))


def draw_badge(draw, x, y, label, value, color=(71, 211, 255)):
    rounded(draw, (x, y, x + 190, y + 94), (8, 26, 48, 210), (*color, 150), 2, 20)
    text(draw, (x + 18, y + 18), str(value), F_H2, (255, 255, 255, 255))
    text(draw, (x + 18, y + 58), label, F_TINY, (190, 220, 238, 255))


def scene_intro(draw, frame, local):
    t = ease(local / (FPS * 5))
    text(draw, (54, int(190 - 50 * (1 - t))), "TraceDoc", F_TITLE, (255, 255, 255, 255))
    text(draw, (54, 260), "面向低资源医疗的少样本可溯源", F_H2, (166, 226, 255, 255))
    text(draw, (54, 304), "临床推理大模型系统", F_H2, (255, 255, 255, 255))
    rounded(draw, (54, 390, 666, 560), (6, 28, 54, 210), (96, 214, 255, 150), 2, 28)
    bullets = ["本地 RAG + RAGFlow 双后端", "指南 / 文献 / 病历三级证据链", "校园网可访问，一键演示"]
    for i, b in enumerate(bullets):
        alpha = int(255 * ease((local / FPS - 1.0 - i * 0.45) / 0.6))
        text(draw, (86, 424 + i * 42), "● " + b, F_BODY, (232, 248, 255, alpha))
    draw.line((64, 665, 656, 665), fill=(90, 214, 255, int(180 * t)), width=3)
    text(draw, (360, 730), "从问诊输入到证据溯源", F_H1, (255, 255, 255, int(255 * t)), "mm")


def scene_input(draw, frame, local):
    draw_phone(draw, 78, 95, 564, 1010, "小溯医生 · 问诊工作台")
    x, y = 112, 190
    fields = [
        ("主诉", "活动后胸前区疼，还出汗"),
        ("现病史", "每次约 10 分钟，休息后缓解"),
        ("既往史", "高血压，否认药物过敏"),
        ("核心问题", "是否需要急诊？下一步检查？"),
    ]
    for i, (k, v) in enumerate(fields):
        yy = y + i * 142
        rounded(draw, (x, yy, x + 496, yy + 112), (255, 255, 255, 238), (166, 202, 224, 180), 1, 18)
        text(draw, (x + 22, yy + 18), k, F_SMALL, (40, 84, 128, 255))
        shown = v[: int(len(v) * ease((local / FPS - i * 0.4) / 1.3))]
        text(draw, (x + 22, yy + 58), shown, F_BODY, (20, 42, 68, 255))
    p = ease((local / FPS - 2.6) / 1.0)
    rounded(draw, (155, 820, 565, 900), (28, 118, 226, int(255 * p)), (100, 205, 255, int(200 * p)), 2, 38)
    text(draw, (360, 860), "开始分析", F_H2, (255, 255, 255, int(255 * p)), "mm")


def scene_pipeline(draw, frame, local):
    text(draw, (54, 110), "后端推理流水线", F_H1)
    steps = [
        ("01", "症状归一化", "同义词、否定词、自然问法识别"),
        ("02", "本地 RAG 检索", "BM25 + 稀疏向量融合召回"),
        ("03", "证据重排", "指南 / PubMed / 病历分层"),
        ("04", "结构化输出", "诊断、鉴别、风险、检查、方案"),
    ]
    for i, (num, title, desc) in enumerate(steps):
        y = 220 + i * 185
        a = ease((local / FPS - i * 0.45) / 0.7)
        x = int(44 + (1 - a) * 120)
        rounded(draw, (x, y, 676, y + 128), (8, 31, 58, int(220 * a)), (86, 211, 255, int(180 * a)), 2, 24)
        text(draw, (x + 26, y + 28), num, F_H1, (105, 231, 255, int(255 * a)))
        text(draw, (x + 120, y + 26), title, F_H2, (255, 255, 255, int(255 * a)))
        text(draw, (x + 120, y + 74), desc, F_SMALL, (190, 225, 240, int(255 * a)))
        if i < 3:
            draw.line((360, y + 132, 360, y + 168), fill=(95, 218, 255, int(170 * a)), width=3)


def scene_evidence(draw, frame, local):
    text(draw, (54, 94), "Level 3 · 证据原文", F_H1)
    cards = [
        ("指南级", "临床指南条目", "胸痛持续 >20 分钟、冷汗或放射痛，需急诊评估。", (88, 205, 255)),
        ("文献级", "PubMed · PMID:28987131", "Chest pain pathways in clinical care. Medical Journal of Australia, 2017.", (115, 255, 190)),
        ("病历级", "脱敏病例 #C008", "活动后胸前区压榨样疼痛，心电图 ST-T 改变。", (255, 206, 116)),
    ]
    for i, (lvl, title, desc, col) in enumerate(cards):
        y = 195 + i * 270
        a = ease((local / FPS - i * 0.55) / 0.7)
        rounded(draw, (42, y, 678, y + 218), (240, 249, 255, int(238 * a)), (*col, int(170 * a)), 2, 26)
        text(draw, (74, y + 26), lvl, F_H2, (26, 66, 108, int(255 * a)))
        text(draw, (74, y + 75), title, F_BODY, (22, 44, 70, int(255 * a)))
        for j, line in enumerate(wrap_text(desc, 23)[:3]):
            text(draw, (74, y + 122 + j * 32), line, F_SMALL, (48, 76, 98, int(255 * a)))
        rounded(draw, (510, y + 26, 638, y + 62), (*col, int(230 * a)), radius=18)
        text(draw, (574, y + 44), "可追溯", F_TINY, (6, 28, 45, int(255 * a)), "mm")


def scene_stats(draw, frame, local):
    text(draw, (54, 110), "数据库与工程化后端", F_H1)
    draw_badge(draw, 54, 210, "知识库文件", STATS["kb"])
    draw_badge(draw, 266, 210, "样本集", STATS["samples"])
    draw_badge(draw, 478, 210, "PubMed文献", STATS["pubmed"])
    draw_badge(draw, 54, 324, "伪标签对", STATS["pseudo"])
    items = [
        "SQLite：患者记录 / 推理历史 / 事件日志",
        "API：检索、分析、统计、自检、备份、导出",
        "脚本：自动生成知识库、抓取 PubMed、冒烟测试",
        "RAGFlow 不可用时自动回退本地 RAG",
    ]
    for i, item in enumerate(items):
        y = 500 + i * 92
        a = ease((local / FPS - i * 0.35) / 0.65)
        rounded(draw, (54, y, 666, y + 66), (7, 30, 55, int(210 * a)), (94, 212, 255, int(120 * a)), 1, 18)
        text(draw, (82, y + 20), "✓ " + item, F_SMALL, (232, 248, 255, int(255 * a)))


def scene_lan(draw, frame, local):
    text(draw, (54, 120), "同校园网 · 直接访问", F_H1)
    rounded(draw, (72, 260, 648, 520), (238, 248, 255, 240), (92, 216, 255, 180), 2, 26)
    text(draw, (105, 310), "前端", F_H2, (22, 60, 104, 255))
    text(draw, (105, 368), "http://172.28.93.56:8501", F_BODY, (15, 77, 138, 255))
    text(draw, (105, 430), "后端", F_H2, (22, 60, 104, 255))
    text(draw, (105, 488), "http://172.28.93.56:8000", F_BODY, (15, 77, 138, 255))
    for i in range(4):
        cx, cy = 140 + i * 145, 720 + math.sin(local / 18 + i) * 12
        draw.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), fill=(80, 213, 255, 70), outline=(130, 230, 255, 180), width=2)
        text(draw, (cx, cy), ["PC", "Pad", "手机", "评委"][i], F_TINY, (245, 252, 255, 255), "mm")
        if i > 0:
            draw.line((cx - 102, cy, cx - 44, cy), fill=(110, 220, 255, 150), width=2)


def scene_end(draw, frame, local):
    text(draw, (360, 340), "TraceDoc", F_TITLE, (255, 255, 255, 255), "mm")
    text(draw, (360, 420), "让每一次辅助诊断都有证据可追溯", F_H2, (164, 229, 255, 255), "mm")
    rounded(draw, (100, 560, 620, 715), (238, 248, 255, 235), (100, 222, 255, 160), 2, 28)
    text(draw, (360, 610), "本地RAG · PubMed文献 · 三级证据链", F_BODY, (24, 58, 92, 255), "mm")
    text(draw, (360, 668), "校园网演示地址已启动", F_BODY, (24, 88, 138, 255), "mm")
    text(draw, (360, 930), "2026 中国大学生计算机设计大赛", F_SMALL, (200, 230, 245, 220), "mm")


SCENES = [
    (0, 6, scene_intro),
    (6, 13, scene_input),
    (13, 21, scene_pipeline),
    (21, 30, scene_evidence),
    (30, 37, scene_stats),
    (37, 41, scene_lan),
    (41, 44, scene_end),
]


def draw_frame(frame: int) -> Image.Image:
    img = draw_bg(None, frame)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    sec = frame / FPS
    for start, end, fn in SCENES:
        if start <= sec < end:
            fn(d, frame, int((sec - start) * FPS))
            break
    d.rectangle((0, H - 8, int(W * frame / max(1, TOTAL - 1)), H), fill=(87, 223, 255, 210))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def main() -> None:
    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = ""

    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            f"{W}x{H}",
            "-pix_fmt",
            "rgb24",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-vcodec",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "30",
            str(OUT),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin is not None
        for frame in range(TOTAL):
            img = draw_frame(frame)
            proc.stdin.write(np.asarray(img, dtype=np.uint8).tobytes())
            if frame % 120 == 0:
                print(f"[FRAME] {frame}/{TOTAL}")
        proc.stdin.close()
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg failed with code {code}")
    else:
        import cv2

        writer = cv2.VideoWriter(str(OUT), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
        if not writer.isOpened():
            raise RuntimeError("OpenCV VideoWriter could not open output file")
        for frame in range(TOTAL):
            img = draw_frame(frame)
            arr = np.asarray(img, dtype=np.uint8)
            writer.write(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
            if frame % 120 == 0:
                print(f"[FRAME] {frame}/{TOTAL}")
        writer.release()
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()
