# -*- coding: utf-8 -*-
"""UE3 패키지(.upk / .xxx) 헤더·압축청크 파서. PC=리틀엔디언 · PS3=빅엔디언.

압축 패키지의 «파일 위 배치»
    [원본 헤더 + CompressedChunks 배열]  ← 여기까지 비압축
    [청크 0][청크 1]...                   ← 각 청크 = FCompressedChunkHeader + 64KB 블록들
헤더 안의 NameOffset/ExportOffset 등은 «압축 풀린 원본 이미지» 기준이다.
청크의 UncompressedOffset 이 그 이미지에서의 자리다.
"""
import struct, zlib


class Pkg(object):
    def __init__(self, path):
        self.raw = open(path, 'rb').read()
        tag = self.raw[:4]
        self.be = (tag == b'\x9e\x2a\x83\xc1')
        if not self.be and tag != b'\xc1\x83\x2a\x9e':
            raise ValueError('UE3 패키지가 아니다')
        self.e = '>' if self.be else '<'
        self.p = 4
        self.ver = self.u32() & 0xFFFF
        self.hdrsize = self.u32()
        self.folder = self.fstr()
        self.flags = self.u32()
        self.ncnt, self.noff = self.u32(), self.u32()
        self.ecnt, self.eoff = self.u32(), self.u32()
        self.icnt, self.ioff = self.u32(), self.u32()
        self.chunks = self._find_chunks()
        if self.chunks:
            # ★청크 표를 «실제로 풀어 보고» 확정한다 — 표 모양만 맞는 오탐이 있다(PC .upk).
            try:
                self._chunk_data(self.chunks[0][2])
            except Exception:
                self.chunks = []
        self.img = self._image()

    # ── 원시 읽기 ────────────────────────────────────────────
    def u32(self, buf=None, off=None):
        b = self.raw if buf is None else buf
        if off is None:
            v = struct.unpack_from(self.e + 'I', b, self.p)[0]; self.p += 4; return v
        return struct.unpack_from(self.e + 'I', b, off)[0]

    def fstr(self, buf=None):
        b = self.raw if buf is None else buf
        n = struct.unpack_from(self.e + 'i', b, self.p)[0]; self.p += 4
        if n == 0:
            return ''
        if n > 0:
            s = b[self.p:self.p + n]; self.p += n
            return s.rstrip(b'\0').decode('latin1')
        m = -n * 2
        s = b[self.p:self.p + m]; self.p += m
        return s.decode('utf-16-le', 'replace').rstrip('\0')

    # ── 압축 청크 ────────────────────────────────────────────
    def _find_chunks(self):
        """CompressedChunks = (원본오프셋, 원본크기, 파일오프셋, 압축크기) 나열.
        ★UE3 헤더는 4바이트 정렬이 아니다(폴더명 길이 때문) — «1바이트 단위»로 찾아야 한다.
        ★확정 기준 = 파일오프셋 자리에 «청크 매직»이 실제로 있고, 그게 2개 이상 연속."""
        mg = bytes([0x9e,0x2a,0x83,0xc1]) if self.be else bytes([0xc1,0x83,0x2a,0x9e])
        best = []
        for base in range(0x30, min(0x400, len(self.raw)) - 16):
            out, p = [], base
            while p + 16 <= len(self.raw):
                uo, us, co, cs = struct.unpack_from(self.e + '4I', self.raw, p)
                ok = (0 < us < 0x10000000 and 0 < cs < len(self.raw)
                      and 16 < co < len(self.raw) - 16 and self.raw[co:co + 4] == mg)
                if ok:
                    # ★청크 머리(FCompressedChunkHeader)까지 대조해야 오탐이 없다
                    _m, blk, csum, usum = struct.unpack_from(self.e + '4I', self.raw, co)
                    ok = (blk in (0x8000, 0x10000, 0x20000) and usum == us)
                if not ok:
                    break
                out.append((uo, us, co, cs)); p += 16
            if len(out) > len(best):
                best = out
        return best

    def _chunk_data(self, co):
        p = co
        mg, blk, csum, usum = struct.unpack_from(self.e + '4I', self.raw, p); p += 16
        nb = (usum + blk - 1) // blk
        sizes = []
        for _ in range(nb):
            c, u = struct.unpack_from(self.e + '2I', self.raw, p); p += 8
            sizes.append((c, u))
        out = bytearray()
        for c, u in sizes:
            blob = self.raw[p:p + c]; p += c
            # ★압축이 이득이 없는 블록은 «그대로» 저장된다(압축크기 == 원본크기)
            out += (bytes(blob) if c == u else zlib.decompress(blob))
        assert len(out) == usum, '청크 길이 불일치'
        return bytes(out), blk

    def _image(self):
        if not self.chunks:
            return bytearray(self.raw)
        end = max(uo + us for uo, us, co, cs in self.chunks)
        img = bytearray(end)
        img[:self.chunks[0][0]] = self.raw[:self.chunks[0][0]]
        for uo, us, co, cs in self.chunks:
            d, _ = self._chunk_data(co)
            img[uo:uo + us] = d
        return img

    # ── 표 ──────────────────────────────────────────────────
    def names(self):
        self.p = self.noff
        out = []
        for _ in range(self.ncnt):
            nm = self.fstr(self.img)
            self.p += 8                      # flags(u64)
            out.append(nm)
        return out

    def exports(self, names):
        """FObjectExport (v690) — 컴포넌트맵 없음.
        cls·sup·outer·이름(idx,num)·archetype·flags(u64)·SerialSize·SerialOffset
        ·ExportFlags·NetObjectCount[]·GUID(16)·PackageFlags
        ★검산 : SerialOffset+SerialSize 가 이미지 안이고 오름차순인가."""
        b = self.img
        self.p = self.eoff
        out = []
        for _ in range(self.ecnt):
            st = self.p
            g = lambda: struct.unpack_from(self.e + 'i', b, self.p)[0]
            cls = g(); self.p += 4
            sup = g(); self.p += 4
            outer = g(); self.p += 4
            nmi = g(); self.p += 4
            self.p += 4                       # name number
            arch = g(); self.p += 4
            self.p += 8                       # object flags (u64)
            size = g(); self.p += 4
            off = g(); self.p += 4
            expflags_at = self.p
            self.p += 4                       # export flags
            nnet = struct.unpack_from(self.e + 'I', b, self.p)[0]; self.p += 4
            self.p += nnet * 4
            self.p += 16                      # guid
            self.p += 4                       # package flags
            out.append(dict(cls=cls, name=names[nmi] if 0 <= nmi < len(names) else '?',
                            size=size, off=off, tbl=st, tblend=self.p,
                            size_at=st + 32, off_at=st + 36))
        for e in out:
            assert 0 <= e['off'] and e['off'] + e['size'] <= len(b), '★export 범위 밖 %r' % e
        return out
