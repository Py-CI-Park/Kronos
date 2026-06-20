# Model Factory 개발 페이지 정리 — 2026-06-11

## 목적

`docs/stom_dashboard_model_factory_review_2026-06-11.md`(설계)와
`docs/stom_rl_uptrend_failure_analysis_and_improvement_2026-06-11.md`(원인 분석)에서
확정된 개발 내용을 실행 가능한 **페이지 단위**로 분해한 작업 원장이다.

가드레일: 왕복 23bp 고정, `ts_imb`는 RULE baseline(RL 아님), webui는 read-only
(학습/주문/쓰기 금지), OOS 무튜닝, 사전등록 선행, 기존 `NO-GO`와
`STOP_RL_EXPANSION` 결정 유지. 수익 보장 없음.

## 마스터 페이지 테이블

| 페이지 | 이름 | 목표 한 줄 | 예상 | 선행 조건 | 상태 |
|---:|---|---|---:|---|---|
| P1 | Episode Store | 전 universe(2,427 테이블) 에피소드 샘플러 + parquet 캐시 | 2일 | 없음 | 대기 |
| P2 | Run Registry + 실험 큐 | 사전등록 강제 실험 큐와 run 계보 SQLite registry | 1.5일 | 없음 (P1과 병행 가능) | 대기 |
| P3 | Gate 진단 확장 | `DEGENERATE_POLICY` 분류 + 행동분포/entropy 진단 | 1일 | 없음 (병행 가능) | 대기 |
| P4 | Probability Lane | P(win) 분류기 + isotonic 보정 + 엣지 회계 (**기대값 최고**) | 3일 | P1, P2 + 사전등록 문서 | 대기 |
| P5 | Walk-forward 통합 | 연도 경계 ≥5 folds, OOS ≥100 trades 강제 | 1.5일 | P4와 동시 진행 | 대기 |
| P6 | Full-Train RL 경로 | VecEnv 병렬 + ≥2e5 steps `--full-train` | 3일 | **P4 gate 통과 시에만** | 차단 (조건부) |
| P7 | Factory Read-only API | `/api/rl/factory/*`, calibration/edge-ledger API | 1일 | P2, P4 산출물 | 대기 |
| P8 | Dashboard 카드 3종 | Calibration · Edge Ledger · Factory Status 카드 | 2일 | P7 | 대기 |
| P9 | Round Replay 패널 | 09:00~09:30 세션 리플레이 + P(win) 오버레이 (read-only) | 2일 | P8 | 대기 (후순위) |
| P10 | RULE 사이징/리스크 설계 | 2026-05-29부터 미룬 운영 설계 (모델과 독립) | 2일 | 없음 — **언제든 병행** | 대기 |
| P11 | 통합 검증 + 결과 문서 | 전체 회귀 + dated result 문서 발행 | 1일 | P1~P8 | 대기 |

권장 실행 순서: **P1 → P2 (+P3, P10 병행) → P4+P5 → P7 → P8 → P11**, P6은 P4
결과가 gate를 통과할 때만, P9는 여유 시.

병렬 가능 조합: {P1, P2, P3, P10}은 상호 독립. {P4 사전등록 문서 작성}은 P1/P2
진행 중 선작성 가능. 사전등록→실행→해석 순서는 페이지 내부에서 직렬 유지.

---

## P1 — Episode Store

| 항목 | 내용 |
|---|---|
| 목표 | 매 실험 ad-hoc 18세션 샘플 → 전 universe 에피소드 공급 계층 |
| 신규 파일 | `stom_rl/factory/__init__.py`, `stom_rl/factory/episode_store.py` |
| 테스트 | `tests/test_stom_rl_factory_episode_store.py` |

작업 항목:

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | sqlite `mode=ro`/`query_only` 전 테이블 스캔러 | 2,427 테이블 열거, 쓰기 시도 시 예외 |
| 2 | 세션(일자) 단위 에피소드 추출 + 시간창(090000~093000) 필터 | 세션당 frame 수·결측 정책 manifest 기록 |
| 3 | parquet 캐시 (`.omx/artifacts/factory_episode_cache/`) | 동일 쿼리 2회째 캐시 적중, 캐시 키 = 테이블+세션+창+스키마 해시 |
| 4 | 종목코드 선행 0 보존 (`000250` str 유지) | 캐시 왕복 후 dtype/값 동일성 테스트 |
| 5 | 샘플링 API: `sample_episodes(n, split, seed)` | seed 고정 시 재현 동일, split 누수 없음 |

검증 명령: `py -3.11 -m pytest tests/test_stom_rl_factory_episode_store.py -q`

## P2 — Run Registry + 실험 큐

| 항목 | 내용 |
|---|---|
| 목표 | 실험 추적을 docs 수기 → SQLite registry + 큐로 |
| 신규 파일 | `stom_rl/factory/run_registry.py`, `stom_rl/factory/experiment_queue.py` |
| 테스트 | `tests/test_stom_rl_factory_registry.py` |

작업 항목:

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | registry 스키마: run_id, split_hash, cost_bps, seed, stage(smoke/full/walkforward/paper), parent_run, prereg_doc, verdict | 스키마 마이그레이션 idempotent |
| 2 | enqueue 가드: `prereg_doc` 경로 없으면 거부 | 거부 테스트 |
| 3 | cost_bps != 23 거부 (기존 `CandidateConfigError` 정책 재사용) | 거부 테스트 |
| 4 | 상태 전이: queued→running→done/failed, 계보 조회 | 전이/계보 테스트 |
| 5 | registry 파일 위치 `webui/rl_runs/factory_registry.sqlite` (generated 영역) | 소스 디렉토리 비오염 |

## P3 — Gate 진단 확장

| 항목 | 내용 |
|---|---|
| 목표 | "신호 없음(`NO-GO_CONTROL`)"과 "학습 안 됨(`DEGENERATE_POLICY`)" 구분 |
| 수정 파일 | `stom_rl/opening_30m_rl_candidate_gate.py`, `stom_rl/opening_30m_rl_candidate_training.py` |
| 테스트 | `tests/test_stom_rl_opening_candidate_gate.py` 확장 |

작업 항목:

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | `_evaluate`에 행동 분포·entropy 수집 | eval log에 `action_distribution` 필드 |
| 2 | 단일 행동 ≥95% 또는 ablation 전수 동일 수익 → `DEGENERATE_POLICY` | 판정 단위 테스트 (퇴화/비퇴화 케이스) |
| 3 | manifest에 `policy_diagnostics`, `sample_power`(oos_trades, ci_width) 필드 | 스키마 테스트 |
| 4 | 기존 verdict 의미 불변 (추가 분류만) | 기존 테스트 전부 green |

## P4 — Probability Lane (핵심)

| 항목 | 내용 |
|---|---|
| 목표 | 참조 이미지의 "P(up) + EDGE VS BOOK" 구조를 도메인 번역: ts_imb 진입 후보 P(win) 분류기 + 보정 + 23bp 엣지 회계 |
| 신규 파일 | `stom_rl/factory/probability_lane.py`, 사전등록 `docs/stom_probability_lane_prereg_2026-06-*.md` |
| 테스트 | `tests/test_stom_rl_factory_probability_lane.py` |

작업 항목:

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | 사전등록 문서: 가설·feature·fold·최소 N·gate 기준 고정 | 문서 커밋 후 실행 |
| 2 | 라벨 생성: 전 universe 갭상승 후보(N≥1,349) TP5/SL1/09:25 결과 | P1 episode store 사용, 누수 검사 |
| 3 | P(win) 분류기 (gradient boosting 우선, 신경망은 비교군) | walk-forward fold별 학습 |
| 4 | isotonic/Platt 보정 + Brier + reliability bins | `calibration` manifest 필드 |
| 5 | 엣지 회계: `edge = P·E[win] + (1−P)·E[loss] − 23bp`, 임계 미달 SKIP | trade별 edge ledger JSON |
| 6 | gate: no-trade/buy-and-hold/ts_imb 균등진입 baseline + shuffle controls + OOS ≥100 trades | 판정은 `GO_CANDIDATE`/`NO-GO_*`로 dated result 문서 발행 |

주의: 이 페이지의 산출물이 `NO-GO`여도 정상이다. 그 경우 P6은 영구 차단 유지.

## P5 — Walk-forward 통합

| 항목 | 내용 |
|---|---|
| 목표 | 단일 frozen split → 연도 경계 ≥5 folds 표준화 |
| 신규/수정 | `stom_rl/factory/walk_forward.py` (기존 `stom_rl/walk_forward.py` 재사용/확장) |
| 테스트 | `tests/test_stom_rl_factory_walk_forward.py` |

작업 항목:

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | fold 생성기: 연도 경계, train/val/OOS 비중첩 | fold 누수 단위 테스트 |
| 2 | fold별 OOS trades 집계, ≥100 미달 시 자동 `INCONCLUSIVE` | 미달 케이스 테스트 |
| 3 | fold 간 verdict 합성 규칙 (전 fold 통과만 GO) | 합성 테스트 |

## P6 — Full-Train RL 경로 (조건부 차단)

**선행 조건: P4 결과가 baseline/control gate 통과.** 미통과 시 이 페이지는
`STOP_RL_EXPANSION` 결정에 따라 착수 금지.

| 항목 | 내용 |
|---|---|
| 신규 파일 | `stom_rl/factory/train_full.py` |
| 테스트 | `tests/test_stom_rl_factory_train_full.py` (smoke 모드로) |

작업 항목:

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | SB3 `SubprocVecEnv` 병렬 (Threadripper 64코어) | env 수 설정 가능, smoke 테스트 통과 |
| 2 | `--full-train`: timesteps ≥2e5, 기존 smoke 기본값 불변 | smoke 경로 회귀 무변화 |
| 3 | 학습 곡선·행동분포 로그 → P3 진단 연동 | manifest 연동 테스트 |
| 4 | 평가는 P5 walk-forward + P3 gate 경유만 허용 | 직접 OOS 평가 경로 없음 |

## P7 — Factory Read-only API

| 항목 | 내용 |
|---|---|
| 신규 파일 | `webui/rl_dashboard_factory.py` (`app.py`에는 라우트 등록만) |
| 테스트 | `tests/test_stom_rl_dashboard_factory_api.py` |

| # | 엔드포인트 | 내용 | 완료 기준 |
|---:|---|---|---|
| 1 | `GET /api/rl/factory/queue` | 큐/registry 스냅샷 (read-only) | 쓰기 메서드 없음 |
| 2 | `GET /api/rl/runs/<run>/calibration` | Brier·reliability bins | path traversal 거부 테스트 |
| 3 | `GET /api/rl/runs/<run>/edge-ledger` | trade별 엣지 원장 | limit 클램프 (기존 `_rl_table_limit` 재사용) |
| 4 | 서버 계산 비교 필드 (edge>0 여부 등) 포함 | UI가 해석 발명하지 않음 |

## P8 — Dashboard 카드 3종

| 항목 | 내용 |
|---|---|
| 신규 파일 | `webui/v2_src/src/tabs/rlTrading/CalibrationCard.svelte`, `EdgeLedgerCard.svelte`, `FactoryStatusCard.svelte` |
| 수정 파일 | `RLTradingTab.svelte` (카드 마운트) — `OpeningWorkflowCard.svelte`는 건드리지 않음 |
| 테스트 | `tests/test_stom_rl_dashboard_tab.py` 확장 + `npm --prefix webui/v2_src run build` |

| # | 카드 | 내용 | 완료 기준 |
|---:|---|---|---|
| 1 | Calibration | reliability diagram, Brier, bias vs 0.5, "현재 N의 CI 폭" LLN 문구 | `NO-GO`/`INCONCLUSIVE` 시 명시 배지 |
| 2 | Edge Ledger | trade별 P(win)·엣지·SKIP 표시, 23bp breakeven 라인 | RULE/모델 라벨 구분 |
| 3 | Factory Status | 큐 상태·계보·학습 스텝·degenerate 플래그 | "data ready ≠ model usable" 구분 유지 |

## P9 — Round Replay 패널 (후순위)

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | 세션 리플레이 API (기존 table API 재사용 우선) | 신규 쓰기 없음 |
| 2 | 09:00~09:30 타임라인 + P(win) 오버레이 Svelte 카드 | "관찰 도구, 수익 증거 아님" 라벨 |

## P10 — RULE 사이징/리스크 설계 (모델 독립, 병행 가능)

2026-05-29 resume 문서가 지정한 미완 트랙. **우상향 곡선을 실제로 보는 가장
빠른 경로.**

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | 사이징 비교: 고정 분수 vs 변동성 타게팅 (235 trades 로그 기반) | MDD/연패 분포 리포트 |
| 2 | 동시보유 한도·일손실 한도·전략 중단 조건 수치화 | 운영 룰 문서 (`*_result_*`) |
| 3 | 2022형 flat 연도 시나리오 스트레스 | 한도 내 생존 확인 |

## P11 — 통합 검증 + 결과 문서

| # | 작업 | 완료 기준 |
|---:|---|---|
| 1 | 전체 회귀: 기존 핵심 pytest 세트 + factory 테스트 | all green |
| 2 | `npm --prefix webui/v2_src run build` | 0 errors |
| 3 | dated result 문서 발행 (verdict 라벨 그대로) | docs 규칙 준수 |
| 4 | 생성물/소스 분리 점검 (`webui/rl_runs/`, `.omx/artifacts/`) | 소스 디렉토리 비오염 |

---

## 페이지 진행 규칙

1. 페이지 시작 전 해당 디렉토리 `AGENTS.md` 재확인.
2. 실험 페이지(P4~P6)는 사전등록 → 실행 → 해석 직렬 순서 고정, OOS 무튜닝.
3. 각 페이지 완료 시 검증 명령 실행 결과를 함께 보고.
4. P6은 P4 gate 통과 증거 없이 착수 금지.
5. 모든 산출물은 `webui/rl_runs/` 또는 `.omx/artifacts/` 아래로.
