# 강화학습 우상향 모델 실패 원인 분석 및 개선 로드맵 — 2026-06-11

## 목적

이 문서는 "수익을 내는, 우상향하는 강화학습 모델"이 이 저장소에서 아직 만들어지지
못한 이유를 코드·데이터·실험 설계·시장 구조 차원에서 전면 검토하고, 사용자가
원하는 목표(꾸준히 우상향하는 수익 곡선)를 이 프로젝트 기반으로 달성하기 위한
현실적 개선 경로를 제시하는 분석 문서다.

이 문서는 연구 분석 문서다. 수익 보장, 실거래 준비, 브로커 연동 준비를 주장하지
않는다. 기본 비용 가정은 왕복 23bp다. 기존 `NO-GO` 판정을 번복하지 않는다.

## 1. 사용자가 원하는 것의 정의

- 목표: 누적 수익 곡선이 꾸준히 우상향하는 모델 (NEAT 유튜브 곡선류).
- 제약(스스로 세운 약속): "억지로 RL에 끼워 맞춰 거짓 우상향을 만들지 않는다"
  (`docs/stom_rl_resume_commit_2026-05-29.md`).
- 핵심 사실: **우상향 곡선 자체는 이미 존재한다.** 다만 RL이 아니라 RULE이다.

| 항목 | ts_imb RULE baseline (23bp, TP5/SL1/09:25) |
|---|---:|
| N | 235 trades |
| 기대값/trade | +0.952% (sl_gap_stress 최악 +0.811%) |
| 누적(비복리) | +223.6% |
| 승률 | 42% |
| MDD | -15.7% |
| breakeven 여유 | 5.1x |

즉 질문은 "곡선을 어떻게 만드나"가 아니라 **"왜 RL로는 안 되고, RL이 무엇을
추가로 기여할 수 있나"**다.

## 2. 현재까지의 RL 판정 원장 (변경 없음)

| 트랙 | 판정 | 출처 |
|---|---|---|
| 1초/1분/세션 cross-sectional RL 선택 알파 | 없음 (shuffle 검정 실패) | resume 2026-05-29 |
| Opening PPO 후보 | `NO-GO_USABLE_MODEL` | 2026-06-01 |
| Skip-gate (supervised) | `NO-GO` (full universe) | 2026-06-01 |
| State-exit gate (supervised) | `NO-GO` | 2026-06-02 |
| Opening 30m DQN/PPO OOS 후보 | `NO-GO_BASELINE` | 2026-06-04 |
| Feature revalidation smoke | `NO-GO_BASELINE` | 2026-06-04 |
| Rule/meta-label filter (bounded/wide/simplified) | `NO-GO_CONTROL` ×3 | 2026-06-04~05 |
| 종합 결정 | `STOP_RL_EXPANSION + SIMPLIFY_FEATURES + PROXY_AUDIT_REQUIRED` | 2026-06-05 |

## 3. 왜 안 되는가 — 원인 3계층 분석

### 3.1 계층 A: 실험 설계 결함 — "RL을 아직 진짜로 학습시킨 적이 없다"

이것이 가장 중요한 발견이다. 지금까지의 모든 `NO-GO` RL 판정은
**smoke 규모 실험**에서 나왔고, 그 규모로는 어떤 RL 알고리즘도 성공할 수 없다.

#### A-1. 학습량이 사실상 0이다 (결정적)

코드 레벨 증거:

| 위치 | 값 | 의미 |
|---|---|---|
| `stom_rl/opening_30m_rl_candidates.py:default_candidate_configs` | `total_timesteps=64` | DQN/PPO 후보의 전체 학습 스텝이 64 |
| `stom_rl/opening_30m_rl_candidate_training.py:_model_kwargs` | `n_steps = max(2, min(8, total_timesteps))` | PPO rollout 길이 2~8로 고정 |
| `stom_rl/opening_30m_rl_train.py` | `total_timesteps: int = 16` | 기본값 16 스텝 |
| `stom_rl/orderbook_sb3_smoke.py` | `total_timesteps: int = 512` | 가장 큰 smoke도 512 |

PPO/DQN이 의미 있는 정책을 학습하려면 통상 1e5~1e7 스텝이 필요하다. 64 스텝으로
학습된 MlpPolicy는 **무작위 초기화 네트워크와 사실상 구별 불가능**하다. 따라서
"DQN/PPO가 baseline을 못 이겼다"는 판정은 정확히 말하면
**"무작위에 가까운 정책이 baseline을 못 이겼다"**이며, 이는 RL 자체의 실패 증거가
아니라 falsification 하네스가 의도대로 동작했다는 증거일 뿐이다.

#### A-2. 데이터 사용량이 가용량의 0.1% 미만이다

- 보유 데이터: `_database/stock_tick_back.db` = **29.7GB, 2,427 종목 테이블**,
  2022~2026 시초 09:00~09:30 1초봉.
- 실제 RL 실험 사용량: `--max-tables 10 --max-sessions-per-table 2` →
  **18개 종목/세션, 39 프레임**. 룰필터 wide run도 frame count 39.
- OOS TAKE 수: 2~8건. 사전등록 최소치(3~10건)조차 못 채움.

trade당 기대값이 +0.95%이고 표준편차가 수 %인 분포에서 OOS 6 trades로는
**어떤 결론도 통계적으로 성립하지 않는다** (SE가 기대값의 수 배). 즉 현재의
OOS net return 부호(+3.58%였다가 -0.54%였다가)는 전부 표본 노이즈다.

#### A-3. 정책 퇴화(degenerate policy)와 attribution collapse

wide/simplified run에서 **8개 ablation 전부 full과 완전히 동일한 수익률**,
filter ≡ buy_and_hold ≡ ts_imb_rule 항등이 관측됐다. 해석은 하나다:
필터/정책이 feature를 전혀 사용하지 않고 **항상 같은 행동(전부 TAKE)**을 하고
있다. 64-step 학습 + 미세한 threshold + 행동마다 부과되는 비용 페널티 조합에서
나오는 전형적 결과다. feature가 쓸모없다는 증거가 아니라,
**학습이 feature를 쓸 수 있는 단계까지 도달한 적이 없다**는 증거다.

#### A-4. 보상 설계가 비용 노이즈에 지배된다

`stom_rl/orderbook_rl_env.py`의 보상은 per-step NAV 변화 −
invalid_action_penalty − overtrade_penalty 구조다. 23bp 왕복비용이 진입 시점에
즉시 unrealized return에 반영되므로, 에이전트가 받는 즉각 신호의 대부분은
"매수하면 즉시 −0.23% + 스프레드"다. 신호(+0.95%/trade, 발생 빈도 낮음)는 sparse
하고 지연돼 있다. 이 신호/잡음 구조에서 짧은 학습은 필연적으로
"아무것도 안 하기" 또는 "전부 하기"로 수렴한다 — 실제 관측과 일치한다.

#### A-5. 행동 공간이 이미 문제를 다 풀어놓고 시작한다

opening candidate의 행동 계약은 `Discrete(2)` = hold/exit
(fixed_entry_exit_only). 즉 RL이 풀 문제는 "진입은 룰이 했고, 언제 나갈까"뿐이다.
이는 올바른 축소지만, 그렇다면 이 문제는 episodic RL보다
**supervised exit-labeling / contextual bandit**이 표본 효율이 수십 배 좋다.
RL의 강점(다단계 credit assignment)이 필요 없는 문제에 RL의 약점(표본 비효율)만
지불하고 있다.

### 3.2 계층 B: 시장/데이터 구조의 제약 — 진짜 어려운 부분

학습량을 늘려도 다음 제약은 남는다. 이것이 "RL이 원래 어려운 이유"다.

1. **비용 장벽**: 23bp 왕복 + 스프레드. 시초 30분 단타에서 trade당 기대 엣지가
   수십 bp 수준인데, 회전이 잦은 RL 정책은 비용에 먹힌다. 이미 1s/1m/세션
   horizon에서 "결정론 RL 대역이 turnover 비용에 먹힘"이 확인됐다.
2. **데이터 희소성·편향**: DB는 이벤트 트리거 희소 기록 1초봉이다. 연속 시계열이
   아니고, 기록 자체가 "움직인 종목" 쪽으로 선택 편향돼 있다.
3. **L2 큐 데이터 부재**: 큐 포지션/부분체결 replay가 불가능하므로 고빈도
   시장가-수동호가 전략군 전체가 검증 불가. marketable-fill(매수@ask, 매도@bid)
   상한 가정만 가능하다.
4. **비정상성(non-stationarity)**: 2022 약세(N=39, CI가 0 포함)처럼 레짐 변동이
   있고, RL은 분포 변화에 취약하다.
5. **신호 자체가 약하다**: skip-gate/state-exit 같은 supervised gate조차 full
   universe에서 `NO-GO`였다. 룰(ts_imb)을 넘어서는 잔여 알파가 현재 feature
   표현으로는 잡히지 않았다는 뜻이다. RL은 supervised보다 더 많은 신호를
   요구하므로, supervised가 못 잡는 신호를 RL이 잡을 가능성은 낮다.

### 3.3 계층 C: 문제 정의의 불일치

"우상향 곡선"은 정책 학습 문제가 아니라 **포트폴리오/운영 설계 문제**다.
ts_imb 곡선이 이미 우상향인 이유는 entry 엣지(+0.95%) × 충분한 N(235) ×
낮은 상관의 합산이지, 어떤 모델의 영리함이 아니다. end-to-end RL에게
"곡선을 만들어라"고 요구하는 것은 entry 발굴 + 비용 극복 + risk 관리 세 문제를
한 번에 풀라는 것이고, 이는 현 데이터·비용 조건에서 가장 성공 확률이 낮은
문제 분해다.

## 4. 결론: 왜 안 됐는가 (한 문단 요약)

지금까지 RL이 실패한 직접 원인은 시장이 아니라 **실험 규모다**: 64-스텝 학습,
18세션 표본, OOS 2~8 trades 위에서 무작위 수준 정책을 평가했고, 당연히 모든
gate에서 `NO-GO`가 나왔다. 동시에, 비용 23bp·희소 1초 데이터·L2 부재·약한 잔여
신호라는 구조적 제약 때문에 **"규모만 키우면 end-to-end RL이 성공한다"는 보장도
전혀 없다**. supervised gate들의 full-universe `NO-GO`는 오히려 잔여 알파가
얇다는 경고다. 따라서 올바른 경로는 RL을 "곡선 생성기"가 아니라 **검증된 RULE
위의 운영 최적화 계층(사이징/스킵/청산)**으로 재배치하고, 그 전에 학습·평가
인프라를 실험이 의미를 갖는 규모로 끌어올리는 것이다.

## 5. 개선 로드맵

### Phase 0 — 목표 재정의 (즉시)

- "RL로 우상향 곡선 만들기" → **"ts_imb RULE 곡선을 운영 가능하게 만들고,
  학습 모델은 그 위의 증분(사이징·스킵·청산)으로만 평가"**로 목표를 바꾼다.
- 우상향 곡선의 1차 소유자는 RULE이다. 이미 있고, 스트레스 후에도
  +0.811%/trade다. 다음 페이지(사이징/리스크 설계)가 2026-05-29부터 미뤄져 있다.

### Phase 1 — 학습/평가 인프라를 실험이 유효한 규모로 (1~2주)

| # | 항목 | 현재 | 목표 |
|---|---|---|---|
| 1 | total_timesteps | 16~512 | **2e5~1e6** (별도 `--full-train` 경로 신설, smoke 경로는 유지) |
| 2 | 학습 데이터 | 10테이블×2~5세션 | **전 universe 2,427 테이블** 에피소드 샘플러 + 캐시 |
| 3 | OOS 최소 trade 수 | 3~10 | **≥100 TAKE**, 미달 시 자동 `INCONCLUSIVE` |
| 4 | 분할 | 단일 frozen split | **walk-forward ≥5 folds** (연도 경계 기준) |
| 5 | 환경 | 단일 env 순차 | SB3 `VecEnv` 병렬화 (Threadripper 64코어 활용) |
| 6 | 정책 진단 | 없음 | 행동 분포·entropy 로그 필수. 행동 분포가 단일 행동 ≥95%면 `DEGENERATE` 플래그 |

핵심: **degenerate-policy 검출을 gate에 추가**한다. ablation 8개가 전부 동일
수익이면 지금처럼 `failed_ablations`가 아니라 `DEGENERATE_POLICY`로 분류해
"feature 실패"와 "학습 실패"를 구분한다.

### Phase 2 — 문제 재구성: RL을 이길 수 있는 자리에 배치 (2~4주)

성공 확률 순서대로:

1. **사이징 오버레이 (RULE + 모델)** — 가장 유망.
   진입/청산은 ts_imb 룰 고정. 모델은 trade당 배팅 크기(0/0.5/1.0x)만 결정.
   비용 구조를 바꾸지 않으므로(트레이드 수 동일) 비용 장벽이 없고, 실패해도
   baseline(균등 사이징)으로 후퇴 가능. 평가: 동일 trade 집합에서
   Sharpe/MDD 개선 여부. contextual bandit으로 시작(per-trade 독립이라 RL 불필요).
2. **오프라인 학습 (logged data)** — 235개 ts_imb trade + 전 universe 갭상승
   후보 1,349개를 로그 데이터셋으로 보고 meta-label(승/패/사이즈)을
   supervised로 학습. 이미 시도된 skip-gate `NO-GO`와의 차이: full-universe
   표본 + 새 feature 표현 + walk-forward를 전제로 사전등록 후 1회만 실행.
3. **청산 타이밍** — fixed-entry 후 exit 정책. 단 state-exit gate `NO-GO`
   전례가 있으므로, 새 가설(예: 체결강도 붕괴 속도, 호가 잔량 소진율) 없이는
   재실행 금지 (stom_rl/AGENTS.md 규칙 준수).
4. **end-to-end tick RL** — 위 1~3이 baseline을 이긴 뒤에만. Phase 1 인프라로
   1e6 스텝 학습 + action masking + 보상을 per-trade net return 합으로 정렬.
   현재 증거로는 성공 확률 최하위.

### Phase 3 — 평가 규율 (유지·강화)

기존 가드레일은 전부 유지한다: 사전등록 → 실행 → 해석 순서, OOS 무튜닝,
no-trade/buy-and-hold/ts_imb 3중 baseline, shuffle/randomized controls,
ablation, 23bp, MDD gate, `NO-GO` 가시화. 추가:

- baseline 항등 검출(이미 구현됨)을 gate 차단 사유에서 **분류 사유**로 승격:
  `NO-GO_CONTROL`(신호 없음)과 `DEGENERATE_POLICY`(학습 안 됨)를 구분.
- 연도별 분해 리포트 의무화 (2022형 레짐 리스크 가시화).

### Phase 4 — 운영 설계 (RULE 트랙, 모델과 무관하게 진행)

2026-05-29 문서가 지정한 미완 과제를 그대로 실행한다: 포지션 사이징(고정 분수
vs 변동성 타게팅), 동시보유 한도, 일손실 한도, 전략 중단 조건, full-universe
재검증, read-only forward/paper 검증. **"우상향 곡선을 실제로 보는" 가장 빠른
경로는 이 트랙이다.**

## 6. 달성 가능성에 대한 정직한 평가

| 목표 | 달성 가능성 | 근거 |
|---|---|---|
| 우상향 수익 곡선 (RULE 기반) | 높음 — 이미 백테스트로 존재 | +223.6% 누적, 스트레스 후 +0.811%/trade. 단 forward 검증 전이며 2022형 flat 연도 가능 |
| RULE + 모델 사이징 오버레이로 곡선 개선 | 중간 | 비용 중립적이라 구조적 장벽 없음. 신호가 얇으면 무개선으로 끝날 수 있음 |
| supervised meta-label로 trade 선별 개선 | 중간~낮음 | skip-gate `NO-GO` 전례. full-universe 표본·새 feature 필요 |
| end-to-end RL 단독 우상향 | 낮음 | 23bp 비용, 희소 데이터, L2 부재, supervised조차 못 잡는 잔여 신호 |
| "강화학습 모델이 만든 우상향"이라는 라벨 | 조건부 | 사이징/청산 RL이 gate를 통과하면 "RULE entry + RL overlay"로 정직하게 표기 가능. 곡선 전체를 RL이라 부르는 것은 계속 금지 |

## 7. 즉시 실행 순서 (권장)

1. `DEGENERATE_POLICY` 분류와 행동 분포 진단을 gate/대시보드에 추가.
2. full-universe 에피소드 샘플러 + `--full-train`(≥2e5 steps) 경로 신설.
   smoke 경로와 기본값은 변경하지 않는다.
3. 사이징 오버레이 실험 사전등록 (`*_prereg_*` 문서): 동일 235 trade 집합,
   contextual bandit, 균등 사이징 baseline, walk-forward 5 folds, 23bp.
4. 병행: RULE 트랙 사이징/리스크 설계 페이지 진행 (모델과 독립).
5. 위 결과가 나오기 전까지 PPO/DQN 확장은 `STOP_RL_EXPANSION` 결정대로 유지.

## 가드레일 재확인

- `ts_imb`는 RULE baseline이다. RL이라 부르지 않는다.
- 비용 가정은 왕복 23bp.
- 본 문서는 어떤 기존 `NO-GO`도 번복하지 않는다.
- 실거래/브로커/수익 보장 주장 없음. 대시보드는 read-only 증거 뷰어다.
- 종목코드 선행 0 보존, DB는 read-only 접근만.
