# Kronos V7 계획서 — 실전형 RL 모델 로드맵 · 화려한 HTML 결과 리포트 시스템 · 테마/비주얼 고도화 — 2026-07-20

> 문서 ID: `KRONOS-V7-RL-MODELS-AND-REPORTS-PLAN-2026-07-20`
> 작성일: `2026-07-20 KST`
> 상태: `PLAN_RECORDED / IMPLEMENTATION_NOT_STARTED`
> 범위: (T) Newsletter_AI 심화 벤치마크 기반 테마·비주얼 시스템, (M) 실제 강화학습 모델 생성 로드맵, (R) 구조해석 보고서급 HTML 결과 리포트 생성기 + 리포트 탭.
> 정직성 경계: 수익성·승격·실거래·paper-forward·`GO` 주장 없음. 기존 `NO_GO`/`INCONCLUSIVE` 유지. 새 실험은 새 사전등록으로만.
> 브랜치(계획 기준): `feature/dashboard-v6-rl-platform` @ `718c6a3`
> 대체 문서: 없음. `docs/kronos_v6_goal_review_and_plan_2026-07-19.md`의 후속.

## 목차

1. [목적과 배경](#1-목적과-배경)
2. [Newsletter_AI 심화 벤치마크 결과](#2-newsletter_ai-심화-벤치마크-결과)
3. [Track T — 테마·비주얼 시스템](#3-track-t--테마비주얼-시스템)
4. [Track M — 강화학습 모델 생성 로드맵](#4-track-m--강화학습-모델-생성-로드맵)
5. [Track R — HTML 결과 리포트 시스템](#5-track-r--html-결과-리포트-시스템)
6. [실행 순서와 세션 계획](#6-실행-순서와-세션-계획)
7. [승인 게이트](#7-승인-게이트)
8. [수용 기준](#8-수용-기준)
9. [위험과 완화](#9-위험과-완화)
10. [관련 문서](#10-관련-문서)
11. [변경 히스토리](#11-변경-히스토리)

## 1. 목적과 배경

V6.1로 플랫폼 골격(5탭·프로세스 스테퍼·차트·정직성 계약)이 완성됐다. 다음 단계는 세 가지다.

1. **실제 쓸모 있는 RL 모델**: v1(tabular-Q)은 `INCONCLUSIVE`로 정직하게 끝났다. 원인(1/3 seed 불안정, 대조군 설계 한계)을 반영한 **모델 시리즈**를 새 사전등록으로 진행한다.
2. **결과의 보고서화**: 실험이 끝날 때마다 구조해석 보고서처럼 **모든 시각 증거를 포함한 self-contained HTML 리포트**를 자동 생성하고, 대시보드 리포트 탭에서 열람한다.
3. **비주얼 완성도**: Newsletter_AI 수준의 테마 시스템과 카드·차트 폴리시로 상향한다.

## 2. Newsletter_AI 심화 벤치마크 결과

이번에 직접 확인한 재사용 대상 패턴:

| 패턴 | 위치 | Kronos 적용 |
|---|---|---|
| **다중 named 테마** | `frontend/src/app/globals.css` — `data-theme` 6종(dark 기본·light/arctic_frost·ocean·forest·sunset…), 테마당 surface 6단계+text 4단계+border 3단계+shadow 토큰, `--font-scale` | V6 테마를 2종→5종+로, 토큰 계층 정밀화, 글자 크기 스케일 설정 |
| **파이프라인 스테퍼** | `pipeline-stages.tsx` | V6.1에 이미 적용 완료 |
| **KPI 카드 폴리시** | `status-cards.tsx` — tone별 tinted icon ring, hover lift+glow shadow, 진행바 그라데이션, 카드 전체 링크 | 홈 KPI 카드에 tone ring·glow·스파크라인 추가 |
| **2열 콘텐츠 그리드** | `dashboard/page.tsx` — `2xl:grid-cols-[1.25fr_0.75fr]` | 적용 완료, 유지 |
| **로그 콘솔·실행 제어** | `pipeline/log-console.tsx`, `pipeline-control.tsx` | 학습 STEP의 라이브 이벤트 뷰(후속) |
| **HTML 리포트 생성기** | `generators/html_report.py` — `HTMLReportGenerator`(self-contained 스타일드 HTML)+`EmailHTMLGenerator`(인라인 스타일), 데이터 객체→output/ 파일 | **Track R의 직접 참조** — Kronos 연구 리포트 빌더의 골격 |
| **리포트 열람 UX** | history/files 패널 + wiki viewer(DOMPurify) | 리포트 탭 카탈로그+안전 뷰어 |

## 3. Track T — 테마·비주얼 시스템

| 단계 | 내용 |
|---|---|
| T1 | **테마 토큰 확장**: `core.css`를 Newsletter 계층(surface-strong/solid/muted/soft/hover 5~6단계, text 4단계, border 3단계, shadow-color)으로 정렬. `data-theme` 5종: `light`(기본 유지), `dark`, `ocean`, `forest`, `quant-terminal`(고대비 흑녹). 설정 탭에서 선택·저장 |
| T2 | **`--font-scale`**: 0.9/1.0/1.1/1.25 사용자 설정, V6 전 페이지 rem 기반 반영 |
| T3 | **KPI 카드 폴리시**: tone ring(아이콘 사각), hover lift+tone glow, 진행바 그라데이션, 미니 스파크라인(최근 val NAV) |
| T4 | **차트 테마 브리지**: echarts 팔레트를 테마 토큰에서 파생(`chart-theme` 헬퍼) — 테마 전환 시 차트 즉시 재렌더 |

## 4. Track M — 강화학습 모델 생성 로드맵

### 4.1 v1 결과에서 얻은 교훈 (설계 반영)

- 1/3 seed만 기준 충족 → **state 표현력 부족 + 탐색 경로 민감**: bucket 4feature 조합으로는 국면 변화를 못 견딤
- smoke에서 shuffled 대조군이 no-trade 초과 → **대조군 기준선 결함**: 상승 구간에선 임의 매수도 no-trade를 이김. **exposure-matched control**(동일 노출 임의 정책 대비)로 교체 필요
- rule_topk_ret5 −37.6% → 단기 모멘텀 역효과 구간; RULE 기준선 세트 다양화 필요(저변동·수급 RULE 추가)

### 4.2 모델 시리즈 (각각 독립 사전등록 버전)

| ID | 모델 | 핵심 설계 | 사전등록 | 컴퓨트 |
|---|---|---|---|---|
| **M1** | tabular-Q v2 | state 확장(수급 2feature 추가 bucket, 시장 breadth 국면 bucket), α/ε 스윕 3셀, seed 5개, exposure-matched shuffled control | `kronos_v7_prereg_m1` | 낮음(CPU 수십 분) |
| **M2** | **SB3 PPO** (본명) | 기존 `daily_portfolio_sb3_*` 프로토콜 스택 재사용, joined dataset 기반 gym Env(연속 feature 벡터 관측·10-slot 마스크), 3 seed × 200k timesteps, checkpoint=val NAV | `kronos_v7_prereg_m2` | 중간(GPU 권장, RTX 4080S 보유) |
| **M3** | LinUCB 컨텍스추얼 밴딧 | 선형 신뢰상한 종목 선택 + 10-slot 제약 — 해석 가능성 최상, 계수 리포트화 적합 | `kronos_v7_prereg_m3` | 낮음 |
| **M4** | 필터 게이트 결합 | M1~M3 최선 정책 앞단에 D4 trade-quality filter 결합(기존 `build_action_filter_decision` 재사용) | 변형 등록 | 낮음 |

### 4.3 공통 프로토콜 (모든 모델 동일)

- 데이터: `kronos_v6_joined_dataset.v1` full(786,872행, SHA `ae44c805…`) 또는 재생성 pin
- 체결: exact 15:20 proxy, `official_close=false`, fallback 없음
- 회계: ₩60M/10슬롯/₩5M/예비 ₩10M, 비용 0.00%/0.23%/0.46%
- 기준선: no_trade + RULE 3종(모멘텀·저변동·기관순매수) + random + **exposure-matched shuffled**
- 판정: validation 다수 seed 합의 → untouched test **1회** → `GO_CANDIDATE/NO_GO/INCONCLUSIVE` 원문 기록. 사후 retune 금지(새 버전만)
- KRX 지수 artifact 확보 시(사용자 자격증명) KOSPI/KOSDAQ 상대 성과를 평가·리포트에 포함

## 5. Track R — HTML 결과 리포트 시스템

### 5.1 리포트 생성기 (`stom_rl/v7_report_builder.py`)

Newsletter의 `HTMLReportGenerator` 패턴을 연구 리포트로 이식:

- 입력: run 디렉터리(`run_manifest.json`+`events.jsonl`+`dataset_manifest.json`+prereg JSON)
- 출력: **self-contained 단일 HTML** (`webui/rl_runs/v6_daily_h1/<dataset>/<train>/report.html`) — 외부 네트워크 0, 스타일 인라인, 차트는 **서버사이드 SVG 렌더**(의존성 없는 자체 SVG 빌더; echarts CDN 금지)
- 산출과 동시에 `report_manifest.json`(SHA-256, 생성 파라미터, 판정) 기록

### 5.2 리포트 표준 양식 (구조해석 보고서 스타일, 16절)

```text
① 표지: 판정 히어로(INCONCLUSIVE/NO_GO/GO_CANDIDATE 대형 배지) · run ID · 기간 · SHA
② 경영 요약: KPI 그리드(val NAV·수익률·MDD·거래수·seed 합의)
③ 연구 질문·사전등록 요약(가설/중단 기준/등록 SHA)
④ 데이터 계보: universe·기간·행수·결측 차트·해시 체인 다이어그램
⑤ 환경·회계: 자본 배분 도넛 · 제약 표
⑥ 알고리즘·하이퍼파라미터
⑦ 학습 곡선: seed별 episode-val NAV 라인(60M 기준선)
⑧ 평가: NAV 곡선 · 비용 3중 민감도 바
⑨ 기준선·대조군 비교: 전략별 NAV 가로 바 + 대조군 판정
⑩ (지수 확보 시) KOSPI/KOSDAQ 대비 정규화 곡선 — 미확보 시 BLOCKED 명시 박스
⑪ 원인 분석(구조 해석): seed 분산, feature 기여, 국면 민감도
⑫ 판정과 근거(사전등록 규칙 대조표)
⑬ 한계·blocker ⑭ 재현 명령 ⑮ artifact 해시 부록 ⑯ 면책(연구용·비수익 주장)
```

디자인: 테마 토큰 기반 인쇄 친화 라이트 팔레트 + 섹션 히어로 컬러 밴드 + KPI 타일 + SVG 차트. **모든 수치는 manifest에서만** — 리포트 생성기는 값 재계산 금지(왜곡 방지).

### 5.3 리포트 탭 (대시보드)

- 백엔드: `GET /api/v6/reports`(카탈로그: run·판정·생성시각·SHA) + `GET /api/v6/reports/<id>`(HTML 원문) — v51 report catalog의 allowlist·traversal 차단·sanitize 패턴 재사용, GET-only 405 계약
- 프론트: RL 워크스페이스 **보고서 STEP 확장** — (a) 리포트 카탈로그 카드 그리드(판정 배지·미리보기 KPI), (b) 클릭 시 sandbox iframe(또는 DOMPurify 정화) 전체 화면 뷰어, (c) HTML 다운로드 버튼 + SHA 표시
- 규칙: 판정과 숫자는 원문 그대로, 뷰어는 read-only, 리포트 삭제·수정 API 없음

## 6. 실행 순서와 세션 계획

```text
세션 1  R1 리포트 빌더 + 기존 2개 run(NO_GO·INCONCLUSIVE) 리포트 소급 생성  ← 즉시 가치
세션 2  R2/R3 리포트 API + 보고서 STEP 뷰어 ∥ T1 테마 토큰
세션 3  M1 사전등록 동결 → 실행 → 리포트 자동 생성 검증 ∥ T2/T3
세션 4  M2 PPO Env 구현 + smoke                                ← A-M2 게이트
세션 5  M2 본 학습(GPU) → 평가 → 리포트 ∥ T4
세션 6  M3/M4 + 통합 검증·스크린샷 재평가·결과 문서
(병행) 사용자 KRX_ID/KRX_PW 설정 시 지수 수집 → 비교 STEP·리포트 ⑩ 활성화
```

## 7. 승인 게이트

| 게이트 | 시점 | 내용 |
|---|---|---|
| A-R | 세션 1 전 | 리포트 양식(§5.2) 확정 — 본 계획 승인으로 갈음 가능 |
| A-M1 | M1 실행 전 | prereg v7-m1 동결 확인 |
| A-M2 | PPO 본 학습 전 | 컴퓨트 예산(GPU 시간) 승인 |
| 상시 금지 | — | push/PR/신규 태그, 실거래·브로커·paper-forward, V6 기본 전환, 사후 retune |

## 8. 수용 기준

- 기존 2개 run의 HTML 리포트가 생성되어 보고서 STEP에서 열람·다운로드 가능(판정 원문 표기)
- 새 모델 실행 종료 시 리포트가 자동 생성되고 카탈로그에 나타남
- M1~M3 각각 사전등록→실행→판정→리포트의 완결 체인 보유(판정 결과 무관)
- 테마 5종 전환 시 전 페이지·차트 가독성 유지(대비 검증)
- 회귀: V3/V4/V5 계약 + `/api/v6` 테스트 + 반응형 3 viewport 유지

## 9. 위험과 완화

| 위험 | 완화 |
|---|---|
| 리포트가 성과를 미화 | 값 재계산 금지(manifest 원문만), 판정 배지 원문, 면책 절 필수, 대조군 절 생략 불가 |
| PPO 컴퓨트 폭주 | smoke(1 seed·10k steps) 게이트 후 본 학습, 조기중단 규칙 사전등록 |
| 대조군 재설계가 사후 조작으로 보임 | v1 결과 문서에 결함 근거 기록됨 — v7 prereg에 변경 사유 명시 절 포함 |
| iframe 리포트 XSS | self-contained 생성물만 allowlist, sandbox 속성, 외부 리소스 0 검증 테스트 |
| 테마 확장으로 대비 회귀 | 테마별 자동 대비 검사(스크린샷+텍스트 대비 스팟) 세션 6에 포함 |

## 10. 관련 문서

- `docs/kronos_dashboard_v61_result_2026-07-20.md` (직전 결과)
- `docs/kronos_v6_daily_h1_rl_result_2026-07-19.md` (v1 연구 판정 — 대조군 결함 근거)
- `docs/kronos_v6_prereg_h1_2026-07-19.json` (v1 사전등록)
- `docs/wiki/14-document-standard.md` (보고서 절 구조 근거)

## 11. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-20 | Newsletter_AI 심화 벤치마크(테마 토큰·HTML 생성기) 반영한 V7 3-Track 계획 최초 기록 | GJC | 본 문서 커밋 |
