# -*- coding: utf-8 -*-
"""LZO1X 해제 (순수 파이썬). UE3 PC 쿠킹 패키지가 쓴다(CompressionFlags=2).

⛔python-lzo 는 이 환경에 없다. minilzo 의 lzo1x_decompress 를 그대로 옮겼다.
★검산은 «해제 길이가 헤더가 말한 원본 크기와 같은가» + «이름표가 읽히는가» 로 한다.
"""


def decompress(src, outlen=None):
    out = bytearray()
    ip = 0

    def match(dist, length):
        s = len(out) - dist
        if s < 0:
            raise ValueError('LZO 거리 초과')
        for i in range(length):
            out.append(out[s + i])

    t = 0
    if src[ip] > 17:
        t = src[ip] - 17
        ip += 1
        if t < 4:
            state = 'match_next'
        else:
            out += src[ip:ip + t]; ip += t
            state = 'first_literal_run'
    else:
        state = 'top'

    while True:
        if state == 'top':
            t = src[ip]; ip += 1
            if t >= 16:
                state = 'match'; continue
            if t == 0:
                while src[ip] == 0:
                    t += 255; ip += 1
                t += 15 + src[ip]; ip += 1
            out += src[ip:ip + t + 3]; ip += t + 3
            state = 'first_literal_run'; continue

        if state == 'first_literal_run':
            t = src[ip]; ip += 1
            if t >= 16:
                state = 'match'; continue
            match(0x0801 + (t >> 2) + (src[ip] << 2), 3); ip += 1
            state = 'match_done'; continue

        if state == 'match':
            if t >= 64:
                d = 1 + ((t >> 2) & 7) + (src[ip] << 3); ip += 1
                match(d, (t >> 5) + 1)
            elif t >= 32:
                tt = t & 31
                if tt == 0:
                    while src[ip] == 0:
                        tt += 255; ip += 1
                    tt += 31 + src[ip]; ip += 1
                d = 1 + (src[ip] >> 2) + (src[ip + 1] << 6); ip += 2
                match(d, tt + 2)
            elif t >= 16:
                d = (t & 8) << 11
                tt = t & 7
                if tt == 0:
                    while src[ip] == 0:
                        tt += 255; ip += 1
                    tt += 7 + src[ip]; ip += 1
                d += (src[ip] >> 2) + (src[ip + 1] << 6); ip += 2
                if d == 0:
                    break                      # 스트림 끝
                match(d + 0x4000, tt + 2)
            else:
                d = 1 + (t >> 2) + (src[ip] << 2); ip += 1
                match(d, 2)
            state = 'match_done'; continue

        if state == 'match_done':
            t = src[ip - 2] & 3
            if t == 0:
                state = 'top'; continue
            state = 'match_next'; continue

        if state == 'match_next':
            out += src[ip:ip + t]; ip += t
            t = src[ip]; ip += 1
            state = 'match'; continue

    if outlen is not None and len(out) != outlen:
        raise ValueError('LZO 길이 불일치 %d != %d' % (len(out), outlen))
    return bytes(out)
