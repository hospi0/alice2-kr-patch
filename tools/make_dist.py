# -*- coding: utf-8 -*-
r"""배포 묶음 (2026-11-11) — 판마다 따로:
  dist/AliceMadnessReturns_PS3_Disc_KR_v0.9/   (디스크판 BLUS30607)
  dist/AliceMadnessReturns_PS3_PSN_KR_v0.9/    (PSN 판 NPUB30545)
  각 묶음 = patch\<파일>.xdelta 152개 + xdelta.exe + readme.txt + 한글패치_적용.bat + 되돌리기.bat (+ zip)

  python tools/make_dist.py            (tools/build.py all 뒤에)

xdelta 원본 = 같은 이름의 원본 파일(판별). 만들고 나서 «원본에 적용 → 빌드와 바이트 동일» 전수 되짚기.
bat : COOKEDPS3 폴더를 찾아 → 파일마다 원본 MD5 확인(이미 한글이면 건너뜀) → 원본을 묶음의 «원본백업\» 에 복사
      → xdelta 적용 → 결과 MD5 확인 → 덮어쓰기.  되돌리기.bat = 원본백업\ 을 다시 복사.
규칙: 해시 MD5 대문자 · 한국어 문서·bat 은 CP949(CRLF) · 버전 v0.9 · bat 의 if 블록 안 echo 에 괄호 금지.
"""
import hashlib, os, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build

VER = 'v0.91'
XDELTA = r'C:\claude\utils\xdelta.exe'
EDS = {
    'disc': ('Disc', 'BLUS30607', '디스크판 (BLUS30607, 북미)', 'PS3_GAME\\USRDIR\\ALICEGAME\\COOKEDPS3'),
    'psn': ('PSN', 'NPUB30545', 'PSN 다운로드판 (NPUB30545, 북미)', 'NPUB30545\\USRDIR\\ALICEGAME\\COOKEDPS3'),
}


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


README = """앨리스 매드니스 리턴즈 (Alice: Madness Returns, PS3) 한글 패치 {ver}
================================================================

{edname} 용입니다. RPCS3 에서 시험했습니다.
(다른 판에는 맞지 않습니다. 디스크판과 PSN 판 묶음이 따로 있습니다)

바꾸는 파일 : USRDIR\\ALICEGAME\\COOKEDPS3 안 {n}개
  (COALESCED_INT.BIN, 글꼴 3개, 음성 자막 패키지 {nsub}개)


[ 적용 방법 ]

1. 이 묶음을 아무 폴더에나 풉니다.
2. 「한글패치_적용.bat」 을 실행하고, 게임 폴더를 끌어다 놓거나 경로를 적고 Enter.
   예) ...\\{folder}
   (게임 최상위 폴더, USRDIR, ALICEGAME, COOKEDPS3 어느 것을 줘도 찾아갑니다)
3. 배치가 파일마다
     원본 MD5 확인 → 원본을 이 묶음의 「원본백업」 폴더에 복사 → 패치 → 결과 MD5 확인
   을 하고 덮어씁니다. 이미 한글판인 파일은 건너뜁니다.
4. 게임 언어(시스템 언어)는 영어로 둡니다.

되돌리기 : 「되돌리기.bat」 → 같은 폴더를 주면 「원본백업」 의 파일로 되돌립니다.
          (「원본백업」 폴더를 지우지 마세요)


[ 바뀌는 것 ]

■ 메뉴, 설정, 조작 안내, 튜토리얼, 목표, 저장 메시지
■ 일지(기억 조각, 관심 지점), 등장인물 설명, 지난 일들, 챕터 이름, 부고 신문
■ 컷신·인게임 음성 대사 자막, 기억 영상·2D 영상 자막, 로딩 힌트
■ 한글 글꼴 (메뉴용·자막용)


[ 알려진 사항 ]

■ 엔딩 크레딧(제작진 명단)은 영어 그대로입니다.
■ 그림으로 된 글자(일부 무비 안 글자)는 영어 그대로입니다.
■ 자막 글꼴에 「…」 가 없어 자막의 말줄임표는 「...」 로 나옵니다.


[ 원본 → 한글판 MD5 ]

{table}
"""

BAT = r"""@echo off
setlocal
chcp 949 >nul
cd /d "%~dp0"
set "XD=%~dp0xdelta.exe"
set "BK=%~dp0원본백업"

echo.
echo  ================================================================
echo    Alice: Madness Returns PS3 Korean Patch {ver}   [{tid}]
echo  ================================================================
echo.

if not exist "%XD%" goto NOXD

set "TARGET=%~1"
if not defined TARGET set /p TARGET=  게임 폴더를 끌어다 놓거나 경로를 적고 Enter:
set TARGET=%TARGET:"=%
if "%TARGET:~-1%"=="\" set "TARGET=%TARGET:~0,-1%"

set "DEST="
if exist "%TARGET%\COALESCED_INT.BIN" set "DEST=%TARGET%"
if exist "%TARGET%\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\COOKEDPS3"
if exist "%TARGET%\ALICEGAME\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\ALICEGAME\COOKEDPS3"
if exist "%TARGET%\USRDIR\ALICEGAME\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\USRDIR\ALICEGAME\COOKEDPS3"
if exist "%TARGET%\PS3_GAME\USRDIR\ALICEGAME\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\PS3_GAME\USRDIR\ALICEGAME\COOKEDPS3"
if not defined DEST goto NODEST
echo  대상 : %DEST%
echo.

if not exist "%BK%" mkdir "%BK%"
set /a DONE=0
set /a SKIP=0
{calls}
echo.
echo  [OK] 끝났습니다. 새로 패치 %DONE%개 · 이미 한글판 %SKIP%개
echo       원본은 "원본백업" 폴더에 있습니다.
goto END

:DO
set "NAME=%~1"
set "SRCMD5=%~2"
set "DSTMD5=%~3"
if not exist "%DEST%\%NAME%" goto MISSING
call :HASH "%DEST%\%NAME%"
if /I "%H%"=="%DSTMD5%" set /a SKIP+=1
if /I "%H%"=="%DSTMD5%" exit /b 0
if /I not "%H%"=="%SRCMD5%" goto WRONG
copy /y "%DEST%\%NAME%" "%BK%\%NAME%" >nul
"%XD%" -d -f -s "%DEST%\%NAME%" "patch\%NAME%.xdelta" "%BK%\%NAME%.new"
if errorlevel 1 goto XFAIL
call :HASH "%BK%\%NAME%.new"
if /I not "%H%"=="%DSTMD5%" goto XFAIL
move /y "%BK%\%NAME%.new" "%DEST%\%NAME%" >nul
set /a DONE+=1
echo      %NAME%
exit /b 0

:HASH
set "H="
for /f "skip=1 tokens=* delims=" %%A in ('certutil -hashfile "%~1" MD5') do if not defined H set "H=%%A"
set "H=%H: =%"
exit /b 0

:MISSING
echo  [!] %NAME% 이 대상 폴더에 없습니다. 판이 맞는지 확인하세요 - 이 묶음은 {tid} 용입니다.
goto FAIL
:WRONG
echo  [!] %NAME% 이 원본과 다릅니다. 다른 판이거나 이미 다른 패치가 들어가 있습니다.
echo      이 묶음은 {tid} 용입니다. 원본 MD5 %SRCMD5%
goto FAIL
:XFAIL
echo  [!] %NAME% 패치 결과가 맞지 않습니다.
if exist "%BK%\%NAME%.new" del "%BK%\%NAME%.new"
goto FAIL
:NOXD
echo  [!] xdelta.exe 가 없습니다. 묶음을 그대로 풀고 실행하세요.
goto END
:NODEST
echo  [!] COOKEDPS3 폴더를 찾지 못했습니다: %TARGET%
goto END
:FAIL
echo.
echo  중단했습니다. 이미 바꾼 파일은 되돌리기.bat 로 되돌릴 수 있습니다.
:END
echo.
if "%~2"=="" pause
endlocal
exit /b 0
"""

UNDO = r"""@echo off
setlocal
chcp 949 >nul
cd /d "%~dp0"
set "BK=%~dp0원본백업"
echo.
echo  Alice: Madness Returns PS3 Korean Patch {ver} - 되돌리기  [{tid}]
echo.
if not exist "%BK%\COALESCED_INT.BIN" goto NOBK
set "TARGET=%~1"
if not defined TARGET set /p TARGET=  게임 폴더를 끌어다 놓거나 경로를 적고 Enter:
set TARGET=%TARGET:"=%
if "%TARGET:~-1%"=="\" set "TARGET=%TARGET:~0,-1%"
set "DEST="
if exist "%TARGET%\COALESCED_INT.BIN" set "DEST=%TARGET%"
if exist "%TARGET%\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\COOKEDPS3"
if exist "%TARGET%\ALICEGAME\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\ALICEGAME\COOKEDPS3"
if exist "%TARGET%\USRDIR\ALICEGAME\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\USRDIR\ALICEGAME\COOKEDPS3"
if exist "%TARGET%\PS3_GAME\USRDIR\ALICEGAME\COOKEDPS3\COALESCED_INT.BIN" set "DEST=%TARGET%\PS3_GAME\USRDIR\ALICEGAME\COOKEDPS3"
if not defined DEST goto NODEST
for %%F in ("%BK%\*") do copy /y "%%F" "%DEST%\%%~nxF" >nul
echo  [OK] 원본으로 되돌렸습니다: %DEST%
goto END
:NOBK
echo  [!] 원본백업 폴더가 비어 있습니다. 한글패치_적용.bat 을 먼저 쓴 묶음에서 실행하세요.
goto END
:NODEST
echo  [!] COOKEDPS3 폴더를 찾지 못했습니다: %TARGET%
:END
echo.
if "%~2"=="" pause
endlocal
"""


def write_cp949(path, text):
    data = text.replace('\r\n', '\n').replace('\n', '\r\n').encode('cp949')
    with open(path, 'wb') as f:
        f.write(data)


def make(ed):
    tag, tid, edname, folder = EDS[ed]
    base = build.BASE[ed]
    out = os.path.join(ROOT, 'work', 'build', ed, 'COOKEDPS3')
    name = 'AliceMadnessReturns_PS3_%s_KR_%s' % (tag, VER)
    dist = os.path.join(ROOT, 'dist', name)
    if os.path.exists(dist):
        shutil.rmtree(dist)
    os.makedirs(os.path.join(dist, 'patch'))
    chk = os.path.join(ROOT, 'work', 'dist_check.bin')
    files = sorted(os.listdir(out))
    rows, calls, total = [], [], 0
    for f in files:
        src, dst = os.path.join(base, f), os.path.join(out, f)
        patch = os.path.join(dist, 'patch', f + '.xdelta')
        subprocess.run([XDELTA, '-e', '-9', '-S', 'djw', '-f', '-s', src, dst, patch], check=True)
        subprocess.run([XDELTA, '-d', '-f', '-s', src, patch, chk], check=True)
        sm, dm = md5(src), md5(dst)
        if md5(chk) != dm:
            raise SystemExit('⛔ xdelta 되짚기 결과가 다르다: ' + f)
        total += os.path.getsize(patch)
        rows.append((f, sm, dm))
        calls.append('call :DO "%s" %s %s' % (f, sm, dm))
    os.remove(chk)
    shutil.copy(XDELTA, os.path.join(dist, 'xdelta.exe'))
    table = '\n'.join('%-40s %s -> %s' % r for r in rows)
    nsub = sum(1 for f in files if f.endswith('_LOC_INT.XXX') and 'FONT' not in f and f != 'ALICEGAME_LOC_INT.XXX')
    write_cp949(os.path.join(dist, 'readme.txt'), README.format(ver=VER, edname=edname, n=len(files), nsub=nsub, folder=folder, table=table))
    write_cp949(os.path.join(dist, '한글패치_적용.bat'), BAT.format(ver=VER, tid=tid, calls='\n'.join(calls)))
    write_cp949(os.path.join(dist, '되돌리기.bat'), UNDO.format(ver=VER, tid=tid))
    z = os.path.join(ROOT, 'dist', name + '.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for r, _, fs in os.walk(dist):
            for f in fs:
                p = os.path.join(r, f)
                zf.write(p, os.path.join(name, os.path.relpath(p, dist)))
    print('%s : xdelta %d개 %.1f MB · zip %.1f MB · zip MD5 %s' % (name, len(files), total / 1e6, os.path.getsize(z) / 1e6, md5(z)))
    return dist, z


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for ed in ('disc', 'psn'):
        make(ed)


if __name__ == '__main__':
    main()
