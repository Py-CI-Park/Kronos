# Kronos 일봉 종가매매 강화학습 G1~G6 전체 개발 결과

- 실행일: 2026-08-04 KST
- 개발 브랜치: `codex/rl-daily-close-dashboard-v1-27`
- 연구 기준: `v1.21.0` 계획 → `v1.27.0-dev` 구현
- 전체 판정: **`IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY`**
- 생성 모델 범위: **`SYNTHETIC_CALIBRATION_ONLY`**
- 실제 경제 모델 생성: **아니오**
- Fresh OOS: **`NOT_RUN_NO_READ`**

## 1. 한 문장 결론

강화학습을 실제로 실행하고 모델 파일을 생성할 수 있는 DQN/CQL 연구 플랫폼, 6천만원·10슬롯 포트폴리오 환경, 시간순 신호 검증, 비용 계약, 강건성 통계, 공통 대시보드까지 구현했다. 실제 20종목 일봉 진단은 유망했지만 시점별 종목군·수정주가·가용시각·원천 해시가 증명되지 않았으므로 **수익 모델 성공으로 판정하지 않는다**.

## 2. 이번에 실제로 만든 모델

| 항목 | 결과 |
|---|---|
| 알고리즘 | discrete DQN baseline + Conservative Q-Learning(CQL) |
| 학습 데이터 | 알려진 최적정책이 있는 action-dependent synthetic offline dataset |
| 상태 | 시장 신호, 이전 포지션 |
| 행동 | 현금 `0`, 투자 `1` |
| 보상 | 시장수익 - 포지션 변경비용 0.230% |
| seed | 0, 1, 2 |
| negative control | reward shuffle CQL, random policy |
| 모델 파일 | `.omx/artifacts/daily_close_rl_g1_g6_v2/models/synthetic_cql_seed_0.pt` |
| 저장·복원 | PyTorch state dict + 차원 계약 |
| 사용 가능 범위 | 환경·학습기 보정, 회귀 테스트, 연구 방법 검증 |
| 사용할 수 없는 범위 | 실제 주식 종목 선택, 경제성 주장, 주문, paper/live |

모델 파일이 존재한다는 사실과 실제 시장에서 수익을 내는 모델이라는 결론은 다르다. 현재 모델은 학습기와 환경이 알려진 문제를 푸는지 확인하는 **보정 모델**이다.

## 3. 목표 포트폴리오 환경

| 계약 | 구현값 | 검증 |
|---|---:|---|
| 초기 NAV | 60,000,000원 | 초기 상태 테스트 |
| 최대 주식 노출 | 50,000,000원 | 매 step invariant |
| 최소 현금 예비금 | 10,000,000원 | 매 step invariant |
| 최대 보유 | 10종목 | 11번째 ADD 거절 테스트 |
| 슬롯 목표 | 5,000,000원 | 수수료 포함 정수주 계산 |
| 주문 단위 | 정수주 | 10,000원 종목 499주 매수 |
| 행동 | HOLD_CASH, HOLD, ADD_ONE, EXIT_ONE, REPLACE_ONE, REDUCE_RISK | typed enum |
| 보상 | `log(NAV_t / NAV_t-1)` | 비용 차감 후 계산 |
| 종가 방식 | POST_CLOSE_NEXT_OPEN | 불가능한 당일 공식종가 체결 금지 |

## 4. 비용 재정의 결과

| 상품·시장 | 매수 | 매도 | 세금 | 왕복 명시비용 | 용도 |
|---|---:|---:|---:|---:|---|
| 국내 개별주식 KRX | 0.015% | 0.015% | 0.200% | **0.230%** | 주식 primary |
| 국내 개별주식 NXT | 0.014% | 0.014% | 0.201% | **0.229%** | venue scenario |
| 국내 주식형 ETF KRX | 0.015% | 0.015% | 0.000% | **0.030%** | ETF actual-cost |
| ETF diagnostic | - | - | - | 0.090% | 민감도 |
| ETF stress | - | - | - | 0.230% | stress, 실제비용 아님 |

UI에서는 `%`를 기본 표기로 사용한다. 내부에서 bp가 필요하면 `1bp = 0.01%`로 함께 저장한다. 실제 계좌 우대수수료와 슬리피지는 운영 전 별도로 실측해야 한다.

## 5. 실제 일봉 DB 실행 결과

```powershell
py -3.11 -m stom_rl.daily_close_research.runner `
  --database _database/Stock_Database_ohlcv_1day.db `
  --output-directory .omx/artifacts/daily_close_rl_g1_g6_v2 `
  --epochs 120
```

| 지표 | 관측값 | 해석 |
|---|---:|---|
| 대상 종목 | 대표 개별주식 20개 | 현재 선택 목록, PIT universe 아님 |
| sample | 131,838 | 5·10·20일 특징 |
| 거래일 | 10,462 | 종목별 가용 기간 합성 |
| 체결 계약 | 다음 거래일 시가 | 당일 종가 누수 차단 |
| 비용 후 평균 | **+0.7574%** | 5일 forward 진단값 |
| shuffle 평균 | +0.2335% | 현재 universe 자체의 양의 편향 가능 |
| native - shuffle | **+0.5239%** | 등록 임계 0.05% 초과 |
| 양수 fold | **4/4** | 시간순 expanding validation |
| signal 판정 | `PASS_SIGNAL_FLOOR` | 단, 진단 전용 |
| 증거 범위 | `DIAGNOSTIC_ONLY_UNVERIFIED_CUSTODY` | 경제성 승격 금지 |

### 5.1 왜 좋은 수치인데도 NO-GO인가

| 차단 | 현재 상태 | 위험 |
|---|---|---|
| `POINT_IN_TIME_UNIVERSE` | 미확인 | 오늘 살아남은 종목을 과거에도 알고 고르는 생존편향 |
| `AVAILABLE_AT_PROVEN` | 미확인 | 의사결정 시각 뒤 데이터를 본 미래누수 가능성 |
| `OFFICIAL_PRICE_IDENTITY` | 미확인 | 시가·종가·조정가격 의미 혼합 가능성 |
| `CORPORATE_ACTION_CONTRACT` | 미확인 | 액면분할·배당·합병 수익률 왜곡 가능성 |
| `IMMUTABLE_SOURCE_HASH` | 미확인 | 동일 입력 재실행 증명 부족 |

shuffle도 +0.2335%라는 사실은 현재 universe가 상승한 생존 종목에 치우쳤을 가능성을 보여준다. +0.7574%는 연구를 계속할 근거이지 수익 증명이 아니다.

## 6. DQN·CQL 보정 성과

| 모델/control | seed별 평가수익 | IQM | 양수 seed | 판정 |
|---|---|---:|---:|---|
| DQN | 0.11666, 0.11973, 0.12215 | 0.11951 | 3/3 | 학습 성공 |
| CQL | 0.11666, 0.11973, 0.12215 | **0.11951** | **3/3** | 학습 성공 |
| shuffled-reward CQL | 0.00000, -0.02442, 0.00870 | -0.00524 | 1/3 | control 실패 기대와 일치 |
| random policy | - | -0.02695 | - | 기준선 |

전체 synthetic 판정은 `PASS_SYNTHETIC_OFFLINE_RL`이다. CQL 코드가 아무것도 배우지 못하는 상태는 벗어났다는 뜻이지만 실제 시장 alpha를 증명하지 않는다.

## 7. 실패를 통해 수정한 사항

| 문제 | 실제 원인 | 수정 | 결과 |
|---|---|---|---|
| pytest torch `c10.dll` WinError 1114 | 전역 pytest-qt가 Qt native runtime을 먼저 로드 | 비-Qt 저장소에서 pytest-qt 자동 로드 차단 | 기본 pytest로 torch 테스트 통과 |
| shuffled CQL도 원래 CQL과 동일 | behavior가 75% 최적행동이라 답이 누출 | behavior action 균등 무작위화 | reward shuffle이 유효한 control이 됨 |
| CQL 현금행동 붕괴 | `alpha=0.5`가 약 0.01 보상보다 너무 큼 | `cql_alpha=0.01` | CQL 3/3 seed 학습 |

## 8. 구현 파일

| 모듈 | 책임 | 상태 |
|---|---|---|
| `costs.py` | 상품·시장별 비용 계약 | 완료 |
| `contracts.py` | 종가 실행·PIT·available-at gate | 완료 |
| `features.py` | t일까지 특징, t+1 시가 이후 label | 완료 |
| `signal_floor.py` | expanding fold ridge·shuffle | 완료 |
| `portfolio.py` | 6천만원·정수주·10슬롯 환경 | 완료 |
| `offline_data.py` | transition·시간순 split·controls | 완료 |
| `models.py` | DQN·CQL·저장·복원 | 완료 |
| `evaluation.py` | seed·IQM·bootstrap·control | 완료 |
| `runner.py` | G1~G6 통합 실행·JSON receipt | 완료 |
| `DailyCloseResearchStatus.svelte` | 공통 연구 상태 UX | 완료 |

## 9. 페이지별 반영 상태

| 페이지 | 이번 반영 | 현재 표시 | 남은 작업 | 예상 |
|---|---|---|---|---:|
| Home | 공통 상태 패널 | 75점·판정·비용·다음 행동 | receipt API 동적화 | 1~2시간 |
| Program Scorecard | 공통 상태 패널 | G1~G8·모델 범위·차단 | 구세대 표 UTF-8 정리 | 2~3시간 |
| RL Discovery | workspace 공통 패널 | 현재 세대와 이전 D계열 | 세대 필터 | 1~2시간 |
| RL Data | workspace 공통 패널 | custody blocker 5개 | metadata 등록 UI | 2~4시간 |
| RL Experiment | workspace 공통 패널 | 6천만원·비용·gate | G7 사전등록 양식 | 승인 후 1~2시간 |
| RL Training | workspace 공통 패널 | synthetic CQL 3/3 | 실제 market model 잠금 | G2 후 3~6시간 |
| RL Evaluation | workspace 공통 패널 | 신호·shuffle·IQM | fold 상세 차트 | 1~2시간 |
| RL Compare | workspace 공통 패널 | DQN/CQL/control | 비용 시나리오 차트 | 1~2시간 |
| RL Report | workspace 공통 패널 | verdict·next action | receipt 다운로드 | 1시간 |
| Insights | 기존 유지 | 종목·수급·regime | PIT top-20 다종목 선택 | 2~4시간 |
| Kronos | 기존 유지 | 예측모델/RL 경계 | embedding 별도 가설 | 1~2일 연구 |
| Settings / Other Lanes | 기존 유지 | 읽기 전용 경계 | artifact root 표시 | 1시간 |

공통 패널은 RL 하위 모든 페이지 상단에 한 번만 배치해 대형 레거시 파일을 늘리지 않았다. 단계 카드는 좁은 화면에서 내부 스크롤되고 판정 문자열에는 줄바꿈 규칙을 적용했다.

## 10. 점수

### 10.1 G1~G6 연구 구현 성숙도: 75/100

| 영역 | 배점 | 획득 | 근거 |
|---|---:|---:|---|
| G1 비용·실행 계약 | 15 | 15 | typed 계약·테스트 |
| G2 데이터 custody | 15 | 0 | 실제 증거 5개 미확인 |
| G3 신호 바닥 | 20 | 20 | 진단 4/4 fold, promotion 불가 |
| G4 포트폴리오 환경 | 15 | 15 | 정수주·노출·현금 invariant |
| G5 DQN·CQL | 20 | 20 | 3-seed calibration |
| G6 통계·controls | 5 | 5 | IQM·bootstrap·shuffle |
| G7 Fresh OOS | 5 | 0 | 봉인·미실행 |
| G8 paper-forward | 5 | 0 | G7 이후 |

### 10.2 전체 프로그램 성숙도: 63/100

| 영역 | 배점 | 획득 | 설명 |
|---|---:|---:|---|
| 목표·계약 | 10 | 9 | 모델·자금·행동·보상 명확 |
| 데이터 증거 | 20 | 5 | DB 존재, custody 부족 |
| 환경·회계 | 15 | 13 | invariant 완료, 실제 fill 미검증 |
| 경제 신호 | 15 | 9 | 유망 진단, 편향 위험 |
| RL 모델 | 15 | 10 | calibration 모델, 시장모델 아님 |
| 검증·통계 | 10 | 7 | fold/control/CI, Fresh OOS 없음 |
| UX·연구관리 | 10 | 8 | 공통 패널·반응형·점수화 |
| 운영 준비 | 5 | 2 | read-only 서버, 주문·paper 없음 |

실제 수익형 강화학습 모델 성공도는 **20/100**이다. 학습기와 synthetic 모델 생성은 성공했지만 실제 시장 controller와 Fresh OOS가 없다.

## 11. 검증 증거

| 검증 | 결과 |
|---|---|
| Python 신규+기존 RL/dashboard 통합 회귀 | **125 passed, 2 skipped** |
| frontend 전체 회귀 | **410 passed** |
| Svelte check | 0 errors, 0 warnings |
| production build | 978 modules transformed, success |
| 실제 runner | exit 0, receipt·model 생성 |
| 로컬 서버 | `127.0.0.1:5070`, HTTP 200, PID 175920 |
| 브라우저 자동 QA | 앱 보안정책이 loopback 탭 제어를 차단해 미실행 |

## 12. 브랜치·커밋 계보

| 순서 | 브랜치 | 커밋 | 내용 |
|---:|---|---|---|
| 1 | `codex/rl-research-governance-v1-21` | `f5e3ae3` | 전체 개발 중간 검토 |
| 2 | `codex/rl-daily-close-contracts-v1-22` | `f1563c8` | 비용·실행 계약 |
| 3 | `codex/rl-daily-close-signal-env-v1-24` | `681fb23` | 신호 바닥·포트폴리오 환경 |
| 4 | `codex/rl-daily-close-cql-eval-v1-26` | `2dcde2b` | DQN·CQL·강건성 검증 |
| 5 | 같은 계보 | `5343e6d` | 통합 runner·receipt |
| 6 | `codex/rl-daily-close-dashboard-v1-27` | 후속 커밋 | UI·결과 문서 |

계보는 선형으로 연결됐다. 아직 push·PR·merge·tag는 하지 않았다. 전체 회귀 후 부모 `research/daily-close-offline-rl-v2`로 병합하고 그 부모에서 integration PR을 만드는 방식이 안전하다.

## 13. 다음 단계

| 우선 | 단계 | 목적 | 완료 조건 | 예상 |
|---:|---|---|---|---:|
| P0 | G2 PIT universe | 생존편향 제거 | 날짜별 membership hash | 1~2일 |
| P0 | 수정주가·기업행사 계약 | 분할·배당 왜곡 제거 | adjustment 정책·source hash | 0.5~1일 |
| P0 | `available_at` | 미래누수 제거 | 모든 feature cutoff 이전 | 0.5~1일 |
| P0 | G3 재실행 | promotion-eligible 승격 | 등록 기준 통과 | 2~4시간 |
| P1 | 시장 offline dataset | synthetic→시장 controller | 6-action transition receipt | 1~2일 |
| P1 | market DQN/CQL 5-seed | 실제 RL 모델 생성 | controls·supervised 우월 | 0.5~1일 |
| P1 | G7 승인 | sealed Fresh OOS | 별도 승인·one-time ledger | 승인 후 0.5일 |
| P2 | G8 paper-forward | 새 데이터 관찰 | 등록 기간·무주문 ledger | 수 주 |

## 14. 지금 가능한 것과 불가능한 것

| 질문 | 답 |
|---|---|
| 강화학습 코드를 실행할 수 있는가 | 가능 |
| DQN/CQL 모델 파일을 만들 수 있는가 | 가능, 이번에 생성함 |
| 6천만원·10종목 회계를 테스트할 수 있는가 | 가능 |
| 실제 일봉 신호 연구를 할 수 있는가 | 가능, 현재 진단 등급 |
| 지금 모델로 실제 종목을 매매해도 되는가 | 불가능 |
| 수익형 강화학습 모델에 성공했는가 | 아직 아님 |
| 연구를 계속할 가치가 있는가 | 있음. 유망한 G3 진단이 있으나 G2를 먼저 해결해야 함 |
