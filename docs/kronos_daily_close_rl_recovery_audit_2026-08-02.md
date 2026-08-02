# Kronos 종가매매 강화학습 실패·증거·UX 복구 감사

- 문서 ID: `KRONOS-DAILY-CLOSE-RL-RECOVERY-AUDIT-2026-08-02`
- 작성일: 2026-08-02 KST
- 부모 연구 브랜치: `codex/rl-etf-stateful-mdp-v1`
- 복구 브랜치: `codex/rl-close-recovery-v1`
- 기준 부모 merge: `690adba`
- 기존 ETF Q0~Q2 PR: [#29](https://github.com/Py-CI-Park/Kronos/pull/29) — `MERGED`
- 범위: 일봉 종가매매 RL, Type1 MaskablePPO, Kronos 예측 모델, V6 대시보드, 인사이트, Git 계보
- 실거래·수익성·broker 준비: **주장하지 않음**

## 1. 결론

Kronos 저장소에는 실제 강화학습 모델이 없다기보다, **모델 파일 생성 성공과 비용 차감 성능 성공이 분리되어 있고, 생성된 모델의 증거가 Windows 줄바꿈 검증 문제로 V6 실행 목록에서 제외**되어 있었다.

| 질문 | 확인 결과 | 판정 |
|---|---|---|
| 실제 강화학습 모델을 만들었는가 | Type1 MaskablePPO primary 5개와 shuffled-reward control 5개, 총 10개 `final_model.zip` 존재 | **모델 생성 성공** |
| 실제 시장 성능에 성공했는가 | publication receipt verdict `NO_GO`, fresh OOS `NOT_RUN` | **성능 성공 아님** |
| Kronos 모델이 삭제됐는가 | `/api/model-status`: `available=true`, `loaded=false` | **삭제 아님·지연 로드 상태** |
| RL 탭의 `MISSING`은 모델 부재인가 | 다음 `DRAFT_NOT_FROZEN` 사전등록이 0건이고, Type1 catalog가 검증에서 차단됨 | **서로 다른 두 원인이 섞임** |
| 인사이트 데이터가 한 종목뿐인가 | 수급 API가 4개 순위표에 각각 20종목 반환 | **데이터 문제가 아니라 탐색 UX 문제** |
| 글자 넘침이 실제인가 | 1024px에서 D6R2 상태표와 step 상태칩 overflow 재현 | **실제 UI 결함** |

따라서 다음 목표는 `GO`를 꾸며내는 것이 아니라 다음 세 성공을 별도로 표시하는 것이다.

1. **빌드 성공**: 학습 가능한 환경과 실제 policy artifact가 생성됐는가.
2. **연구 성공**: 비용·대조군·fold·seed gate를 통과했는가.
3. **운영 성공**: fresh OOS, paper-forward, broker 안전성이 입증됐는가.

현재는 1번만 충족하고 2번과 3번은 충족하지 못했다.

## 2. 실제 모델 증거

### 2.1 Type1 Sequential MaskablePPO

| 항목 | 값 |
|---|---|
| dataset | `type1-close-20260803-005` |
| train run | `train_type1-public-005` |
| algorithm family | `MASKABLE_PPO` |
| primary seeds | 0, 1, 2, 3, 4 |
| shuffled-reward seeds | 0, 1, 2, 3, 4 |
| seed당 timesteps | 200,000 |
| primary model 파일 | 5개 |
| negative-control model 파일 | 5개 |
| 총 model artifact | 10개 |
| execution | exact 15:20 close proxy |
| accounting | 60M fixed notional, 5M/slot, 최대 10 slots |
| primary cost | 왕복 23bp |
| training state | `COMPLETE` |
| reused validation | `COMPLETE` |
| verdict | **`NO_GO`** |
| fresh OOS | **`NOT_RUN / NO_READ`** |

대표 증거:

- `webui/rl_runs/v6_daily_h1/type1-close-20260803-005/train_type1-public-005/publication_receipt.json`
- `webui/rl_runs/v6_daily_h1/type1-close-20260803-005/train_type1-public-005/primary/seed_*/final_model.zip`
- `webui/rl_runs/v6_daily_h1/type1-close-20260803-005/train_type1-public-005/shuffled_reward/seed_*/final_model.zip`
- `webui/rl_runs/v6_daily_h1/type1-close-20260803-005/train_type1-public-005/type1_reports/`

이 artifact는 “강화학습 코드를 작성했다” 수준이 아니라 SB3 MaskablePPO가 실제로 학습되고 저장된 증거다. 그러나 `NO_GO`이므로 거래 가능한 모델 성공으로 표현하면 안 된다.

### 2.2 이전 일봉 종가매매 연구

| 연구 | 실제 실행 | 결과 | 핵심 실패 |
|---|---|---|---|
| V6 tabular Q | 500종목, 3 seeds | `INCONCLUSIVE` | 1/3 seed만 양수, seed 분산 지배 |
| V7 PPO MLP | SB3 PPO | `NO_GO` | 비용 후 no-trade를 안정적으로 넘지 못함 |
| V8 M3E | LinUCB 5-member | `NO_GO` | 23bp NAV 52.88M, MDD 53.57%, control 실패 |
| Type1 MaskablePPO | primary 5 + shuffled 5, 각 200k | `NO_GO` | reused validation에서 승격 불가, fresh OOS 미개방 |
| D6R2 DQN/ridge | 70/70 evaluations | `NO_GO` | 13 gate 중 2개 통과, 신호 floor 실패 |
| ETF Q2-A momentum | 5 folds, shuffle 3 seeds | `NO_GO` | 23bp -9.23bp, 1/5 fold, MDD 94.79% |
| ETF Q2-B synthetic MDP | 3 seeds | `PASS` | 환경 learnability만 통과, 시장 alpha 아님 |

## 3. 왜 많은 커밋을 했는데도 성능은 실패하는가

커밋 수는 코드·테스트·문서·안전장치의 양이고 시장 신호의 표본 수나 예측력을 증가시키지 않는다.

| 원인 | 관측 증거 | 의미 |
|---|---|---|
| 비용보다 작은 edge | ETF 9bp에서는 +4.77bp지만 23bp에서 -9.23bp | 약한 신호가 거래비용에 소멸 |
| shuffle을 못 이김 | ETF native−shuffle -2.334bp, 여러 연구에서 control 초과 | 모델이 시장 구조보다 잡음·상승 편향을 학습 |
| 시간 안정성 부족 | ETF 1/5 fold만 양수, V6 1/3 seed만 양수 | 특정 국면 또는 초기화에 민감 |
| 과도한 거래 | D6R2 median trade rate 0.90 | 작은 예측 오차가 반복 비용으로 확대 |
| 큰 drawdown | ETF 94.79%, M3E 53.57% | 평균 수익 이전에 경로 위험이 허용 불가 |
| 약한 baseline | V6 rule_topk_ret5 -37.6% | RL이 약한 RULE보다 낫다는 사실은 절대 성과가 아님 |
| point-in-time custody 부족 | ETF Q1의 PIT universe·identity·available_at·total return 실패 | 미래 정보·상품 생존편향을 배제할 증거 부족 |
| 전략 정의 불일치 | 현재 실행은 공식 종가가 아니라 15:20 proxy | 사용자가 말한 종가매매와 체결 계약이 정확히 같지 않음 |
| 동일 검증구간 반복 | reused validation을 여러 세대가 관측 | 반복할수록 숨은 사후 과적합 위험 증가 |
| 모델 복잡도 우선 | feature floor보다 PPO/DQN/LinUCB 반복 | 정보가 없으면 알고리즘 변경으로 alpha가 생기지 않음 |

### 3.1 가장 큰 병목

현재 병목은 “PPO 구현 여부”가 아니다. 실제 PPO 모델 10개가 존재한다. 병목은 다음 순서다.

```text
시점별 정확한 데이터
→ 비용 후 supervised signal floor
→ stateful portfolio 환경
→ RL이 단순 scorer/RULE보다 주는 추가 가치
→ fresh OOS
→ paper-forward
```

두 번째 단계가 실패하면 네 번째 단계의 모델 크기와 학습시간을 늘려도 성공 확률이 높아지지 않는다.

## 4. 종가매매 전략 정의가 아직 완전히 일치하지 않는 이유

사용자가 원하는 전략은 “일정 금액을 여러 종목에 배분하여 종가에 매수·매도하는 일봉 전략”이다. 현재 구현은 상당 부분을 갖췄지만 다음 차이가 있다.

| 원하는 의미 | 현재 구현 | 차이·위험 |
|---|---|---|
| 공식 종가 체결 | 15:20 5분봉 close proxy | 종가 동시호가·체결 잔량·슬리피지 미반영 |
| 일정 총자금 | 60M 명목 회계 | 실제 self-financing broker NAV가 아님 |
| 종목당 일정 금액 | 5M/slot | 호가 단위·정수 주식수·미체결 처리 부족 |
| 최대 일정 종목 | 최대 10개 distinct | 10개 보장 아님, 0개 선택 가능 |
| 매일 보유상태 연결 | Type1은 sequential state/mask 제공 | 기존 V6/V7 일부 연구는 contextual 선택 성격이 강함 |
| 거래비용 | 왕복 23bp 고정 | 종목·시점별 시장충격과 유동성 차이 미반영 |
| 종목 유니버스 | 고정/후대 기준 manifest가 섞인 이력 | 거래일별 PIT membership 필요 |
| 배당·분배금 | total-return custody 미완료 | ETF 장기 성과 왜곡 가능 |

따라서 “종가매매 RL 구현 성공”의 최소 정의는 다음과 같아야 한다.

1. 전일 또는 의사결정 시각 이전 데이터만 observation에 포함한다.
2. 행동은 현금·기존 보유종목·교체비용을 다음 state로 변화시킨다.
3. 매수하지 않는 행동과 0~10개 선택을 허용한다.
4. 종목당 5M, 최대 50M exposure, 10M reserve를 강제한다.
5. 공식 종가가 아니면 화면과 문서에서 `15:20 proxy`라고 표시한다.
6. 23bp 비용 후 no-trade·RULE·supervised scorer·shuffle을 함께 이긴다.
7. 최소 5-fold와 다중 seed에서 안정성을 보인다.

## 5. `MISSING`과 Kronos 누락의 실제 원인

### 5.1 다음 사전등록 카드

`/api/v6/research-registry`에는 5개 preregistration이 있지만 모두 `FROZEN`이다. `DRAFT_NOT_FROZEN` 항목은 0개다. 프런트엔드의 `newestDraftPreregistration()`이 `null`을 반환하는 것은 맞지만, 실험 페이지가 ID·family·state·run_count를 각각 `MISSING`으로 출력한다.

개선 기준:

- `MISSING` 4개 대신 `새 사전등록 초안 없음` 한 문장으로 표시한다.
- 서버 오류와 정상적인 “없음” 상태를 분리한다.
- 다음 행동을 `새 가설 amendment 작성`으로 표시한다.
- 기존 동결 prereg 수와 최신 동결 ID를 함께 보여준다.

### 5.2 Type1 실행 목록 누락

현재 실제 호출 결과:

```text
GET /api/v6/run-detail?dataset=type1-close-20260803-005&train=train_type1-public-005
status = BLOCKED
reason = TYPE1_CATALOG_INVALID
```

직접 verifier의 실제 예외:

```text
Type1ReportError:
publication receipt does not prove the recovered v5 publication move
```

SHA 비교:

| 대상 | SHA-256 |
|---|---|
| publication receipt의 publisher source | `2bace1c8...` |
| Git commit `4760a0e`의 LF source | `2bace1c8...` |
| 현재 Windows CRLF worktree source | `c405c14d...` |

Git 내용은 같은 커밋의 같은 소스인데 줄바꿈 표현만 달라 raw byte SHA가 달라졌다. verifier가 현재 worktree raw bytes만 허용해 artifact를 무효로 만들고, `_runs_payload()`가 그 차단 사유를 노출하지 않은 채 Type1 row를 제외한다.

개선 기준:

1. publisher Python source에 한해 LF/CRLF 정규화 동등성을 검증한다.
2. 실제 내용이 한 글자라도 바뀌면 계속 차단한다.
3. Type1 projection 실패를 런 목록에서 조용히 제거하지 않고 blocked evidence로 표시한다.
4. Windows 실제 artifact에 대한 회귀 테스트를 추가한다.

### 5.3 Kronos 예측 모델 누락

`/api/model-status`는 다음을 반환한다.

```json
{
  "available": true,
  "loaded": false,
  "message": "Kronos 모델은 사용 가능하지만 아직 로드되지 않았습니다"
}
```

Kronos는 RL policy가 아니라 금융 시계열 예측 모델이다. V6에서는 `KronosPage`가 존재하지만 `다른 레인` 카드 안으로 숨겨져 있다. 이 때문에 사용자는 강화학습 모델과 Kronos foundation model을 구분하기 어렵고, Kronos가 제거됐다고 느끼게 된다.

개선 기준:

- V6 탐색에 `Kronos 모델`을 독립 항목으로 복원한다.
- `사용 가능 / 아직 미로드 / 로드됨 / 사용 불가`를 명시한다.
- `Kronos 예측 모델 ≠ 강화학습 policy` 경계를 같은 화면에서 설명한다.
- 자동 로드는 메모리 비용 때문에 하지 않고 사용자가 예측 워크벤치에서 명시적으로 실행한다.

## 6. 인사이트가 한 종목처럼 보이는 이유

종목 심층 화면은 다음 초기값을 고정한다.

```text
code = 005930
```

직접 6자리 코드를 입력하면 다른 종목 조회가 가능하지만, 화면에 유니버스·최근 관측 종목·수급 상위 종목 연결이 없다. 반면 `/api/v6/insight/flow?window=20&limit=20`은 다음 네 목록을 각각 20개씩 반환한다.

- 기관 순매수 상위
- 기관 순매도 상위
- 외국인 비율 증가 상위
- 외국인 비율 감소 상위

개선 기준:

- 수급 API에서 중복 제거한 8개 내외 종목을 quick pick으로 제공한다.
- 선택하면 종목 코드 입력과 차트를 같은 화면에서 갱신한다.
- 순위는 추천이 아니라 탐색 진입점임을 명시한다.
- 선행 0 종목코드를 문자열로 유지한다.

## 7. UX/UI 감사

디자인 방향은 “산업용 연구 계기판”을 유지하되, 상태 토큰보다 질문과 다음 행동을 먼저 읽게 하는 것이다.

### 7.1 확인된 문제

| 문제 | 실제 관측 | 사용자 영향 |
|---|---|---|
| 7열 고정 stepper | 1024px에서 상태칩 overflow | 단계 이름과 판정이 잘림 |
| D6R2 상태표 압축 | `D7 / Promotion`, `NOT_RUN_NO_READ` overflow | 핵심 잠금 상태를 읽기 어려움 |
| 영어 raw token 과다 | `MISSING`, `HAS_RUNS`, `TEST_NOT_RUN` | 의미를 학습해야 화면을 이해할 수 있음 |
| 연구 세대 혼합 | ETF Q0~Q2, D6R2, Type1이 한 화면 상단에 혼재 | 현재 실행 대상이 무엇인지 불명확 |
| Kronos 숨김 | Other Lanes 내부 링크 | 모델이 삭제된 것으로 오해 |
| 종목 탐색 부재 | 기본 005930 하나 | 데이터가 한 종목뿐인 것으로 오해 |
| 성공 정의 혼합 | 학습 완료와 GO 여부가 같은 녹색 계열 | 파일 생성 성공을 수익 성공으로 오해 |

### 7.2 수정 원칙

| 우선순위 | 원칙 | 적용 |
|---:|---|---|
| 1 | 상태를 한국어 의미와 raw token으로 함께 표시 | `학습 완료 · COMPLETE`, `성능 탈락 · NO_GO` |
| 2 | 없음·오류·차단을 분리 | `EMPTY`, `UNAVAILABLE`, `BLOCKED` 별도 표현 |
| 3 | 현재 연구 계보를 상단에 고정 | ETF / Type1 / D6R2를 lane으로 분리 |
| 4 | 다음 행동을 가장 가까이에 표시 | Q1 데이터, 새 Q2-A prereg, Q3 잠금 |
| 5 | 긴 token은 줄바꿈 허용 | chip `white-space: normal`, `overflow-wrap:anywhere` |
| 6 | 1024px 이하 stepper 재배치 | 4열 또는 3열로 전환 |
| 7 | 모델 존재와 성능 판정을 분리 | artifact count와 verdict를 별도 카드로 표시 |

## 8. 복구 개발 순서

| 순서 | 작업 | 목적 | 완료 조건 |
|---:|---|---|---|
| R1 | CRLF/LF Type1 source 검증 회귀 테스트 | Windows에서 실제 model catalog 복구 | 실제 Type1 detail `OK` |
| R2 | Type1 blocked projection 가시화 | 검증 실패가 `NOT_RUN`으로 숨지 않게 함 | 목록에 `BLOCKED + reason` 표시 |
| R3 | 다음 prereg empty-state UX | 정상적인 초안 부재와 API 오류 분리 | `MISSING` 4개 제거 |
| R4 | Kronos 독립 탐색·model status | Kronos 삭제 오해 제거 | V6에서 직접 접근·상태 표시 |
| R5 | 인사이트 multi-symbol quick pick | 한 종목 고정 오해 제거 | 2개 이상 종목 전환 브라우저 QA |
| R6 | stepper·상태표 overflow 수정 | 1024/768/390 가독성 | overflow offender 0 |
| R7 | 전체 회귀·빌드·브라우저 QA | 변경 안전성 확인 | Python/TS/Svelte/build/console 통과 |
| R8 | 연구 재판정 문서 | 모델 존재·NO_GO·다음 gate 분리 | 한국어 결과표와 Git SHA 기록 |

## 9. 다음 강화학습 연구의 성공 조건

### 9.1 즉시 허용

- Type1 기존 모델의 artifact·catalog 복구와 읽기 전용 비교
- Q1 point-in-time 데이터 custody 구축
- 기존 결과의 turnover/cost/regime 설명적 분석
- 새 feature/horizon 가설의 사전등록
- synthetic learnability와 negative-control 회귀

### 9.2 선행 gate 없이 금지

- 같은 validation에서 feature·threshold·seed를 보고 다시 선택
- 23bp를 실패한 정책을 9bp 결과만으로 승격
- 단일 seed 또는 마지막 fold만 선택
- 기존 sealed OOS 반복 열람
- Kronos forecast를 RL policy 성과로 합산
- model zip 존재를 수익성 성공으로 표현

### 9.3 Q3 실시장 PPO 진입 조건

| Gate | 최소 조건 |
|---|---|
| Q1 data | PIT universe, official identity, available_at, total return 전부 PASS |
| Q2-A primary | 23bp 평균 > 0 |
| shuffle delta | native−shuffle ≥ 10bp |
| fold stability | 4/5 이상 양수 |
| seed stability | 2/3 이상 control 우위 |
| drawdown | ≤ 25% |
| environment | action-dependent state와 23bp 회계 PASS |

이 조건을 통과한 뒤에만 Residual MLP PPO를 먼저 실행한다. LSTM/Mamba는 MLP보다 같은 split·cost·seed에서 반복 가능한 우위를 보일 때만 추가한다.

## 10. Git 운영 규칙

| 단계 | 한국어 커밋 예시 |
|---|---|
| 감사 문서 | `docs(rl): 종가매매 강화학습 실패와 복구 기준을 기록하다` |
| red test | `test(type1): Windows 줄바꿈으로 모델 증거가 사라지는 문제를 재현하다` |
| verifier fix | `fix(type1): LF와 CRLF 소스의 의미 동등성을 검증하다` |
| UX | `feat(dashboard): 모델 존재와 연구 판정을 분리해 표시하다` |
| insight | `feat(insight): 여러 종목으로 이동하는 탐색 진입점을 추가하다` |
| build | `build(dashboard): 종가매매 복구 화면 번들을 갱신하다` |
| result | `docs(rl): 종가매매 복구 실행 결과를 기록하다` |

브랜치는 페이지별로 과도하게 나누지 않고 하나의 증거 단위로 관리한다.

```text
master
└─ codex/rl-etf-stateful-mdp-v1
   └─ codex/rl-close-recovery-v1
      ├─ 문서
      ├─ red test
      ├─ Type1 catalog fix
      ├─ V6 UX 복구
      └─ 검증·결과·bundle
```

## 11. 현재 판정

| 축 | 현재 상태 |
|---|---|
| 실제 RL 학습 실행 | **성공** |
| RL model artifact 생성 | **성공 — 10개 확인** |
| 대시보드 model evidence 표시 | **실패 — Type1 catalog invalid** |
| 비용 차감 연구 성능 | **NO_GO** |
| 공식 종가 체결 모델 | **미완료 — 15:20 proxy만 존재** |
| fresh OOS | **NOT_RUN / NO_READ** |
| paper/live/broker | **BLOCKED** |

이번 복구의 성공 기준은 먼저 “실제로 존재하는 강화학습 모델을 대시보드가 정확히 보여주고, 모델 생성 성공과 성능 실패를 동시에 이해할 수 있게 만드는 것”이다. 그다음 데이터와 supervised floor를 통과하는 새 가설을 통해 실시장 RL 성공 가능성을 높인다.
