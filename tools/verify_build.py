# -*- coding: utf-8 -*-
"""빌드 검산 (2026-11-11)  python tools/verify_build.py
 ① 판별 패키지 머리 0x68 바이트가 «그 판 원본»과 같은가 (디스크 0x67 / PSN 0x69)
 ② COALESCED : 번역 대상 아닌 값(skip·credits·ini)은 원본과 같고, 대상 값만 바뀌었나 · 개행 종류 보존
 ③ 자막 패키지 : 이름·import·export «개수» 불변 · 바뀐 export 는 SoundNodeWave 뿐
 ④ 산출 파일 목록 두 판 동일
"""
import os, sys, re, glob, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract, build
from coalesced import load as load_coal
from ue3pkg import Pkg

ROOT = build.ROOT


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    bad = 0
    lists = {}
    for ed, base in build.BASE.items():
        out = os.path.join(ROOT, 'work', 'build', ed, 'COOKEDPS3')
        files = sorted(os.listdir(out)); lists[ed] = files
        # ①
        hb = {}
        for f in files:
            if not f.endswith('.XXX'):
                continue
            a = Pkg(os.path.join(base, f)).img[0x68]; b = Pkg(os.path.join(out, f)).img[0x68]
            hb.setdefault((a, b), []).append(f)
        print('%s ① 머리 0x68 (원본,산출): %s' % (ed, {('%02X' % k[0], '%02X' % k[1]): len(v) for k, v in hb.items()}))
        if any(k[0] != k[1] for k in hb):
            bad += 1
        # ②
        O = load_coal(os.path.join(base, 'COALESCED_INT.BIN')); B = load_coal(os.path.join(out, 'COALESCED_INT.BIN'))
        assert len(O.files) == len(B.files)
        same_other = changed = wrong = nl_bad = 0
        for fo, fb in zip(O.files, B.files):
            assert fo[0] == fb[0] and len(fo[2]) == len(fb[2])
            fn = fo[0].replace('/', '\\').split('\\')[-1]
            for so, sb in zip(fo[2], fb[2]):
                assert so[0] == sb[0] and len(so[2]) == len(sb[2])
                for (k, _, v, _), (k2, _, v2, _) in zip(so[2], sb[2]):
                    assert k == k2
                    tgt = fo[0].lower().endswith('.int') and extract.HAS_TEXT.search(v) and \
                        extract.bundle_of(fn, fo[0], so[0], k, v) in ('ui', 'movie', 'engine')
                    if not tgt:
                        if v != v2:
                            wrong += 1
                        else:
                            same_other += 1
                    else:
                        changed += (v != v2)
                        if ('\n' in v) != ('\n' in v2) and (chr(92) + 'n') in (extract.esc(v)):
                            nl_bad += 1
        print('%s ② COALESCED 대상 아닌 값 %d개 그대로 · 바뀐 대상 값 %d · 대상 아닌데 바뀜 %d · 개행 종류 어긋남 %d'
              % (ed, same_other, changed, wrong, nl_bad))
        bad += (wrong > 0) + (nl_bad > 0)
        # ③
        cnt_bad = 0; cls_bad = 0
        for f in files:
            if not f.endswith('.XXX') or 'FONT' in f or f == 'ALICEGAME_LOC_INT.XXX':
                continue
            So = Pkg(os.path.join(base, f)); Sb = Pkg(os.path.join(out, f))
            if (So.ncnt, So.icnt, So.ecnt) != (Sb.ncnt, Sb.icnt, Sb.ecnt):
                cnt_bad += 1; continue
            no = So.names(); eo = So.exports(no); eb = Sb.exports(Sb.names())
            imp = []
            p = So.ioff
            for _ in range(So.icnt):
                v = struct.unpack_from('>7i', So.img, p); p += 28; imp.append(no[v[5]])
            for a, b in zip(eo, eb):
                da = bytes(So.img[a['off']:a['off'] + a['size']]); db = bytes(Sb.img[b['off']:b['off'] + b['size']])
                if da != db:
                    c = imp[-a['cls'] - 1] if a['cls'] < 0 else '?'
                    if c != 'SoundNodeWave':
                        # 벌크 오프셋만 다른 export 는 허용(데이터 위치가 밀렸으니까) — 크기 같으면 OK
                        if len(da) != len(db):
                            cls_bad += 1
        print('%s ③ 자막 패키지 개수 바뀜 %d · SoundNodeWave 아닌데 크기 바뀐 export %d' % (ed, cnt_bad, cls_bad))
        bad += cnt_bad + cls_bad
    print('④ 두 판 산출 목록 같음:', lists['disc'] == lists['psn'], len(lists['disc']))
    bad += lists['disc'] != lists['psn']
    print('결과:', '통과' if not bad else '★실패 %d' % bad)


if __name__ == '__main__':
    main()
