# Kronos Dashboard V6/V6.1 개발 결과 보고서 — 2026-07-20

> 문서 ID: `KRONOS-DASHBOARD-V61-RESULT-2026-07-20`
> 작성일: `2026-07-20 KST`
> 실행 기간: `2026-07-19 ~ 2026-07-20 KST`
> 상태: `COMPLETE / V6.1_WORKSPACE_PLATFORM_SHIPPED`
> 모델·실거래 판정: **변동 없음** — H1 tabular-Q smoke `NO_GO`, full `INCONCLUSIVE`, live/profit/GO 주장 없음
> 범위: V6 opt-in 플랫폼 신설(13페이지) → V6.1 워크스페이스 재편(5탭+프로세스 스테퍼+차트)
> 브랜치: `feature/dashboard-v6-rl-platform`
> 기준 commit: `00b4ce4` → 최종 `718c6a3`
> 기본 UI: `V3 유지` · tag/push/merge: 수행하지 않음
> 대체 문서: 없음. 연구 결과는 `docs/kronos_v6_daily_h1_rl_result_2026-07-19.md`가 권위.

## 목차

1. [요약 판정](#1-요약-판정)
2. [V6 1차 구축 결과](#2-v6-1차-구축-결과)
3. [V6.1 UX 고도화 결과](#3-v61-ux-고도화-결과)
4. [탭별 사용성 점수 변화](#4-탭별-사용성-점수-변화)
5. [검증](#5-검증)
6. [한계·blocker](#6-한계blocker)
7. [관련 commit](#7-관련-commit)
8. [변경 히스토리](#8-변경-히스토리)

## 1. 요약 판정

| 축 | 결과 |
|---|---|
| V6 플랫폼 | `?ui=v6` opt-in 신설, V3/V4/V5 격리, 13페이지 → **5탭 워크스페이스**로 재편 |
| 강화학습 연구 실행 | D-1~D-4, R-1~R-6 완주: universe 500 동결, 786,872행 dataset, 사전등록 학습 2회 실행, 판정 문서화 |
| UX 성숙도 | 시각 사용성 평균 **50 → ≈78** (재감사 74점 후 P1 수정·시각화 주입) |
| 정직성 | `NO_GO`/`INCONCLUSIVE`/`BLOCKED_INDEX_SERIES_SOURCE` 원문 표기, six locks false, untouched test 미접근 유지 |

## 2. V6 1차 구축 결과

- **F0**: `?ui=v6` opt-in shell (`shellMode` 4번째 shell), 전용 `src/v6shell/` 격리, 안전 스트립+기본 닫힘 drawer
- **F1**: 일봉 DB 전수 감사(4,727테이블) → 유동성 상위 500 universe manifest 동결(SHA `8695ca76…`), ETF 혼입 `UNVERIFIED` 캐비앗 명시
- **백엔드**: GET-only `/api/v6/*` 9개 라우트(status/universe/data-readiness/experiment/runs/run-detail/insight 3종), 405+`Allow: GET` 계약, path traversal 차단
- **연구 실행**: 결합 인과 dataset(`kronos_v6_joined_dataset.v1`, 일봉 D-1 feature × 5분봉 exact 15:20 체결) → 사전등록 동결 → smoke `NO_GO`(shuffled 대조군 발동) → full 3-seed `INCONCLUSIVE`(1/3 seed) → 결과 문서
- **성능 수정**: dataset 생성기의 O(n²) 스캔·메모리 폭탄을 스트리밍으로 교체(SHA 등가 증명, 1시간+ 소멸 → 수 분)

## 3. V6.1 UX 고도화 결과

Newsletter_AI 대시보드(`pipeline-stages`, `status-cards`, full-width `main`) 벤치마크 적용:

### 3.1 IA: 13페이지 → 5탭

```text
홈(KPI) · 강화학습(단일 탭) · 인사이트 · 다른 레인 · 설정
```

### 3.2 강화학습 단일 탭 + 클릭형 프로세스 스테퍼

- 상단 STEP 1~6 카드(데이터→실험 설계→학습→평가→비교→보고서), `/api/v6/status` 원문 토큰으로 상태색(FROZEN/HAS_RUNS 녹색·BLOCKED 적색·NOT_RUN 회색)
- 카드 클릭 = 서브뷰 전환, `?tab=rl&step=<id>` deep link
- 구 주소 자동 매핑: `?tab=training` → `tab=rl&step=training`, `?tab=insight-flow` → `tab=insight&sub=flow` 등

### 3.3 전체 폭 + 시각화

- `max-width:980px` 전면 제거 → 화면 사용률 실측 **28% → 98%**
- echarts 12캔버스: 학습 곡선(60M 기준선), 평가 NAV 곡선+seed별 비용 바, 전략별 NAV 가로 바, 수급 랭킹 바 4종, 종목 40년 차트(₩축·dataZoom·수급 페인), breadth 게이지, 자본 배분 바
- 홈: KPI 4카드(클릭 이동+진행바) + KRX blocker 배너 + 여정 스테퍼 + 빠른 이동
- Data 페이지 JSON 원문 덤프 제거 → 스탯 타일+경계 칩

## 4. 탭별 사용성 점수 변화

| 화면 | V6 초기 | V6.1 최종 |
|---|---:|---:|
| 홈 | 55 | **82** |
| RL·데이터 | 40 | **72** |
| RL·실험 설계 | 50 | **75** |
| RL·학습 | 45 | **78** |
| RL·평가 | 50 | **85** |
| RL·비교 | 42 | **84** |
| RL·보고서 | 58 | **75** |
| 인사이트·종목 | 60 | **85** |
| 인사이트·수급 | 55 | **82** |
| 인사이트·국면 | 50 | **74** |
| 레인·설정 | 45~55 | **65~70** |
| **평균** | **50** | **≈78** |

독립 아키텍트 재감사(중간 시점): 74/100 `USABLE_WITH_GAPS` → P1 5건(테마 대비·상태기계·launch 명령·run 상세·전 seed 비교) 즉시 폐쇄 후 시각화 주입.

## 5. 검증

```text
frontend: 357 passed · Svelte 432 files 0 errors/0 warnings · build 통과
backend: /api/v6 계약 + V3/V4/V5 회귀 43~92 passed (-W error)
반응형: 1440×900 / 1080×1920 / 390×844 — 수평 overflow 0
화면 사용률: 9개 주요 화면 98% (3440×1440 실측)
legacy deep link: overview/training/insight-flow/intraday 자동 매핑 확인
스크린샷: artifacts/v61-final-*.png, artifacts/v61-eval-charts.png 외
```

## 6. 한계·blocker

- **KOSPI/KOSDAQ 지수 수집**: 2026 KRX API가 로그인 계정 요구(익명 요청 400 "LOGOUT" 실측). `KRX_ID`/`KRX_PW` 설정 후 `scripts/collect_korean_index_artifact.py` 1회 실행 필요 — 해소 전까지 비교 STEP은 `BLOCKED_INDEX` 정직 표기
- 레인 탭은 링크 중심(65점) — V5 증거 화면의 V6 내재화는 후속 과제
- 홈 KPI에 미니 스파크라인 미탑재 — 후속 폴리시 항목
- 테마는 light/dark 2종 — 다중 테마 시스템은 V7 계획으로 이관

## 7. 관련 commit

| commit | 내용 |
|---|---|
| `e404204` | V6 목표 적합성 검토·3-Track 계획 |
| `9b8e650` | F0 opt-in shell + universe 동결 |
| `c7947d5` | P1/P2 + `/api/v6` |
| `e89e52b` | D-4 결합 dataset + P3/P4 |
| `e5c8ae0` | R-2 사전등록 동결 |
| `e5758a7` | R-3 트레이너+판정 기계 |
| `0a263d3` | P5/P6 + run-detail API |
| `0284385` | 인사이트 3종 + 보고서 |
| `4c38265` | 레인·설정 — 13페이지 완성 |
| `2daa131` | V5 계약 테스트에 v6 405 라우트 제외 |
| `70ee784` | dataset 스트리밍·O(n²) 수정 |
| `b7723c5` | 재감사 P1 폐쇄(테마·상태기계) |
| `d4ad9c5` | H1 연구 결과 문서(NO_GO/INCONCLUSIVE) |
| `718c6a3` | **V6.1 워크스페이스 IA+스테퍼+차트** |

## 8. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-20 | V6 구축과 V6.1 UX 고도화 결과 최초 기록. 사용성 평균 50→≈78. | GJC | 본 문서 커밋 |
