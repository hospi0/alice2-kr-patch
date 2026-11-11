# -*- coding: utf-8 -*-
"""UE3 UFont 공백 글리프 칸 옮기기 (2026-11-11 하스피 실기: 로딩 화면 «글자 밑에 살짝 밑줄»)

원인(실측): PC 한글패치 글꼴 아틀라스에서 ' '(U+0020)·NBSP(U+00A0) 칸 «바로 아래 줄»에 다른 글자 획이 붙어 있다.
           게임이 텍스처를 보간해 그리면 칸 밖 1화소가 묻어나 공백 자리마다 밑줄처럼 찍힌다.
           (나머지 2,606자는 칸 밖 1화소 테두리에 잉크 0 — tools/font_dump.py 로 전수 확인)
고침  : 두 글리프의 StartU/StartV/TextureIndex 만 «사방 3화소까지 완전히 빈 곳»으로 옮긴다.
        USize/VSize·VerticalOffset 은 그대로 → 글자 간격·줄 높이 불변.
python tools/fix_space_glyph.py <패키지.XXX> [...]   (제자리 수정 — build.py 가 부른다)
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue3pkg import Pkg
import uprops, build_subs, font_dump

MARGIN = 3
TARGET = (0x20, 0xA0)


def find_empty(pages, w, h, used):
    for ti, pg in enumerate(pages):
        a = pg.split()[3].load()
        W, H = pg.size
        for y in range(MARGIN, H - h - MARGIN, 2):
            for x in range(MARGIN, W - w - MARGIN, 2):
                if (ti, x, y) in used:
                    continue
                ok = True
                for yy in range(y - MARGIN, y + h + MARGIN):
                    for xx in range(x - MARGIN, x + w + MARGIN):
                        if a[xx, yy]:
                            ok = False; break
                    if not ok:
                        break
                if ok:
                    return ti, x, y
    raise SystemExit('★빈 자리를 못 찾았다')


def fix(path):
    chars, remap, pages = font_dump.load(path)
    S = Pkg(path); nm = S.names()
    e = [x for x in S.exports(nm) if x['name'] == font_dump.FONT][0]
    net, props, tail = uprops.read(S.img, e['off'], e['size'], nm, '>', 1)
    val = [p for p in props if p['name'] == 'Characters'][0]['val']
    seg = bytes(S.img[e['off']:e['off'] + e['size']])
    at = seg.find(val)
    assert at >= 0 and seg.find(val, at + 1) < 0, 'Characters 배열 자리 모호'
    base = e['off'] + at
    img = bytearray(S.img)
    used = set(); log = []
    for cp in TARGET:
        gi = remap[cp]
        u, v, us, vs, ti, vo = chars[gi]
        nti, nx, ny = find_empty(pages, us, vs, used)
        used.add((nti, nx, ny))
        q = base + 4 + gi * 21
        struct.pack_into('>2i', img, q, nx, ny)
        img[q + 16] = nti
        log.append('U+%04X 글리프 %d : 페이지 %d (%d,%d) → 페이지 %d (%d,%d)  %dx%d' % (cp, gi, ti, u, v, nti, nx, ny, us, vs))
    build_subs.write_pkg(S, img, path)
    # 검산
    c2, r2, p2 = font_dump.load(path)
    for cp in TARGET:
        u, v, us, vs, ti, vo = c2[r2[cp]]
        a = p2[ti].split()[3].load()
        ink = sum(1 for yy in range(v - 2, v + vs + 2) for xx in range(u - 2, u + us + 2) if a[xx, yy])
        assert ink == 0, '★옮긴 자리에 잉크 %d' % ink
    assert [c for i, c in enumerate(c2) if i not in (r2[0x20], r2[0xA0])] == \
        [c for i, c in enumerate(chars) if i not in (remap[0x20], remap[0xA0])], '★다른 글리프가 바뀌었다'
    return log


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for p in sys.argv[1:]:
        for ln in fix(p):
            print(os.path.basename(p), ln)
