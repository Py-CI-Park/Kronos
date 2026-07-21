# Kronos V8 M3E 종가매매 연구 결과와 강화학습 로드맵 — 2026-07-21

> 문서 ID: `KRONOS-V8-M3E-RESULT-AND-RL-ROADMAP-2026-07-21`
> 브랜치: `research/m3e-closing-consensus`
> 상태: `M3E_COMPLETE / NO_GO / OOS_CLOSED`
> 분류: `CONTEXTUAL_BANDIT_RESEARCH_EXPERIMENT` — full sequential RL이 아님
> primary cost: 왕복 0.23%
> 가격 기준: exact 15:20 bar close proxy — 공식 종가가 아님

## 1. 실행 계약

| 항목 | 동결 값 |
|---|---|
| 모델 | LinUCB fixed-seed consensus 5-member |
| seeds | `[0,1,2,3,4]` |
| 학습 | train-only, member당 chronological session의 seeded order 1 pass |
| 집계 | member raw score의 무가중 평균 후 action 결정 |
| action | mean score > 0 중 score 내림차순·symbol 오름차순, 서로 다른 종목 0~10개 |
| reward | 선택 slot마다 `future_return_h1_1520_proxy - 0.0023` |
| 연구 회계 | 60M fixed notional, 5M/slot, 최대 50M exposure, 10M reserve |
| validation | 2024-01-01~2025-06-30 reused screen |
| OOS | 2025-07-01~2026-06-12 sealed, `NOT_RUN` |
| claim | 실제 운영금·10종목 보장·공식 종가·수익성·GO·live/broker/order 아님 |

동결 사전등록은 `docs/kronos_v8_prereg_m3e_2026-07-21.json`입니다. public train/validation과 sealed test는 생성 시점부터 서로 다른 sink로 기록되었고 combined plaintext artifact는 생성하지 않았습니다.

## 2. Custody 증거

| 증거 | 값 |
|---|---|
| custody UID | `v8-m3e-20260721-001` |
| public train/validation SHA-256 | `c9d85ba5f843293f784b9890db7e1f9b15114cace55229af2d02bf2cc3242ec2` |
| sealed test SHA-256 | `e5ddc0572a2be0da122661e6fd1cee2d9d88104b0acef0522206d201c0df96cb` |
| sealed membership SHA-256 | `b609a52d041f28d1e2fe46fc9a8d175f3e7ad62a7510317ef45a307706fb9de4` |
| daily source SHA-256 | `9a363b33a9c2d125f3df7010e54efcec9d53fd6a40dbf16a39b538c20247a09c` |
| five-minute source SHA-256 | `ea78dd192f769580680ec2edb8382bf8308b0914b46e020f567c8c7f34dcd2ef` |
| trainer SHA-256 | `9e7bc1f7a144a755ea39c67728e6a50d345eceba4cb2936512a8c9b16560f755` |
| protocol SHA-256 | `4c84d77dabf1d2efe6ea6fda9726cbdc7164de66506c6f56235f053b90659e98` |
| test state | `NOT_RUN` |

Independent gate receipt 발행을 실제 run manifest에 대해 시도했으나 `NO_GO`이므로 fail-closed 거절되었습니다. 따라서 test vault read와 one-time access ledger 소비는 발생하지 않았습니다.

## 3. Reused-validation 결과

| 지표 | 결과 |
|---|---:|
| full ensemble NAV, 0bp 표시 control | 93,233,898.71 |
| **full ensemble NAV, 23bp primary** | **52,880,398.71** |
| full ensemble NAV, 46bp stress | 12,526,898.71 |
| 23bp net return | -11.8660% |
| max drawdown | 53.5743% |
| trades | 3,509 |
| turnover days | 361 |
| max positions/session | 10 |
| max notional exposure | 50,000,000 |
| no-trade | 60,000,000 |
| best frozen baseline | institutional-flow RULE 36,706,205.47 |

0bp curve는 수익성 증거가 아닙니다. 23bp primary에서 no-trade보다 7,119,601.29 낮고 drawdown도 53.57%입니다. 비용 민감도가 매우 커서 현재 정책은 실제 운영 후보가 아닙니다.

### Jackknife 안정성

| omitted member | 23bp NAV | pass |
|---:|---:|---|
| 0 | 50,577,192.51 | false |
| 1 | 47,390,099.27 | false |
| 2 | 54,225,407.82 | false |
| 3 | 52,078,976.84 | false |
| 4 | 50,960,561.48 | false |

5개 중 통과 0개입니다.

### Negative control

`shuffled jackknife_4` NAV 61,810,918.98이 exposure-matched threshold 61,028,773.85를 초과하여 control failure입니다. full ensemble 자체도 no-trade를 넘지 못했으므로 control 결과와 무관하게 eligibility는 충족되지 않습니다.

**최종 판정: `NO_GO`. OOS는 열지 않습니다.**

## 4. 구축된 연구 시스템

| 구성요소 | 파일 | 역할 |
|---|---|---|
| M3E policy engine | `stom_rl/daily_v8_m3e.py` | 동일 train/eval score·action·reward 계약 |
| custody-safe runner | `stom_rl/daily_v8_m3e_run.py` | public train/validation만 load, test switch 없음 |
| partition generator | `stom_rl/daily_v6_dataset.py` | 생성 시 public/sealed sink 분리 |
| custody boundary | `stom_rl/daily_v8_custody.py` | integrity, split, traversal, one-time ledger |
| gate receipt | `stom_rl/daily_v8_gate_receipt.py` | independent Ed25519 eligibility receipt |
| custody bootstrap | `scripts/build_m3e_custody_v8.py` | test 값을 출력하지 않는 genesis seal |
| frozen prereg | `docs/kronos_v8_prereg_m3e_2026-07-21.json` | model/data/reward/gate 계약 |
| run manifest | `webui/rl_runs/v6_daily_h1/v8-m3e-20260721-001/train_20260721T154052Z/run_manifest.json` | immutable validation result |
| HTML report builder | `stom_rl/daily_v8_m3e_report.py` | test를 읽지 않는 탭·SVG 연구 보고서 |
| immutable HTML report | `webui/rl_runs/v6_daily_h1/v8-m3e-20260721-001/train_20260721T154052Z/report.html` | `NO_GO` visual evidence |

보고서 SHA-256은 `05562cc6ec8c1e2c757e2c1f892d220eb8414e2f0ad17d1069dcfbe5a0e36aaf`이고 report manifest가 run `693d3f2909030c5a6dc8bec9ae0d1c8cef44ad0f42d07e63668439b4c778a1ea`, prereg `4fa04d66d67d8fcd9bf2f561893387bfb0181ddbf25abb870726fdd88cb9a0d5`, public custody manifest `780e64a2c79442788018426a60c43bb4de30b75989af397675d9ee999d498ef3`를 결합합니다.

## 5. Full sequential RL 구축 로드맵

M3E를 결과 확인 후 임의 조정하지 않습니다. 아래 full RL은 **새 가설·새 preregistration·새 confirmatory window**가 필요한 다음 연구이며 현재 M3E 결과를 GO로 전환하는 작업이 아닙니다.

### Phase R0 — 실패 진단 고정

| 작업 | 허용 범위 | gate |
|---|---|---|
| churn/cost decomposition | 현재 validation 결과의 설명적 분석만 | feature·threshold·seed 재선택 금지 |
| action-frequency 분석 | session별 0~10 pick 분포와 비용 기여 | OOS 접근 금지 |
| M2 mismatch 회귀 테스트 | train/eval policy가 같은 함수인지 확인 | neutral-context 평가 금지 |

### Phase R1 — 환경 계약

| 항목 | 제안 동결 값 |
|---|---|
| episode | train session을 시간순으로 순회; shuffle 금지 |
| observation | D-1 causal features, candidate mask, current slots/cash, prior selection, portfolio drawdown |
| action | 각 종목 enter/skip score + masked top-k, 0개 허용, 최대 10개 distinct |
| fill | exact 15:20 proxy; 공식 종가 표현 금지 |
| transition | 선택 결과를 다음 session portfolio state에 반영 |
| termination | train window 종료 또는 preregistered safety boundary |
| invalid action | mask하여 0건 목표; invalid rate 별도 기록 |

### Phase R2 — 보상 계약

Primary reward 후보는 다음처럼 단순하게 유지합니다.

```text
session_reward = Σ[5M / 60M × (H1_15:20_proxy_return - 0.0023)]
```

- no-trade reward는 0입니다.
- 23bp 비용은 reward에서 직접 차감합니다.
- turnover penalty를 중복 추가하지 않습니다.
- drawdown penalty를 추가하려면 계수까지 결과 보기 전에 새 prereg에 동결합니다.
- reward normalization은 train-only 통계만 사용하고 validation/test로 fit하지 않습니다.

### Phase R3 — 모델과 동일-policy 평가

| 순서 | 모델 | 목적 |
|---:|---|---|
| 1 | deterministic no-trade/rule | 환경·회계 회귀 기준 |
| 2 | supervised cost-aware scorer | RL이 단순 예측보다 나은지 기준 |
| 3 | masked PPO 또는 actor-critic | portfolio state를 쓰는 full sequential RL |
| 4 | seeded random/shuffle controls | action exposure와 leakage falsification |

모델 actor를 평가 시 다시 score/top-k 함수로 대체하지 않습니다. 학습과 평가가 같은 observation, mask, action decoder를 사용해야 합니다.

### Phase R4 — 테스트 단계

1. synthetic environment: zero action, 10-slot cap, leading-zero symbol, 23bp reward, invalid mask.
2. train-only overfit smoke: 작은 synthetic signal을 학습할 수 있는지만 확인.
3. negative/shuffle controls: 가짜 label에서 성과가 나면 `NO_GO`.
4. 최소 5 seeds와 seed consensus; 단일 winner 선택 금지.
5. reused validation은 screening으로만 사용.
6. 새 fresh OOS custody가 확보된 경우에만 independent gate 후 1회 평가.
7. 어떤 결과도 immutable HTML report와 ledger에 기록.

## 6. 다음 연구 의사결정

현재 M3E는 종료합니다. 같은 validation에서 threshold, feature, seed, member, cost를 조정해 재실행하면 post-hoc tuning입니다. 다음 full RL cycle은 R0 설명적 실패 분석 후 별도의 사전등록 문서로 시작해야 하며, confirmatory claim에는 기존 sealed test를 사용하지 않고 새 fresh OOS window를 축적하는 것이 안전합니다.
