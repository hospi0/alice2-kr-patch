# -*- coding: utf-8 -*-
"""PS3 *_LOC_INT.XXX 의 UFont `WarfareFonts_Chrom20` 을 PC 한글패치 것으로 갈아끼운다.

실측 확정 사항
  · 자막·로딩 화면은 GFx 가 아니라 이 **UE3 UFont** 가 그린다.
      PS3 원본 : 글리프 256자 · 텍스처 2장  /  PC 한글 : 글리프 2,608자 · 20장
  · FFontCharacter = i32 5개 + u8 1개 = 21 B (양쪽 동일)  · CharRemap = i32 수 + (u16,u16)
  · Texture2D 꼬리 = 빈벌크(16B) + 밉수(4) + 벌크헤더(16) + DXT5 + SizeX + SizeY + GUID(16)
                     [+ PS3 만 끝에 u32 0]
    ★원본 실측 검산 : 빈벌크.오프셋 = export시작+속성길이+16 · 밉.오프셋 = +36
  · DXT5 픽셀 배치는 PC/PS3 동일
  · PC(v648) 는 BoolProperty 값이 4바이트, PS3(v690) 은 1바이트
  · ImportOptions 는 에디터용 — PS3 원본을 그대로 둔다(안에 FName 색인이 있다)
  · 이름은 «뒤에만» 덧붙인다 → import 표의 이름 색인이 안 밀린다
"""
import os
import sys
import struct
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcloc
import uprops
from ue3pkg import Pkg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCF = os.path.join(ROOT, 'Alice2_KOR PC Patch', 'Game', 'Alice2', 'AliceGame',
                   'CookedPC', 'AliceGame_LOC_INT.upk')
CK = os.path.join(ROOT, 'NPUB30545 PS3 files', 'USRDIR', 'ALICEGAME', 'COOKEDPS3')
OUT = os.path.join(ROOT, 'patches')
FONT = 'WarfareFonts_Chrom20'
PAGE = [FONT + '_Page' + chr(ord('A') + i) for i in range(20)]
BLK = 0x10000
# 헤더 필드 자리 (실측)
H_HDR = 0x08
H_NCNT, H_NOFF = 0x19, 0x1D
H_ECNT, H_EOFF = 0x21, 0x25
H_ICNT, H_IOFF = 0x29, 0x2D
H_DEP, H_IEG = 0x31, 0x35
H_GEN = 0x55


def swap_chars(v):
    """FFontCharacter 배열 : i32 개수 + 항목 21 B.

    ★★★항목 배치는 «i32 x4 + u8 + i32» 다(실측으로 확정) :
        i32 StartU, StartV, USize, VSize   (0..15)
        u8  TextureIndex                   (16)
        i32 VerticalOffset                 (17..20)  ← 4바이트 정렬이 아니다
    ⛔«i32 x5 + u8» 로 잡으면 TextureIndex 와 VerticalOffset 이 통째로 깨진다.
      실기 증상 = 글리프가 엉뚱한 페이지에서 나와 «깨진 점», 세로 위치가 날아가 «자막 안 보임».
    검증 : PC 쪽 TextureIndex 분포가 0~19(=페이지 20장)로 고르게 나오는지 본다.
    """
    n = struct.unpack_from('<i', v, 0)[0]
    o = bytearray(struct.pack('>i', n))
    p = 4
    for _ in range(n):
        o += struct.pack('>4i', *struct.unpack_from('<4i', v, p))
        o += v[p + 16:p + 17]
        o += struct.pack('>i', struct.unpack('<i', bytes(v[p + 17:p + 21]))[0])
        p += 21
    assert p == len(v), '문자표 길이 %d != %d' % (p, len(v))
    return bytes(o), n


def swap_remap(t):
    n = struct.unpack_from('<i', t, 0)[0]
    o = bytearray(struct.pack('>i', n))
    p = 4
    for _ in range(n):
        o += struct.pack('>2H', *struct.unpack_from('<2H', t, p))
        p += 4
    assert p == len(t), 'CharRemap 길이 %d != %d' % (p, len(t))
    return bytes(o), n


def build(ps3_name, out_name):
    S = Pkg(os.path.join(CK, ps3_name))
    snm = S.names()
    sex = S.exports(snm)
    sget = {e['name']: e for e in sex}
    P = pcloc.load(PCF)
    pnm = pcloc.names(P)
    pex = pcloc.exports(P, pnm)
    pget = {e['name']: e for e in pex}
    print('=== %s : export %d · 이름 %d · 이미지 %d B'
          % (ps3_name, len(sex), len(snm), len(S.img)))

    names = list(snm)
    for n in PAGE + ['IsRemapped']:
        if n not in names:
            names.append(n)
    nidx = {n: i for i, n in enumerate(names)}
    print('   이름 %d -> %d' % (len(snm), len(names)))

    # ── 폰트 오브젝트 -------------------------------------------------
    pf, sf = pget[FONT], sget[FONT]
    pnet, pprops, ptail = uprops.read(P['img'], pf['off'], pf['size'], pnm, '<', 4)
    snet, sprops, stail = uprops.read(S.img, sf['off'], sf['size'], snm, '>', 1)
    pp = {q['name']: q for q in pprops}
    sp = {q['name']: q for q in sprops}
    chars, nchar = swap_chars(pp['Characters']['val'])
    remap, nrem = swap_remap(ptail)

    # PageA/PageB 는 원래 있던 export, PageC~T 는 뒤에 새로 붙는다
    slot = {}
    nxt = len(sex)
    for k, nm2 in enumerate(PAGE):
        if nm2 in sget:
            slot[k] = sex.index(sget[nm2])
        else:
            slot[k] = nxt
            nxt += 1
    tex = struct.pack('>i', 20) + b''.join(struct.pack('>i', slot[k] + 1) for k in range(20))

    io_ = dict(sp['ImportOptions'])
    io_['exname'] = snm[io_['extra'][0]]
    fprops = [
        dict(name='Characters', nn=0, type='ArrayProperty', tn=0,
             size=len(chars), ai=0, val=chars, extra=None),
        dict(name='Textures', nn=0, type='ArrayProperty', tn=0,
             size=len(tex), ai=0, val=tex, extra=None),
        dict(name='IsRemapped', nn=0, type='IntProperty', tn=0,
             size=4, ai=0, val=struct.pack('>i', 1), extra=None),
        io_,
    ]
    font_data = uprops.write(snet, fprops, remap, lambda n: nidx[n], '>')
    print('   폰트 : 글리프 %d자 · CharRemap %d · %d -> %d B'
          % (nchar, nrem, sf['size'], len(font_data)))

    # ── 텍스처 속성부 : PS3 PageA 를 본으로 --------------------------
    tnet, tprops, _ = uprops.read(S.img, sget[PAGE[0]]['off'], sget[PAGE[0]]['size'], snm, '>', 1)
    for q in tprops:
        if q['type'] in ('StructProperty', 'ByteProperty'):
            q['exname'] = snm[q['extra'][0]]
    tex_props = uprops.write(tnet, tprops, b'', lambda n: nidx[n], '>')
    plen = len(tex_props)

    mips = []
    for nm2 in PAGE:
        pe = pget[nm2]
        _n, _pr, pt = uprops.read(P['img'], pe['off'], pe['size'], pnm, '<', 4)
        mf, mc, ms = struct.unpack_from('<3i', pt, 20)
        data = pt[36:36 + ms]
        sx, sy = struct.unpack_from('<2i', pt, 36 + ms)
        guid = pt[36 + ms + 8:36 + ms + 24]
        assert len(pt) == 36 + ms + 24, 'PC 꼬리 길이 %d' % len(pt)
        mips.append((mf, mc, ms, data, sx, sy, guid))
    print('   텍스처 20장 : %dx%d · 밉 %d B · 속성부 %d B'
          % (mips[0][4], mips[0][5], mips[0][2], plen))

    # ── export 표 ----------------------------------------------------
    ent = [bytearray(S.img[e['tbl']:e['tblend']]) for e in sex]
    tmpl = bytearray(S.img[sget[PAGE[1]]['tbl']:sget[PAGE[1]]['tblend']])
    for k in range(2, 20):
        b = bytearray(tmpl)
        struct.pack_into('>i', b, 12, nidx[PAGE[k]])
        ent.append(b)

    noff = 0x7D
    nt = bytearray()
    for n in names:
        nt += struct.pack('>i', len(n) + 1) + n.encode('latin1') + b'\0'
        nt += struct.pack('>2I', 0, 0)
    ioff = noff + len(nt)
    it = bytes(S.img[S.ioff:S.eoff])
    eoff = ioff + len(it)
    dep = eoff + sum(len(x) for x in ent)
    hdr_end = dep + 4 * len(ent)

    # ── export 데이터 배치 -------------------------------------------
    page_of = {slot[k]: k for k in range(20)}
    body = bytearray()
    for j in range(len(ent)):
        cur = hdr_end + len(body)
        if j in page_of:
            mf, mc, ms, data, sx, sy, guid = mips[page_of[j]]
            t = bytearray()
            t += struct.pack('>4i', 0, 0, 0, cur + plen + 16)
            t += struct.pack('>i', 1)
            t += struct.pack('>4i', mf, mc, ms, cur + plen + 36)
            t += data
            t += struct.pack('>2i', sx, sy)
            t += guid
            t += struct.pack('>i', 0)
            blob = tex_props + bytes(t)
        elif j < len(sex) and sex[j]['name'] == FONT:
            blob = font_data
        else:
            e = sex[j]
            blob = bytes(S.img[e['off']:e['off'] + e['size']])
        struct.pack_into('>2i', ent[j], 32, len(blob), cur)
        body += blob
    print('   export %d개 · 헤더끝 0x%X · 데이터 %d B' % (len(ent), hdr_end, len(body)))

    # ── 이미지 조립 --------------------------------------------------
    img = bytearray(S.img[:noff])
    img += nt + it + b''.join(bytes(x) for x in ent) + bytes(4 * len(ent)) + body

    def fix(buf):
        struct.pack_into('>I', buf, H_HDR, hdr_end)
        struct.pack_into('>I', buf, H_NCNT, len(names))
        struct.pack_into('>I', buf, H_NOFF, noff)
        struct.pack_into('>I', buf, H_ECNT, len(ent))
        struct.pack_into('>I', buf, H_EOFF, eoff)
        struct.pack_into('>I', buf, H_IOFF, ioff)
        struct.pack_into('>I', buf, H_DEP, dep)
        struct.pack_into('>I', buf, H_IEG, hdr_end)
        struct.pack_into('>3i', buf, H_GEN + 4, len(ent), len(names), 0)

    fix(img)

    # ── 압축(청크 1개 — 원본과 같은 구조) ----------------------------
    hdr = bytearray(S.raw[:S.chunks[0][2]])
    uo, us = noff, len(img) - noff
    blocks = [bytes(img[uo + i:uo + min(i + BLK, us)]) for i in range(0, us, BLK)]
    # ★압축이 이득 없으면 원본 그대로 둔다(엔진이 압축크기==원본크기 로 판별)
    comp = []
    for b in blocks:
        c = zlib.compress(b, 9)
        comp.append(c if len(c) < len(b) else bytes(b))
    ch = bytearray(struct.pack('>4I', 0x9E2A83C1, BLK, sum(len(c) for c in comp), us))
    for b, c in zip(blocks, comp):
        ch += struct.pack('>2I', len(c), len(b))
    for c in comp:
        ch += c
    pos = None
    for base in range(0x30, len(hdr) - 16):
        if struct.unpack_from('>4I', hdr, base) == S.chunks[0]:
            pos = base
            break
    assert pos is not None, '청크 표 자리를 못 찾았다'
    struct.pack_into('>4I', hdr, pos, uo, us, len(hdr), len(ch))
    fix(hdr)
    out = bytes(hdr) + bytes(ch)
    if len(out) % BLK:
        out += bytes(BLK - len(out) % BLK)
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, out_name)
    open(dst, 'wb').write(out)
    print('   -> %s  %d B (원본 %d B)'
          % (dst, len(out), os.path.getsize(os.path.join(CK, ps3_name))))

    # ── 검산 ----------------------------------------------------------
    C = Pkg(dst)
    cn = C.names()
    ce = C.exports(cn)
    assert bytes(C.img[noff:]) == bytes(img[noff:]), '★재파싱 이미지 불일치'
    print('   ★재파싱 OK : 이름 %d · export %d' % (len(cn), len(ce)))
    fe = [e for e in ce if e['name'] == FONT][0]
    n2, pr2, t2 = uprops.read(C.img, fe['off'], fe['size'], cn, '>', 1)
    nch = struct.unpack_from('>i', [q for q in pr2 if q['name'] == 'Characters'][0]['val'], 0)[0]
    ntx = struct.unpack_from('>i', [q for q in pr2 if q['name'] == 'Textures'][0]['val'], 0)[0]
    print('      폰트 속성 %s · 글리프 %d · 텍스처참조 %d · CharRemap 꼬리 %d B'
          % ([q['name'] for q in pr2], nch, ntx, len(t2)))
    bad = 0
    for k in range(20):
        pe = [e for e in ce if e['name'] == PAGE[k]][0]
        _n, _p, tt = uprops.read(C.img, pe['off'], pe['size'], cn, '>', 1)
        if struct.unpack_from('>i', tt, 32)[0] != pe['off'] + plen + 36:
            bad += 1
        if struct.unpack_from('>i', tt, 24)[0] != mips[k][2]:
            bad += 1
        if tt[36:36 + mips[k][2]] != mips[k][3]:
            bad += 1
    print('      페이지 20장 검산 불일치 %d개' % bad)
    assert bad == 0
    return dst


if __name__ == '__main__':
    build('ALICEGAME_LOC_INT.XXX', 'ALICEGAME_LOC_INT.XXX')
    print()
    build('ALICEFONTS_LOC_INT.XXX', 'ALICEFONTS_LOC_INT.XXX')
