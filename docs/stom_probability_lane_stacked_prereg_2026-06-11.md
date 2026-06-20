# Probability Lane 2차 사전등록 — Stacked Gate (G4 재도전) — 2026-06-11

## 상태

`supervised gate` 사전등록 문서다. RL이 아니다. `ts_imb`는 RULE baseline이며 RL이라
부르지 않는다. 실거래/브로커/수익 보장 주장 없음. 이 문서 커밋 이후 실험을
실행하고, OOS 결과를 본 뒤 가설·임계치·gate를 수정하지 않는다.

선행 실험: `docs/stom_probability_lane_result_2026-06-11.md`
(`probability_lane_tp5sl1_2026_06_11`, verdict `NO-GO_BASELINE` — G4 단독 실패,
G1/G2/G3/G5/G6/G7 통과).

## Skip-gate 전례와의 차별성 (stom_rl/AGENTS.md 요건)

과거 skip-gate는 full-universe `NO-GO`였다. 본 실험은 다음이 새 가설 요소다:
full-universe 27,311 인스턴스로 학습한 HistGradientBoosting + isotonic **보정
확률** 기반 엣지 회계(선행 실험에서 G3/G5/G6/G7 입증), walk-forward 5 folds,
표본력 있는 OOS(선행 12,194 TAKE). 과거 skip-gate는 이 중 어느 것도 갖추지
못했다.

## 가설

### 주실험 A — Stacked Gate

ts_imb RULE 통과 후보 내부에서, 보정된 P(win) 엣지가 양(+)인 부분집합만 선별하면
ts_imb 단독보다 trade당 평균 net이 높다.

- TAKE 규칙: `pass_ts_imb == True AND edge > 0` (edge 정의는 선행 실험과 동일).
- 분류기 학습은 선행 실험과 동일하게 **전체 후보**로 수행하고, 선별만 ts_imb
  부분집합에 적용한다.

### 보조실험 B — 매칭 임계치 비교

TAKE 규모를 ts_imb와 맞췄을 때(per-fold validation에서 임계치 결정) 모델 선별이
ts_imb 평균 이상인지 검증한다.

- 임계치 τ_k: fold k의 **validation** 후보 edge 분포에서, TAKE 비율이 validation의
  ts_imb 통과 비율과 같아지는 분위수로 결정. OOS에는 τ_k를 그대로 적용
  (OOS 무튜닝).
- TAKE 규칙: `edge >= τ_k` (전체 후보 대상).

### 다중비교 규칙

성공 주장(`GO_CANDIDATE`)은 **주실험 A의 gate만으로** 판정한다. B는 지지/반박
증거로만 기록한다. 둘 중 좋은 쪽을 사후 선택하지 않는다.

## 데이터/모델/분할 (선행 실험과 동일, 고정)

`.omx/artifacts/gap_up_full/instances.json`, `tp5_sl1` 고정, 23bp(+0.02%p 환산),
feature 5종(entry_change_rate, entry_trade_strength, entry_bid_ask_imbalance,
entry_sec_amount, entry_price), HistGradientBoostingClassifier(seed 100) +
isotonic, `chronological_folds` n_folds=5. split hash는 선행과 동일해야 하며
달라지면 실험 중단.

## Gate (주실험 A, 고정)

| ID | Gate | 기준 | 실패 라벨 |
|---|---|---|---|
| A-G1 | 표본력 | 전 fold 합산 OOS TAKE ≥ 100 | `INCONCLUSIVE` |
| A-G2 | 절대 수익 | OOS TAKE 평균 net > 0 | `NO-GO` |
| A-G3 | 증분 엣지 | OOS TAKE 평균 > ts_imb 단독 평균 (동일 fold OOS) | `NO-GO_BASELINE` |
| A-G4 | fold 일관성 | 5 fold 중 ≥3 fold에서 A-G3 개별 성립 | `NO-GO_BASELINE` (failed_fold_consistency) |
| A-G5 | 음성 컨트롤 | 라벨 셔플 시 A-G3 실패해야 함 | `NO-GO_CONTROL` |
| A-G6 | 보정 skill | ts_imb 부분집합 OOS Brier ≤ 상수 예측기 | `NO-GO_CONTROL` |
| A-G7 | Ablation | 단일 feature 제거 5종 중 ≥3이 full보다 A-G3 마진 우위면 실패 | `NO-GO_ABLATION` |

모든 gate 통과 시에만 `GO_CANDIDATE`. 이는 "연구 후보" 자격이며 수익
보장이 아니다.

## Gate (보조실험 B, 고정 — 기록용)

B-G1: OOS TAKE ≥ 100. B-G2: TAKE 수가 동일 OOS의 ts_imb 수 대비 0.8~1.2배.
B-G3: TAKE 평균 ≥ ts_imb 평균. B는 verdict에 영향 없음.

## 강건성 검사 (기록용, gate 아님)

주실험 A 파이프라인을 `gap_up_realized` 캐시(N=1,349, realized fill)에 동일
적용해 방향성을 기록한다. 표본이 작아 `INCONCLUSIVE` 가능성이 높음을 사전에
명시한다. 이 결과는 A의 verdict를 바꾸지 않는다.

## 보고 의무 (탐색적 관찰 포함)

TAKE 평균 외에 TAKE 총합, 스킵된 ts_imb trade 수와 그 평균 net(선별이 버린
가치), fold별 표를 모두 보고한다. mean이 올라도 총합이 줄어드는 trade-off를
숨기지 않는다.

## 실행 등록

| run id | 내용 | stage | parent |
|---|---|---|---|
| `probability_lane_stacked_2026_06_11` | 주실험 A | walkforward | `probability_lane_tp5sl1_2026_06_11` |
| `probability_lane_matched_2026_06_11` | 보조실험 B | walkforward | `probability_lane_tp5sl1_2026_06_11` |
| `probability_lane_stacked_realized_2026_06_11` | 강건성 | smoke | `probability_lane_stacked_2026_06_11` |

cost_bps=23.0, seed=100. 산출물은 `webui/rl_runs/probability_lane/<run_id>/`에
선행 실험과 동일 파일명(summary/calibration/edge_ledger)으로 기록한다.

## 해석 경계

- A가 `GO_CANDIDATE`면: P6(Full-Train RL) 차단 해제 **검토** 자격이 생기고, 다음
  단계는 realized/sl_gap_stress 본검증과 read-only forward 설계다. 즉시 운영
  후보가 되는 것이 아니다.
- A가 `NO-GO_*`/`INCONCLUSIVE`면: 그대로 기록하고 P6 차단 유지. 같은 데이터로
  임계치/feature를 바꿔 재시도하려면 새 사전등록이 필요하다.
