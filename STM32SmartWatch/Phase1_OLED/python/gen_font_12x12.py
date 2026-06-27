"""
Generate 12x12 Chinese character bitmaps for SSD1306 OLED.

Format: Column-major, 12 columns × 2 pages = 24 bytes per character.
  - Bytes 0..11:  upper page (rows 0-7), each byte = 8 vertical pixels, bit0=top
  - Bytes 12..23: lower page (rows 8-11), each byte = 8 vertical pixels, bit0=top

Usage:
    python gen_font_12x12.py

Update the CHARS list below with the characters you need.
"""

from PIL import Image, ImageFont, ImageDraw
import os

# Characters to generate (add more as needed)
CHARS = [
    ("xin",   "心"),
    ("lv",    "率"),
    ("bu",    "步"),
    ("wen",   "温"),
    ("du",    "度"),
    ("she",   "设"),
    ("bei",   "备"),
    ("xin2",  "信"),
    ("xi",    "息"),
    ("nian",  "年"),
    ("yue",   "月"),
    ("ri",    "日"),
    ("shi",   "湿"),
    ("yun",   "运"),
    ("dong",  "动"),
]

# Try multiple Chinese fonts, pick the best available
FONT_CANDIDATES = [
    "C:/Windows/Fonts/simhei.ttf",       # 黑体 (best for small sizes)
    "C:/Windows/Fonts/simsun.ttc",       # 宋体
    "C:/Windows/Fonts/msyh.ttc",         # 微软雅黑
    "C:/Windows/Fonts/Deng.ttf",         # 等线
    "C:/Windows/Fonts/STKAITI.TTF",      # 楷体
]

def find_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No Chinese font found in C:/Windows/Fonts/")

def gen_char_bitmap(font_path: str, char: str, size: int = 12) -> list[int]:
    """
    Render a single character and return 24 bytes of bitmap data
    in column-major SSD1306 page format.
    """
    # Create canvas (add padding for anti-aliasing buffer)
    pad = 2
    canvas_w = size + pad * 2
    canvas_h = size + pad * 2

    img = Image.new("L", (canvas_w, canvas_h), 0)
    draw = ImageDraw.Draw(img)

    # Try font sizes from small to large to find best fit
    font = ImageFont.truetype(font_path, size)
    bbox = draw.textbbox((0, 0), char, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Position: center in canvas
    x = (canvas_w - tw) // 2 - bbox[0]
    y = (canvas_h - th) // 2 - bbox[1]

    draw.text((x, y), char, fill=255, font=font)

    # Threshold to pure black/white (no anti-aliasing artifacts)
    threshold = 128
    img = img.point(lambda p: 255 if p > threshold else 0)
    img = img.convert("1")

    pixels = img.load()

    # Extract 12x12 bitmap: column-major, 12 columns, each split into 2 pages
    bitmap = []
    for col in range(size):
        # Upper page: rows 0-7 (from padded y)
        upper = 0
        for row in range(8):
            if pixels[pad + col, pad + row]:
                upper |= (1 << row)
        bitmap.append(upper)

        # Lower page: rows 8-11 (only 4 rows)
        lower = 0
        for row in range(4):
            if pixels[pad + col, pad + 8 + row]:
                lower |= (1 << row)
        bitmap.append(lower)

    return bitmap

def main():
    print("Finding font...")
    font_path = find_font()
    print(f"Using font: {font_path}")

    print(f"\nGenerating {len(CHARS)} characters at 12x12...\n")

    results = {}
    for name, char in CHARS:
        bitmap = gen_char_bitmap(font_path, char)
        results[name] = (char, bitmap)

        # Print C array line
        hex_str = ",".join(f"0x{b:02X}" for b in bitmap)
        print(f"    /* {char} ({name}) */")
        print(f"    {{{hex_str}}},")

    # Print the #define section
    print("\n\n/* ==================== Copy to oled.h ==================== */")
    for i, (name, char) in enumerate(CHARS):
        print(f"#define CN_{name.upper():6s} {i}   /* {char} */")

    print("\n/* ==================== Copy to oled.c ==================== */")
    print(f"const uint8_t Chinese12x12[{len(CHARS)}][24] = {{")
    for name, (char, bitmap) in results.items():
        hex_str = ",".join(f"0x{b:02X}" for b in bitmap)
        print(f"    /* {char} */ {{{hex_str}}},")
    print("};")

if __name__ == "__main__":
    main()
