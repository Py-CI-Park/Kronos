# STOM 일봉 SB3 R3b 사전등록 — 2026-07-12

## 연구 질문과 경계

공식 일봉 D3 예측 계보를 `PortfolioEnv` 계약으로 변환했을 때 SB3 정책이 학습·평가 배관을 정상적으로 통과하는지 확인한다. 이 실험은 **portfolio RL 연구**이며 라이브 거래, 브로커 주문, 계좌, 페이퍼 전환 또는 수익성을 승인하지 않는다. 성공적인 실행도 곧바로 알파나 모델 사용 가능성을 의미하지 않는다.

## 동결 입력 계약

- 입력: 권위 있는 공식 일봉 D3 `predictions.csv`와 그 run/manifest.
- 필수 계보: source run ID, source manifest SHA-256, predictions SHA-256, split lineage, 생성 시각, schema version, 이 사전등록 문서의 명시적 경로와 SHA-256.
- 필수 열: `timestamp`, 문자열 `symbol`, `rank_score`, `price`, `fill_price`, `future_return_1d`, `split`.
- 종목 코드는 6자리 문자열로 유지한다. 예: `000250`.
- `fill_price`와 `future_return_1d`는 동일 심볼의 다음 거래일 행에서만 구성한다. 다음 거래일 가격·수익이 없거나 비정상/비유한 값이면 학습 전에 fail-closed하고 제외 수를 manifest에 기록한다.
- Close-slot CSV를 일반 `PortfolioEnv`에 직접 입력하지 않는다.
- 비용: 왕복 **23bp가 primary**, 0bp control, 46bp stress.
- test OOS는 끝까지 미사용/미튜닝 상태로 유지한다. 각 fold 모델은 해당 fold의 `train_frame`으로만 학습한다.

## 알고리즘과 재현성

| 단계 | 알고리즘 | timestep | seed | device |
|---|---|---:|---:|---|
| 합성 E2E | PPO | 512 | 7 | auto |
| G017 smoke | PPO | 5,000 | 7 | auto |
| G018 full | PPO | seed당 200,000 이상 | 7, 17, 29 | auto |

- 구현은 `PPO`와 `DQN` 선택을 명시적으로 노출하지만, 이번 공식 smoke/full의 동결 primary는 PPO이다. 알고리즘을 조용히 바꾸지 않는다.
- 동일 seed/config/fold는 동일한 데이터·설정·코드 hash를 갖는다.
- `device_requested`와 실제 `device_used`를 run manifest에 기록한다.
- 모델 ZIP, run manifest, split별 원시 평가 ledger, live event stream, source/config/code/artifact SHA-256을 저장한다.
- `stom_rl_live_event.v1`은 변경하지 않고 reward/equity kind·unit, action availability, phase, lifecycle을 additive `info`로 선언한다.

## 평가와 대조군

각 seed/fold에서 다음을 분리 보고한다.

- train, validation, untouched test OOS
- 23bp primary와 0/46bp controls
- cumulative/net return, MDD, trade count, invalid-action rate, never-trade 여부
- no-trade, momentum, 관련 RULE baseline, buy-and-hold(적용 가능할 때)
- shuffled-label 재학습 control
- 핵심 입력/정규화/보상 ablation

Validation과 test를 합산한 값은 보조 정보일 뿐이며 test OOS를 가릴 수 없다.

## G017 smoke 판정

배관 성공 조건:

1. 5,000 timestep 완료, 모든 학습/평가 metric 유한값.
2. model ZIP, manifest, hashes, validation callback, live events가 존재하고 상호 일치.
3. 이벤트가 RUNNING 중 실제 step 증가를 보이고 완료 후 COMPLETED로 전환.
4. split/hash/schema/cost/baseline/action/unit 검증 통과.
5. `stage=smoke`, `authoritative=true`, `status=completed`, smoke label과 연구 전용 잠금이 동시에 존재.

학습 품질이 기준선보다 낮아도 배관이 정상이면 `NON_IMPROVING`이라는 유효한 smoke 결과다. NaN, invalid-action gate, split/hash/schema/event/dashboard lineage 실패는 `INCONCLUSIVE` 또는 `NO-GO` stop이며 G018 확장을 차단한다.

## G018 full 판정 및 stop 규칙

G018은 G017 배관·데이터 gate 통과 후에만 실행한다. 양의 reward는 확장 조건이 아니다.

- seed `{7,17,29}` 각각 동일 설정으로 200,000 timestep 이상.
- seed/fold 누락, NaN/Inf, schema/hash mismatch, 다음날 행 오류, 비정상 invalid-action rate, 자원 고갈, event 정체 또는 기준선/control 누락 시 즉시 preregistered stop artifact를 기록한다.
- negative test OOS 또는 높은 MDD seed를 제외하지 않는다.
- train/validation 개선은 negative test를 뒤집지 못한다.
- test OOS가 불확실성·drawdown gate를 포함해 기준선보다 우월하지 않으면 모델 verdict는 `NO-GO`/`NON_IMPROVING`이다.
- stop trigger가 발생하면 남은 compute를 강행하지 않는다. 완전한 stop 문서도 엔지니어링 완료 증거로 인정한다.

## 변경 금지

결과 확인 뒤 seed, 비용, split, timestep, baseline, stop threshold 또는 primary 알고리즘을 소급 변경하지 않는다. 변경이 필요하면 새 날짜의 별도 사전등록과 이유를 먼저 작성한다.
