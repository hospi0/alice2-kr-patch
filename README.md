# 앨리스 매드니스 리턴즈 (Alice: Madness Returns, PS3) 한글 패치

> **내려받기:** [릴리즈 페이지](https://github.com/hospi0/alice2-kr-patch/releases/latest) — 최신 v0.91.
> 디스크판(BLUS30607)과 PSN 판(NPUB30545) 묶음이 따로 있습니다. 적용 방법·원본 MD5 는 묶음의 readme.txt 에 있습니다.
>
> 이 저장소에는 도구·번역 텍스트·작업 문서만 있습니다(게임 데이터·빌드 결과물 없음).

## 적용

1. 맞는 판의 zip 을 풉니다.
2. `한글패치_적용.bat` 을 실행하고 게임 폴더(또는 `USRDIR\ALICEGAME\COOKEDPS3`)를 끌어다 놓습니다.
3. 파일마다 원본 MD5 확인 → 원본 백업 → xdelta 적용 → 결과 MD5 확인 후 덮어씁니다.
   되돌리기는 `되돌리기.bat`.

RPCS3 에서 시험했습니다. 게임 언어는 영어로 둡니다.

## 바뀌는 것

- 메뉴, 설정, 조작 안내, 튜토리얼, 목표, 저장 메시지
- 일지(기억 조각·관심 지점), 등장인물 설명, 지난 일들, 챕터 이름, 부고 신문
- 컷신·인게임 음성 대사 자막, 기억 영상·2D 영상 자막, 로딩 힌트
- 한글 글꼴(메뉴 GFx · 자막 UE3)

엔딩 크레딧과 무비 안 그림 글자는 영어 그대로입니다.

## 구조

| 경로 | 내용 |
|---|---|
| `tools/extract.py` | COALESCED_INT.BIN 의 .int 와 `*_LOC_INT.XXX` 음성 자막(LocalizedSubtitles[INT]) 추출 |
| `tools/merge_ko.py` | 번역 병합·검사(토큰·용어·표기 치환·버튼 아이콘 조사) → `work/text/ko.tsv` |
| `tools/build.py` | 판별 빌드 — COALESCED · 자막 패키지 · 글꼴(GFx·UE3), 공백 글리프 칸 보정 |
| `tools/verify_build.py` | 빌드 검산 |
| `tools/make_dist.py` | 배포 묶음(xdelta + bat) |
| `docs/` | 조사 기록, 용어표, 인물별 말투표, 표기 치환표 |
| `work/text/ko.tsv` | 번역(번호 · 위치 · EN · KO) |
| `work/ko/` | 다듬기 수정분 |

글꼴은 PC 한글패치의 한글 글꼴(글리프)만 이식했습니다. 번역문은 새로 만들었습니다.
