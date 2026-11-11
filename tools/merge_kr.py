# -*- coding: utf-8 -*-
"""PC 한글패치의 .int 를 PS3 COALESCED_INT.BIN 에 넣는다.

  python tools/merge_kr.py            보수판(UI+자막)만
  python tools/merge_kr.py --vo       VO 대사 자막까지(미검증 가설)

★키는 «섹션 안 순서»로 짝짓는다 — GFxUI 의 FontLib 처럼 같은 키가 여러 번 나온다.
★값만 바꾸고 키·섹션·파일 순서는 원본 그대로 둔다(왕복 바이트 동일이 검산 기준).
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coalesced

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INT = os.path.join(ROOT, 'Alice2_KOR PC Patch', 'Game', 'Alice2', 'AliceGame', 'Localization', 'INT')
SRC = os.path.join(ROOT, 'NPUB30545 PS3 files', 'USRDIR', 'ALICEGAME', 'COOKEDPS3', 'COALESCED_INT.BIN')
OUT = os.path.join(ROOT, 'patches')
SEP = chr(92)          # 역슬래시 — heredoc 이 먹으므로 코드로 쓴다


def parse_int(path):
    """[(섹션, [(키, 값)])] — 파일 순서 그대로."""
    secs, cur = [], None
    # ★★★strip() 은 «전각 공백 U+3000» 까지 먹는다 — 그건 가운데 정렬용 «내용»이다.
    #   (LOADING_TEXT 의 앞 전각공백이 사라져 화면 정렬이 깨진다)
    #   → ASCII 공백/탭/개행만 벗긴다.
    WS = ' ' + chr(9) + chr(13) + chr(10)
    for ln in io.open(path, encoding='utf-16').read().splitlines():
        s = ln.strip(WS)
        if not s or s.startswith(';'):
            continue
        if s.startswith('[') and s.endswith(']'):
            cur = (s[1:-1], []); secs.append(cur); continue
        if '=' in s and cur is not None:
            k, v = s.split('=', 1)
            cur[1].append((k.strip(WS), unescape(v.strip(WS))))
    return secs


BS = chr(92)


def unescape(v):
    """UE3 쿠커가 .int 값에 하던 변환 — PS3 원본과 대조해 확정했다.
      · 통째로 감싼 따옴표는 벗긴다   ("FAILURE" -> FAILURE)
      · 이스케이프 \n 은 «진짜 줄바꿈»으로 바꾼다
    ⛔값이 '(' 로 시작하면(=구조체 리터럴 (Text="...")) 줄바꿈 변환은 하지 않는다 —
      따옴표 안에 진짜 개행을 넣으면 구조체 파싱이 깨진다.
    """
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"' and not v[-2:-1] == BS:
        v = v[1:-1].replace(BS + '"', '"')
    if not v.startswith('('):
        v = v.replace(BS + 'n', chr(10))
    return v


def has_kr(s):
    return any('가' <= ch <= '힣' for ch in s)


def main():
    vo = '--vo' in sys.argv
    c = coalesced.load(SRC)
    idx = {}
    for f in c.files:
        idx[os.path.basename(f[0].replace(SEP, '/')).lower()] = f

    rep = added = 0
    log = []
    for name in sorted(os.listdir(INT)):
        if not name.lower().endswith('.int'):
            continue
        isvo = name.lower().startswith('vo_')
        if isvo and not vo:
            continue
        f = idx.get(name.lower())
        if f is None:
            log.append('   ⚠️PS3 에 없는 파일 — 건너뜀 : %s' % name)
            continue
        pc = parse_int(os.path.join(INT, name))
        pcmap = {}
        for sn, kv in pc:
            pcmap.setdefault(sn.lower(), []).extend(kv)
        n_rep = n_add = 0
        # ① 이미 있는 섹션 : «키 이름»으로 짝짓는다(같은 이름이 여럿이면 나온 순서대로).
        #    ⛔순서로 짝지으면 한쪽에 키가 하나만 더/덜 있어도 그 뒤가 통째로 어긋난다(실측).
        used = set()
        for sec in f[2]:
            sn, sw, kv = sec
            lst = pcmap.get(sn.lower())
            if lst is None:
                continue
            used.add(sn.lower())
            byname = {}
            for k, v in lst:
                byname.setdefault(k.lower(), []).append(v)
            seen = {}
            for ent in kv:
                kl = ent[0].lower()
                i = seen.get(kl, 0); seen[kl] = i + 1
                vals = byname.get(kl)
                if not vals or i >= len(vals):
                    continue
                pv = vals[i]
                if pv != ent[2]:
                    ent[2] = pv
                    ent[3] = ent[3] or has_kr(pv)
                    n_rep += 1
            miss = [k for k in byname if k not in seen]
            if miss:
                log.append('   ⚠️%s [%s] PC 에만 있는 키 %d개(무시) 예:%s'
                           % (name, sn, len(miss), miss[:3]))
        # ② PS3 에 «없는» 섹션(=VO 처럼 비어 있는 파일) : 통째로 추가
        for sn, kv in pc:
            if sn.lower() in used:
                continue
            f[2].append([sn, False, [[k, False, v, has_kr(v)] for k, v in kv]])
            n_add += len(kv)
            pcmap.pop(sn.lower(), None)
        rep += n_rep; added += n_add
        if n_rep or n_add:
            log.append('   %-26s 값교체 %5d · 새로추가 %5d' % (name, n_rep, n_add))

    blob = c.build()
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, 'COALESCED_INT_VO.BIN' if vo else 'COALESCED_INT.BIN')
    open(dst, 'wb').write(blob)
    print('\n'.join(log))
    print('── 값교체 %d · 새로추가 %d' % (rep, added))
    print('-> %s  %d B (원본 %d B)' % (dst, len(blob), os.path.getsize(SRC)))
    # 검산 : 다시 읽어 파싱이 되는가 + 한글 키 수
    c2 = coalesced.Coalesced(blob)
    kr = sum(1 for f in c2.files for sn, sw, kv in f[2] for k, kw, v, vw in kv if has_kr(v))
    print('★재파싱 OK · 한글 값 %d개' % kr)


if __name__ == '__main__':
    main()
