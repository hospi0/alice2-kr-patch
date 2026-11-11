# -*- coding: utf-8 -*-
"""UE3 오브젝트 «속성 스트림» 읽기/쓰기 (LE/BE 공용).

배치 :  i32 NetIndex
        속성마다 : FName 이름(i32,i32) · FName 형(i32,i32) · i32 크기 · i32 배열첨자
                   [StructProperty 면 FName 구조체이름] [ByteProperty 면 FName 열거형]
                   [BoolProperty 면 «크기 0» 이고 값 u8 이 따로 온다]
                   그 뒤 크기만큼 값
        FName None 으로 끝 · 그 뒤는 «클래스 고유 이진»(Texture2D 의 밉 등)
"""
import struct


def read(img, off, size, names, e, boolsz=1):
    p = off
    net = struct.unpack_from(e + 'i', img, p)[0]; p += 4
    props = []
    end = off + size
    while True:
        if p + 8 > end:
            raise ValueError('속성 스트림이 export 를 넘었다 (p=0x%X end=0x%X)' % (p, end))
        ni, nn = struct.unpack_from(e + '2i', img, p); p += 8
        nm = names[ni] if 0 <= ni < len(names) else '?%d' % ni
        if nm == 'None':
            break
        ti, tn = struct.unpack_from(e + '2i', img, p); p += 8
        tp = names[ti] if 0 <= ti < len(names) else '?%d' % ti
        sz, ai = struct.unpack_from(e + '2i', img, p); p += 8
        extra = None
        if tp == 'StructProperty':
            extra = struct.unpack_from(e + '2i', img, p); p += 8
        elif tp == 'ByteProperty':
            extra = struct.unpack_from(e + '2i', img, p); p += 8
        elif tp == 'BoolProperty':
            extra = img[p]; p += boolsz      # ★PC(v648)=4바이트 · PS3(v690)=1바이트 (실측)
        if sz < 0 or p + sz > end:
            raise ValueError('속성 %s 크기 이상 %d' % (nm, sz))
        val = bytes(img[p:p + sz]); p += sz
        props.append(dict(name=nm, ni=ni, nn=nn, type=tp, ti=ti, tn=tn,
                          size=sz, ai=ai, extra=extra, val=val))
    tail = bytes(img[p:off + size])
    return net, props, tail


def write(net, props, tail, nidx, e):
    """nidx = 이름 -> 색인 함수."""
    o = bytearray()
    o += struct.pack(e + 'i', net)
    for pr in props:
        o += struct.pack(e + '2i', nidx(pr['name']), pr['nn'])
        o += struct.pack(e + '2i', nidx(pr['type']), pr['tn'])
        o += struct.pack(e + '2i', pr['size'], pr['ai'])
        if pr['type'] in ('StructProperty', 'ByteProperty'):
            o += struct.pack(e + '2i', nidx(pr['exname']), pr['extra'][1])
        elif pr['type'] == 'BoolProperty':
            o += bytes([pr['extra']])
        o += pr['val']
    o += struct.pack(e + '2i', nidx('None'), 0)
    o += tail
    return bytes(o)
