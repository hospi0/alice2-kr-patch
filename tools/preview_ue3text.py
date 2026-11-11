# -*- coding: utf-8 -*-
"""UE3 UFont 로 문장을 «게임처럼 보간 확대»해 그려 보는 미리보기 (2026-11-11)
  python tools/preview_ue3text.py <원래.XXX> <고친.XXX> <출력.png> "문장" ["문장" …]
글자 칸을 칸 밖 1화소까지 함께 잘라 쌍선형 확대(배율 1.9 ≒ 4K 화면) → 칸 밖이 묻어나는지 보인다. 위=원래 · 아래=고친 것.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import font_dump
from PIL import Image, ImageDraw

S = 1.9


def render(path, text):
    chars, remap, pages = font_dump.load(path)
    H = int(40 * S); x = 10
    im = Image.new('RGBA', (int(len(text) * 24 * S) + 40, H + 10), (20, 20, 28, 255))
    for ch in text:
        gi = remap.get(ord(ch))
        if gi is None:
            continue
        u, v, us, vs, ti, vo = chars[gi]
        crop = pages[ti].crop((u - 1, v - 1, u + us + 1, v + vs + 1))
        big = crop.resize((int(crop.width * S), int(crop.height * S)), Image.BILINEAR)
        # 칸 안쪽 + 보간으로 번진 반 화소만 남김(게임이 그리는 사각형 = 칸 크기)
        big = big.crop((int(S * 0.5), int(S * 0.5), int(S * (us + 1.5)), int(S * (vs + 1.5))))
        im.alpha_composite(big, (x, int(vo * S) + 4))
        x += int(us * S)
    return im.crop((0, 0, x + 10, im.height))


def main():
    a, b, out = sys.argv[1:4]
    texts = sys.argv[4:]
    rows = []
    for t in texts:
        rows.append(render(a, t)); rows.append(render(b, t))
    W = max(r.width for r in rows) + 120
    sheet = Image.new('RGBA', (W, sum(r.height + 8 for r in rows)), (60, 60, 70, 255))
    d = ImageDraw.Draw(sheet); y = 0
    for i, r in enumerate(rows):
        d.text((4, y + r.height // 2 - 6), '원래' if i % 2 == 0 else '고침', fill=(255, 255, 0, 255))
        sheet.alpha_composite(r, (110, y)); y += r.height + 8
    sheet.save(out)
    print('->', out)


if __name__ == '__main__':
    main()
