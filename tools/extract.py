# -*- coding: utf-8 -*-
"""앨리스 매드니스 리턴즈 PS3 번역 대상 추출 (2026-11-11).

원본(읽기만) : 디스크판 BLUS30607 PS3_GAME\\USRDIR\\ALICEGAME (아래 ORIG)
              PSN 판 NPUB30545(ORIG_PSN)와 문장 동일 — 디스크로 바꾼 뒤 all.tsv 바이트 동일 확인

출처 두 갈래
  C  COOKEDPS3/COALESCED_INT.BIN 의 *.int  — 위치 = C|<int파일>|<섹션>|<키>
  S  COOKEDPS3/*_LOC_INT.XXX 의 SoundNodeWave.LocalizedSubtitles[INT].Subtitles[i].Text
                                           — 위치 = S|<웨이브이름>|<i>
     ★언어별 패키지(_LOC_DEU 등)에도 6개 언어가 다 구워져 있지만 엔진은 INT 엔트리를 읽는다.
     ★같은 웨이브가 여러 패키지에 있어도 INT 문장은 전부 같다(검산함) → 한 번만.
  MOVIES/*.TXT 는 «시각 + Subtitles.int 키»뿐이라 번역 대상 아님.

산출
  work/text/all.tsv   : 위치 · 꾸러미 · EN · KO        (출현마다 한 줄 — 재삽입 기준)
  work/text/uniq.tsv  : EN · 출현수 · 첫위치 · KO      (같은 원문 한 번)
  my files/tsv/<꾸러미>_NNN.tsv : 번호 · 위치 · EN · KO — UTF-8 18KB(머리줄 포함) 단위
      꾸러미 = ui(GFxUI·AliceGame) · movie(Subtitles.int) · voice(음성 대사) · engine(엔진 .int)
      순서 = 플레이어가 먼저 보는 것부터.

표기 : 원문 줄바꿈은 «\\n» 두 글자로 적는다(원문 토큰 — 번역에도 그대로).
검산 : coalesced 무수정 재직렬화가 원본과 바이트 동일한지.
python tools/extract.py
"""
import os, sys, re, glob, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coalesced import load as load_coal
from ue3pkg import Pkg
from build_subs import rd_props, rd_str

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 기준 = 디스크판 BLUS30607 (2026-11-11 하스피 «패치 적용은 디스크로»). PSN NPUB30545 와 문장 2,854곳 동일,
# 차이는 .ini IniVersion 시각과 패키지 머리 0x68 한 바이트(디스크 0x67 / PSN 0x69)뿐 — 빌더는 «대상 판 원본»을 읽어 고칠 것.
# ★게임 폴더(D:\hospi\rpcs3\games\Alice - Madness Returns (USA)\Alice - Madness Returns (USA)\PS3_GAME)는
#   시험 설치로 덮인다 → 패치 대상 174개를 work/orig_disc 에 떠 둔 «깨끗한 사본»(md5_disc.txt)을 기준으로 읽는다.
ORIG = os.path.join(ROOT, 'work', 'orig_disc')
ORIG_PSN = r'C:\claude\utils\한글화 이식\Alice2\NPUB30545 PS3 files\USRDIR\ALICEGAME'
CK = os.path.join(ORIG, 'COOKEDPS3')
SPLIT = 18 * 1024
HAS_TEXT = re.compile('[A-Za-z]')

UI_FILES = ('GFxUI.int', 'AliceGame.int')
MOVIE_FILES = ('Subtitles.int',)


def esc(s):
    if '\t' in s:
        raise SystemExit('탭 든 원문: %r' % s[:60])
    return s.replace('\r\n', '\n').replace('\n', '\\n')


ENGINE_KEEP = {('PS3.int', 'General'), ('Engine.int', 'Progress'), ('Engine.int', 'General')}


def bundle_of(intname, path, sec, key, val):
    """credits = 스태프 롤(⛔허락 전 번역 금지) · skip = PS3 화면에 안 나오는 엔진·개발 문구."""
    if intname == 'GFxUI.int' and sec in ('FontLib', 'Fonts', 'IME'):
        return 'uiskip'                       # 글꼴 이름·경로 설정값 — 번역 금지(번호는 ui 자리 유지)
    if 'AliceGame' in path and intname in UI_FILES:
        if key.startswith('FlashUI_ExtraContent_Credits') and key not in (
                'FlashUI_ExtraContent_Credits', 'FlashUI_ExtraContent_CreditsDescription'):
            return 'credits'
        return 'ui'
    if 'AliceGame' in path and intname in MOVIE_FILES:
        return 'movie'
    if (intname, sec) in ENGINE_KEEP and not val.startswith('('):
        return 'engine'
    return 'skip'


def coal_rows():
    src = os.path.join(CK, 'COALESCED_INT.BIN')
    raw = open(src, 'rb').read()
    C = load_coal(src)
    assert C.build() == raw, '★coalesced 무수정 왕복 불일치'
    rows = []
    for path, _pw, secs in C.files:
        if not path.lower().endswith('.int'):
            continue
        fn = path.replace('/', '\\').split('\\')[-1]
        for sec, _sw, kv in secs:
            for k, _kw, v, _vw in kv:
                if not HAS_TEXT.search(v):
                    continue
                b = bundle_of(fn, path, sec, k, v)
                rows.append(('C|%s|%s|%s' % (fn, sec, k), b, esc(v)))
    return rows


def _imports(S, nm):
    b = S.img; p = S.ioff; out = []
    for _ in range(S.icnt):
        v = struct.unpack_from('>7i', b, p); p += 28
        out.append(nm[v[5]])
    return out


def _subarr(v, nm):
    n = struct.unpack_from('>i', v, 0)[0]; p = 4; r = []
    for _ in range(n):
        el, p = rd_props(v, p, nm)
        t = [rd_str(y['val'], 0)[0] for y in el if y['name'] == 'Text']
        r.append(t[0] if t else '')
    return r


def voice_rows():
    seen = collections.OrderedDict()   # 웨이브 -> [줄]
    clash = []
    for f in sorted(glob.glob(os.path.join(CK, '*_LOC_INT.XXX'))):
        S = Pkg(f); nm = S.names()
        if 'LocalizedSubtitles' not in nm:
            continue
        im = _imports(S, nm)
        for e in S.exports(nm):
            c = e['cls']
            if c >= 0 or im[-c - 1] != 'SoundNodeWave':
                continue
            d = bytes(S.img[e['off']:e['off'] + e['size']])
            props, _q = rd_props(d, 4, nm)
            lines = None
            for pr in props:
                if pr['name'] != 'LocalizedSubtitles':
                    continue
                v = pr['val']; n = struct.unpack_from('>i', v, 0)[0]; p = 4
                for _ in range(n):
                    lp, p = rd_props(v, p, nm)
                    ext = None; sub = None
                    for z in lp:
                        if z['name'] == 'LanguageExt':
                            ext = rd_str(z['val'], 0)[0]
                        elif z['name'] == 'Subtitles':
                            sub = z['val']
                    if ext == 'INT' and sub is not None:
                        lines = _subarr(sub, nm)
            if not lines or not any(HAS_TEXT.search(t) for t in lines):
                continue
            if e['name'] in seen:
                if seen[e['name']] != lines:
                    clash.append(e['name'])
                continue
            seen[e['name']] = lines
    if clash:
        raise SystemExit('★같은 웨이브인데 INT 문장이 다름: %s' % clash[:5])
    rows = []
    for w, lines in seen.items():
        for i, t in enumerate(lines):
            if HAS_TEXT.search(t):
                rows.append(('S|%s|%d' % (w, i), 'voice', esc(t)))
    return rows


def write_split(folder, stem, head, lines):
    chunks = []; cur = []; hb = len(head.encode('utf-8')); size = hb
    for ln in lines:
        n = len(ln.encode('utf-8'))
        if cur and size + n > SPLIT:
            chunks.append(cur); cur = []; size = hb
        cur.append(ln); size += n
    if cur:
        chunks.append(cur)
    for i, c in enumerate(chunks, 1):
        with open(os.path.join(folder, '%s_%03d.tsv' % (stem, i)), 'w', encoding='utf-8', newline='\n') as w:
            w.write(head + ''.join(c))
    return len(chunks)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = coal_rows() + voice_rows()
    order = {'ui': 0, 'uiskip': 0, 'movie': 1, 'voice': 2, 'engine': 3, 'credits': 4, 'skip': 5}
    rows.sort(key=lambda r: order[r[1]])          # 안정 정렬 — 꾸러미 안 순서는 원본 순서
    tdir = os.path.join(ROOT, 'work', 'text'); os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, 'all.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('위치\t꾸러미\tEN\tKO\n')
        for at, b, en in rows:
            w.write('%s\t%s\t%s\t\n' % (at, b, en))
    uniq = collections.OrderedDict()
    for at, b, en in rows:
        u = uniq.setdefault(en, [0, at, b]); u[0] += 1
    with open(os.path.join(tdir, 'uniq.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('EN\t출현수\t첫위치\tKO\n')
        for en, (n, at, b) in uniq.items():
            w.write('%s\t%d\t%s\t\n' % (en, n, at))
    out = os.path.join(ROOT, 'my files', 'tsv'); os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.tsv')):
        os.remove(f)
    no = 0; per = collections.OrderedDict()
    for en, (n, at, b) in uniq.items():
        no += 1
        # 엔진 자투리는 ui 끝에 합침
        per.setdefault('ui' if b == 'engine' else b, []).append('%05d\t%s\t%s\t\n' % (no, at, en))
    print('출현 %d줄 · 고유 %d줄' % (len(rows), len(uniq)))
    for b, lines in per.items():
        if b in ('credits', 'skip', 'uiskip'):   # TSV 로 내보내지 않음(all/uniq 에는 남김)
            print('  %-7s 고유 %5d줄 — TSV 제외' % (b, len(lines)))
            continue
        words = sum(len(l.split('\t')[2].split()) for l in lines)
        nf = write_split(out, b, '번호\t위치\tEN\tKO\n', lines)
        print('  %-7s 고유 %5d줄 · 낱말 %6d · 파일 %d개' % (b, len(lines), words, nf))


if __name__ == '__main__':
    main()
