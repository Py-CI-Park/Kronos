# Kronos V7 페이지 단위 실행 계획서 — 브랜치-머지 전략 · 데이터 확보 · 요구사항 반영 재검토 — 2026-07-20

> 문서 ID: `KRONOS-V7-PAGED-EXECUTION-PLAN-2026-07-20`
> 작성일: `2026-07-20 KST`
> 상태: `PLAN_RECORDED / EXECUTION_READY`
> 기반 문서: `docs/kronos_v7_rl_models_and_reports_plan_2026-07-20.md` (3-Track 내용 정의) — 본 문서는 그 내용을 **페이지 단위 실행 순서**로 재편성한다. 대체가 아니라 실행 계획이다.
> 통합 브랜치: `feature/dashboard-v7-rl-reports` (master merge `acde888`, tag `fork-v1.5.0-dashboard-v6-rl-platform` 이후 분기)
> 정직성 경계: 수익성·승격·실거래·`GO` 주장 없음. push/PR/원격 배포 없음(별도 승인). V3 기본 유지.

## 목차

1. [기준점 상태](#1-기준점-상태)
2. [이전 요청사항 반영 재검토](#2-이전-요청사항-반영-재검토)
3. [데이터 확보 체계 — Quant-Insight 참조](#3-데이터-확보-체계--quant-insight-참조)
4. [브랜치-머지 전략](#4-브랜치-머지-전략)
5. [페이지별 실행 계획 (P1~P10)](#5-페이지별-실행-계획-p1p10)
6. [페이지 공통 완료 정의(DoD)](#6-페이지-공통-완료-정의dod)
7. [위험과 완화](#7-위험과-완화)
8. [변경 히스토리](#8-변경-히스토리)

## 1. 기준점 상태

| 항목 | 값 |
|---|---|
| master merge | `acde888` (V6 플랫폼 + V6.1 워크스페이스 + V7 계획) |
| tag | `fork-v1.5.0-dashboard-v6-rl-platform` (로컬, 미push) |
| 통합 브랜치 | `feature/dashboard-v7-rl-reports` |
| RL 판정 | H1 smoke `NO_GO` · full `INCONCLUSIVE` · test `NOT_RUN` (변동 없음) |
| **지수 blocker** | **해소됨** — 2026-07-20 pykrx 1.2.8 + KRX 로그인으로 수집 완료 |

### 1.1 확보된 지수 artifact (2026-07-20 수집)

```text
artifacts/korean_index/
├─ KOSPI  (1001): 2018-01-02 ~ 2026-06-12
│   normalized SHA-256 3ed025901b290a6ff3dd3b6c539397b1f224a824168609ed331ca26f2a839512
│   raw        SHA-256 7384bee14cbf3343438c5918231560a8462abf2cf0a1e17385504511949e11b6
└─ KOSDAQ (2001): 2018-01-02 ~ 2026-06-12
    normalized SHA-256 a42f3e306ff8af565441114127e5e599bcdd01afa156355e6d757469c20f5ba7
    raw        SHA-256 7bd81505c7533e546613232dea7c50511291db4b2d69a52a66fde716cf3d2a3c
정책 플래그: naver_disabled=true · no_fallback=true · no_interpolation=true
```

자격증명 취급: `KRX_ID`/`KRX_PW`는 `Quant-Insight/.env`에 존재하며 **런타임 환경변수로만 주입**한다. 값은 이 리포의 어떤 파일·커밋에도 기록하지 않는다. KRX 비밀번호 90일 만료 정책(CD010 오류 시 갱신)에 유의한다.

## 2. 이전 요청사항 반영 재검토

사용자가 요청했던 항목 전수 점검:

| # | 요청 | 상태 | 근거 / 잔여 조치 |
|---|---|---|---|
| 1 | REINFORCEMENT LEARNING 단일 탭 | ✅ 반영 | V6.1 `tab=rl` 단일 워크스페이스 (`718c6a3`) |
| 2 | 상단 프로세스(단계) 표시 | ✅ 반영 | STEP 1~6 스테퍼, 상태색 실시간 (`ProcessStepper.svelte`) |
| 3 | 프로세스 클릭 시 해당 단계로 이동 | ✅ 반영 | 카드 클릭 → `?tab=rl&step=<id>` deep link |
| 4 | 키보드/탭 순서 내비게이션 | ✅ 반영 (보강 여지) | 네이티브 `<button>` — Tab 순서·Enter/Space·`:focus-visible` 동작 확인. 방향키 roving tabindex는 P5에서 보강 |
| 5 | Newsletter_AI 구조·프로세스 벤치마크 | ✅ 반영 | pipeline-stages·status-cards·full-width main 적용 |
| 6 | Newsletter_AI 테마·비주얼 심화 벤치마크 | 🔶 계획 반영 | 테마 토큰 6종 체계·`--font-scale`·HTML 생성기 분석 완료 → P4/P5에서 구현 |
| 7 | 비주얼·사용자 친화(화면 활용·차트) | ✅ 1차 반영 | 사용성 50→≈78, 사용률 98%. 목표 85+는 P4/P5 |
| 8 | 실제 RL 모델 생성 계획 | ✅ 계획 확정 | M1 tabular-Q v2 → M2 SB3 PPO → M3 LinUCB → M4 게이트 (각 독립 사전등록) → P7~P10에서 실행 |
| 9 | 구조해석 보고서급 화려한 HTML 결과 양식 | ❌ 미구현 → **P2** | 16절 self-contained HTML 표준 양식 정의 완료 |
| 10 | 결과 리포트 탭(열람 기능) | ❌ 미구현 → **P3** | 카탈로그 API + sandbox 뷰어 설계 완료 |
| 11 | 데이터 확보 — Quant-Insight 참조 | ✅ 1차 완료 | KRX 자격증명 확인, **지수 수집 오늘 완료(§1.1)**. 수집기 패턴 확장은 P6 |
| 12 | 결과 보고서 문서화·커밋 | ✅ 반영 | `docs/kronos_dashboard_v61_result_2026-07-20.md` |

결론: UX/UI 골격·계획류는 반영 완료. **미구현 핵심은 HTML 리포트 시스템(P2/P3)과 모델 실행(P7~P10)**이며 본 계획이 이를 페이지로 배치한다.

## 3. 데이터 확보 체계 — Quant-Insight 참조

`D:/Chanil_Park/Project/Programming/Quant-Insight/`에서 재사용할 검증된 패턴:

| Quant-Insight 자산 | 내용 | Kronos 이식 방침 |
|---|---|---|
| `collectors/base.py` + graceful-skip 계약 | 인증 실패/비거래일 → 0건 적재+warning, 예외 전파 없음 | V7 수집기 공통 계약으로 채택 |
| `collectors/pykrx_flow_aggregate.py` | 투자자별(기관/외국인/개인) 순매수 집계 | P6 후보 ① — RL feature 확장(시장 수급 국면) |
| `collectors/pykrx_foreign_ratio.py` | 외국인 보유/한도 소진율 | P6 후보 ② (일봉 DB 기존 컬럼과 중복 검증 후) |
| `collectors/pykrx_shortselling.py` | 공매도 잔고/거래 | P6 후보 ③ — 신규 feature 계열 |
| `collectors/pykrx_fundamental.py` | PER/PBR/배당 등 | P6 후보 ④ — 저평가 RULE 기준선용 |
| `config/loader.py` | `.env`→`os.environ` 단일 주입 지점 | 자격 필요 스크립트에서 동일 패턴(단, Kronos에는 `.env` 커밋 금지) |
| 90일 만료 운영 지식 | CD010 → data.krx.co.kr 갱신 | 수집 실패 시 진단 절차로 문서화 |

원칙 유지: 수집은 **오프라인 custody artifact 생성으로 격리**(수집 시점에만 네트워크), 런타임 검증은 네트워크 0. Naver 계열 수집기는 지수·시세에 대해 정책상 금지 유지(뉴스 등 비가격 데이터는 별도 승인 전 도입하지 않음). RL 사용 시 모든 신규 데이터도 **D-1 이하 feature 전용**, 체결·라벨 권위는 5분봉 exact 15:20 불변.

## 4. 브랜치-머지 전략

```text
master ──(acde888, tag fork-v1.5.0)
  └─ feature/dashboard-v7-rl-reports          ← 통합 브랜치(본 계획서 커밋)
       ├─ feature/v7-p01-index-overlay        ← 페이지 1 개발
       │     └─ 완료·검증 → --no-ff merge → 통합 브랜치
       ├─ feature/v7-p02-report-builder
       ├─ … (P3~P10 동일)
       └─ 전 페이지 완료 → 통합 검증 → master merge + tag (별도 승인)
```

규칙:

1. 페이지 브랜치는 **항상 통합 브랜치 최신에서 분기**하고, 완료 즉시 `--no-ff` merge 후 삭제한다.
2. merge 전 페이지 DoD(§6) 전부 통과. 실패 시 merge 금지, 브랜치에서 수정.
3. 페이지 간 의존은 번호 순서로만 해결(P2는 P1 merge 후 분기). 병행 가능 표시(∥)된 페이지만 동시 분기 허용.
4. 통합 브랜치→master merge와 새 tag는 **사용자 승인 후에만**.

## 5. 페이지별 실행 계획 (P1~P10)

### P1 — 지수 오버레이 통합 (`feature/v7-p01-index-overlay`)

- §1.1 artifact를 V6 비교 STEP·`/api/v6/status`에 연결, `BLOCKED_INDEX_SERIES_SOURCE` 해제
- 비교 STEP에 KOSPI/KOSDAQ 정규화 곡선(기준일=100) vs 전략 NAV 차트 추가
- artifact 무결성 재검증(SHA 재계산 일치) 테스트, 결측일은 결측으로 표기(보간 금지)
- 산출: 백엔드 route 확장 + `ComparePage` 차트 + 테스트

### P2 — HTML 리포트 빌더 (`feature/v7-p02-report-builder`)

- `stom_rl/v7_report_builder.py`: run 디렉터리(manifest·events·prereg·dataset manifest) → **16절 self-contained HTML**(기반 계획 §5.2 양식: 판정 히어로→KPI→데이터 계보→학습 곡선→비용 민감도→기준선 비교→지수 대비(P1 산출 사용)→원인 분석→재현 명령→해시 부록→면책)
- 차트는 의존성 없는 서버사이드 SVG, 외부 리소스 0, 값 재계산 금지(manifest 원문만)
- **기존 2개 run(smoke NO_GO·full INCONCLUSIVE) 소급 생성**으로 즉시 검증
- 산출: 빌더 + `report_manifest.json`(SHA) + 단위 테스트(판정 원문·외부 리소스 0 검사)

### P3 — 리포트 카탈로그 API + 리포트 탭 (`feature/v7-p03-report-tab`)

- `GET /api/v6/reports`(카탈로그) + `GET /api/v6/reports/<id>`(HTML) — v51 report catalog의 allowlist·traversal 차단 패턴 재사용, GET-only 405 계약
- RL 워크스페이스 보고서 STEP: 판정 배지 카드 그리드 → sandbox iframe 전체 뷰어 → 다운로드+SHA
- 산출: API+계약 테스트, 뷰어, 브라우저 스크린샷

### P4 — 테마 시스템 (`feature/v7-p04-theme-system`) ∥ P3과 병행 가능

- Newsletter 토큰 계층(surface 6단계·text 4단계·border 3단계·shadow) 이식, `data-theme` 5종(light 기본 유지·dark·ocean·forest·quant-terminal), `--font-scale` 4단계, 설정 탭 선택·저장
- 산출: `core.css` 재편 + 설정 UI + 테마별 대비 스팟 검사

### P5 — KPI 폴리시 + 차트 테마 브리지 (`feature/v7-p05-visual-polish`)

- KPI 카드 tone ring·hover glow·진행바 그라데이션·미니 스파크라인
- echarts 팔레트를 테마 토큰에서 파생, 테마 전환 시 즉시 재렌더
- 스테퍼 방향키 roving tabindex 보강(§2 #4 잔여)
- 산출: 3 viewport 스크린샷 재평가 — **시각 사용성 목표 평균 85+**

### P6 — 데이터 확장 수집기 (`feature/v7-p06-data-collectors`)

- Quant-Insight 패턴(§3) 기반 custody 수집기 1~2종 우선(투자자 수급 집계·공매도), graceful-skip 계약
- 일봉 DB 기존 컬럼(`기관순매수` 등)과 중복·정합 검증 후 도입 — 중복이면 수집 생략하고 검증 보고서만
- 산출: 수집 스크립트 + artifact 해시 + 정합 보고서 (RL 투입은 P7 prereg에 명시된 것만)

### P7 — M1: tabular-Q v2 (`feature/v7-p07-m1-tabularq2`)

- `kronos_v7_prereg_m1` 동결(state 확장: 수급·breadth bucket / seed 5 / **exposure-matched shuffled control** — v1 대조군 결함 교정 사유 명시)
- 실행 → 판정 원문 기록 → **P2 빌더로 리포트 자동 생성** → P3 탭 노출 확인
- 산출: prereg JSON + run + report.html + 결과 문서

### P8 — M2: SB3 PPO 환경 + smoke (`feature/v7-p08-m2-ppo-env`)

- joined dataset 기반 gym Env(연속 관측·10-slot 제약), `kronos_v7_prereg_m2` 동결
- smoke(1 seed·축소 steps) → **컴퓨트 게이트 A-M2**: smoke 정상 종료+대조군 통과 시에만 본 학습 승인 요청
- 산출: Env+테스트, smoke run+리포트

### P9 — M2: PPO 본 학습·평가 (`feature/v7-p09-m2-ppo-full`) — A-M2 승인 후

- 3 seed 본 학습(GPU) → validation 판정 → (GO 후보 시에만) untouched test 1회
- 산출: run+판정+리포트+결과 문서

### P10 — M3/M4 + 통합 검증 (`feature/v7-p10-m3-m4-closure`)

- LinUCB(M3)·필터 게이트 결합(M4) prereg→실행→리포트
- 전체 회귀(V3/V4/V5/V6 계약, `-W error`)+프론트 전체+3 viewport 스크린샷+사용성 재평가
- V7 종합 결과 문서 → master merge·tag는 **별도 승인 요청으로 종료**

## 6. 페이지 공통 완료 정의(DoD)

1. 해당 페이지 신규·수정 코드의 테스트 통과 (`py -3.11 -m pytest <관련> -q -W error`, `bun test src`)
2. `npm run check` 0 오류/0 경고, `npm run build` 통과, dist 갱신 커밋
3. V3/V4/V5 계약 회귀 유지 (`test_v3_contract_snapshot` 외 관련 세트)
4. UI 변경 페이지는 3440×1440 + 390×844 스크린샷, 수평 overflow 0
5. 판정·차단 토큰 원문 유지(`NO_GO`/`INCONCLUSIVE`/`BLOCKED*` 미화 금지)
6. 통합 브랜치로 `--no-ff` merge + 페이지 브랜치 삭제 + 원장 갱신

## 7. 위험과 완화

| 위험 | 완화 |
|---|---|
| KRX 자격 90일 만료로 재수집 실패 | artifact는 오프라인 불변 — 재수집 필요 시에만 갱신. CD010 시 갱신 절차 문서화(§3) |
| 자격증명 유출 | 값은 리포 외부(`Quant-Insight/.env`)에만 존재, 커밋·로그·문서 기록 금지 |
| 페이지 브랜치 장기 표류 | 페이지당 1~2 세션 상한, 초과 시 분할 |
| dist 충돌(페이지 병행 시) | dist 재빌드는 merge 직전 통합 브랜치에서 1회 수행 |
| PPO 컴퓨트 폭주 | P8 smoke 게이트 필수, 조기중단 규칙 prereg 동결 |
| 리포트 미화 왜곡 | 값 재계산 금지·판정 원문·대조군 절 생략 불가·면책 필수(P2 테스트로 강제) |

## 8. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-20 | 페이지 단위(P1~P10) 브랜치-머지 실행 계획 최초 기록. 지수 artifact 수집 완료 반영, 이전 요청사항 12건 반영 재검토 수록 | GJC | 본 문서 커밋 |
