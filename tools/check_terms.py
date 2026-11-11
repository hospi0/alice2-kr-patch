# -*- coding: utf-8 -*-
"""용어 통일 검사 — EN 에 용어가 든 줄의 KO 에 «확정 표기»가 있는지 (2026-11-11).

docs/용어.tsv 의 EN 칸(« / » 로 여러 개)을 낱말 경계·대소문자 구분으로 찾고,
KO(공백 무시)에 확정 표기(« / » 로 여러 개 중 하나)가 없으면 «어긋남»으로 모은다.
EN 칸이 «A (B)» 꼴이면 B 는 설명이라 무시.
산출 work/text/terms_report.txt — 용어별 어긋난 줄 수 + 그 줄 KO
python tools/check_terms.py [--all]   (--all: 어긋난 줄 전부)
"""
import os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_terms():
    out = []
    for l in open(os.path.join(ROOT, 'docs', '용어.tsv'), encoding='utf-8').read().splitlines()[1:]:
        c = l.split('\t')
        if len(c) < 3 or not c[2].strip():
            continue
        ens = [e.strip() for e in re.split(r'\s*/\s*', c[0]) if e.strip()]
        oks = [o.strip() for o in re.split(r'\s*/\s*', c[2]) if o.strip()]
        out.append((ens, oks, c[0]))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'ko.tsv'), encoding='utf-8')][1:]
    terms = load_terms()
    rep = []
    tot = 0
    for ens, oks, label in terms:
        pat = re.compile(r'(?<![A-Za-z])(' + '|'.join(re.escape(e) for e in ens) + r')(?![a-z])')
        bad = []
        hit = 0
        for no, at, en, ko in rows:
            if not pat.search(en):
                continue
            hit += 1
            k = ko.replace(' ', '')
            if not any(o.replace(' ', '') in k for o in oks):
                bad.append((no, en, ko))
        if bad:
            tot += len(bad)
            rep.append((len(bad), hit, label, oks, bad))
    rep.sort(key=lambda x: -x[0])
    full = '--all' in sys.argv
    with open(os.path.join(ROOT, 'work', 'text', 'terms_report.txt'), 'w', encoding='utf-8', newline='\n') as w:
        for n, hit, label, oks, bad in rep:
            w.write('### %s → %s : 어긋남 %d / %d\n' % (label, ' / '.join(oks), n, hit))
            for no, en, ko in bad:
                w.write('  %s | %s\n        %s\n' % (no, en[:150], ko[:150]))
    print('용어 %d개 중 어긋난 용어 %d · 어긋난 줄 %d → work/text/terms_report.txt' % (len(terms), len(rep), tot))
    for n, hit, label, oks, bad in rep:
        print('  %4d/%-4d %s → %s' % (n, hit, label, ' / '.join(oks)))


if __name__ == '__main__':
    main()
