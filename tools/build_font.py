# -*- coding: utf-8 -*-
"""PS3 ALICEFONTS.XXX 의 fonts_en 을 PC 한글패치의 한글 GFx 폰트로 갈아끼운다.

확정 사실 (실측)
  · PC/PS3 의 fonts_jp·gfxfontlib RawData 가 «바이트 완전 동일» → GFx 블롭은 플랫폼 무관
  · 한글패치가 바꾼 건 fonts_en 하나뿐 (350,707 B -> 10,224,715 B)
  · PS3 GFxMovieInfo export 직렬화 =
        i32 netIndex
        FName RawData(i32 idx, i32 num) · FName ArrayProperty(i32,i32)
        i32 속성크기(=원소수+4) · i32 배열첨자 · i32 원소수 · byte[원소수]
        FName None(i32,i32)
    -> export 크기 = 블롭 + 40  (원본 350,747 = 350,707+40 으로 검산됨)
  · 이름 색인은 «패키지마다 다르다» — PC 것을 그대로 베끼면 안 되고 PS3 이름표로 다시 쓴다.
  · 압축 청크 경계는 원본이 «export 경계»와 정확히 일치한다 → 그 구조를 그대로 유지한다.
"""
import os, sys, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue3pkg import Pkg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS3 = os.path.join(ROOT, 'NPUB30545 PS3 files', 'USRDIR', 'ALICEGAME', 'COOKEDPS3', 'ALICEFONTS.XXX')
PC = os.path.join(ROOT, 'Alice2_KOR PC Patch', 'Game', 'Alice2', 'AliceGame', 'CookedPC', 'GFx', 'AliceFonts.upk')
OUT = os.path.join(ROOT, 'patches', 'ALICEFONTS.XXX')
BLK = 0x10000


def raw_of(p, name):
    nm = p.names(); e_ = '>' if p.be else '<'
    for e in p.exports(nm):
        if e['name'] != name:
            continue
        d = p.img[e['off']:e['off'] + e['size']]
        cnt = struct.unpack_from(e_ + 'i', d, 28)[0]
        return d[32:32 + cnt]
    raise KeyError(name)


def main():
    src = Pkg(PS3)
    names = src.names()
    ex = src.exports(names)
    kr = raw_of(Pkg(PC), 'fonts_en')
    print('한글 fonts_en %d B' % len(kr))
    iRaw, iArr, iNone = names.index('RawData'), names.index('ArrayProperty'), names.index('None')

    fe = [e for e in ex if e['name'] == 'fonts_en'][0]
    old = src.img[fe['off']:fe['off'] + fe['size']]
    net = struct.unpack_from('>i', old, 0)[0]
    assert struct.unpack_from('>2i', old, len(old) - 8) == (iNone, 0), '★꼬리가 None 이 아니다'
    new = (struct.pack('>i', net) + struct.pack('>4i', iRaw, 0, iArr, 0)
           + struct.pack('>3i', len(kr) + 4, 0, len(kr)) + kr
           + struct.pack('>2i', iNone, 0))
    assert len(new) == len(kr) + 40
    delta = len(new) - fe['size']
    print('fonts_en export %d -> %d B (차이 %+d)' % (fe['size'], len(new), delta))

    img = bytearray(src.img[:fe['off']]) + new + src.img[fe['off'] + fe['size']:]
    # export 표의 SerialSize/SerialOffset 갱신
    for e in ex:
        if e['name'] == 'fonts_en':
            struct.pack_into('>i', img, e['size_at'], len(new))
        elif e['off'] > fe['off']:
            struct.pack_into('>i', img, e['off_at'], e['off'] + delta)
    # 검산 : 다시 파싱해 export 가 연속인가
    print('새 이미지 %d B' % len(img))

    # ── 청크 3개 — 원본과 같은 «export 경계»로 자른다
    bounds = [src.chunks[0][0]]
    for nm2 in ('fonts_jp', 'gfxfontlib'):
        e = [x for x in ex if x['name'] == nm2][0]
        bounds.append(e['off'] + (delta if e['off'] > fe['off'] else 0))
    bounds.append(len(img))
    ranges = [(bounds[i], bounds[i + 1] - bounds[i]) for i in range(3)]
    print('청크 경계:', ['0x%X +%d' % r for r in ranges])

    hdr = bytearray(src.raw[:src.chunks[0][2]])       # 원시 헤더(첫 청크 바로 앞까지)
    body = bytearray()
    tbl = []
    coff = len(hdr)
    for uo, us in ranges:
        blocks = [img[uo + i:uo + min(i + BLK, us)] for i in range(0, us, BLK)]
        comp = [zlib.compress(b, 9) for b in blocks]
        ch = bytearray()
        ch += struct.pack('>4I', 0x9E2A83C1, BLK, sum(len(c) for c in comp), us)
        for b, c in zip(blocks, comp):
            ch += struct.pack('>2I', len(c), len(b))
        for c in comp:
            ch += c
        tbl.append((uo, us, coff, len(ch)))
        body += ch
        coff += len(ch)
    # 청크 표 자리 = 원본과 같은 곳(0x75 부근) — 원본 표의 «첫 항목 위치»를 찾아 덮어쓴다
    pos = None
    for base in range(0x30, len(hdr) - 16):
        if struct.unpack_from('>4I', hdr, base) == src.chunks[0]:
            pos = base; break
    assert pos is not None, '★청크 표 자리를 못 찾았다'
    for i, t in enumerate(tbl):
        struct.pack_into('>4I', hdr, pos + i * 16, *t)
    out = bytes(hdr) + bytes(body)
    # ★PS3 .XXX 는 «64KB 배수»로 0 패딩돼 있다(표본 200개 전부) — 같은 규약을 지킨다
    if len(out) % BLK:
        out += bytes(BLK - len(out) % BLK)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'wb').write(out)
    print('-> %s  %d B (원본 %d B)' % (OUT, len(out), os.path.getsize(PS3)))

    # ── 검산 : 다시 읽어서 원래대로 풀리는가
    chk = Pkg(OUT)
    n2 = chk.names(); e2 = chk.exports(n2)
    # ★헤더 0x75~0x7C 는 «압축 파일에만 있는 청크 표»가 겹치는 자리라 다를 수밖에 없다.
    #   실제 패키지 데이터는 이름표 시작(0x7D)부터다 — 거기서부터 대조한다.
    st = src.chunks[0][0]
    assert bytes(chk.img[st:]) == bytes(img[st:]), '★재파싱 이미지가 다르다'
    print('★재파싱 OK · 이름 %d · export %d' % (len(n2), len(e2)))
    for e in e2:
        print('   %-18s size %9d off 0x%08X' % (e['name'], e['size'], e['off']))
    assert raw_of(chk, 'fonts_en') == kr, '★fonts_en 블롭 불일치'
    assert raw_of(chk, 'fonts_jp') == raw_of(src, 'fonts_jp'), '★fonts_jp 가 변했다'
    assert raw_of(chk, 'gfxfontlib') == raw_of(src, 'gfxfontlib'), '★gfxfontlib 가 변했다'
    print('★블롭 전수 대조 통과 (fonts_en=한글 · 나머지 원본 그대로)')


if __name__ == '__main__':
    main()
