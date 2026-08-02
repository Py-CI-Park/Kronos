# Quantylab 강화학습 ETF 투자 전체 콘텐츠 검토와 Kronos 연구 업데이트

- 작성일: 2026-08-01 KST
- 원문 카테고리: [파이썬을 이용한 강화학습 주식투자](https://contents.premium.naver.com/misoncorp/quantylab/contents?categoryId=1903f00aa0a000gzs)
- 확인 범위: 카테고리의 12개 게시물 전체 목록, 2026년 ETF 구현 6편 본문, 2024년 개정판 6편의 목차와 허용된 읽기전용 PDF 뷰어
- 검토 목적: 원문 복제나 투자 추천이 아니라 Kronos D6R2 이후의 연구 가설·환경·검증 체계를 개선하는 것
- 저작권 경계: 유료 원문·코드·PDF를 재배포하지 않고 핵심 개념과 비판적 검토를 독자적으로 재구성함
- 기존 Kronos 판정: `D6R2_TOP5_SIGNAL_FLOOR_NOT_CONFIRMED`, 모델 성과 18/100, D7 `LOCKED`
- 업데이트 판정: **기존 lane STOP 유지 + ETF stateful MDP 신규 lane `CONDITIONAL-GO`**

## 1. 한 줄 결론

Quantylab 자료는 Kronos의 기존 18점 모델이 사실은 성공했다는 증거가 아니다. 대신 기존 실패의 핵심 원인이었던 `행동이 다음 상태를 바꾸지 않는 contextual 선택 문제`와 `일봉 단일 종목 top-5 신호 부족`을 피할 수 있는 구체적인 새 연구 설계를 제공한다.

가장 가치 있는 아이디어는 다음 세 가지다.

1. 개별 종목 선택이 아니라 국내 주식형 ETF 스윙 포지션 제어로 문제를 바꾼다.
2. 행동을 `[0,1]` 목표 보유 비율로 정의하고 현금·수량·포트폴리오 가치가 다음 상태에 반영되게 한다.
3. 전일 정보로 당일 시가에 거래하고 당일 종가로 평가하여 시간 순서와 look-ahead 경계를 명시한다.

그러나 현재 게시된 12편에는 다중 seed, chronological fold, shuffle control, sealed OOS, 비용 민감도, 실제 성과표가 없다. 따라서 자료의 위치는 **검증된 수익 모델**이 아니라 **실험할 가치가 있는 설계 참고안**이다.

## 2. 검토 방법과 범위

| 항목 | 확인 결과 |
|---|---|
| 카테고리 게시물 | 12개 |
| 2024년 개정판 안내·기초 | 6개 |
| 2026년 ETF 구현 시리즈 | 6개 |
| 2026년 본문 | 로그인 세션에서 전체 본문 확인 |
| 2024년 PDF | 소유자가 다운로드·인쇄를 차단한 Google Drive 읽기전용 뷰어 사용 |
| PDF 상세 확인 | 1장 금융 데이터와 3장 강화학습의 뷰어 텍스트·페이지 확인, 나머지는 게시물에 공개된 전체 목차 중심 |
| 원문 저장 | 하지 않음 |
| 재배포 | 하지 않음 |

PDF 소유자의 다운로드 제한은 우회하지 않았다. 검토 문서에는 원문 전체나 긴 인용을 넣지 않고 연구 설계에 필요한 요약과 비판만 남긴다.

## 3. 전체 12개 콘텐츠 목록과 핵심

| 순서 | 게시물 | 일자 | 핵심 내용 | Kronos 관련성 |
|---:|---|---|---|---|
| 1 | [4판 개정 안내](https://contents.premium.naver.com/misoncorp/quantylab/contents/240622171313918mv) | 2024-06-22 | Keras 제외, PyTorch 집중, Transformer·PPO 추가 계획 | 기술 선택보다 문제·검증 설계가 먼저라는 기준 필요 |
| 2 | [금융 데이터 분석](https://contents.premium.naver.com/misoncorp/quantylab/contents/240622171419161px) | 2024-06-22 | 기본·기술·정서 분석, 퀀트, return·alpha·beta·Sharpe·Sortino·MDD | Kronos 대시보드에 risk-adjusted 평가 보강 |
| 3 | [딥러닝 배경](https://contents.premium.naver.com/misoncorp/quantylab/contents/240713153923242vm) | 2024-07-13 | 퍼셉트론, 역전파, 과적합, RNN·LSTM·CNN·Transformer | 복잡한 모델보다 데이터량·과적합 통제가 우선 |
| 4 | [강화학습 배경](https://contents.premium.naver.com/misoncorp/quantylab/contents/240725215416527xh) | 2024-07-25 | MDP, 가치함수, Bellman, Q/DQN, PG, actor-critic, PPO | 행동이 전이에 영향을 주는 MDP 계약 재확인 |
| 5 | [금융 데이터 수집](https://contents.premium.naver.com/misoncorp/quantylab/contents/241024214245992cr) | 2024-10-26 | HTS·HTS API·KIS REST·크롤링·DART·Quantylab DB/API | source·시점·수정 이력·point-in-time custody 필요 |
| 6 | [주식 피처 엔지니어링](https://contents.premium.naver.com/misoncorp/quantylab/contents/241024214549366df) | 2024-11-02 | 시장·금리·환율·원자재·재무·OHLCV·공매도·에이전트 상태 | 현재 14-feature lane보다 넓은 후보 가설 제공 |
| 7 | [ETF 투자 기초](https://contents.premium.naver.com/misoncorp/quantylab/contents/260607151307598ed) | 2026-06-07 | 64개 TIGER ETF, 섹터 로테이션, 스윙, 9bp 비용 가정 | 새 universe/horizon 후보 |
| 8 | [시스템 설계](https://contents.premium.naver.com/misoncorp/quantylab/contents/260627212601095nc) | 2026-06-28 | dataset→train→backtest→predict, PPO·Beta action | Kronos 실험 파이프라인과 직접 비교 가능 |
| 9 | [투자 환경 설계](https://contents.premium.naver.com/misoncorp/quantylab/contents/260704191746406ke) | 2026-07-04 | 포지션·현금 state, 연속 action, 시가 체결, 5항 보상 | 기존 MDP 오지정의 직접 대안 |
| 10 | [특성 공학](https://contents.premium.naver.com/misoncorp/quantylab/contents/260711074241539hc) | 2026-07-11 | 기술·시장·매크로·수급·시간·ETF 메타·포트폴리오 특성 | 새 signal floor 후보, 누출 위험도 큼 |
| 11 | [신경망 아키텍처](https://contents.premium.naver.com/misoncorp/quantylab/contents/260723114716917kg) | 2026-07-23 | Mamba/Residual MLP/LSTM, LayerNorm, Beta policy | 복잡도 ablation과 checkpoint 계약 필요 |
| 12 | [PPO 학습](https://contents.premium.naver.com/misoncorp/quantylab/contents/260729132352432xd) | 2026-07-29 | PPO·GAE·clip·entropy·action mixing·risk reward | 학습 레시피는 있으나 성능 증거는 없음 |

## 4. 2024년 기초 콘텐츠 종합

### 4.1 금융 데이터와 평가

자료는 OHLCV만으로 충분하다고 보지 않는다. 시장·종목·수급·환율·금리·원자재·재무·정서 데이터를 함께 분석하고, 성과는 단순 수익률뿐 아니라 alpha, beta, Sharpe, Sortino, MDD로 평가해야 한다고 설명한다.

Kronos에 주는 의미는 두 가지다.

- D6R2의 14-feature top-5 표현은 비용 후 ridge signal floor까지 실패했으므로, 입력 가설을 넓힐 합리적 근거가 있다.
- reward ratio와 MDD만 보지 말고 시장 대비 alpha, downside 변동성, turnover-adjusted 결과를 함께 봐야 한다.

### 4.2 강화학습 이론

자료의 강화학습 정의는 MDP `(S,A,P,R,γ)`를 중심에 둔다. 정책이 행동을 선택하고 그 행동이 전이와 보상에 영향을 줘야 한다. 이 원칙은 D6R2에서 확인한 현재 `HistoricalTopKEnv`의 한계와 정확히 맞닿는다. 기존 환경은 오늘의 후보 선택이 다음 날의 보유상태·현금·후보를 바꾸지 않아 sequential control보다 contextual selection에 가까웠다.

### 4.3 데이터 수집과 피처

자료는 HTS/API/REST/DART/크롤링/자체 DB 등 다양한 소스를 제안한다. 데이터 소스가 많아질수록 예측 정보도 늘 수 있지만, 다음 위험도 함께 증가한다.

| 위험 | Kronos 필수 통제 |
|---|---|
| 발표·수정 시점 불명확 | 각 row에 `available_at`과 source snapshot SHA 기록 |
| 현재 구성종목 기준 생존편향 | point-in-time ETF universe 사용 |
| 스케일러 누출 | fold train에서만 fit, evaluation row 0 |
| 결측치 미래 채움 | `bfill` 금지, train-only imputation 또는 warm-up drop |
| 다른 시장의 시차 | 한국 장 개장 전에 실제 확정된 데이터만 사용 |
| 재무 데이터 revision | 당시 공개본 또는 filing timestamp 기준 |

## 5. 2026년 ETF 구현 설계

### 5.1 연구 대상

| 항목 | Quantylab 설계 |
|---|---|
| universe | TIGER 국내 ETF 64개 |
| 최소 이력 | 약 250 거래일 |
| 제외 | 채권·해외·레버리지·인버스·원자재·외화 |
| 목적 | ETF별 목표 보유 비율 제어와 섹터 로테이션 |
| 보유 방식 | 수일~수주 스윙 |
| 학습 단위 | 한 번에 ETF 하나, ETF별 episode 순환 |
| 주문 범위 | 공유판은 신호 추론까지만, 주문 없음 |

ETF는 개별 기업 이벤트 노이즈가 작고 거래세가 없으며, 섹터·거시 피처와 연결하기 쉽다는 장점이 있다. 이 변경은 기존 개별 종목 top-5 lane과 충분히 다른 새 가설이다.

### 5.2 상태·행동·전이

| MDP 요소 | 설계 |
|---|---|
| 시장 상태 | API scaled feature vector |
| 포트폴리오 상태 | 누적 수익, drawdown, 최근 승률, streak, 변동성, 현재 포지션 비율 6개 |
| 행동 | ETF 목표 보유 비율 `a∈[0,1]` |
| 행동 분포 | Beta distribution |
| 거래 억제 | 현재 비율과 목표 비율 차이가 학습 설정 20%를 넘을 때만 리밸런싱 |
| 정보 시점 | `t-1` feature로 결정 |
| 체결 | `t` 시가에 fee·slippage 반영 |
| 평가 | `t` 종가로 portfolio value 계산 |
| 다음 상태 | 변경된 현금·수량·포지션·성과를 포함 |
| ETF 경계 | 포지션 청산, 수익 집계, 자본 reset |

이 구조는 행동이 실제로 다음 상태를 바꾸기 때문에 D6R2의 MDP 오지정 문제를 직접 개선한다.

다만 여러 ETF를 동시에 보유하고 자본을 배분하는 portfolio MDP는 아니다. 각 ETF를 독립적으로 제어한 뒤 별도 ranking/backtest 계층에서 후보를 선택한다. 따라서 `single-ETF position-control MDP`라고 부르는 것이 정확하다.

### 5.3 거래 비용 차이

| 항목 | Quantylab | Kronos 현재 기준 |
|---|---:|---:|
| 매매 수수료 | 편도 1.5bp | 23bp round trip에 포함 |
| 슬리피지 | 편도 3bp | 23bp round trip에 포함 |
| 거래세 | ETF 0 | 종목/실험 계약별 포함 |
| 왕복 합계 | 약 9bp | 23bp primary |

새 ETF lane에서도 **23bp를 primary gate로 유지**하고 9bp는 ETF 전용 진단으로만 병기한다. 9bp만 통과하고 23bp에서 실패하면 비용 민감 후보일 뿐 승격하지 않는다. 특히 거래량이 작은 ETF에서는 고정 3bp 슬리피지가 낙관적일 수 있어 bid/ask·거래대금 기반 stress가 필요하다.

### 5.4 보상 함수

자료의 reward는 다섯 요소를 조합한다.

| 요소 | 설명 | 주요 계수 |
|---|---|---:|
| 일간 수익 | 손실일에 더 큰 가중치 | reward scale 30, loss aversion 1.2 |
| 수수료 패널티 | 거래 억제 | 15 |
| drawdown 패널티 | 12% 초과 낙폭과 포지션에 비례 | threshold 0.12, scale 25 |
| rolling Sharpe | 최근 20일 안정성 보너스 | scale 2 |
| terminal reward | CAGR·Sharpe·Calmar·손익비 결합 | terminal scale 30 |

최종 step reward는 `[-5,+5]`, terminal bonus는 별도 범위로 clip한다. 학습 설정에는 inaction penalty 10도 포함된다.

이 설계는 리스크를 명시한다는 장점이 있지만 reward hacking과 사후 계수 튜닝 위험이 크다. 특히 `20% hold threshold`로 거래를 줄이면서 `inaction penalty`로 행동을 강요하면 목표가 충돌할 수 있다.

Kronos에서는 다음 세 arm을 사전등록해 ablation해야 한다.

1. `NET_RETURN_ONLY`: 비용 후 순수 포트폴리오 변화
2. `RISK_MINIMAL`: net return + drawdown constraint
3. `FULL_SHAPED`: 자료의 복합 보상

FULL_SHAPED만 통과하고 NET_RETURN_ONLY가 실패하면 실제 alpha보다 reward shaping을 학습했을 가능성을 우선 의심한다.

### 5.5 특성 벡터

| 묶음 | 예시 |
|---|---|
| ETF 기술 | RSI, MACD, Bollinger, ADX, Stochastic, OBV, ATR, momentum, z-score |
| 국내 시장 | KOSPI, KOSDAQ, 거래량, 이동평균, 변동성 |
| 해외 시장 | S&P 500, NASDAQ, Dow |
| 매크로 | USD/KRW, VIX, KOSPI VIX, SOX, 금리, GSCI, DX, Fear & Greed, PER/PBR |
| 수급 | 신용, 선물 basis, 프로그램 매매, 외국인·기관·개인, 공매도 |
| 원자재·운임 | BDI, SCFI, WTI, 금, 은, 구리, 철광석 |
| 시간 | 요일, 월, 월말 |
| ETF 메타 | 섹터, 변동성, 상장기간, 유동성 |
| 포트폴리오 | 누적 수익, DD, 승률, streak, 변동성, 포지션 |

자료는 모든 로컬 기술 지표에 `shift(1)`을 적용한다고 설명하지만, 공유 경로는 API가 미리 scaled한 feature vector를 그대로 사용하며 shift와 scaling의 안전성을 API 생성 단계에 의존한다. 또한 fallback 결측치 처리 예시의 `ffill().bfill()`은 time series에서 미래 값을 과거로 넣을 수 있다.

Kronos 적용 시 필수 변경은 다음과 같다.

- API scaled value를 그대로 신뢰하지 않고 raw/as-of snapshot을 custody한다.
- scaler는 fold-local로 fit한다.
- `bfill`을 금지한다.
- 긴 warm-up이 필요한 지표는 초기 row를 제거하거나 missing indicator를 둔다.
- feature를 한 번에 전부 넣지 않고 그룹별 supervised floor와 ablation을 먼저 수행한다.

### 5.6 신경망과 행동 분포

| 후보 | 장점 | 위험 | Kronos 우선순위 |
|---|---|---|---:|
| Residual MLP | 단순·안정·빠름 | 시계열 메모리 약함 | 1 |
| LSTM | 장기 순서 표현 | 학습 불안정·state 관리 | 2 |
| Mamba/SSMGate | 경량 선택 게이팅 | 실험적·구현 복잡·과적합 해석 어려움 | 3 |
| FT-Transformer | feature interaction | 데이터 요구량과 과적합 위험 큼 | HOLD |

자료 내부에서도 기본값은 Mamba라고 설명하면서 안정성과 프로덕션에서는 Residual MLP를 권장하는 부분이 있다. 또한 train CLI 예시는 `d_model=128, n_blocks=3`이고 prediction 기본 로드는 `d_model=64, n_blocks=2`라고 설명한다. checkpoint에 architecture manifest가 없으면 학습·추론 구조 불일치가 생길 수 있다.

따라서 첫 pilot은 Residual MLP 하나로 시작하고, Mamba는 동일한 사전등록 gate를 baseline이 통과한 뒤에만 비교한다. 모델 저장물에는 input dimension, architecture, hidden size, blocks, action distribution, feature schema SHA를 반드시 포함한다.

Beta distribution은 `[0,1]` 포지션에 자연스럽지만 `α,β≥1.5`는 0% 현금 또는 100% 투자 같은 경계를 구조적으로 억제한다. 완전 risk-off가 필요한 시장에서 문제가 될 수 있으므로 다음을 비교해야 한다.

- 순수 Beta continuous
- `cash/position` discrete gate + Beta amount의 혼합 정책
- 안전 제약이 있는 squashed Gaussian baseline

### 5.7 PPO 설정

| 파라미터 | 게시 설정 |
|---|---:|
| episodes | 500 |
| update interval | 64 steps |
| gamma | 0.995 |
| GAE lambda | 0.95 |
| PPO clip epsilon | 0.2 |
| policy LR | 0.0001 → 0.00002 cosine |
| value LR | 0.0003 → 0.00005 cosine |
| entropy coefficient | 0.05 → 0.01 |
| random action mix | 0.05 → 0.01 |
| gradient clip | 1.0 |
| reward clip | 5.0 |

이 설정은 구현 가능한 출발점이지만 최적값이나 수익성을 증명하지 않는다. 게시물에는 학습 loss, entropy, action distribution, seed dispersion, walk-forward 성과, shuffle control, Fresh OOS가 없다.

## 6. 콘텐츠에서 확인되지 않은 것

| 미확인 증거 | 왜 필요한가 | 현재 판정 |
|---|---|---|
| chronological train/validation/test 범위 | 시간 일반화 확인 | 없음 |
| point-in-time universe | 생존편향 방지 | 없음 |
| fold-local scaler proof | normalization 누출 방지 | 없음 |
| 다중 seed | 초기화 안정성 | 없음 |
| shuffle/negative control | 우연·암기 분리 | 없음 |
| no-trade·equal-weight·momentum baseline | RL 추가가치 확인 | 설명만 있고 성과표 없음 |
| 9bp/23bp cost sensitivity | 비용 강건성 | 없음 |
| OOS MDD·Sharpe·Calmar | 위험 조정 일반화 | 없음 |
| dividend/분배금 total-return 처리 | ETF 경제성과 정확성 | 상세 미확인 |
| bid/ask·거래대금 체결 stress | 실제 체결 가능성 | 없음 |
| artifact SHA·receipt·custody | 재현성과 변조 방지 | 없음 |
| paper forward | 실제 시간 순서 | 없음 |

따라서 공개된 콘텐츠만으로 “PPO ETF 모델이 수익성이 있다”거나 “Kronos보다 우수하다”고 결론내릴 수 없다.

## 7. Kronos D6R2와 직접 비교

| 항목 | Kronos 현재 lane | Quantylab ETF 설계 | 판단 |
|---|---|---|---|
| 대상 | 일봉 top-5 종목 선택 | 국내 TIGER ETF 스윙 | 충분히 다른 새 가설 |
| 행동 | 후보 선택 | 목표 보유비율 `[0,1]` | ETF 쪽이 포트폴리오 상태에 직접 영향 |
| 순차성 | 다음 날짜 state에 행동 영향 약함 | 현금·수량·포지션이 다음 state에 반영 | 기존 MDP 오지정 개선 |
| horizon | 사실상 일별 contextual | 수일~수주 | 거래비용·거시 신호에 유리할 가능성 |
| feature | top-5, 14 feature | 시장·매크로·수급·메타+포트폴리오 | signal 후보는 넓지만 누출 위험 증가 |
| 알고리즘 | DQN gamma 0/1 | PPO gamma 0.995, Beta action | 문제에 맞는 연속 제어 |
| 비용 | 23bp primary | 약 9bp | Kronos는 23bp gate 유지 |
| 통제 | 5 folds·3 seeds·shuffle·ridge | 게시 성과 통제 없음 | Kronos 거버넌스가 강함 |
| 결과 | 70/70, 2/13, NO-GO | 설계·코드 설명, 결과표 없음 | 기존 판정 변경 불가 |
| OOS | D7 locked | 게시물에서 미확인 | 둘 다 live 근거 없음 |

## 8. 업데이트된 점수

### 8.1 기존 결과

| 대상 | 점수 | 변경 |
|---|---:|---|
| 기존 D6R2 모델 성과 | 18/100 | 변경 없음 |
| Kronos 연구 플랫폼 | 90/100 | 변경 없음 |
| live readiness | 0~5/100 | 변경 없음 |

외부 설계 문서를 읽었다고 기존 모델의 실제 보상·fold·seed 결과가 좋아진 것은 아니다.

### 8.2 ETF 신규 lane 설계 준비도

| 축 | 점수 | 가중치 | 근거 |
|---|---:|---:|---|
| 문제·MDP 적합성 | 82 | 25% | action-dependent position/cash transition |
| feature·domain 가설 | 75 | 20% | ETF·거시·수급·portfolio state |
| 누출·데이터 안전 | 35 | 20% | shift 설명은 있으나 API scaler·bfill·point-in-time 미검증 |
| 구현 구체성 | 75 | 15% | CLI·환경·PPO·network 구체적 |
| 평가·control 증거 | 5 | 15% | 게시된 성과표·seed·fold·shuffle 없음 |
| live 준비 | 0 | 5% | 주문·paper·broker evidence 없음 |
| **가중 종합** | **44/100** | **100%** | 모델 점수가 아니라 연구 착수 준비도 |

44점은 실제 모델 성능이 아니다. 환경과 실험을 설계할 정보는 충분하지만, 성과를 믿을 검증 증거는 거의 없다는 뜻이다.

## 9. 업데이트된 실행 계획

기존 계획의 `새 signal floor → 합성 stateful MDP → 최소 pilot` 원칙은 유지한다. 다만 ETF 자료 덕분에 질문과 구현 계약이 구체화됐으므로 Phase A와 B는 서로 다른 자원을 사용해 병렬 준비할 수 있다. 실제 시장 RL 학습은 두 단계 모두 통과한 뒤에만 한다.

| 단계 | 작업 | 핵심 gate | 예상 | 실패 시 |
|---:|---|---|---:|---|
| Q0 | ETF lane prereg·universe 계약 | current lane과 완전 분리, D7 no-read | 4~8시간 | 착수 보류 |
| Q1 | point-in-time 데이터·as-of audit | raw SHA, `available_at`, bfill 0, split-local scaler | 1~2일 | 데이터 lane 종료 |
| Q2-A | ETF feature/horizon supervised floor | 5 folds, shuffle, 9/23bp, positive 4/5 | 1~2일 | 실제 RL 금지 |
| Q2-B | synthetic stateful environment | position/cash/fee invariant 100%, 알려진 정책 3/3 seeds | 1~2일 | 실제 RL 금지 |
| Q3 | Residual MLP PPO 최소 pilot | 5 folds×3 seeds, net-return arm 우선 | 1~3일+연산 | 후보 종료 |
| Q4 | reward ablation | minimal vs full-shaped, 동일 seed·fold | 1~2일 | shaping 채택 금지 |
| Q5 | Mamba/LSTM 비교 | Q3 통과 후보에 한함 | 1~2일 | baseline 유지/후보 종료 |
| Q6 | 새 sealed ETF OOS 1회 | 별도 prereg·승인 | 0.5~1일 | 모델 폐기 |
| Q7 | paper forward | 지연·체결·분배금·운영 risk | 수주 | live 금지 |

기존 D7은 현재 top-5 계보의 봉인 데이터이므로 계속 잠근다. ETF lane의 최종 검증은 기존 D7을 재사용하지 않고 새 기간·새 이름·새 prereg로 관리한다.

## 10. 사전등록할 최소 실험 행렬

| 축 | 값 |
|---|---|
| Universe | point-in-time 국내 주식형 ETF, 현재 64개를 소급 적용하지 않음 |
| Horizon | 5일·10일·20일 중 supervised floor로 하나만 선택 |
| Cost | 23bp primary, 9bp ETF diagnostic |
| Split | chronological expanding 5-fold |
| Seeds | 0, 1, 2 |
| Control | shuffled reward, no-trade, equal-weight, simple momentum |
| Reward arms | net return only, risk minimal, full shaped |
| Network | Residual MLP first; Mamba는 후속 |
| State | raw/as-of market features + 6 portfolio state |
| Action | continuous target ratio; mixed cash gate는 ablation |
| Gate | native>0, native−shuffle≥0.10, positive fold≥4/5, positive seed≥2/3, DD≤0.25 |
| Stop | signal floor 또는 synthetic gate 하나라도 실패하면 Q3 금지 |

## 11. 전체 대시보드 페이지 업데이트

| 페이지 | 추가할 표시 | 검토할 위험 | 예상 |
|---|---|---|---:|
| Home | `ETF STATEFUL MDP · CANDIDATE · NOT RUN` | 기존 D6R2 결과와 혼동 금지 | 30분 |
| Program Scorecard | 기존 모델 18, ETF lane readiness 44 분리 | 44를 성능으로 오해하지 않기 | 30~60분 |
| Discovery Lab | Q0~Q7 신규 사다리 | 기존 D7 잠금 유지 | 1~2시간 |
| Data | point-in-time universe, as-of timestamp, 9/23bp | bfill·scaler·survivorship | 4~8시간 |
| Experiment | state/action/reward/network ablation | 사후 best-of-many | 2~4시간 |
| Training | PPO entropy·policy std·action histogram·trade rate | reward hacking·policy collapse | 4~8시간 |
| Evaluation | 5fold×3seed·shuffle·MDD·Sharpe·Calmar | 9bp만 통과하는 비용 민감성 | 4~8시간 |
| Compare | D6R2 stock lane과 ETF lane을 별도 섹션으로 비교 | 서로 다른 universe cross-rank 금지 | 2~4시간 |
| Report | source, feature schema SHA, architecture manifest | 외부 콘텐츠를 성과 증거로 오인 금지 | 1~2시간 |
| Insights | 금리·VIX·수급·섹터 regime | 사후 설명을 예측 신호로 착각 | 2~4시간 |
| Other Lanes | Quantylab은 external design reference로 표시 | 제3자 결과를 Kronos 성과에 합산 금지 | 30~60분 |
| Settings | API token 로컬 보관, raw cache·cutoff 설정 | 키·유료 데이터 노출 금지 | 1~2시간 |

## 12. 최종 의사결정

| 질문 | 업데이트된 답 |
|---|---|
| 기존 18점 DQN을 계속 튜닝할 것인가 | 아니다. 기존 top-5 lane은 계속 STOP이다. |
| Quantylab 설계를 그대로 복사할 것인가 | 아니다. 데이터·보상·비용·검증 위험을 먼저 제거한다. |
| 강화학습 연구를 계속할 의미가 생겼는가 | 있다. ETF swing stateful MDP라는 충분히 다른 가설이 생겼다. |
| 바로 PPO 500 episode를 돌릴 것인가 | 아니다. Q1·Q2-A·Q2-B 통과 전 금지한다. |
| Mamba부터 사용할 것인가 | 아니다. Residual MLP baseline 이후에만 비교한다. |
| 기존 D7을 열 것인가 | 아니다. 계속 LOCKED다. |
| 언제 실제 모델을 테스트할 수 있는가 | 데이터 audit·signal floor·synthetic MDP 통과 후 Q3에서 가능하다. 빠르면 3~5 작업일 이후다. |
| 성공 모델을 보장할 수 있는가 | 없다. 다만 기존 lane 반복보다 정보가치가 훨씬 높은 연구다. |

## 13. 즉시 해야 할 순서

1. 이 문서와 기존 계속 진행 판단 문서를 리뷰·병합한다.
2. `ETF stateful MDP`를 기존 Type2 D7과 분리된 신규 prereg lane으로 등록한다.
3. point-in-time ETF universe와 raw/as-of feature source를 먼저 확정한다.
4. 23bp primary supervised signal floor와 synthetic environment를 병렬로 실행한다.
5. 두 gate가 통과할 때만 Residual MLP PPO pilot을 실제로 학습한다.
6. 성과가 있어도 새로운 sealed ETF OOS 전에는 모델 점수를 올리지 않는다.

## 14. 관련 Kronos 문서

- [`kronos_rl_continuation_decision_review_2026-07-31.md`](kronos_rl_continuation_decision_review_2026-07-31.md)
- [`kronos_rl_dashboard_direct_review_guide_2026-08-01.md`](kronos_rl_dashboard_direct_review_guide_2026-08-01.md)
- [`kronos_rl_discovery_type2_d6r2_result_2026-07-31.md`](kronos_rl_discovery_type2_d6r2_result_2026-07-31.md)
- [`kronos_rl_discovery_type2_d6r2_program_report_2026-07-31.md`](kronos_rl_discovery_type2_d6r2_program_report_2026-07-31.md)

이 검토로 바뀐 것은 기존 모델의 성과가 아니라 다음 가설의 구체성이다. 현재 18점 모델은 그대로 실패지만, ETF 스윙·연속 포지션·action-dependent transition을 사용하면 지금까지와 다른 강화학습 문제를 과학적으로 검증할 수 있다.

## 15. Kronos Q0~Q2 실제 실행 업데이트

외부 설계 검토 이후 Q0 사전등록, Q1 데이터 감사, Q2-A 20일 momentum canary, Q2-B stateful 환경을 실제로 구현·실행했다. 결과는 Q1 `BLOCKED_DATA_CUSTODY`, Q2-A `NO_GO_SIGNAL_FLOOR`, Q2-B `PASS_SYNTHETIC_STATEFUL_MDP`, Q3 `LOCKED_NOT_RUN`이다.

상세 수치·테스트·브랜치 계보·12페이지 반영은 [`kronos_etf_stateful_mdp_q0_q2_result_2026-08-01.md`](kronos_etf_stateful_mdp_q0_q2_result_2026-08-01.md)에 기록했다. 이 실행으로 ETF 설계가 검증된 수익 모델로 승격된 것은 아니다.
