# -*- coding: utf-8 -*-
"""PC(리틀엔디언) UE3 패키지 해제 — LZO/zlib 둘 다. 청크 표는 «이름표 오프셋»으로 앵커링한다.

⛔청크 표를 «매직이 보이는 첫 자리»로 찾으면 오탐이 난다(실측: 1개만 잡혀 67MB 이미지).
★첫 청크의 원본오프셋은 «NameOffset» 과 같다 — 압축은 거기서 시작한다. 그걸 앵커로 쓴다.
"""
import struct, zlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lzo1x


def load(path):
    d = open(path, 'rb').read()
    be = d[:4] == bytes([0x9e, 0x2a, 0x83, 0xc1])
    e = '>' if be else '<'
    mg = bytes([0x9e, 0x2a, 0x83, 0xc1]) if be else bytes([0xc1, 0x83, 0x2a, 0x9e])
    p = 4
    ver = struct.unpack_from(e + 'I', d, p)[0] & 0xFFFF; p += 4
    p += 4                                     # header size
    n = struct.unpack_from(e + 'i', d, p)[0]; p += 4 + (n if n > 0 else -n * 2)
    p += 4                                     # package flags
    ncnt, noff, ecnt, eoff, icnt, ioff = struct.unpack_from(e + '6I', d, p)
    best = []
    for base in range(0x30, 0x400):
        uo, us, co, cs = struct.unpack_from(e + '4I', d, base)
        if uo != noff:                         # ★앵커
            continue
        out, q = [], base
        while q + 16 <= len(d):
            uo, us, co, cs = struct.unpack_from(e + '4I', d, q)
            if not (0 < us < 0x10000000 and co + 4 <= len(d) and d[co:co + 4] == mg):
                break
            if out and uo != out[-1][0] + out[-1][1]:
                break                          # 연속이어야 한다
            out.append((uo, us, co, cs)); q += 16
        if len(out) > len(best):
            best = out
    img = bytearray(best[-1][0] + best[-1][1]) if best else bytearray(d)
    if best:
        img[:best[0][0]] = d[:best[0][0]]
        for uo, us, co, cs in best:
            m, blk, c2, u2 = struct.unpack_from(e + '4I', d, co); q = co + 16
            nb = (u2 + blk - 1) // blk
            sz = [struct.unpack_from(e + '2I', d, co + 16 + i * 8) for i in range(nb)]
            q = co + 16 + nb * 8
            o = bytearray()
            for c, u in sz:
                blob = d[q:q + c]; q += c
                o += (zlib.decompress(blob) if blob[:1] == b'\x78' else lzo1x.decompress(blob, u))
            img[uo:uo + us] = o
    return dict(raw=d, img=bytes(img), be=be, e=e, ver=ver, ncnt=ncnt, noff=noff,
                ecnt=ecnt, eoff=eoff, icnt=icnt, ioff=ioff, chunks=best)


def names(P):
    img, e, p, out = P['img'], P['e'], P['noff'], []
    for _ in range(P['ncnt']):
        n = struct.unpack_from(e + 'i', img, p)[0]; p += 4
        if n > 0:
            out.append(img[p:p + n].rstrip(b'\0').decode('latin1')); p += n
        else:
            out.append(img[p:p - n * 2].decode('utf-16-le').rstrip('\0')); p += -n * 2
        p += 8
    return out


def exports(P, nm):
    img, e, p, out = P['img'], P['e'], P['eoff'], []
    for _ in range(P['ecnt']):
        st = p
        cls, sup, outer, nmi, nnum, arch = struct.unpack_from(e + '6i', img, p); p += 24
        p += 8
        size, off = struct.unpack_from(e + '2I', img, p); p += 8
        p += 4
        nnet = struct.unpack_from(e + 'I', img, p)[0]; p += 4 + nnet * 4
        p += 16 + 4
        out.append(dict(name=nm[nmi] if 0 <= nmi < len(nm) else '?', cls=cls,
                        size=size, off=off, tbl=st, size_at=st + 32, off_at=st + 36))
    return out
