# -*- coding: utf-8 -*-
"""PC 한글패치에서 «고유명사 표기만» 후보로 뽑는다 (2026-11-11 하스피: «pc패치는 고유명사만 참고»).

⛔PC 패치 문장은 번역 참고 금지 — 여기서는 «이름 대응»만 뽑는다.
방법 : work/text/all.tsv 의 EN 에서 대문자 낱말(문장 첫머리 제외)·대문자 연속 낱말 묶음을 후보로,
       같은 위치(키·웨이브)의 PC 한글 문장들에서 «그 후보가 든 줄에 유독 많이 나오는» 한글 낱말을 고른다.
산출 : work/glossary_pc.tsv  EN · 출현 · PC후보1 · PC후보2 · PC후보3   (사람이 골라 docs/용어.tsv 로)
python tools/pc_glossary.py
"""
import os, re, io, sys, collections, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PC = r'C:\claude\utils\한글화 이식\Alice2\Alice2_KOR PC Patch\Game\Alice2\AliceGame\Localization\INT'
HANGUL = re.compile('[가-힣]{2,}')
JOSA = ('으로', '에게', '에서', '까지', '부터', '처럼', '보다', '이나', '이랑', '하고', '께서',
        '은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '도', '로', '야', '아', '여', '만', '랑')
STOP = set('I A The An And But Or Of In On At To For With From By As It Its If So Do Don\'t '
           'You Your We Our He His She Her They Their This That These Those What Who Why How '
           'When Where Is Are Was Were Be Been Not No Yes Oh Ah My Me Us Him Them OK Okay Now '
           'Then There Here All Just Well Come Get Let Go Can Will Would Should Could Press Hold '
           'Use Collect Find Shoot Take Kill Defeat Return Open Use Select'.split())


def stem(w):
    for j in JOSA:
        if w.endswith(j) and len(w) - len(j) >= 2:
            return w[:-len(j)]
    return w


def load_pc():
    kr = {}
    for fn in os.listdir(PC):
        if not fn.lower().endswith('.int'):
            continue
        txt = io.open(os.path.join(PC, fn), encoding='utf-16').read()
        if fn.lower().startswith('vo_'):
            cur = None
            for ln in txt.splitlines():
                s = ln.strip()
                m = re.match(r'^\[(\S+) SoundNodeWave\]$', s)
                if m:
                    cur = m.group(1); continue
                if cur and s.lower().startswith('subtitles[0]'):
                    m2 = re.search(r'Text="(.*)"\)', s)
                    if m2:
                        kr['S|%s|0' % cur] = m2.group(1)
                    cur = None
        else:
            sec = None
            for ln in txt.splitlines():
                s = ln.strip()
                if s.startswith('[') and s.endswith(']'):
                    sec = s[1:-1]; continue
                if '=' in s and sec:
                    k, v = s.split('=', 1)
                    kr['C|%s|%s|%s' % (fn, sec, k.strip())] = v.strip().strip('"')
    return kr


def candidates(en):
    out = set()
    for sent in re.split(r'(?<=[.!?…])\s+|\\n', en):
        toks = re.findall(r"[A-Za-z][A-Za-z'\-]*", sent)
        run = []
        for i, t in enumerate(toks):
            cap = t[0].isupper() and not t.isupper() or (t.isupper() and len(t) > 1 and False)
            if cap and t not in STOP and (i > 0 or len(toks) == 1 or True):
                run.append(t)
            else:
                if run:
                    out.add(' '.join(run))
                run = []
        if run:
            out.add(' '.join(run))
    return {c for c in out if c not in STOP}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'all.tsv'), encoding='utf-8')][1:]
    pc = load_pc()
    df = collections.Counter()        # 한글 낱말 → 줄 수
    for v in pc.values():
        for w in set(stem(x) for x in HANGUL.findall(v)):
            df[w] += 1
    N = len(pc)
    cand = collections.defaultdict(list)
    for at, b, en, _ko in rows:
        if b in ('skip',):
            continue
        for c in candidates(en):
            cand[c].append(at)
    out = []
    for c, ats in cand.items():
        if len(ats) < 2 and ' ' not in c:
            continue
        hits = [pc[a] for a in ats if a in pc]
        if not hits:
            continue
        tf = collections.Counter()
        for v in hits:
            for w in set(stem(x) for x in HANGUL.findall(v)):
                tf[w] += 1
        sc = sorted(((tf[w] / len(hits)) * math.log(N / (1 + df[w])), w, tf[w]) for w in tf)[::-1][:3]
        out.append((len(ats), c, len(hits), ['%s(%d/%d)' % (w, n, len(hits)) for s, w, n in sc]))
    out.sort(key=lambda x: (-x[0], x[1]))
    p = os.path.join(ROOT, 'work', 'glossary_pc.tsv')
    with open(p, 'w', encoding='utf-8', newline='\n') as w:
        w.write('EN\t출현\tPC대응줄\tPC후보1\tPC후보2\tPC후보3\n')
        for n, c, h, ws in out:
            w.write('%s\t%d\t%d\t%s\n' % (c, n, h, '\t'.join(ws + [''] * (3 - len(ws)))))
    print('후보 %d개 -> %s · PC 대응 키 %d개' % (len(out), p, N))


if __name__ == '__main__':
    main()
