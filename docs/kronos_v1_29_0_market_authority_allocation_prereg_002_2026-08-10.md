# Kronos v1.29.0-dev 일봉 4행동 RL 계보 재현 002 사전등록

- 사전등록일: 2026-08-10 KST
- 개발 브랜치: `codex/v1.29.0-dev-market-authority`
- 권위 감사 ID: `DAILY_MARKET_AUTHORITY_2026_08_10_002`
- 강화학습 실행 ID: `DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002`
- 연구 등급: `POST_HOC_CUSTODY_REPRODUCTION`
- 학습·보상 허용 데이터: TRAIN, VALIDATION
- historical TEST 공개 경계: 후보 점수·상태 feature 46일은 001에서 이미 파싱되어 오염됨. reward·가격 체결·행동 평가는 읽지 않음
- 금지 데이터: Fresh OOS 전체, historical TEST reward·가격 체결·행동 평가
- 금지 동작: paper/live/broker 주문, 자동 승격, 결과 확인 후 임계값 변경

## 1. 목적과 이전 001의 한계

이 연구는 한국 주식 일봉 후보군을 대상으로, D 종가 직후 자금 노출 수준을 선택하는 오프라인 강화학습 모델을 만든다. 행동은 현금과 Top-3·Top-5·Top-10 동일 슬롯 배분 네 가지다. D+1 시가에 진입하고 다음 관측 가능한 청산 시가에 종료하며, 비용을 차감한 로그 NAV 변화를 보상으로 사용한다.

`001` 실행은 실제 10개 모델과 검증 결과를 만들었지만 다음 핵심 값이 사전등록 문서와 영수증에 완전히 결속되지 않았다.

- 행동 데이터 생성 시드 `1000..1031`
- 행동 데이터 정책 `TRAIN 전용 4행동 균등 무작위`
- `reward_scale=100.0`
- `target_update_interval=25`
- 실행 코드 Git SHA, 사전등록 SHA-256, 직접 입력 5종 SHA-256

따라서 `001`은 보존하되 `LEGACY_EXPLORATORY_CANDIDATE`로만 해석한다. `002`는 위 항목을 재실행 전에 고정하지만, 동일 TRAIN/VALIDATION 결과를 이미 확인한 뒤 등록하므로 새로운 성능 사전검증이 아니다. `002`의 목적은 코드·입력·설정·산출물 계보의 사후 재현이며, `001` 결과를 독립 검증 후보로 승격하거나 새 영수증으로 소급 포장하지 않는다.

## 2. 데이터와 권위 경계

| 구분 | 고정 입력 | 허용 용도 |
|---|---|---|
| 후보 점수 | `candidate_score_rows.csv` | TRAIN/VALIDATION 후보 선택 |
| 점수 manifest | `close_slot_dataset_manifest.json` | 원천·split 해시 검증 |
| 인과 상태 panel | `close_slot_panel.csv` | D 종가까지 관측 가능한 172차원 상태 |
| 일봉 DB | `_database/Stock_Database_ohlcv_1day.db` | 불변 byte snapshot에서 가격 실행 |
| 종목 메타 DB | `_database/stock_tick_back.db:stockinfo` | bounded canonical query identity |
| 권위 receipt | `DAILY_MARKET_AUTHORITY_2026_08_10_002/authority_receipt.json` | D0/D1 차단 상태와 입력 결속 |
| 001 기준 receipt | `DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001/validation_receipt.json` | 10모델·checkpoint·gate 정규화 지문 비교 |

권위 감사는 파일 해시만으로 Kiwoom·KRX 공식성이나 사람 검토를 주장하지 않는다. 서명된 reviewer trust root, 검토자 principal/key, 원본 응답에서 정규화 파일로 이어지는 extraction receipt가 구현되기 전에는 D0/D1을 `VERIFIED`로 만들지 않는다. D0/D1이 `BLOCKED`여도 로컬 연구용 TRAIN/VALIDATION 학습은 실행할 수 있지만 수익성 확정·paper/live 승격은 계속 금지한다.

001 코드 감사에서 historical TEST의 reward·시가 체결 DB는 열지 않았지만, 후보 점수와 상태 feature 46일을 파싱해 score/state dataset hash에 포함한 사실을 확인했다. 따라서 기존 historical TEST는 더 이상 untouched OOS가 아니며 향후 경제 성능 판정에서 영구 제외한다. 002는 이 오염된 입력 경계를 숨기지 않고 그대로 재현하는 보관·결정성 검사이며, 최종 경제 판정은 새로 축적되는 Fresh OOS만 사용한다.

## 3. 환경·자금·행동·보상

| 항목 | 사전 고정 값 |
|---|---|
| 의사결정 시각 | D 종가 이후 15:30 KST |
| 진입 | D+1 시가, 매수 비용 포함 |
| 보상 관측 | 청산 시가가 관측된 시점, 의사결정 시각과 별도 기록 |
| 초기 자금 | 60,000,000원 |
| 현금 하한 | 10,000,000원 |
| 종목당 슬롯 | 최대 5,000,000원 |
| 행동 0 | `CASH` |
| 행동 1 | `INVEST_TOP3_EQUAL_SLOT` — 최대 15,000,000원 노출 |
| 행동 2 | `INVEST_TOP5_EQUAL_SLOT` — 최대 25,000,000원 노출 |
| 행동 3 | `INVEST_TOP10_EQUAL_SLOT` — 최대 50,000,000원 노출 |
| 기본 왕복 비용 | 0.230% |
| 스트레스 왕복 비용 | 0.460% |
| 보상 | 각 step의 비용 차감 후 `log(final_nav / previous_nav)` |
| 상태 | D 시점까지 관측 가능한 172차원 벡터 |

행동은 구체 종목을 직접 고르는 것이 아니라 사전 계산된 동일 날짜 후보 순위 중 몇 종목까지, 얼마를 노출할지를 결정한다. 이는 “종가에 판단하고 다음 시가에 체결”하는 현실적 경계를 유지하면서 강화학습이 현금 보유와 노출 강도를 학습하게 한다.

## 4. 모델과 행동 데이터 생성 계약

| 항목 | DQN | CQL |
|---|---:|---:|
| 모델 시드 | 0, 1, 2, 3, 4 | 0, 1, 2, 3, 4 |
| 입력 차원 | 172 | 172 |
| 행동 수 | 4 | 4 |
| 은닉층 | 128, 64 | 128, 64 |
| 학습률 | 0.0003 | 0.0003 |
| discount | 0.95 | 0.95 |
| CQL alpha | 0.0 | 1.0 |
| reward scale | 100.0 | 100.0 |
| batch size | 256 | 256 |
| gradient steps | 600 | 600 |
| target update interval | 25 | 25 |

- 행동 데이터 생성 시드: `1000..1031` 총 32개
- 행동 데이터 정책: 각 TRAIN 궤적에서 네 행동을 균등 무작위로 표본화
- VALIDATION 보상은 정책 선택이나 하이퍼파라미터 수정에 사용하지 않고 고정 gate 평가에만 사용
- historical TEST의 후보 점수·상태 feature는 이미 소비됨. reward·가격 체결·행동 평가는 읽지 않음
- Fresh OOS의 상태·보상·행동은 모두 읽지 않음

## 5. 이미 소비된 VALIDATION gate의 재산출

| gate ID | PASS 조건 |
|---|---|
| `CQL_VALIDATION_MEDIAN_BEATS_NO_TRADE` | CQL 기본 비용 5시드 중앙값 > 0% |
| `CQL_VALIDATION_FOUR_OF_FIVE_POSITIVE` | CQL 기본 비용에서 최소 4/5 시드 > 0% |
| `CQL_VALIDATION_STRESS_MEDIAN_POSITIVE` | CQL 스트레스 비용 중앙값 > 0% |
| `CQL_VALIDATION_ACTION_DIVERSITY` | 최소 4/5 CQL 시드가 3개 이상 행동 사용 |
| `CQL_VALIDATION_BEATS_DQN_MEDIAN` | CQL 중앙값 > DQN 중앙값 |
| `CQL_VALIDATION_MDD_WITHIN_20_PERCENT` | 모든 CQL 시드 MDD >= -20% |

이 gate는 `001`에서 이미 소비된 VALIDATION을 동일 코드로 재산출하는 재현 체크다. 001 receipt 전체 SHA-256과 10모델·checkpoint·gate의 canonical evidence SHA-256을 002 입력·영수증에 결속한다. 정확히 일치하면 `REPRODUCTION_ONLY_VALIDATION_CONSUMED`, 하나라도 다르면 `REPRODUCTION_MISMATCH_VALIDATION_CONSUMED`로 게시한다. 어느 경우에도 경제 성능 점수를 올리지 않는다. D0/D1, Fresh OOS, 사람 승인 중 하나라도 미완료이면 실전 모델 성공으로 표현하지 않는다. 재산출 결과가 달라지거나 gate가 실패하면 동일 ID에서 재학습·시드 선별·임계값 조정을 하지 않고 재현 실패로 기록한다.

## 6. 실행 계보와 산출물

`002` 영수증은 다음을 반드시 포함한다.

- 이 문서의 상대 경로와 SHA-256
- 실행 코드의 40자리 Git commit SHA
- commit의 `stom_rl` tree 목록 SHA-256
- 후보 점수, dataset manifest, causal panel, authority receipt, 001 validation receipt의 SHA-256
- 001 reference evidence SHA-256, 002 observed evidence SHA-256, exact match 여부
- 모델/행동 시드, 행동 정책, 전체 optimizer 계약
- 일봉 DB SHA-256
- DQN 5개와 CQL 5개 checkpoint 상대 경로·SHA-256
- gate 재계산에 필요한 각 시드 기본/스트레스 metrics

완료 bundle은 `summary.json`, `validation_receipt.json`, `validation_action_ledger.jsonl`, `rl_live_events.jsonl`, 10개 checkpoint의 정확히 14개 파일을 manifest로 결속한다. `summary.json`은 마지막 completion marker로 게시한다. 브라우저는 manifest 해시뿐 아니라 receipt schema, 10모델 집합, 비용, 행동, gate, summary 투영을 재검산한 경우에만 결과를 표시한다.

## 7. 성공 정의와 다음 단계

| 단계 | 성공 정의 | `002`에서 가능한가 |
|---|---|---|
| 구현 성공 | 10개 모델·영수증·ledger·telemetry·manifest 생성 | 가능 |
| 계보 재현 | hash-bound 001과 동일한 여섯 gate·10모델·checkpoint 결과를 결속 | 가능 |
| 새 검증 후보 | 아직 보지 않은 검증 구간에서 gate 통과 | 현재 불가 |
| 데이터 권위 | 서명된 원천 검토를 포함한 D0/D1 통과 | 현재 차단 |
| historical TEST | feature 46일이 이미 소비되어 독립 OOS 자격 상실 | 경제 증거로 사용 불가 |
| 경제 성능 | 새 Fresh OOS에서 비용 후 성능 확인 | 현재 금지 |
| 최종 연구 성공 | 권위·Fresh OOS·사람 승인 모두 통과 | `002`만으로 불가 |

Fresh OOS는 계산 시간이 아니라 새로운 미래 거래일이 쌓이는 시간이다. 최소 20~60 거래일, 약 4~12주를 예상하며 몇 시간의 추가 학습으로 대체하지 않는다. `002` 완료 후 모델은 동결하고, 다음 성능 판정은 데이터 권위 trust root 구현과 아직 보지 않은 새 미래 표본이 준비된 뒤 별도 ID로 사전등록해 진행한다.
