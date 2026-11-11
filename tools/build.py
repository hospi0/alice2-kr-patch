# -*- coding: utf-8 -*-
"""앨리스 매드니스 리턴즈 PS3 한글 빌드 (2026-11-11) — 디스크판·PSN 판을 «각자의 원본»에서 따로 만든다.

  python tools/build.py [disc|psn|all]      (기본 all)

입력  work/text/ko.tsv (tools/merge_ko.py 산출 — 먼저 돌릴 것)
기준  disc = work/orig_disc/COOKEDPS3 (BLUS30607 깨끗한 사본, md5_disc.txt)
      psn  = C:\\claude\\utils\\한글화 이식\\Alice2\\NPUB30545 PS3 files\\USRDIR\\ALICEGAME\\COOKEDPS3
      ⛔한 판으로 만든 파일을 다른 판에 덮지 말 것 — 패키지 머리 0x68 (디스크 0x67 / PSN 0x69), ini IniVersion 이 다르다.
산출  work/build/<판>/COOKEDPS3/
  COALESCED_INT.BIN        .int 값 한글(ui·movie·engine 꾸러미). 원본이 «진짜 개행»이던 값만 \\n → 개행.
  *_LOC_INT.XXX (자막)     SoundNodeWave.LocalizedSubtitles[INT] 의 Text 를 줄(순번)마다 교체
  ALICEFONTS.XXX           GFx fonts_en ← PC 한글패치 한글 GFx 글꼴(글꼴만 — 번역 문장은 안 씀)
  ALICEGAME_LOC_INT.XXX · ALICEFONTS_LOC_INT.XXX   UE3 UFont WarfareFonts_Chrom20 ← PC 한글패치 글꼴
글꼴 : 번역 음절 1,043종 전부 두 글꼴에 있음(tools/font_cover.py). UE3 글꼴엔 «…» 가 없어서
       UE3 로 그리는 줄(음성 자막·Subtitles.int)은 «…» → «...»
공백 : 문장부호 뒤 공백은 지우지 않는다(가변폭 글꼴 — 2026-11-11 하스피 «공백 두고»).
"""
import os, sys, re, glob, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract
from coalesced import load as load_coal
from ue3pkg import Pkg
import build_subs, build_font, build_locfont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = r'C:\claude\utils\한글화 이식\Alice2'
PCPATCH = os.path.join(PORT, 'Alice2_KOR PC Patch', 'Game', 'Alice2', 'AliceGame', 'CookedPC')
BASE = {
    'disc': os.path.join(ROOT, 'work', 'orig_disc', 'COOKEDPS3'),
    'psn': os.path.join(PORT, 'NPUB30545 PS3 files', 'USRDIR', 'ALICEGAME', 'COOKEDPS3'),
}
N = chr(92) + 'n'


def load_ko():
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'ko.tsv'), encoding='utf-8')][1:]
    by_en = {}
    subs = collections.defaultdict(dict)
    for no, at, en, ko in rows:
        by_en[en] = ko
        if at.startswith('S|'):
            _, w, i = at.split('|')
            subs[w][int(i)] = ko
    # ko.tsv 는 같은 영문을 한 줄(첫 위치)로 합쳐 둔다 → 같은 문장을 쓰는 다른 웨이브 자막이 영어로 남았음
    # (2026-11-12 제보 «Killed her family!» S|1_1_H_Dred, 체셔 수수께끼 등 16큐). all.tsv 의 S| 위치 전부를 영문으로 채움.
    for l in open(os.path.join(ROOT, 'work', 'text', 'all.tsv'), encoding='utf-8').read().splitlines()[1:]:
        f = l.split('\t')
        if len(f) < 3 or not f[0].startswith('S|'): continue
        _, w, i = f[0].split('|')
        if int(i) not in subs[w]:
            if f[2] not in by_en: raise SystemExit('자막 번역 없음: %s %s' % (f[0], f[2]))
            subs[w][int(i)] = by_en[f[2]]
    return rows, by_en, subs


def ue3_text(s):
    """UE3 UFont 로 그리는 줄 — 글꼴에 «…» 가 없다."""
    return s.replace('…', '...')


# ── COALESCED ─────────────────────────────────────────────────────────
def build_coal(base, out, by_en):
    src = os.path.join(base, 'COALESCED_INT.BIN')
    C = load_coal(src)
    n = 0; miss = []
    for path, _pw, secs in C.files:
        if not path.lower().endswith('.int'):
            continue
        fn = path.replace('/', '\\').split('\\')[-1]
        for sec, _sw, kv in secs:
            for item in kv:
                k, _kw, v, _vw = item
                if not extract.HAS_TEXT.search(v):
                    continue
                b = extract.bundle_of(fn, path, sec, k, v)
                if b not in ('ui', 'movie', 'engine'):
                    continue
                key = extract.esc(v)
                if key not in by_en:
                    miss.append('%s|%s|%s' % (fn, sec, k)); continue
                ko = by_en[key]
                if '\n' in v:                       # 원본이 진짜 개행이던 값만
                    ko = ko.replace(N, '\n')
                if b == 'movie':
                    ko = ue3_text(ko)
                item[2] = ko; item[3] = True
                n += 1
    if miss:
        raise SystemExit('★COALESCED 번역 없는 값 %d: %s' % (len(miss), miss[:5]))
    data = C.build()
    open(os.path.join(out, 'COALESCED_INT.BIN'), 'wb').write(data)
    # 검산 : 다시 읽혀서 끝 오프셋 = 파일 크기(파서 assert) · 한글 값 수
    C2 = load_coal(os.path.join(out, 'COALESCED_INT.BIN'))
    kr = sum(1 for f in C2.files for s in f[2] for x in s[2] if re.search('[가-힣]', x[2]))
    print('  COALESCED_INT.BIN  값 %d개 교체 · 다시 읽어 한글 값 %d · %d B' % (n, kr, len(data)))


# ── 자막 패키지 ───────────────────────────────────────────────────────
_orig_set_text = build_subs.set_text


def set_text_multi(arr_val, nm, kr):
    """kr 가 dict{순번:문장} 이면 원소마다 교체(여러 줄 큐 7개). 없는 순번은 원문 그대로."""
    if not isinstance(kr, dict):
        return _orig_set_text(arr_val, nm, kr)
    cnt = struct.unpack_from('>i', arr_val, 0)[0]
    p = 4
    o = bytearray(struct.pack('>i', cnt))
    for i in range(cnt):
        props, p2 = build_subs.rd_props(arr_val, p, nm)
        if i in kr:
            for q in props:
                if q['name'] == 'Text':
                    q['val'] = build_subs.wr_str(kr[i])
        o += build_subs.wr_props(props) + build_subs.none_tag(nm)
        p = p2
    assert p == len(arr_val)
    return bytes(o)


build_subs.set_text = set_text_multi


def build_subs_all(base, out, subs):
    kr = {w: {i: ue3_text(t) for i, t in d.items()} for w, d in subs.items()}
    npkg = ncue = 0; bad = []
    seen = set()
    for f in sorted(glob.glob(os.path.join(base, '*_LOC_INT.XXX'))):
        r = build_subs.do_pkg(f, kr)
        if r is None:
            continue
        S, img, nrep, ncues, b2, cueset = r
        dst = os.path.join(out, os.path.basename(f))
        build_subs.write_pkg(S, img, dst)
        # 검산 : 다시 읽어 큐마다 첫 문장 앞 6자가 UTF-16 으로 들어 있나
        Cc = Pkg(dst); cn = Cc.names()
        ok = 0
        for e in Cc.exports(cn):
            if e['name'] in cueset:
                d = bytes(Cc.img[e['off']:e['off'] + e['size']])
                first = kr[e['name']][min(kr[e['name']])]
                if first[:6].encode('utf-16-le') in d:
                    ok += 1; seen.add(e['name'])
        if ok != ncues:
            bad.append('%s %d/%d %s' % (os.path.basename(f), ok, ncues, b2[:2]))
        npkg += 1; ncue += ok
    miss = sorted(set(kr) - seen)
    print('  자막 패키지 %d개 · 확인된 큐 %d · 번역 있는데 못 넣은 웨이브 %d' % (npkg, ncue, len(miss)))
    for x in bad[:10]:
        print('    ★', x)
    if miss:
        print('    ★못 넣음:', miss[:10])
    return npkg


# ── 글꼴 ───────────────────────────────────────────────────────────────
def build_fonts(base, out):
    build_font.PS3 = os.path.join(base, 'ALICEFONTS.XXX')
    build_font.PC = os.path.join(PCPATCH, 'GFx', 'AliceFonts.upk')
    build_font.OUT = os.path.join(out, 'ALICEFONTS.XXX')
    build_locfont.CK = base
    build_locfont.OUT = out
    build_locfont.PCF = os.path.join(PCPATCH, 'AliceGame_LOC_INT.upk')
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        build_font.main()
        build_locfont.build('ALICEGAME_LOC_INT.XXX', 'ALICEGAME_LOC_INT.XXX')
        build_locfont.build('ALICEFONTS_LOC_INT.XXX', 'ALICEFONTS_LOC_INT.XXX')
    log = buf.getvalue()
    # ★공백·NBSP 글리프 칸 바로 아래에 이웃 글자 획이 붙어 있어 보간 때 밑줄처럼 묻어난다(2026-11-11 실기) → 빈 곳으로 옮김
    import fix_space_glyph
    for f in ('ALICEGAME_LOC_INT.XXX', 'ALICEFONTS_LOC_INT.XXX'):
        for ln in fix_space_glyph.fix(os.path.join(out, f)):
            log += '%s %s\n' % (f, ln)
            print('    공백 칸 옮김 %s %s' % (f, ln))
    open(os.path.join(out, '..', 'font_build.log'), 'w', encoding='utf-8').write(log)
    for ln in log.splitlines():
        if '★' in ln or '->' in ln:
            print('   ', ln.strip()[:110])


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    eds = ['disc', 'psn'] if which == 'all' else [which]
    rows, by_en, subs = load_ko()
    print('번역 %d줄 · 자막 웨이브 %d' % (len(rows), len(subs)))
    for ed in eds:
        base = BASE[ed]
        out = os.path.join(ROOT, 'work', 'build', ed, 'COOKEDPS3')
        os.makedirs(out, exist_ok=True)
        for f in glob.glob(os.path.join(out, '*')):
            os.remove(f)
        print('── %s  (기준 %s)' % (ed, base))
        build_coal(base, out, by_en)
        build_subs_all(base, out, subs)
        build_fonts(base, out)
        files = sorted(os.listdir(out))
        print('  산출 %d개 · %.1f MB' % (len(files), sum(os.path.getsize(os.path.join(out, f)) for f in files) / 1e6))


if __name__ == '__main__':
    main()
