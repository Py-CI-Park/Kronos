# 대시보드 백엔드 '모델 공장' 적합성 검토 및 개선 설계 — 2026-06-11

## 목적

참조 이미지(Threads @conanssam, "CLAUDE FABLE 5 · MIROFISH" 대시보드)를 분석하고,
현재 Kronos 대시보드 백엔드가 "수익 내는 강화학습/딥러닝 모델을 쉽게 만들 수 있는
구조"인지 진단한 뒤, 측정 가능한 기준으로 2~3배 개선하는 시스템 설계와 개발
안내를 제시한다.

이 문서는 연구/설계 문서다. 수익 보장·실거래 준비·브로커 연동을 주장하지 않는다.
기본 비용 가정은 왕복 23bp. 기존 `NO-GO` 판정과 `STOP_RL_EXPANSION` 결정은 그대로
유지된다. 본 문서의 자매 문서는
`docs/stom_rl_uptrend_failure_analysis_and_improvement_2026-06-11.md`다.

## 1. 참조 이미지 분석

이미지는 Polymarket BTC 5분/1시간 up/down 바이너리 마켓을 거래하는 AI 에이전트
대시보드 콘셉트다. 구성 요소:

| 패널 | 내용 |
|---|---|
| 헤더/PnL | Total PnL $330,853 · 36,402 trades · 71% WR · Sharpe 4.21 |
| Probability Lattice | 갈톤보드(quincunx) 시각화, bias 0.54, "Law of large numbers — the edge only needs repetition" |
| Relationship Graph | 신호 노드 그래프 → P(UP)=0.76 / P(DOWN)=0.24, **EDGE VS BOOK +29¢**, confidence 94.2% |
| BTC Hourly Pulse | 라운드 lifecycle: price to beat, 현재가, UP 51¢/DOWN 49¢, L2 호가, 카운트다운 |
| 푸터 provenance | model id, fills 수, backtest 41.8GB, latency 11ms, stack 표기 |

### 1.1 믿지 말아야 할 것

표시된 수치($330k, Sharpe 4.21, 71% WR)는 검증 불가능한 홍보/콘셉트 이미지다.
본 저장소의 anti-pattern 규칙("대시보드 시각물을 수익성 증거로 취급하지 말 것")
그대로, 이 이미지는 **시스템이 아니라 화면**이다. 화면을 베끼는 것은 목표가 아니다.

### 1.2 빌릴 가치가 있는 구조적 아이디어 (핵심)

이미지의 정직한 알맹이는 4가지이고, 전부 우리 진단과 정확히 합치한다.

1. **확률 우선(probability-first) 모델링**: 모델 출력은 "행동"이 아니라
   **보정된 P(up)**이고, 거래는 P(model)와 시장가격(book)의 괴리(=엣지)가 임계치를
   넘을 때만 발생한다. 우리 도메인 번역: P(win|진입후보) 분류기 + "엣지 = 기대수익
   − 23bp breakeven" 명시 회계. 현재 저장소에는 **확률 보정 도구가 전혀 없다**
   (calibration/Brier/reliability 검색 결과 0건).
2. **대수의 법칙 프레이밍**: bias 0.54 × 36,402 trades. 작은 엣지는 반복으로만
   곡선이 된다. 우리 현실: OOS TAKE 2~8건으로 판정해 왔다 — 정확히 반대다.
3. **바이너리 단일 결정 프레이밍**: "고정 horizon 내 up/down"은 multi-step RL이
   아니라 분류/메타라벨 문제다. 자매 문서 Phase 2와 동일 결론.
4. **라운드 lifecycle + provenance**: run 메타데이터(모델·fill 수·데이터 규모·
   지연시간)를 1급 시민으로 노출. 우리의 split hash/cost/seed 계약의 확장형.

## 2. 진단: 현 백엔드는 모델을 쉽게 만들 수 있는 구조인가?

**아니오.** 단, 이유가 중요하다. `webui/`는 의도적으로 read-only 증거 뷰어로
설계됐고 그 역할은 잘 한다(잘못이 아님). 문제는 **"증거 뷰어"와 "smoke 하네스"
사이에 모델 생산 계층이 통째로 없다**는 것이다.

### 2.1 계층별 진단표

| 계층 | 현재 상태 | 모델 공장 관점 평가 |
|---|---|---|
| 데이터 | 29.7GB·2,427종목 1초봉 DB. CLI마다 ad-hoc 바운드 샘플링(10테이블×2~5세션) | **병목.** 전 universe 에피소드 샘플러/캐시 없음. 매 실험 18세션 |
| 학습 | `stom_rl/*` CLI smoke 하네스. timesteps 16~512, PPO n_steps 2~8 | **사실상 부재.** full-train 경로·실험 큐·병렬화(64코어 미활용) 없음 |
| 평가 | gate(باseline/control/ablation) 우수. 단 OOS 2~8 trades 위에서 작동 | 설계는 좋고 **표본이 무의미.** 확률 보정 평가(Brier/reliability) 0건 |
| 실험 관리 | 산출물 = `webui/rl_runs/` JSON 파일 더미. run registry/모델 레지스트리/계보 없음 | **부재.** "어떤 실험을 했고 다음에 뭘 하나"가 docs 수기 관리 |
| 서빙/API | `app.py` 1,450줄 모놀리스: Kronos 예측 + STOM 진단 + 학습 모니터 + RL 증거 혼재 | 동작하나 결합도 높음. RL 증거 API 자체는 read-only 규칙 준수 |
| 시각화 | Svelte 탭 + 증거 테이블(controls/ablations/failure) 충실 | 증거 falsification은 강함. **확률·엣지·보정·LLN 패널 없음** |

### 2.2 한 줄 결론

현 시스템은 "모델을 **죽이는**(falsify) 공장"으로는 잘 설계됐고, "모델을
**만드는** 공장"은 존재하지 않는다. 우상향 모델이 안 나오는 이유의 절반은
시장이 아니라 이 빈 계층이다.

## 3. 개선 설계 — 3계층 아키텍처

"200~300% 개선"을 측정 가능하게 정의한다:

| 지표 | 현재 | 목표 (2~3배 이상) |
|---|---:|---:|
| 실험당 학습 스텝 | 16~512 | 2e5~1e6 (**~1000x**) |
| 실험당 데이터 | 18 세션 | 전 universe 수천 세션 (**~100x**) |
| OOS 판정 표본 | 2~8 trades | ≥100 trades, walk-forward ≥5 folds |
| 실험 처리량 | 수동 CLI 1회/세션 | 큐 기반 일 단위 배치 (64코어 병렬) |
| 모델 출력 | 행동(hold/exit) | 보정된 P(win) + 엣지 회계 |
| 실험 추적 | 수기 docs | run registry + 계보 자동 기록 |

주의: 개선되는 것은 **시스템 처리량과 증거 품질**이다. 수익률 2~3배가 아니다.

### 3.1 계층 A — Model Factory (신규, `stom_rl/factory/`)

대시보드 밖, 학습 오케스트레이션 계층. webui는 절대 학습하지 않는다(read-only
규칙 유지).

| 모듈 | 역할 |
|---|---|
| `factory/episode_store.py` | 전 universe(2,427 테이블) 에피소드 샘플러 + parquet 캐시. 종목코드 선행 0 보존, sqlite `mode=ro` |
| `factory/experiment_queue.py` | 실험 큐(SQLite registry). 사전등록 config 없으면 enqueue 거부 |
| `factory/run_registry.py` | run id·split hash·cost·seed·계보(부모 실험)·상태(smoke/full/walkforward/paper) 기록 |
| `factory/walk_forward.py` | 연도 경계 ≥5 folds 오케스트레이션 (기존 `stom_rl/walk_forward.py` 확장) |
| `factory/train_full.py` | `--full-train` 경로: timesteps ≥2e5, SB3 VecEnv 병렬, 행동분포/entropy 로그, `DEGENERATE_POLICY` 자동 플래그 |
| `factory/probability_lane.py` | **이미지에서 빌린 핵심**: P(win) 분류기 학습(메타라벨), 보정(Platt/isotonic), Brier/reliability 산출, 엣지 = E[ret]−23bp 회계 |

기존 smoke 경로와 기본값은 변경하지 않는다 (falsification 하네스로 존속).

### 3.2 계층 B — Evidence Contract 확장 (기존 계약에 추가)

모든 run manifest에 추가 필드:

```text
calibration: { brier, reliability_bins[], pos_rate }
edge_accounting: { mean_edge_pct, breakeven_bp, edge_threshold, trades_above_threshold }
policy_diagnostics: { action_distribution, entropy, degenerate: bool }
sample_power: { oos_trades, min_required, ci_width_pct }
lineage: { parent_run, prereg_doc, stage }
```

gate 분류 추가: `DEGENERATE_POLICY`(학습 실패)를 `NO-GO_CONTROL`(신호 없음)과
구분 — 자매 문서 Phase 1과 동일.

### 3.3 계층 C — Dashboard (read-only 유지, 패널 추가)

| 신규 패널 | 이미지 대응물 | 내용 |
|---|---|---|
| Calibration Card | Probability Lattice | reliability diagram, Brier, bias(승률) vs 0.5, "현재 N으로 CI 폭 ±x%" LLN 수학 |
| Edge Ledger | EDGE VS BOOK | trade별 P(win)·기대수익·23bp breakeven·엣지, 임계치 미달 SKIP 표시 |
| Round Replay | BTC Hourly Pulse | 09:00~09:30 세션 read-only 리플레이 + 모델 P(win) 오버레이. 라이브 주문 아님 |
| Factory Status | 푸터 provenance | 실험 큐 상태, run 계보, 학습 스텝, 데이터 규모, degenerate 플래그 |

API: `/api/rl/factory/queue`, `/api/rl/runs/<run>/calibration`,
`/api/rl/runs/<run>/edge-ledger` — 전부 read-only, path traversal 방어 동일 적용.

## 4. 무엇이 "쉽게 만들 수 있는 구조"를 만드는가 (원리)

1. **문제를 RL에서 확률 추정으로 끌어내린다.** 이미지의 에이전트도 본질은
   P(up) 추정기 + 엣지 임계 규칙이다. 분류기는 RL보다 표본 효율이 수십 배 높고,
   기존 gate 체계(컨트롤/ablation/walk-forward)를 그대로 쓸 수 있다.
2. **반복 가능한 대량 실험.** 엣지는 반복으로만 증명된다(LLN). 실험도 같다 —
   사전등록→큐→자동 실행→registry 기록 루프가 사람 손 실험 대비 처리량을 만든다.
3. **falsification 자산 재사용.** 이 저장소의 강점(gate·control·ablation)은
   그대로 두고, 그 앞단에 생산 계층만 보강한다.

## 5. 개발 안내 (실행 순서)

### Phase F1 — Episode Store + Run Registry (기반, ~3일)

1. `stom_rl/factory/episode_store.py`: 전 universe 샘플러 + parquet 캐시.
   테스트: 코드 선행 0 보존, read-only 접근, 캐시 적중.
2. `stom_rl/factory/run_registry.py`: SQLite registry + 계보.
   테스트: enqueue 거부(사전등록 없음), 상태 전이.
3. 검증: `py -3.11 -m pytest tests/test_stom_rl_factory_*.py -q`

### Phase F2 — Probability Lane (가장 높은 기대값, ~4일)

1. `stom_rl/factory/probability_lane.py`: ts_imb 진입 후보(전 universe,
   N≈1,349+) 대상 P(win) 분류기 + isotonic 보정 + Brier/reliability.
2. 엣지 회계: trade별 `edge = P(win)·E[win] + (1−P(win))·E[loss] − 23bp`.
3. walk-forward ≥5 folds, OOS ≥100 trades 강제.
4. 사전등록 문서(`*_prereg_*`) 작성 후에만 실행.

### Phase F3 — Full-Train RL 경로 (probability lane 통과 후에만, ~4일)

1. `factory/train_full.py`: VecEnv 병렬 + timesteps ≥2e5 + 행동분포 로그.
2. gate에 `DEGENERATE_POLICY` 분류 추가 (`opening_30m_rl_candidate_gate.py`).
3. `STOP_RL_EXPANSION` 결정 존중: F2의 RULE/메타라벨 gate 통과가 선행 조건.

### Phase F4 — Dashboard 패널 (~3일)

1. read-only API 3종 추가 (`webui/rl_dashboard_factory.py` 신규 모듈,
   `app.py`에는 라우트만).
2. Svelte: `CalibrationCard.svelte`, `EdgeLedgerCard.svelte`,
   `FactoryStatusCard.svelte` (`webui/v2_src/src/tabs/rlTrading/`).
3. 검증: 기존 대시보드 테스트 + `npm run build`.

### 가드레일 (전 Phase 공통)

- webui는 학습·주문·쓰기 작업을 하지 않는다.
- `ts_imb`는 RULE baseline. RL이라 부르지 않는다.
- OOS 무튜닝, 사전등록 선행, 23bp, `NO-GO` 가시화 유지.
- 이미지의 수치는 목표가 아니라 콘셉트다. 우리의 성공 기준은 "gate를 통과한
  보정된 엣지 × 충분한 N"이지, 화면의 화려함이 아니다.

## 6. 결론

현 백엔드는 증거 뷰어로는 80점, 모델 공장으로는 0점이다. 참조 이미지에서 빌릴
것은 화면이 아니라 **확률 우선 + 엣지 회계 + 대수의 법칙 + provenance** 구조다.
가장 기대값 높은 다음 단계는 RL 확장이 아니라 Phase F1~F2(에피소드 스토어 +
P(win) 보정 lane)이며, 이것이 통과해야 F3(진짜 규모의 RL)가 의미를 갖는다.
