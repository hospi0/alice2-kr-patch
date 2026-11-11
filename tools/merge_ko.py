# -*- coding: utf-8 -*-
"""번역 병합·검사 (2026-11-11).

입력  my files/번역/*.tsv          하스피가 준 초벌 (번호 · 위치 · EN · KO) — ⛔읽기만
      work/ko/fix_*.tsv            내가 다듬은 줄 (번호 · KO)  — 뒤 파일이 앞을 덮는다(이름순)
                                   KO 가 «@찾을말=>바꿀말 ;; @…» 이면 부분 치환(긴 줄용)
기준  work/text/uniq.tsv + extract.py 번호 규칙(꾸러미 순 고유 번호)
산출  work/text/ko.tsv             번호 · 위치 · EN · KO  (빌더 입력)
      work/text/ko_report.txt      경고 목록

★규칙은 «쓰는 순간» 막는다 [[feedback_enforce_rules_at_write_time]]
  막음 : 번호 누락·중복 · EN 이 원문과 다름 · 빈 KO · 탭/실개행 ·
         토큰 불일치([styleN]…[/styleN] · %…ICON% · `~ · \\n 개수와 순서)
  경고 : 용어표 «PC표기»(확정과 다른 것)가 KO 에 남음 · 영문 낱말이 KO 에 남음
  정리 : ... / …… → … (한국식 말줄임표 한 칸)
python tools/merge_ko.py
"""
import os, re, sys, glob, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'my files', '번역')
FIX = os.path.join(ROOT, 'work', 'ko')
N = chr(92) + 'n'
TOK = re.compile(r'\[/?style\d+\]|%[A-Z_]+ICON%|`~|' + re.escape(N))

BANNER = """── 병합 규칙 ─────────────────────────────────────────────
 막음: 누락·중복 번호 · EN 불일치 · 빈 KO · 탭/실개행 · 토큰([styleN] %…ICON% `~ \\n) 개수·순서
 경고: 용어표 PC표기 잔존 · KO 안 영문 낱말
 정리: ... ……  →  …
──────────────────────────────────────────────────────────"""


def source_rows():
    """extract.py 와 같은 번호 매김 — my files/tsv 를 다시 만들지 않고 uniq 순서에서 계산."""
    import importlib.util
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'all.tsv'), encoding='utf-8')][1:]
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    order = {'ui': 0, 'engine': 0, 'movie': 1, 'voice': 2}
    uniq = collections.OrderedDict()
    for at, b, en, _ in rows:
        uniq.setdefault(en, (at, b))
    # extract.py: 꾸러미 정렬 뒤 uniq 순서로 번호 → all.tsv 가 이미 그 순서
    out = collections.OrderedDict()
    no = 0
    for en, (at, b) in uniq.items():
        no += 1
        if b in ('credits', 'skip', 'uiskip'):
            SKIPPED.add('%05d' % no)
            continue
        out['%05d' % no] = (at, b, en)
    return out


SKIPPED = set()


def tok_ok(en, k):
    """토큰은 «개수»가 같고 [styleN] 짝이 바르면 통과 — 한국어 어순으로 아이콘 위치가 바뀌는 건 정상."""
    te, tk = TOK.findall(en), TOK.findall(k)
    if sorted(te) != sorted(tk):
        return False
    st = []
    for t in tk:
        m = re.match(r'\[(/?)style(\d+)\]', t)
        if not m:
            continue
        if not m.group(1):
            if st:
                return False                  # 겹친 태그 금지
            st.append(m.group(2))
        else:
            if not st or st.pop() != m.group(2):
                return False
    if st:
        return False
    # 줄바꿈 \n 은 개수만(위치는 번역이 정함)
    return True


STICK = r'%(?:CAMERA|MOVE|SWITCH)ICON%'


def icon_josa(s):
    """버튼 아이콘 뒤 «을(를)» → «버튼을», 스틱 아이콘 뒤 → «스틱을/스틱으로» (화면엔 아이콘 그림이 들어가 조사를 못 고름)."""
    s = re.sub('(' + STICK + r') ?(?:을\(를\)|를|을)(?= )', lambda m: m.group(1) + ' 스틱을', s)
    s = re.sub('(' + STICK + r') ?(?:\(으\)로|으로|로)(?= )', lambda m: m.group(1) + ' 스틱으로', s)
    s = re.sub(r'(%[A-Z]+ICON%) ?(?:을\(를\)|를|을)(?= )', lambda m: m.group(1) + ' 버튼을', s)
    s = re.sub(r'(%[A-Z]+ICON%) ?(?:\(으\)로|으로|로)(?= )', lambda m: m.group(1) + ' 버튼으로', s)
    return s


def ellipsis(s):
    s = re.sub(r'\.{3,}|…{2,}|…\.+|\.+…', '…', s)
    return s


def load_subst():
    """docs/표기치환.tsv — 받침 같은 표기만(조사 안 깨짐)."""
    out = []
    for l in open(os.path.join(ROOT, 'docs', '표기치환.tsv'), encoding='utf-8').read().splitlines():
        if not l.strip() or l.startswith('#'):
            continue
        c = l.split('	')
        a, b = c[0], c[1]
        cond = re.compile(c[3]) if len(c) > 3 and c[3].strip() else None
        # 마지막 글자 받침 같은지 검사(다르면 조사가 깨진다)
        jong = lambda ch: (ord(ch) - 0xAC00) % 28 if '가' <= ch <= '힣' else -1
        if jong(a[-1]) != jong(b[-1]):
            raise SystemExit('★표기치환 «%s→%s» 받침이 달라 조사가 깨진다' % (a, b))
        out.append((a, b, cond))
    return out


def subst_one(k, a, b):
    """a→b. b 가 a 를 품으면(히스테리→히스테리아, 목마→막대 목마) 이미 b 인 자리는 건너뛴다."""
    i = b.find(a)
    pre, post = (b[:i], b[i + len(a):]) if i >= 0 else ('', '')
    pat = (('(?<!' + re.escape(pre) + ')') if pre else '') + re.escape(a) + (('(?!' + re.escape(post) + ')') if post else '')
    return re.subn(pat, lambda m: b, k)


def load_glossary():
    bad = []
    p = os.path.join(ROOT, 'docs', '용어.tsv')
    for l in open(p, encoding='utf-8').read().splitlines()[1:]:
        c = l.split('\t')
        if len(c) < 4:
            continue
        en, pc, ok, kind = c[0], c[1], c[2], c[3]
        if kind in ('의역→원문', '표기법') and pc and not pc.startswith('('):
            for frag in re.split(r'\s*/\s*', pc):
                frag = frag.replace(' ', '')
                if len(frag) >= 2 and frag not in ok.replace(' ', ''):
                    bad.append((frag, ok, en))
    return bad


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print(BANNER)
    src = source_rows()
    skipped = SKIPPED
    ko = {}
    origin = {}
    errs = []
    for f in sorted(glob.glob(os.path.join(SRC, '*.tsv'))):
        bn = os.path.basename(f)
        for i, l in enumerate(open(f, encoding='utf-8-sig').read().split('\n')[1:], 2):
            if not l.strip():
                continue
            c = l.split('\t')
            if len(c) < 4:
                errs.append('%s:%d 열 부족 %r' % (bn, i, l[:60])); continue
            no, at, en, k = c[0], c[1], c[2], '\t'.join(c[3:])
            # 번역 도구가 큰따옴표를 \" 로 이스케이프해 둔 파일이 있다(movie_001/002) — 되돌림
            en = en.replace(chr(92) + '"', '"'); k = k.replace(chr(92) + '"', '"')
            if no not in src:
                if no in skipped:
                    continue                  # 번역 금지 줄(글꼴 설정 등) — 받은 번역 무시
                errs.append('%s:%d 모르는 번호 %s' % (bn, i, no)); continue
                errs.append('%s:%d 모르는 번호 %s' % (bn, i, no)); continue
            if src[no][2] != en:
                errs.append('%s:%d EN 불일치 %s' % (bn, i, no)); continue
            if no in ko:
                errs.append('%s:%d 중복 번호 %s' % (bn, i, no)); continue
            ko[no] = k; origin[no] = bn
    for f in sorted(glob.glob(os.path.join(FIX, 'fix_*.tsv'))):
        bn = os.path.basename(f)
        for i, l in enumerate(open(f, encoding='utf-8-sig').read().split('\n'), 1):
            if not l.strip() or l.startswith('#') or l.startswith('번호'):
                continue
            c = l.split('\t')
            if len(c) != 2 or not re.match(r'^\d{5}$', c[0]):
                errs.append('%s:%d 형식(번호\\tKO) 아님 %r' % (bn, i, l[:60])); continue
            if c[0] not in src:
                errs.append('%s:%d 모르는 번호 %s' % (bn, i, c[0])); continue
            v = c[1]
            if v.startswith('@') and '=>' in v:
                # 부분 치환: @찾을말=>바꿀말 ;; @찾을말=>바꿀말 (긴 줄 통째로 다시 쓰지 않으려고)
                if c[0] not in ko:
                    errs.append('%s:%d 부분 치환인데 바탕 번역 없음 %s' % (bn, i, c[0])); continue
                cur = ko[c[0]]
                for part in v.split(' ;; '):
                    a, b2 = part[1:].split('=>', 1)
                    if a not in cur:
                        errs.append('%s:%d 부분 치환 «%s» 를 %s 에서 못 찾음' % (bn, i, a[:30], c[0])); break
                    cur = cur.replace(a, b2)
                ko[c[0]] = cur; origin[c[0]] = bn
                continue
            ko[c[0]] = v; origin[c[0]] = bn
    miss = [n for n in src if n not in ko]
    if miss:
        errs.append('번역 없음 %d개: %s' % (len(miss), miss[:20]))
    warn = []
    gl = load_glossary()
    subst = load_subst()
    nsub = collections.Counter()
    out = []
    for no, (at, b, en) in src.items():
        if no not in ko:
            continue
        k = icon_josa(ellipsis(ko[no].strip()))
        for a, b2, cond in subst:
            if cond and not cond.search(en):
                continue                      # 원문에 그 게임 용어가 없는 줄은 안 바꿈(일반 낱말 hysterical 등)
            if a in k:
                k, n = subst_one(k, a, b2)
                nsub[a] += n
        if not k:
            errs.append('%s 빈 KO' % no); continue
        if '\t' in k or '\n' in k or '\r' in k:
            errs.append('%s 탭/실개행' % no); continue
        if not tok_ok(en, k):
            errs.append('%s 토큰 %s → %s  [%s]' % (no, TOK.findall(en), TOK.findall(k), origin[no]))
        for frag, ok, ge in gl:
            if frag in k.replace(' ', '') and ok.replace(' ', '') not in k.replace(' ', ''):
                warn.append('%s 용어 «%s» → «%s»(%s) : %s' % (no, frag, ok, ge, k[:70]))
        en_left = [w for w in re.findall(r'[A-Za-z]{3,}', TOK.sub('', k)) if w not in ('PlayStation', 'PS3', 'HDD', 'MB', 'KB')]
        if en_left:
            warn.append('%s 영문 남음 %s : %s' % (no, en_left[:4], k[:70]))
        out.append((no, at, en, k))
    with open(os.path.join(ROOT, 'work', 'text', 'ko_report.txt'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('막음 %d\n' % len(errs) + '\n'.join(errs) + '\n\n경고 %d\n' % len(warn) + '\n'.join(warn) + '\n')
    print('원문 %d · 번역 %d · 막음 %d · 경고 %d → work/text/ko_report.txt' % (len(src), len(ko), len(errs), len(warn)))
    print('표기 치환:', ', '.join('%s %d' % (a, n) for a, n in nsub.items()) or '없음')
    for e in errs[:30]:
        print('  ✗', e)
    if errs:
        raise SystemExit('★막힌 줄이 있어 ko.tsv 를 쓰지 않았다')
    with open(os.path.join(ROOT, 'work', 'text', 'ko.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('번호\t위치\tEN\tKO\n')
        for r in out:
            w.write('\t'.join(r) + '\n')
    print('→ work/text/ko.tsv %d줄' % len(out))


if __name__ == '__main__':
    main()
