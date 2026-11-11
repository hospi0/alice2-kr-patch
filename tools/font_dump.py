# -*- coding: utf-8 -*-
"""UE3 UFont(WarfareFonts_Chrom20) 페이지·글자 칸 덤프 (2026-11-11)
  python tools/font_dump.py <패키지.XXX> <출력폴더> [글자들]
페이지(256x256 DXT5)를 PNG 로, 지정 글자 칸을 빨간 상자로 표시한 확대 그림을 만든다.
DXT5 는 Pillow 의 DDS 읽기로 푼다(DDS 머리말을 붙여서).
"""
import os, sys, struct, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue3pkg import Pkg
import uprops
from PIL import Image, ImageDraw

FONT = 'WarfareFonts_Chrom20'


def dds_dxt5(w, h, data):
    hdr = bytearray(128)
    struct.pack_into('<4s', hdr, 0, b'DDS ')
    struct.pack_into('<7I', hdr, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, len(data), 0, 1)
    struct.pack_into('<2I4s', hdr, 76, 32, 0x4, b'DXT5')
    struct.pack_into('<I', hdr, 108, 0x1000)
    return Image.open(io.BytesIO(bytes(hdr) + data)).convert('RGBA')


def load(path):
    S = Pkg(path); nm = S.names(); ex = S.exports(nm)
    get = {e['name']: e for e in ex}
    f = get[FONT]
    net, props, tail = uprops.read(S.img, f['off'], f['size'], nm, '>', 1)
    pp = {p['name']: p for p in props}
    v = pp['Characters']['val']; n = struct.unpack_from('>i', v, 0)[0]
    chars = []
    for i in range(n):
        q = 4 + i * 21
        u, vv, us, vs = struct.unpack_from('>4i', v, q)
        ti = v[q + 16]; vo = struct.unpack_from('>i', v, q + 17)[0]
        chars.append((u, vv, us, vs, ti, vo))
    m = struct.unpack_from('>i', tail, 0)[0]
    remap = {}
    for i in range(m):
        a, b = struct.unpack_from('>2H', tail, 4 + i * 4)
        remap[a] = b
    pages = []
    for i in range(20):
        e = get[FONT + '_Page' + chr(65 + i)]
        d = bytes(S.img[e['off']:e['off'] + e['size']])
        _net, _pr, t = uprops.read(S.img, e['off'], e['size'], nm, '>', 1)
        # 꼬리: 빈벌크16 + 밉수4 + 벌크헤더16(flags,count,size,offset) + 데이터 + SizeX + SizeY
        sz = struct.unpack_from('>i', t, 16 + 4 + 8)[0]
        data = t[36:36 + sz]
        w, h = struct.unpack_from('>2i', t, 36 + sz)
        pages.append(dds_dxt5(w, h, data))
    return chars, remap, pages


def main():
    path, out = sys.argv[1], sys.argv[2]
    text = sys.argv[3] if len(sys.argv) > 3 else ' 로딩중'
    os.makedirs(out, exist_ok=True)
    chars, remap, pages = load(path)
    print('글자 %d · remap %d · 페이지 %d (%dx%d)' % (len(chars), len(remap), len(pages), *pages[0].size))
    for ch in text:
        gi = remap.get(ord(ch))
        if gi is None:
            print(repr(ch), '없음'); continue
        u, v, us, vs, ti, vo = chars[gi]
        print('%r 글리프 %d 페이지 %d 칸 (%d,%d) %dx%d 세로보정 %d' % (ch, gi, ti, u, v, us, vs, vo))
        pg = pages[ti]
        x0, y0, x1, y1 = max(0, u - 6), max(0, v - 6), min(pg.width, u + us + 6), min(pg.height, v + vs + 6)
        crop = pg.crop((x0, y0, x1, y1))
        bg = Image.new('RGBA', crop.size, (40, 40, 60, 255)); bg.alpha_composite(crop)
        big = bg.resize((bg.width * 12, bg.height * 12), Image.NEAREST)
        dr = ImageDraw.Draw(big)
        dr.rectangle(((u - x0) * 12, (v - y0) * 12, (u - x0 + us) * 12 - 1, (v - y0 + vs) * 12 - 1), outline=(255, 0, 0, 255), width=2)
        big.save(os.path.join(out, 'glyph_%04X.png' % ord(ch)))
    for i in range(2):
        bg = Image.new('RGBA', pages[i].size, (40, 40, 60, 255)); bg.alpha_composite(pages[i])
        bg.resize((768, 768), Image.NEAREST).save(os.path.join(out, 'page_%c.png' % (65 + i)))


if __name__ == '__main__':
    main()
