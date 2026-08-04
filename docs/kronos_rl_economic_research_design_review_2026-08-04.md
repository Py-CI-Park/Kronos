# Kronos 강화학습 경제성·환경·보상 설계 재검토

- 문서 ID: `KRONOS-RL-ECONOMIC-DESIGN-REVIEW-2026-08-04`
- 기준일: 2026-08-04 KST
- 기준 브랜치: `codex/rl-research-governance-v1-21`
- 기준 커밋: `30297a0634375a0a535a593556ff57beab6d1c83`
- 대상: 일봉을 이용한 종가 의사결정, 일정 자금·최대 10종목 포트폴리오 강화학습
- 현재 경계: 로컬 연구·백테스트·대시보드 증거. 수익성·Fresh OOS·paper·live broker 준비를 주장하지 않는다.

## 1. 최종 결론

Kronos는 강화학습 모델을 만들지 못한 시스템이 아니다. 실제 MaskablePPO와 DQN 모델을 생성하고 저장했으며, 합성 환경에서는 알려진 정책을 학습하는 데도 성공했다. 현재 실패는 모델 파일 생성 실패가 아니라 실제 시장 데이터에서 비용 후 일반화 가능한 행동 우위를 확인하지 못한 것이다.

`NO-GO`의 올바른 의미는 다음과 같다.

| 구분 | 현재 상태 | 의미 |
|---|---|---|
| 모델 artifact 생성 | `SUCCESS` | 실행 가능한 정책 파일이 존재한다. |
| 학습 파이프라인 | `COMPLETE` | 사전등록된 학습량과 산출물을 완료했다. |
| 현재 후보 경제성 | `NO_GO` | 해당 후보를 OOS·paper·live로 승격하지 않는다. |
| 강화학습 연구 프로그램 | `CONTINUE / PIVOT` | 새 데이터·feature·horizon·MDP 가설 연구는 계속한다. |
| Fresh OOS | `NOT_RUN_NO_READ` | 새 후보와 별도 승인 전까지 봉인한다. |

따라서 현재 후보를 더 오래 반복하는 것은 중단하되, 강화학습 연구 전체를 중단해서는 안 된다. 대시보드도 `후보 NO-GO`와 `연구 계속 가능`을 서로 다른 상태로 표시해야 한다.

## 2. 비용 계약 재검토

### 2.1 사용자 표시 단위

사용자 화면과 신규 문서는 `%`를 기본 단위로 사용한다. 기존 artifact/API 호환성 때문에 `base_23bp` 같은 내부 식별자는 유지할 수 있지만 화면에는 `0.23%`를 먼저 표시하고 `(23bp)`를 보조로 표시한다.

| 내부 값 | 사용자 기본 표시 |
|---:|---:|
| 1bp | 0.01% |
| 3bp | 0.03% |
| 9bp | 0.09% |
| 23bp | 0.23% |
| 46bp | 0.46% |

### 2.2 키움증권 공식 기본 온라인 비용

2026-08-04에 확인한 키움증권 공식 안내를 기준으로 한다. 계좌·매체·이벤트에 따라 실제 수수료가 달라질 수 있으므로 실행 manifest에는 적용 계좌의 수수료 계약과 유효기간을 기록한다.

| 상품·거래소 | 매수 수수료 | 매도 수수료 | 매도세금 | 동일 금액 왕복 명시비용 |
|---|---:|---:|---:|---:|
| KRX 코스피·코스닥 주식 | 0.015% | 0.015% | 0.20% | **0.230%** |
| NXT 코스피·코스닥 주식 | 0.0145% | 0.0145% | 0.20% | **0.229%** |
| KRX 국내주식형 ETF | 0.015% | 0.015% | 0% | **0.030%** |
| 신규계좌 할인 KRX 주식 예시 | 0.0036396% | 0.0036396% | 0.20% | **0.2072792%** |

정확한 비용은 매수금액과 매도금액이 다를 수 있으므로 다음처럼 계산한다.

```text
explicit_cost_krw =
    buy_notional  × buy_commission_rate
  + sell_notional × sell_commission_rate
  + sell_notional × sell_tax_rate
```

실제 경제성 평가에는 명시비용과 암묵비용을 분리한다.

```text
realized_cost = explicit_cost + spread + slippage + market_impact
```

공식 근거:

- 키움 국내주식: https://www3.kiwoom.com/h/domestic/stock/VStockMainView?dummyVal=0
- 키움 국내주식 핵심설명서: https://download.kiwoom.com/deploy/AG003/pdf/AG003_27.pdf
- 키움 ETF 세금: https://www3.kiwoom.com/m/domestic/stock/VEtfMainView
- 키움 신규계좌 수수료 할인: https://www1.kiwoom.com/e/home/event/VEvent20260001View?dummyVal=0

### 2.3 기존 판정에서 맞은 부분과 수정할 부분

| 기존 적용 | 재검토 | 조치 |
|---|---|---|
| 개별주식 Type1 `0.23%` | 공식 기본 온라인 비용과 일치 | primary 유지. 계좌별 할인 시나리오를 별도 추가한다. |
| ETF Q2-A primary `0.23%` | 국내주식형 ETF의 실제 명시비용으로는 과도함 | 실제 기본 `0.03%`, 실측 비용, 스트레스 `0.23%`로 재분류한다. |
| ETF diagnostic `0.09%` | 공식 수수료만으로 산출되지 않음 | `0.03%` 명시비용과 추가 `0.06%` 체결 가정을 분해한다. |
| 기본 시나리오 slippage `0%` | 개별주식에는 낙관적 | 거래대금·호가·주문크기별 실측 또는 보수적 구간을 추가한다. |

ETF의 `0.23%` 결과는 스트레스 내구성 자료로 보존하되 실제 기본비용 판정으로 사용하지 않는다. 반대로 ETF가 `0.03%`에서 양수여도 native-shuffle 차이, fold 안정성, drawdown, baseline 비교를 모두 다시 통과해야 한다.

## 3. 강화학습 개념과 Kronos 적용 계약

강화학습은 에이전트가 환경과 상호작용하며 장기 누적 보상을 크게 만드는 정책을 학습하는 방법이다. 일반적인 Markov Decision Process는 `(S, A, P, R, gamma)`로 표현한다.

| 요소 | 일반 의미 | Kronos에서 필요한 구체값 |
|---|---|---|
| `S`, State | 의사결정에 필요한 현재 상태 | 현금, 보유종목, 수량, 평균단가, 보유일수, 미실현 손익, 노출, 시장 관찰값 |
| `O`, Observation | 에이전트가 실제로 관측하는 정보 | 결정시점까지 공개된 가격·거래량·수급·시장 국면·PIT feature |
| `A`, Action | 환경을 바꾸는 행동 | 현금 유지, 보유 유지, 한 종목 추가, 한 종목 청산, 한 종목 교체, 위험 축소 |
| `P`, Transition | 행동 뒤 다음 상태 분포 | 체결·비용 반영 후 현금·수량·보유상태·다음날 평가금액 갱신 |
| `R`, Reward | 학습할 한 단계 가치 | 비용 차감 후 self-financing NAV 변화 |
| `gamma` | 미래 보상의 현재 가치 | 보유 horizon과 episode 정의에 맞춰 사전등록. 임의 sweep 금지 |
| Terminal | episode 종료 | 고정 연구기간 종료, 강제청산 규칙과 잔존 포지션 회계 포함 |

시장은 완전 관측 상태가 아니므로 실제 문제는 POMDP에 가깝다. 하지만 처음부터 LSTM·Transformer를 추가하면 표현력과 과적합이 함께 커진다. 먼저 사람이 해석할 수 있는 작은 상태와 보유 history를 사용하고, 그 기준선이 통과한 뒤 recurrent 모델을 ablation으로 추가한다.

### 3.1 상태 불변조건

1. 모든 feature는 주문 결정시점에 실제로 이용 가능해야 한다.
2. 종목 코드는 문자열로 유지하고 선행 0을 보존한다.
3. 현금 + 보유자산 평가액 - 누적비용이 NAV와 일치해야 한다.
4. 행동 후 수량·현금·보유일수·평균단가가 다음 observation에 반영되어야 한다.
5. 매수 불가·현금 부족·종목 수 초과 행동은 action mask로 차단한다.
6. episode 종료 시 강제청산 여부와 비용을 사전에 고정한다.
7. 미래가격, 미래 universe membership, 사후 수정된 기업정보를 읽지 않는다.

### 3.2 종가매매 시간 계약

당일 공식 종가는 주문 전에 알 수 없다. 아래 두 계약 중 하나를 명시적으로 선택해야 한다.

| 계약 | 입력 | 결정·체결 | 이름 |
|---|---|---|---|
| Closing-auction 계약 | 15:20 또는 주문 마감 전까지 이용 가능한 정보 | 주문을 먼저 결정하고 공식 종가 경매에서 체결 | `CLOSE_AUCTION_CAUSAL` |
| Next-session 계약 | 당일 공식 일봉 종가까지 사용 | 다음 거래일 시가·지정 시점에 체결 | `NEXT_SESSION_AFTER_DAILY_CLOSE` |

현재 `15:20 close proxy`는 공식 종가 체결과 같지 않으므로 유지할 경우 UI와 보고서에서 proxy라고 명시한다. 당일 공식 종가를 feature와 동일 체결가격으로 동시에 사용하는 경로는 미래정보 누출로 금지한다.

## 4. 보상 설계

### 4.1 권장 기본 보상

```text
reward_t = log(NAV_t / NAV_t-1)
```

`NAV_t`는 이미 다음을 반영한다.

- 체결 가격
- 매수·매도 수수료
- 매도세금
- spread·slippage·market impact
- 현금과 보유수량
- 배당·분할 등 total-return 조정 또는 명시적 현금흐름

비용이 NAV에 반영됐다면 동일 turnover 비용을 reward에서 다시 차감하지 않는다. 중복 벌점은 정책을 무조건 현금 보유로 몰 수 있다.

### 4.2 보상과 제약의 분리

| 항목 | 권장 처리 | 이유 |
|---|---|---|
| 거래비용 | NAV에 직접 반영 | 실제 현금흐름이다. |
| 최대 10종목 | hard constraint/action mask | 정책이 위반할 수 없는 운용 계약이다. |
| 최대 5천만원 노출 | hard constraint | 6천만원 중 1천만원 reserve 계약을 보존한다. |
| 최대 낙폭 | 평가 gate 또는 constrained RL | 임의 reward 계수보다 해석 가능하다. |
| 종목 집중도 | hard limit 또는 별도 risk budget | reward hacking을 줄인다. |
| 잦은 교체 | 실제 비용으로 우선 억제 | 추가 penalty는 별도 ablation에서만 검증한다. |

보상 shaping이 필요하면 최적 정책을 바꾸지 않는 potential-based shaping부터 검토한다. 원 연구는 Andrew Ng, Daishi Harada, Stuart Russell, “Policy Invariance Under Reward Transformations”(ICML 1999)이다.

## 5. 현재 Kronos 연구 타당성 감사

| 검사 질문 | 증거 | 판정 |
|---|---|---|
| 실제 RL 모델을 만들었는가 | Type1 primary 5 + shuffled 5, seed당 200,000 step | `PASS_MODEL_BUILD` |
| 작은 train 문제를 학습할 수 있는가 | D5S 100K에서 7/7 gate 통과 | `PASS_TRAIN_ONLY` |
| 더 오래 학습하면 개선되는가 | 200K→800K accuracy lift -0.176265, reward lift -0.233700 | `FAIL_MORE_STEPS` |
| validation에 일반화하는가 | D5S 0.827225 → D6 0.179688 | `FAIL_GENERALIZATION` |
| 비용만이 원인인가 | D6R 0% 명시비용에서도 reward ratio -0.077106 | `NO` |
| 현재 top-5 표현에 신호가 있는가 | D6R2 DQN -0.127615, ridge -0.152520, 2/13 gates | `FAIL_SIGNAL_FLOOR` |
| 거래가 너무 잦은가 | D6R2 median trade rate 0.90 | `YES` |
| 환경이 알려진 정책을 학습하는가 | ETF Q2-B synthetic 3/3 seed | `PASS_SYNTHETIC_MDP` |
| ETF 실제 기본비용이 맞는가 | 0.23% primary는 국내주식형 ETF 명시비용과 불일치 | `REVISE_COST_CONTRACT` |
| 공식 종가 계약인가 | 15:20 proxy | `NOT_YET` |

가장 강한 결론은 다음과 같다.

1. 구현과 학습기 자체는 작동한다.
2. 기존 top-5/14-feature/동일 horizon 후보는 일반화하지 못했다.
3. 기존 후보에 seed·step·gamma를 더 넣는 것은 정보가치가 낮다.
4. ETF 비용 계약은 실제 기본비용과 스트레스 비용으로 분리해 재실행할 가치가 있다.
5. 실제 시장 RL 전에는 인과적 종가 계약과 point-in-time 데이터 custody가 필요하다.

## 6. 왜 로봇·게임 RL과 금융 RL이 다른가

| 성공 사례 | 성공 조건 | Kronos에 가져올 원칙 |
|---|---|---|
| AlphaGo Zero | 정확한 규칙, self-play, 약 500만 게임 | 합성 환경에서 알려진 최적 정책을 반복 학습해 구현을 검증한다. |
| OpenAI Five | 대규모 병렬 self-play, 하루 수백 년의 새 경험 | 동일 역사 재생을 새 경험으로 착각하지 않는다. |
| QT-Opt 로봇 집기 | 58만 회 실제 시도, 명확한 성공 보상, 재시도 가능 | 성공·실패가 명확한 synthetic curriculum과 invariant를 만든다. |
| SAC | replay와 entropy, seed 안정성 | 평균 하나가 아니라 여러 seed와 분포를 평가한다. |
| 선물 Trading RL | 유동성 높은 다수 계약, 포지션 유지, 변동성 조절 | 종목을 매일 전량 교체하지 않고 보유·현금 행동을 강화한다. |

금융에서는 과거 경로가 고정되어 있고 실제 시장을 자유롭게 reset할 수 없다. 따라서 PPO 같은 online/on-policy 알고리즘을 같은 역사에 오래 돌리는 것보다 offline RL의 데이터 분포 이탈을 통제하는 것이 중요하다.

관련 연구:

- AlphaGo Zero: https://www.nature.com/articles/nature24270
- OpenAI Five: https://openai.com/index/openai-five/
- QT-Opt: https://arxiv.org/abs/1806.10293
- Soft Actor-Critic: https://proceedings.mlr.press/v80/haarnoja18b.html
- CQL: https://proceedings.neurips.cc/paper/2020/hash/0d2b2061826a5df3221116a5085a6052-Abstract.html
- 금융 RL 일반화: https://www.ijcai.org/proceedings/2023/553
- RL 과적합: https://arxiv.org/abs/1804.06893
- RL 소표본 통계평가: https://proceedings.neurips.cc/paper/2021/hash/f514cec81cb148559cf475e7426eed5e-Abstract.html
- 백테스트 과적합 확률: https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253
- 대규모 포트폴리오 반증: https://www.sciencedirect.com/science/article/pii/S154461232500131X
- 비용 후 선물 RL 사례: https://arxiv.org/abs/1911.10107

## 7. 권장 모델 구조

### 7.1 개별주식 주력 lane

| 항목 | 권장 계약 |
|---|---|
| 사용자 목표 | 일봉 기반 종가 의사결정, 일정 금액, 최대 10종목 |
| 비용 | KRX 0.230%, NXT 0.229%, 계좌 할인 별도, 체결비용 별도 |
| 후보 생성 | 인과적 supervised ranker가 상위 20개 후보를 생성 |
| RL 역할 | 현금 유지, 기존 보유 유지, 추가, 청산, 한 종목 교체, 위험 축소 |
| 평균 보유기간 가설 | 5·10·20거래일을 별도 사전등록 |
| 알고리즘 | 작은 DQN 기준선 → CQL/IQL 계열 offline RL → simulator 통과 후 PPO ablation |
| 평가 | no-trade, equal-weight, RULE, supervised-only, shuffled controls |

후보 ranker가 종목 예측을 담당하고 RL이 연속된 포트폴리오 의사결정을 담당하면 이를 `HYBRID_RL`로 정직하게 표시한다. 모든 종목 선택을 RL이 직접 해야만 강화학습인 것은 아니다.

### 7.2 국내주식형 ETF 저비용 lane

| 비용 시나리오 | 용도 |
|---:|---|
| 0.00% | 회계·신호 진단 control |
| 0.03% | 키움 기본 명시비용 primary |
| 실측 비용 | 호가·체결 데이터에서 산출한 primary-realized |
| 0.09% | 명시 0.03% + 추가 체결비용 0.06% 진단 |
| 0.23% | 개별주식 수준 stress |

ETF lane은 기존 Q2-A를 같은 결과에 맞춰 수정하는 것이 아니라, 비용 계약 변경을 새 preregistration으로 동결한 뒤 처음부터 다시 평가한다.

## 8. 검증 프로토콜

| 구간 | 사용할 수 있는 목적 | 금지 |
|---|---|---|
| Synthetic | 회계·환경·학습기 검증, 의도적 과적합 | 시장 alpha 주장 |
| TRAIN inner folds | feature·architecture 학습, 사전등록된 early-stop | outer fold 결과를 사용한 튜닝 |
| Outer validation | 후보의 시간 일반화 확인 | 결과를 본 뒤 같은 구간에 재튜닝 |
| Fresh OOS | 최종 후보 단 한 번 반증 | best-of-many 선택, 반복 열람 |
| Paper-forward | 실제 주문·지연·체결·슬리피지 측정 | 백테스트 결과로 대체 |

필수 경제성 보고 항목:

- 비용 후 누적수익률과 연환산수익률
- Sharpe, Sortino, Calmar, MDD
- 회전율과 명시·암묵 비용 drag
- seed별 값, IQM, bootstrap 신뢰구간
- positive fold 비율
- no-trade·RULE·supervised-only 대비 delta
- native-shuffled delta
- action distribution과 현금 보유 비중
- 결과가 가장 나쁜 seed·fold

## 9. UX/UI 연결 요구사항

### 9.1 공통 상태 카드

모든 RL 페이지 상단에서 다음 네 상태를 독립적으로 표시한다.

| 질문 | 표시 예시 |
|---|---|
| 모델이 만들어졌는가 | `모델 생성 완료 · 10개` |
| 학습이 끝났는가 | `학습 완료 · seed당 200,000 step` |
| 경제성이 있는가 | `현재 후보 NO-GO · 검증 일반화 실패` |
| 연구를 계속할 수 있는가 | `새 연구 가능 · 비용/상태/보유기간 PIVOT` |

### 9.2 비용 UX

- 상품: 개별주식 / 국내주식형 ETF / 기타 ETF를 선택한다.
- 거래소: KRX / NXT / SOR 결과를 구분한다.
- 계좌 수수료: 기본 / 이벤트 / 사용자 입력을 구분한다.
- 매수·매도 수수료, 세금, spread, slippage를 `%`와 원화로 보여준다.
- `0.23%`를 모든 상품의 단일 정답으로 표시하지 않는다.
- artifact의 `base_23bp`는 “이전 개별주식 비용 시나리오”라고 설명한다.

### 9.3 연구 단계 UX

```text
현재 후보 종료(NO-GO)
  → 비용 계약 수정
  → 인과적 데이터 확인
  → 신호 바닥
  → 합성 환경
  → 최소 offline RL
  → nested validation
  → Fresh OOS
```

각 단계에는 `왜 필요한가`, `통과 기준`, `실패 시 다음 행동`, `어떤 페이지에서 확인하는가`를 함께 표시한다. `NO-GO`만 보여주고 사용자가 갈 곳을 잃게 해서는 안 된다.

## 10. 점수 재평가

이 점수는 수익 확률이 아니라 현재 증거와 설계의 성숙도를 나타낸다.

| 축 | 점수 | 근거 | 목표 |
|---|---:|---|---:|
| RL 개념·환경 명세 | 82 | stateful synthetic 3/3, 실제 종가 계약 미완료 | 95 |
| 비용 회계 | 78 | 개별주식 0.23% 정확, ETF 계약 수정 필요 | 95 |
| 데이터 인과성·custody | 58 | PIT universe·available_at·total return 미완료 | 90 |
| 모델 생성·재현성 | 94 | 다중 seed 모델·receipt·controls 존재 | 98 |
| 일반화 증거 | 18 | D6·D6R2·ETF Q2-A 실패 | 70 이상 필요 |
| UX/UI 설명력 | 84 | 모델/경제성 분리, 비용 상품별 UX 미구현 | 95 |
| 연구 거버넌스 | 92 | prereg·봉인·Git 계보 강함 | 97 |
| live 준비도 | 0 | Fresh OOS·paper·broker 미실행 | 별도 단계 |

## 11. 다음 결정

1. 기존 top-5/14-feature PPO/DQN 반복은 종료한다.
2. 비용 계약을 개별주식과 ETF로 분리한다.
3. 종가 의사결정 시점과 실제 체결 시점을 하나의 인과적 계약으로 동결한다.
4. 신규 5·10·20일 horizon에서 값싼 supervised signal floor를 먼저 실행한다.
5. synthetic stateful 환경은 유지하고 정확한 비용·강제청산·cash/position invariant를 확대한다.
6. 실제 시장 데이터는 CQL 등 보수적 offline RL을 우선한다.
7. 하나의 후보가 nested validation을 통과할 때만 Fresh OOS를 별도 승인한다.
