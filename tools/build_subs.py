# -*- coding: utf-8 -*-
"""PS3 시네마틱 패키지(*_LOC_INT.XXX)의 대사 자막을 한글로 바꾼다.

왜 .int 오버라이드로는 안 되는가 (실기로 확인)
  콘솔판 SoundNodeWave 는 `Subtitles`(=.int 가 덮는 자리) 말고
  **`LocalizedSubtitles`** 배열을 쓴다. 언어별 엔트리(INT/JPN/DEU/FRA/ESN/ITA…)가
  패키지 안에 구워져 있고, 엔진은 현재 언어(INT)의 것을 고른다.
  ★JPN 엔트리가 «UTF-16» 으로 들어 있다 — 한글도 같은 방식으로 들어간다.

구조 (실측)
  Subtitles          = i32 개수 + [태그된 속성 스트림(Text/Time/…) + None] x 개수
  LocalizedSubtitles = i32 개수 + [LanguageExt(Str) · Subtitles(Array) · … + None] x 개수
  꼬리 = FUntypedBulkData 나열 (flags,count,size,offset) — offset = 자기자리+16 (인라인)
  FString : i32 길이(BE). 양수=8비트, 음수=UTF-16 «문자 데이터는 리틀엔디언»

바꾸는 것
  · LocalizedSubtitles 의 «INT» 엔트리 Text
  · 겸사겸사 Subtitles[0].Text (구형 경로 대비)
바꾸지 않는 것 : 이름표·import·export 개수 (그래서 표 위치가 안 밀린다)
"""
import os
import re
import io
import sys
import glob
import struct
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue3pkg import Pkg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CK = os.path.join(ROOT, 'NPUB30545 PS3 files', 'USRDIR', 'ALICEGAME', 'COOKEDPS3')
INT = os.path.join(ROOT, 'Alice2_KOR PC Patch', 'Game', 'Alice2', 'AliceGame',
                   'Localization', 'INT')
OUT = os.path.join(ROOT, 'patches', 'COOKEDPS3')
BLK = 0x10000
BS = chr(92)


# ── FString ────────────────────────────────────────────────────────────
def rd_str(b, p):
    n = struct.unpack_from('>i', b, p)[0]
    p += 4
    if n == 0:
        return '', p, False
    if n > 0:
        return b[p:p + n].rstrip(b'\0').decode('latin1'), p + n, False
    m = -n * 2
    return b[p:p + m].decode('utf-16-le', 'replace').rstrip('\0'), p + m, True


def wr_str(s):
    if s == '':
        return struct.pack('>i', 0)
    if any(ord(c) > 0x7F for c in s):
        d = (s + '\0').encode('utf-16-le')
        return struct.pack('>i', -(len(d) // 2)) + d
    d = (s + '\0').encode('latin1')
    return struct.pack('>i', len(d)) + d


# ── 태그된 속성 스트림 ────────────────────────────────────────────────
def rd_props(b, p, nm):
    out = []
    while True:
        ni, nn = struct.unpack_from('>2i', b, p)
        p += 8
        n = nm[ni] if 0 <= ni < len(nm) else '?%d' % ni
        if n == 'None':
            return out, p
        ti, tn = struct.unpack_from('>2i', b, p)
        p += 8
        t = nm[ti] if 0 <= ti < len(nm) else '?%d' % ti
        sz, ai = struct.unpack_from('>2i', b, p)
        p += 8
        ex = None
        if t in ('StructProperty', 'ByteProperty'):
            ex = struct.unpack_from('>2i', b, p)
            p += 8
        elif t == 'BoolProperty':
            ex = b[p]
            p += 1
        out.append(dict(ni=ni, nn=nn, name=n, ti=ti, tn=tn, type=t,
                        size=sz, ai=ai, extra=ex, val=bytes(b[p:p + sz])))
        p += sz


def wr_props(props):
    o = bytearray()
    for q in props:
        o += struct.pack('>2i', q['ni'], q['nn'])
        o += struct.pack('>2i', q['ti'], q['tn'])
        o += struct.pack('>2i', len(q['val']), q['ai'])
        if q['type'] in ('StructProperty', 'ByteProperty'):
            o += struct.pack('>2i', *q['extra'])
        elif q['type'] == 'BoolProperty':
            o += bytes([q['extra']])
        o += q['val']
    return bytes(o)


def none_tag(nm):
    return struct.pack('>2i', nm.index('None'), 0)


# ── 자막 배열 ─────────────────────────────────────────────────────────
def set_text(arr_val, nm, kr):
    """Subtitles 배열의 첫 원소 Text 를 kr 로. (개수·나머지 속성은 그대로)"""
    cnt = struct.unpack_from('>i', arr_val, 0)[0]
    p = 4
    o = bytearray(struct.pack('>i', cnt))
    for i in range(cnt):
        props, p2 = rd_props(arr_val, p, nm)
        if i == 0:
            for q in props:
                if q['name'] == 'Text':
                    q['val'] = wr_str(kr)
        o += wr_props(props) + none_tag(nm)
        p = p2
    assert p == len(arr_val), 'Subtitles 길이 %d != %d' % (p, len(arr_val))
    return bytes(o)


def set_localized(arr_val, nm, kr, lang='INT'):
    """언어별 엔트리 중 lang 것의 자막 Text 를 kr 로.

    ★★★INT 엔트리의 자막 배열이 «비어 있는» 패키지가 있다(JPN 엔 들어 있다).
      그 경우 다른 언어 엔트리의 원소를 «본»으로 삼아 만들어 넣는다.
      안 그러면 원소가 0개라 아무 일도 안 일어나고 자막이 영어(원문)로 남는다.
    """
    cnt = struct.unpack_from('>i', arr_val, 0)[0]
    # 1차 : 본이 될 원소 찾기
    tmpl = None
    langtmpl = None
    p = 4
    for _ in range(cnt):
        props, p2 = rd_props(arr_val, p, nm)
        if langtmpl is None and any(q['name'] == 'LanguageExt' for q in props):
            langtmpl = props
        for q in props:
            if q['name'] == 'Subtitles' and struct.unpack_from('>i', q['val'], 0)[0] > 0:
                el, _e = rd_props(q['val'], 4, nm)
                if tmpl is None:
                    tmpl = el
        p = p2
    # 2차 : 실제 교체
    p = 4
    o = bytearray(struct.pack('>i', cnt))
    hit = 0
    for _ in range(cnt):
        props, p2 = rd_props(arr_val, p, nm)
        ext = None
        for q in props:
            if q['name'] == 'LanguageExt':
                ext = rd_str(q['val'], 0)[0]
        if ext == lang:
            for q in props:
                if q['name'] != 'Subtitles':
                    continue
                if struct.unpack_from('>i', q['val'], 0)[0] > 0:
                    q['val'] = set_text(q['val'], nm, kr)
                elif tmpl is not None:
                    el = [dict(z) for z in tmpl]
                    for z in el:
                        if z['name'] == 'Text':
                            z['val'] = wr_str(kr)
                    q['val'] = struct.pack('>i', 1) + wr_props(el) + none_tag(nm)
                else:
                    continue
                hit += 1
        o += wr_props(props) + none_tag(nm)
        p = p2
    assert p == len(arr_val), 'LocalizedSubtitles 길이 %d != %d' % (p, len(arr_val))
    if not hit and langtmpl is not None:
        # ★INT 엔트리가 아예 없는 큐가 있다 — 다른 언어 엔트리를 복제해 «INT» 로 붙인다
        el = [dict(z) for z in langtmpl]
        for z in el:
            if z['name'] == 'LanguageExt':
                z['val'] = wr_str(lang)
            elif z['name'] == 'Subtitles':
                if tmpl is not None:
                    e2 = [dict(y) for y in tmpl]
                    for y in e2:
                        if y['name'] == 'Text':
                            y['val'] = wr_str(kr)
                    z['val'] = struct.pack('>i', 1) + wr_props(e2) + none_tag(nm)
        o += wr_props(el) + none_tag(nm)
        struct.pack_into('>i', o, 0, cnt + 1)
        hit = 1
    return bytes(o), hit


# ── 한글 대사 표 ──────────────────────────────────────────────────────
def load_kr():
    kr = {}
    for fn in sorted(os.listdir(INT)):
        if not fn.lower().startswith('vo_'):
            continue
        cur = None
        for ln in io.open(os.path.join(INT, fn), encoding='utf-16').read().splitlines():
            s = ln.strip()
            m = re.match(r'^\[(\S+) SoundNodeWave\]$', s)
            if m:
                cur = m.group(1)
                continue
            if cur and s.lower().startswith('subtitles[0]'):
                v = s.split('=', 1)[1].strip()
                m2 = re.match(r'^\(Text="(.*)"\)$', v, re.S)
                if m2:
                    kr[cur] = m2.group(1).replace(BS + '"', '"').replace(BS + BS, BS)
                cur = None
    return kr


# ── 패키지 하나 ───────────────────────────────────────────────────────
def do_pkg(path, kr, dry=False):
    S = Pkg(path)
    nm = S.names()
    if 'LocalizedSubtitles' not in nm:
        return None
    ex = S.exports(nm)
    # ★큐 이름이 꼭 숫자로 시작하지는 않는다(Dormouse_BossCine_End 같은 것)
    #   -> 한글 번역이 있는 export 는 전부 대상으로 삼는다
    cues = [e for e in ex if e['name'] in kr]
    if not cues:
        return None

    tails = {}
    blobs = []
    nrep = 0
    bad = []
    for e in ex:
        d = bytes(S.img[e['off']:e['off'] + e['size']])
        if e in cues:
            try:
                net = struct.unpack_from('>i', d, 0)[0]
                props, q = rd_props(d, 4, nm)
                tail = d[q:]
                txt = kr[e['name']]
                hit = 0
                for pr in props:
                    if pr['name'] == 'LocalizedSubtitles':
                        pr['val'], h = set_localized(pr['val'], nm, txt)
                        hit += h
                    elif pr['name'] == 'Subtitles':
                        pr['val'] = set_text(pr['val'], nm, txt)
                nd = struct.pack('>i', net) + wr_props(props) + none_tag(nm) + tail
                tails[len(blobs)] = len(nd) - len(tail)
                d = nd
                if hit:
                    nrep += 1
                if not hit:
                    bad.append('%s(INT엔트리없음)' % e['name'])
            except Exception as ex:
                bad.append('%s(%s)' % (e['name'], str(ex)[:30]))
                tails[len(blobs)] = None
        else:
            tails[len(blobs)] = None
        blobs.append(bytearray(d))

    # ── 배치 : 표는 그대로, 데이터만 다시 깐다
    ent = [bytearray(S.img[e['tbl']:e['tblend']]) for e in ex]
    start = min(e['off'] for e in ex)
    img = bytearray(S.img[:start])
    for j, b in enumerate(blobs):
        cur = len(img)
        # 꼬리의 벌크 오프셋 재계산
        tl = tails[j]
        if tl is None:
            # 원래 export : 꼬리 위치를 그대로 재계산해야 하므로 벌크를 훑는다
            tl = _tail_start(bytes(b), nm)
        if tl is not None and tl < len(b):
            _fix_bulk(b, tl, cur + tl)
        struct.pack_into('>2i', ent[j], 32, len(b), cur)
        img += b
    img[S.eoff:S.eoff + sum(len(x) for x in ent)] = b''.join(bytes(x) for x in ent)
    return S, img, nrep, len(cues), bad, set(e['name'] for e in cues)


def _tail_start(d, nm):
    try:
        _p, q = rd_props(d, 4, nm)
        return q
    except Exception:
        return None


def _fix_bulk(b, tl, absbase):
    q = tl
    while q + 16 <= len(b):
        f, c, s, o = struct.unpack_from('>4i', b, q)
        if s < 0 or q + 16 + s > len(b):
            break
        struct.pack_into('>i', b, q + 12, absbase + (q - tl) + 16)
        q += 16 + s


def write_pkg(S, img, dst):
    hdr = bytearray(S.raw[:S.chunks[0][2]])
    uo = S.chunks[0][0]
    us = len(img) - uo
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
    # ★청크가 여러 개면 표 칸 수를 맞춰야 한다 — 나머지 칸은 «빈 청크»로 채운다
    for k in range(1, len(S.chunks)):
        struct.pack_into('>4I', hdr, pos + k * 16, uo + us, 0, len(hdr) + len(ch), 0)
    out = bytes(hdr) + bytes(ch)
    if len(out) % BLK:
        out += bytes(BLK - len(out) % BLK)
    open(dst, 'wb').write(out)
    return len(out)


def main():
    kr = load_kr()
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(CK, '*_LOC_INT.XXX')))
    npkg = ncue = 0
    for f in files:
        try:
            r = do_pkg(f, kr)
        except Exception as ex:
            print('   ★%s : %s' % (os.path.basename(f), str(ex)[:70]))
            continue
        if r is None:
            continue
        S, img, nrep, ncues, bad, cueset = r
        dst = os.path.join(OUT, os.path.basename(f))
        sz = write_pkg(S, img, dst)
        # 검산 : 다시 읽어 자막이 한글인지
        C = Pkg(dst)
        cn = C.names()
        ce = C.exports(cn)
        okk = 0
        for e in ce:
            if e['name'] in cueset:
                d = bytes(C.img[e['off']:e['off'] + e['size']])
                if kr[e['name']][:6].encode('utf-16-le') in d:
                    okk += 1
        npkg += 1
        ncue += okk
        print('   %-42s 큐 %2d · 교체 %2d · 확인 %2d · %d B' %
              (os.path.basename(f), ncues, nrep, okk, sz))
        if okk != ncues:
            print('      ★확인 실패 %d개 %s' % (ncues - okk, bad[:4]))
    print('패키지 %d개 · 한글 확인된 대사 %d개 -> %s' % (npkg, ncue, OUT))


if __name__ == '__main__':
    main()
