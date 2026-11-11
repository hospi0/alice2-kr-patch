# -*- coding: utf-8 -*-
"""번역문 글자가 두 글꼴에 다 있는지 센다 (2026-11-11).
  ① UE3 UFont WarfareFonts_Chrom20 (자막·로딩) — 이식판 patches/ALICEGAME_LOC_INT.XXX 의 CharRemap
  ② GFx fonts_en (메뉴) — 이식판 patches/ALICEFONTS.XXX 의 SWF DefineFont2/3 코드표
python tools/font_cover.py
"""
import os, sys, struct, zlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue3pkg import Pkg
import uprops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = r'C:\claude\utils\한글화 이식\Alice2\patches'


def ufont_chars(path):
    S = Pkg(path); nm = S.names(); ex = S.exports(nm)
    for e in ex:
        if e['name'] != 'WarfareFonts_Chrom20':
            continue
        net, props, tail = uprops.read(S.img, e['off'], e['size'], nm, '>', 1)
        # CharRemap 은 속성 뒤 꼬리 : i32 수 + (u16 유니코드, u16 글리프번호) 쌍
        n = struct.unpack_from('>i', tail, 0)[0]
        assert 4 + n * 4 == len(tail), 'CharRemap 길이 이상'
        return {struct.unpack_from('>H', tail, 4 + i * 4)[0] for i in range(n)}
    raise SystemExit('UFont 못 찾음')


def swf_codes(blob):
    """GFx 블롭(SWF 류) 안 DefineFont2/3 의 코드표를 모두 모은다."""
    sig = blob[:3]
    if sig in (b'CWS', b'CFX'):
        body = zlib.decompress(blob[8:])
    else:
        body = blob[8:]
    nbits = body[0] >> 3
    p = (5 + nbits * 4 + 7) // 8 + 4
    codes = set(); fonts = []
    while p + 2 <= len(body):
        h = struct.unpack_from('<H', body, p)[0]; p += 2
        t, ln = h >> 6, h & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from('<I', body, p)[0]; p += 4
        d = body[p:p + ln]; p += ln
        if t == 0:
            break
        if t in (48, 75):
            fid, flags = struct.unpack_from('<HB', d, 0)
            q = 4
            nl = d[q]; name = d[q + 1:q + 1 + nl].decode('latin1', 'replace'); q += 1 + nl
            ng = struct.unpack_from('<H', d, q)[0]; q += 2
            wide_off = flags & 0x08
            offs = q
            q += ng * (4 if wide_off else 2)
            code_off = struct.unpack_from('<I' if wide_off else '<H', d, q)[0]
            wide_codes = flags & 0x04
            cp = offs + code_off
            cs = set()
            for i in range(ng):
                cs.add(struct.unpack_from('<H', d, cp + i * 2)[0] if wide_codes else d[cp + i])
            fonts.append((name, ng)); codes |= cs
    return codes, fonts


def gfx_codes(path):
    S = Pkg(path); nm = S.names()
    for e in S.exports(nm):
        if e['name'] == 'fonts_en':
            d = S.img[e['off']:e['off'] + e['size']]
            cnt = struct.unpack_from('>i', d, 28)[0]
            return swf_codes(bytes(d[32:32 + cnt]))
    raise SystemExit('fonts_en 못 찾음')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'ko.tsv'), encoding='utf-8')][1:]
    need = collections.Counter()
    for r in rows:
        for ch in r[3]:
            need[ch] += 1
    u = ufont_chars(os.path.join(PORT, 'ALICEGAME_LOC_INT.XXX'))
    g, fonts = gfx_codes(os.path.join(PORT, 'ALICEFONTS.XXX'))
    print('번역 글자 종류 %d (한글 음절 %d)' % (len(need), sum(1 for c in need if '가' <= c <= '힣')))
    print('UE3 UFont 코드 %d개 · GFx 글꼴 %s 코드 %d개' % (len(u), fonts[:6], len(g)))
    for nmx, have in (('UE3', u), ('GFx', g)):
        miss = sorted((c for c in need if ord(c) not in have and c not in '\t'), key=lambda c: -need[c])
        print('  %s 에 없는 글자 %d: %s' % (nmx, len(miss), ' '.join('%s(%d)' % (c, need[c]) for c in miss[:60])))


if __name__ == '__main__':
    main()
