#!/usr/bin/env python3
"""
完赛证书批量生成工具
用法:
  python3 generate_certs.py data.csv        # 批量生成证书
  python3 generate_certs.py --sample        # 生成示例 CSV 模板
"""

import csv
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template", "2026.jpg")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# 文字颜色
TEXT_COLOR = (0, 0, 0)

# 字段定义: (csv列名, y坐标, x_start, x_end, 字号, 固定值或None)
# 固定值字段不从CSV读取，直接写入固定文字
FIELDS = [
    # 团队信息
    ("团队名称",  1044,  747, 2196, 80, None),
    ("团队口号",  1274,  240, 2196, 70, None),
    # 成员（第1行3列）
    ("成员1",     1572,  763, 1157, 60, None),
    ("成员2",     1572, 1278, 1672, 60, None),
    ("成员3",     1572, 1793, 2187, 60, None),
    # 成员（第2行4列）
    ("成员4",     1782,  253,  647, 60, None),
    ("成员5",     1782,  766, 1160, 60, None),
    ("成员6",     1782, 1280, 1674, 60, None),
    ("成员7",     1782, 1793, 2187, 60, None),
    # 棒次数据（每行: 棒次固定值 | 圈数 | 距离 | 配速）
    (None,        2442,  253,  647, 60, "1"),   # 棒次1固定
    ("棒1圈数",   2442,  766, 1160, 60, None),
    ("棒1距离",   2442, 1280, 1674, 60, None),
    ("棒1配速",   2442, 1793, 2187, 60, None),
    (None,        2647,  253,  647, 60, "2"),   # 棒次2固定
    ("棒2圈数",   2647,  766, 1160, 60, None),
    ("棒2距离",   2647, 1280, 1674, 60, None),
    ("棒2配速",   2647, 1793, 2187, 60, None),
    (None,        2852,  253,  647, 60, "3"),   # 棒次3固定
    ("棒3圈数",   2852,  766, 1160, 60, None),
    ("棒3距离",   2852, 1280, 1674, 60, None),
    ("棒3配速",   2852, 1793, 2187, 60, None),
    # 总计（右侧有固定标签文字，x范围限制在标签左侧）
    ("总圈数",    3162,  685,  990, 60, None),
    ("总距离",    3162, 1130, 1490, 60, None),
    ("平均配速",  3162, 1628, 2080, 60, None),
]

# CSV 中所有需要填写的列（固定值字段不在CSV中）
CSV_COLUMNS = [f[0] for f in FIELDS if f[0] is not None]

# 文字在划线上方的偏移量（像素）
TEXT_Y_OFFSET = 38
TEXT_Y_OFFSET_EXTRA = 28  # 成员/棒次/总计字段下移10px（贴近横线）


def find_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def find_bold_font(size: int) -> ImageFont.FreeTypeFont:
    """查找中文粗体字体，找不到则降级为普通字体。"""
    bold_candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in bold_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return find_font(size)


def draw_field(draw: ImageDraw.ImageDraw, text: str, x1: int, x2: int, y: int, font: ImageFont.FreeTypeFont, y_offset: int = TEXT_Y_OFFSET):
    """在划线区域内居中绘制文字，文字位于划线上方。"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    cx = (x1 + x2) // 2
    tx = cx - text_w // 2
    ty = y - y_offset - text_h
    draw.text((tx, ty), text, font=font, fill=TEXT_COLOR)


def generate_cert(data: dict, index: int = 1):
    """根据 data 字典生成一张证书并保存到 output/ 目录。"""
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 预加载不同字号的字体（避免重复创建）
    font_cache: dict[int, ImageFont.FreeTypeFont] = {}

    bold_font_cache: dict[int, ImageFont.FreeTypeFont] = {}

    for col_name, y, x1, x2, size, fixed_val in FIELDS:
        # 团队名称使用粗体
        if col_name == "团队名称":
            if size not in bold_font_cache:
                bold_font_cache[size] = find_bold_font(size)
            font = bold_font_cache[size]
        else:
            if size not in font_cache:
                font_cache[size] = find_font(size)
            font = font_cache[size]

        if fixed_val is not None:
            text = fixed_val
        else:
            text = data.get(col_name, "").strip()
            if not text:
                continue
            # 距离字段去掉 km/公里 单位后缀（模板中已印有单位）
            if col_name and "距离" in col_name:
                text = re.sub(r'\s*(km|公里|KM|Km)\s*$', '', text, flags=re.IGNORECASE).strip()

        # 团队名称/口号保持原偏移，其余字段下移10px（贴近横线）
        y_off = TEXT_Y_OFFSET if col_name in ("团队名称", "团队口号") else TEXT_Y_OFFSET_EXTRA
        draw_field(draw, text, x1, x2, y, font, y_offset=y_off)

    team_name = data.get("团队名称", f"证书{index}").strip() or f"证书{index}"
    # 文件名去除非法字符
    safe_name = "".join(c for c in team_name if c not in r'\/:*?"<>|')
    out_path = os.path.join(OUTPUT_DIR, f"{safe_name}.jpg")
    img.save(out_path, "JPEG", quality=95)
    print(f"  已生成: {out_path}")


def generate_sample_csv(path: str = "sample.csv"):
    """生成示例 CSV 文件。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerow({
            "团队名称": "飞翔队",
            "团队口号": "向前奔跑 永不止步",
            "成员1": "张三",
            "成员2": "李四",
            "成员3": "王五",
            "成员4": "赵六",
            "成员5": "钱七",
            "成员6": "孙八",
            "成员7": "周九",
            "棒1圈数": "15",
            "棒1距离": "6.2km",
            "棒1配速": "5'30\"",
            "棒2圈数": "18",
            "棒2距离": "7.4km",
            "棒2配速": "5'15\"",
            "棒3圈数": "12",
            "棒3距离": "4.8km",
            "棒3配速": "5'45\"",
            "总圈数": "45",
            "总距离": "18.4km",
            "平均配速": "5'30\"",
        })
    print(f"示例 CSV 已生成: {path}")
    print(f"CSV 列顺序: {', '.join(CSV_COLUMNS)}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print(f"CSV 列: {', '.join(CSV_COLUMNS)}")
        sys.exit(0)

    if sys.argv[1] == "--sample":
        out = sys.argv[2] if len(sys.argv) > 2 else "sample.csv"
        generate_sample_csv(out)
        return

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"错误: 找不到文件 {csv_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(TEMPLATE_PATH):
        print(f"错误: 找不到模板 {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"读取到 {len(rows)} 条记录，开始生成证书...")
    for i, row in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {row.get('团队名称', '未命名')}")
        generate_cert(row, index=i)

    print(f"\n完成！证书已保存至 {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
