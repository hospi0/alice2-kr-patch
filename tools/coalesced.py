# -*- coding: utf-8 -*-
"""UE3 Coalesced(.BIN) 읽기/쓰기 — PS3(빅엔디언) 판.

포맷 (실측으로 확정 · 파싱 끝 오프셋이 파일 크기와 정확히 일치)
    u32 파일수
    파일마다 : FString 경로 · u32 섹션수
        섹션마다 : FString 이름 · u32 키수
            키마다 : FString 키 · FString 값
FString = i32 길이(빅엔디언).
    양수 n  -> 8비트 n바이트(NUL 포함)
    음수 n  -> UTF-16 (-n)문자 (NUL 포함) · ★문자 데이터는 «리틀엔디언»이다
★검산은 «무수정 왕복이 바이트 동일»로 한다.
"""
import struct


class Coalesced(object):
    def __init__(self, data):
        self.d = data
        self.p = 0
        self.files = []          # [(경로, wide?, [(섹션명, wide?, [(키, wide?, 값, wide?)])])]
        self._parse()

    # ── 읽기 ────────────────────────────────────────────────
    def _i32(self):
        v = struct.unpack_from('>i', self.d, self.p)[0]
        self.p += 4
        return v

    def _s(self):
        n = self._i32()
        if n == 0:
            return '', False
        if n > 0:
            b = self.d[self.p:self.p + n]; self.p += n
            return b.rstrip(b'\0').decode('latin1'), False
        m = -n * 2
        b = self.d[self.p:self.p + m]; self.p += m
        return b.decode('utf-16-le', 'replace').rstrip('\0'), True

    def _parse(self):
        for _ in range(self._i32()):
            path, pw = self._s()
            secs = []
            for _ in range(self._i32()):
                sn, sw = self._s()
                kv = []
                for _ in range(self._i32()):
                    k, kw = self._s()
                    v, vw = self._s()
                    kv.append([k, kw, v, vw])
                secs.append([sn, sw, kv])
            self.files.append([path, pw, secs])
        assert self.p == len(self.d), '★파싱 끝 0x%X != 파일 0x%X' % (self.p, len(self.d))

    # ── 쓰기 ────────────────────────────────────────────────
    @staticmethod
    def _es(s, wide):
        if s == '' and not wide:
            return struct.pack('>i', 0)
        if wide or any(ord(c) > 0x7F for c in s):
            b = (s + '\0').encode('utf-16-le')
            return struct.pack('>i', -(len(b) // 2)) + b
        b = (s + '\0').encode('latin1')
        return struct.pack('>i', len(b)) + b

    def build(self):
        o = bytearray()
        o += struct.pack('>i', len(self.files))
        for path, pw, secs in self.files:
            o += self._es(path, pw)
            o += struct.pack('>i', len(secs))
            for sn, sw, kv in secs:
                o += self._es(sn, sw)
                o += struct.pack('>i', len(kv))
                for k, kw, v, vw in kv:
                    o += self._es(k, kw)
                    o += self._es(v, vw)
        return bytes(o)


def load(path):
    return Coalesced(open(path, 'rb').read())
