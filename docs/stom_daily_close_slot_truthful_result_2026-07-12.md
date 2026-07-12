# STOM 일봉 close-slot 정직화 결과 — 2026-07-12

## 결론

| 항목 | 결과 |
|---|---|
| 연구 판정 | **NO-GO / WATCH_RESEARCH_ONLY** |
| primary | test OOS · `base_23bp` · `linear_score_and_pick_train_only` |
| test OOS reward | **0.0** |
| test OOS filled slots | **0** |
| gate artifact validation | **PASS** (오류 0) |
| 모델·라이브·수익성 승인 | **아님** |

정정된 정책은 test OOS에서 threshold를 넘는 종목을 선택하지 않았다. 이는 회계·계보 실패가 아니라 **NO-GO라는 유효한 연구 결과**다. 양의 전체 합계나 강제 top-10 진단은 test OOS primary를 대체하지 않는다.

## 입력과 실행

- 입력 dataset run: `daily_close_slot_research_dataset_2026_07_03`
- dataset manifest SHA-256: `7eb208e68c4b6359d8c2c8ddaaf4c280700539f5f05bcd57f90316e630697829`
- 정정 train run: `daily_close_slot_truthful_policy_2026_07_12`
- train manifest SHA-256: `56e7a12568448832a6b18a9d4b75f78653070baa65a8d9cd3a5613ef7fad0cc4`
- gate run: `daily_close_slot_truthful_gate_2026_07_12`
- gate manifest SHA-256: `49b16a58dbc0b61fdbe7fcd55f9ef561d02169add7970e7d832a7ce63e2e6066`
- seed: `100`
- 비용: 23bp primary, 0bp control, 46bp stress
- split: train-only fit, val/test no-retune, test OOS primary

실행 명령:

```powershell
py -3.11 -m stom_rl.daily_close_slot_train --dataset-run-id daily_close_slot_research_dataset_2026_07_03 --dataset-manifest-sha 7eb208e68c4b6359d8c2c8ddaaf4c280700539f5f05bcd57f90316e630697829 --run-id daily_close_slot_truthful_policy_2026_07_12 --seed 100
```

Gate는 `write_close_slot_gate_artifacts(...)`로 동일 train manifest와 SHA를 검증하여 생성했다.

## 코드 정정 사항

1. 수량 계산에서 매수 수수료·슬리피지를 먼저 예약해 `notional + buy costs <= slot cash`를 보장한다.
2. action tie order를 `score desc → tie_score desc(missing last) → 6자리 code asc → table asc → candidate index asc`로 고정하고 manifest와 구현을 일치시켰다.
3. 표준 CLI 경로가 `RlLiveEventWriter`를 기본 생성하며 기존 `stom_rl_live_event.v1`을 그대로 사용한다.
4. 실제 탐색이 없는 정책 이름을 `linear_score_and_pick_train_only`로 바꾸고 contextual-bandit 표현을 현재 코드/UI에서 제거했다.
5. 손실의 절댓값이 양의 학습 가중치가 되던 경로를 제거했다. 음수 수익은 weight 0, 중립은 1, 양수만 상향한다.
6. primary headline은 항상 test OOS·23bp이며 GO를 허용하지 않는다.

## 결과 상세

| 정책/진단 | cumulative reward | filled slots | 해석 |
|---|---:|---:|---|
| `no_trade_control` | 0.0 | 0 | 기준선 |
| `deterministic_shuffle_top10_control` | -0.47390756503 | 2,352 | control, 정책 action 아님 |
| `momentum_top10_score_and_pick` | 0.30857179941 | 2,449 | 별도 baseline |
| `linear_score_and_pick_train_only` | -0.060214987315 | 30 | primary 정책 전체 split 합계 |
| `linear_score_and_pick_top10_forced_diagnostic` | 0.40049514802 | 2,451 | threshold 없는 진단, 정책 action·headline 아님 |

Primary split별 결과:

| split | reward | filled slots |
|---|---:|---:|
| train | 0.0 | 0 |
| validation | -0.060214987315 | 30 |
| test OOS | **0.0** | **0** |

강제 top-10 진단의 양수 값은 threshold 정책이 test OOS에서 거래하지 않은 사실을 뒤집지 않는다. 특히 test OOS 우월성·불확실성·drawdown 증거가 없으므로 승격하지 않는다.

## 이벤트와 무결성

- 이벤트 행: 265
- 이벤트 SHA-256: `69d9b4e824328aeb1d8a7242ae5eb2779b5a160b9057cc74447256154a22fcb0`
- schema: `stom_rl_live_event.v1`만 존재
- algorithm: `linear_score_and_pick_train_only`만 존재
- source: `daily_close_slot_train`
- reward: `return_fraction` / `fraction`
- equity: `cumulative_pnl` / `krw`
- `action_recorded=false`; 실제 discrete action을 꾸며내지 않음

Gate report는 artifact hash, row count, schema, threshold/OOS, replay, 비용 구성, baseline 및 false-lock을 모두 통과했고 `gate_status=WATCH_RESEARCH_ONLY`를 반환했다.

## 남은 차단 요인

- `D0_PRICE_BASIS_NOT_VERIFIED`
- `D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED`
- dataset `price_basis_status=UNKNOWN_CONFIRMED`
- `decision_grade_return_status=BLOCKED_UNTIL_PRICE_BASIS_VERIFIED`
- D3 comparator는 현재 run에 포함되지 않음

따라서 이 결과는 로컬 연구·대시보드 증거일 뿐이며 live/broker/order/account/paper/profitability 또는 model-build readiness를 열지 않는다.
