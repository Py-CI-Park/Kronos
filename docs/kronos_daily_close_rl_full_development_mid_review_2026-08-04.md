# Kronos 일봉 종가매매 강화학습 전체 개발 중간 검토

- 작성일: 2026-08-04 KST
- 기준 브랜치: `codex/rl-research-governance-v1-21`
- 기준 커밋: `0b2f49b`
- 문서 성격: G1~G6 구현 전 중간 설계 동결 및 실행 승인 기준
- 목표 버전: `v1.21.0` 문서 기준선 → `v1.27.0` 검증 가능한 연구 파이프라인

## 1. 결론

이번 개발의 목표는 **국내 개별주식 일봉을 이용해 장 마감 의사결정을 내리는 상태형 포트폴리오 강화학습 모델**을 만드는 것이다. 총 연구자금은 6,000만원, 최대 주식 노출은 5,000만원, 현금 예비금은 1,000만원, 최대 보유 종목은 10개, 1슬롯 목표금액은 약 500만원으로 고정한다.

현재 Kronos에는 단일 ETF target-position 환경, 일봉 SQLite 읽기, momentum signal-floor, synthetic MDP gate가 있다. 그러나 다음 핵심 요소가 없어 개별주식 종가매매 RL의 성공 여부를 아직 판정할 수 없다.

1. 주식·ETF를 구분하는 비용 계약과 매수수수료·매도수수료·거래세 분해
2. 공식 종가 또는 명시된 종가 proxy의 `available_at` 증거
3. 5·10·20일 예측 horizon을 비교하는 OOS supervised signal floor
4. 최대 10종목·정수주·현금·교체 행동을 갖는 상태형 포트폴리오 환경
5. DQN 및 보수적 오프라인 RL(CQL) 학습기
6. seed·fold·shuffle control·bootstrap 신뢰구간을 묶은 검증 receipt
7. 실패 이유와 다음 행동을 한 화면에서 읽을 수 있는 대시보드 표현

따라서 이번 사이클에서는 모델 파일을 만드는 것만을 성공으로 부르지 않는다. **코드 성공**, **학습 성공**, **경제성 성공**, **운영 승격**을 분리한다. G1~G6 구현과 synthetic calibration은 진행하되, 실제 데이터 custody 또는 signal floor가 실패하면 경제성 결론은 `NO_GO`로 보존한다.

## 2. 만들 모델의 정확한 계약

| 항목 | 동결 사양 | 이유 |
|---|---|---|
| 시장 | 한국 개별주식 연구 universe | ETF lane과 비용·세금·종목 생존 조건이 다름 |
| 빈도 | 일봉 | 사용자가 요구한 종가매매와 일치 |
| 결정시점 | 당일 마감 직전 또는 장 종료 후 | 데이터 가용시점에 따라 두 모드를 구분 |
| 체결시점 | `CLOSE_PROXY` 또는 `NEXT_OPEN` | 공식 종가를 의사결정 전에 사용할 수 없는 누수를 차단 |
| 초기 NAV | 60,000,000원 | 연구 기준금액 |
| 최대 노출 | 50,000,000원 | 최소 10,000,000원 현금 예비금 |
| 최대 슬롯 | 10 | 종목당 약 5,000,000원 |
| 주문 단위 | 정수주 | 실제 주식 주문 가능성과 일치 |
| 후보군 | 시점별 PIT universe 중 supervised top-20 | RL이 전 종목을 직접 탐색하는 난제를 축소 |
| 상태 | 5·10·20일 수익률, 변동성, 거래대금, 시장상태, 보유·현금·평단·경과일 | 시장과 계좌 상태를 함께 관측 |
| 행동 | `HOLD_CASH`, `HOLD`, `ADD_ONE`, `EXIT_ONE`, `REPLACE_ONE`, `REDUCE_RISK` | 10종목 포트폴리오를 제한된 이산 행동으로 제어 |
| 보상 | 비용 차감 후 `log(NAV_t / NAV_t-1)` | 장기 복리와 비용을 동시에 반영 |
| 제약 | 슬롯·노출·현금·회전율·낙폭 제한 | 보상 조작과 안전제약을 분리 |
| 알고리즘 | supervised floor → DQN baseline → offline CQL | 신호 없음과 RL 실패를 분리하고 과대추정을 억제 |
| 비교대상 | no-trade, equal-weight, supervised top-k, random/shuffle | RL 자체의 추가가치를 검증 |

### 2.1 종가라는 말의 두 가지 실행 모드

| 모드 | 의사결정 데이터 | 체결 가격 | 증거 등급 |
|---|---|---|---|
| `PRE_CLOSE_PROXY` | 15:20까지 확정된 특징 | 등록된 마감 proxy | 연구 가능, proxy임을 명시 |
| `POST_CLOSE_NEXT_OPEN` | 공식 종가까지 포함 | 다음 거래일 시가 | 누수 없이 재현 가능 |

당일 공식 종가를 보고 같은 공식 종가에 체결하는 계산은 불가능한 체결을 가정하므로 금지한다. 현재 로컬 데이터가 공식 종가 가용시각을 증명하지 못하면 `POST_CLOSE_NEXT_OPEN`을 기본 연구모드로 사용한다.

## 3. 비용 계약

`bp`는 0.01%다. UI·문서에서는 사용자가 비교하기 쉬운 `%`를 기본 표기로 사용하고, 내부 계산·receipt에는 `%`와 bp를 함께 기록한다.

| 상품 | 매수수수료 | 매도수수료 | 거래세 등 | 명시비용 왕복 | 연구 사용 |
|---|---:|---:|---:|---:|---|
| 국내 개별주식 KRX 표준 | 0.015% | 0.015% | 0.200% | **0.230%** | 개별주식 primary |
| 국내 개별주식 NXT 표준 | 0.014% | 0.014% | 0.201% | **0.229%** | venue 시나리오 |
| 국내 주식형 ETF 표준 | 0.015% | 0.015% | 0.000% | **0.030%** | ETF actual-cost |
| ETF 진단 | - | - | - | 0.090% | 민감도 비교 |
| ETF 스트레스 | - | - | - | 0.230% | 보수적 stress, actual-cost 아님 |

위 수치는 연구 기본값이며 실제 계좌·매체·우대수수료와 다를 수 있다. 운영 승격 전에는 키움 계좌 체결내역 또는 공식 계약 화면에서 실측 비용을 다시 고정해야 한다. 슬리피지·호가 충격은 명시비용과 별도 항목이다.

## 4. 현재 자산과 부족한 부분

| 영역 | 현재 자산 | 판정 | 이번 구현 |
|---|---|---|---|
| 일봉 원천 | `_database/Stock_Database_ohlcv_1day.db`, SQLite 약 1GB | 사용 가능하나 custody 미검증 | read-only 로더·시점별 증거 검사 |
| 단일자산 회계 | `stom_rl/etf_research/environment.py` | 재사용 가능 | 다종목 정수주 환경으로 확장 |
| 데이터 gate | `stom_rl/etf_research/data.py` | 기본 integrity 존재 | 공식종가·available-at·PIT를 별도 계약화 |
| 신호 바닥 | 20일 momentum, 5일 보유 | 가설이 너무 좁음 | 5·10·20일 horizon과 fold-local ranker |
| synthetic gate | 알려진 정책 3/3 통과 | 환경 학습 가능성만 증명 | 다슬롯 action-dependent gate 추가 |
| RL | Type1 PPO와 기존 DQN은 `NO_GO` | 경제성 실패 | 동일 데이터 계약 위 DQN/CQL 비교 |
| 통계 | seed/fold 일부 존재 | 불충분 | IQM·bootstrap CI·shuffle control |
| UI | 12개 페이지와 기존 evidence 표시 | 세대 혼합·MISSING·글자 깨짐 | 단계·비용·모델·차단 원인 중심 재구성 |

## 5. 왜 지금까지 실패했는가

| 실패 원인 | 관측 증거 | 이번 대책 |
|---|---|---|
| train 분류 성능을 거래 성능으로 오해 | D5S train accuracy 0.827225, D6 validation 0.179688 | train·validation·경제성 지표를 분리 |
| 단순 장시간 학습 | 200k→800k가 개선되지 않음 | 학습시간보다 데이터·보상·행동 진단 우선 |
| 높은 거래 빈도 | D6R2 trade rate 약 0.90 | 비용 포함 reward와 turnover constraint |
| 비용만의 문제가 아님 | 0% 비용 진단도 음수 | 0%·actual·stress를 같이 표시 |
| 너무 큰 행동·종목 공간 | 기존 PPO가 전 문제를 동시에 학습 | supervised top-20 + 작은 이산 controller |
| 미래정보·종가 계약 불명확 | 현재 일부 경로가 15:20 proxy | `available_at` fail-closed와 실행모드 고정 |
| 실제 경제 신호 바닥 부재 | ETF Q2-A 23bp에서 실패 | 상품별 실제 비용으로 새 사전등록 후 재검증 |
| 실패 증거가 UI에서 혼재 | 이전 세대와 현재 세대 상태가 한 화면에 혼합 | 세대·단계·gate·다음 행동을 표로 고정 |

`NO_GO`는 학습을 멈추기 위한 장치가 아니라, 같은 실패 가설을 더 오래 돌리지 않기 위한 분기점이다. 이후 연구는 계속하되 실패한 설정을 성공한 모델로 승격하지 않는다.

## 6. G1~G6 개발 범위

| Gate / 버전 | 구현물 | 자동 검증 | 완료 조건 | 실패 시에도 남는 성과 |
|---|---|---|---|---|
| G1 / v1.22 | typed 비용 계약, 주식·ETF 시나리오, UI 표기 | 비용 분해·왕복 합계·%/bp 변환 | 주식 0.230%, ETF 0.030% 일치 | 비용 오판 제거 |
| G2 / v1.23 | 종가 실행모드·PIT custody contract | 미래값 차단·코드 보존·read-only | 실제 데이터는 증거 없으면 BLOCKED | 누수 없는 연구 경계 |
| G3 / v1.24 | 5·10·20일 ranker signal floor | chronological fold·shuffle·no-trade | 최소 하나의 OOS horizon이 등록 gate 통과 | 신호 없음과 RL 실패 분리 |
| G4 / v1.25 | 6천만원·10슬롯 상태형 환경 | 현금·정수주·노출·보상 invariant | known policy가 controls 우월 | 환경 learnability 증명 |
| G5 / v1.26 | DQN baseline·offline CQL | seed 반복·model save/load·shuffle | CQL이 random/shuffle과 supervised floor를 안정적으로 우월 | 학습기와 모델 artifact |
| G6 / v1.27 | nested validation·IQM·bootstrap receipt | fold/seed 격리·CI 재현 | design/validation 결과와 blocker가 한 receipt에 존재 | 검증 가능한 NO_GO 또는 후보 |

G7 sealed Fresh OOS와 G8 paper-forward는 이번 범위에서 자동 개봉하지 않는다. G7은 별도 사용자 승인과 새 데이터 기간이 필요하고, G8은 G7 통과 뒤 진행한다.

## 7. 코드 구조 계획

새 코드는 `stom_rl/daily_close_research/`에 격리하고 각 파일을 작은 typed 모듈로 유지한다.

| 파일 | 책임 |
|---|---|
| `costs.py` | 비용 항목·상품별 시나리오·단위 변환 |
| `contracts.py` | 실행모드·PIT evidence·gate receipt |
| `features.py` | t-1 또는 next-open 기준 5·10·20일 특징 |
| `portfolio.py` | 정수주·현금·슬롯·행동·보상 |
| `offline_data.py` | transition과 chronological split |
| `models.py` | DQN·CQL Q-network 학습·저장·복원 |
| `evaluation.py` | baseline·fold·seed·IQM·bootstrap |
| `runner.py` | G1~G6 실행과 JSON receipt |

외부 대형 offline-RL 프레임워크를 새로 추가하지 않는다. 이미 설치된 PyTorch·NumPy를 사용해 작은 discrete DQN/CQL을 구현하여 환경·보상·평가를 직접 감사할 수 있게 한다.

## 8. TDD 및 검증 순서

모든 Python·TypeScript 구현은 실패 테스트를 먼저 추가한 뒤 최소 구현으로 통과시킨다.

| 순서 | 테스트 초점 | 실행 |
|---:|---|---|
| 1 | 비용 계약 | `py -3.11 -m pytest tests/test_daily_close_costs.py -q` |
| 2 | 실행·custody 계약 | `py -3.11 -m pytest tests/test_daily_close_contracts.py -q` |
| 3 | 다종목 환경 | `py -3.11 -m pytest tests/test_daily_close_portfolio.py -q` |
| 4 | feature·offline transition | `py -3.11 -m pytest tests/test_daily_close_features.py tests/test_daily_close_offline_data.py -q` |
| 5 | DQN·CQL 학습 | `py -3.11 -m pytest tests/test_daily_close_models.py -q` |
| 6 | 통계·runner receipt | `py -3.11 -m pytest tests/test_daily_close_evaluation.py tests/test_daily_close_runner.py -q` |
| 7 | 기존 회귀 | AGENTS.md의 RL/dashboard·rule gate 회귀 |
| 8 | frontend | `npm test`, `npm run check`, `npm run build` |
| 9 | 브라우저 | 1280px·768px·390px에서 overflow·MISSING·한글 표시 확인 |

## 9. UI/UX 연결 계획

| 페이지 | 보여줄 핵심 | 사용자가 즉시 알아야 할 질문 |
|---|---|---|
| Home | 현재 세대, 전체 gate, 경제성 판정 | 지금 모델이 있는가, 쓸 수 있는가 |
| Data | close mode, PIT/custody, 종목 수, 기간 | 미래정보 없이 학습 가능한가 |
| Experiment | 6천만원·10슬롯·행동·보상·비용 | 무엇을 학습하는가 |
| Training | DQN/CQL seed 진행, model artifact | 실제 학습이 실행됐는가 |
| Evaluation | baseline·fold·seed·CI·cost scenario | 경제성이 재현되는가 |
| Program scorecard | 구현·데이터·모델·경제성·운영 점수 | 다음 우선순위는 무엇인가 |

현재 일부 Svelte 한글이 mojibake로 보이는 문제가 관측됐다. 신규 UI에서는 UTF-8 한글을 직접 검증하고, 좁은 화면에서는 표를 가로 스크롤 컨테이너에 두며 긴 식별자는 `overflow-wrap:anywhere`로 처리한다.

## 10. 브랜치·커밋 계획

| 단계 | 브랜치 | 커밋 예시 |
|---|---|---|
| 중간 검토 | `codex/rl-research-governance-v1-21` | `docs(rl): 일봉 종가매매 전체 개발 중간 검토를 기록하다` |
| 전체 연구 부모 | `research/daily-close-offline-rl-v2` | 단계별 커밋 수용 |
| G1~G2 | `codex/rl-daily-close-contracts-v1-22` | `feat(rl): 종가 실행과 비용 계약을 구현하다` |
| G3~G4 | `codex/rl-daily-close-signal-env-v1-24` | `feat(rl): 신호 바닥과 다종목 환경을 구현하다` |
| G5~G6 | `codex/rl-daily-close-cql-eval-v1-26` | `feat(rl): 오프라인 CQL과 중첩 검증을 구현하다` |
| UI·결과 | `codex/rl-daily-close-dashboard-v1-27` | `feat(ui): 종가 RL 연구 증거 대시보드를 갱신하다` |

로컬 커밋까지 진행한다. push·PR·부모 브랜치 merge·태그는 전체 테스트와 브라우저 QA가 끝난 뒤 결과를 보고하고, 원격 변경 권한과 릴리스 경계를 확인한 다음 수행한다. 태그 후보는 `v1.27.0-rc.1`이며 결과가 `NO_GO`여도 연구 인프라 릴리스 태그와 경제성 판정은 분리한다.

## 11. 예상 시간과 중간 보고 기준

| 구간 | 예상 | 보고 시점 |
|---|---:|---|
| 중간 문서·커밋 | 20~40분 | 커밋 직후 |
| G1~G2 | 1~2시간 | 테스트·커밋 직후 |
| G3~G4 | 2~4시간 | synthetic gate와 실제 데이터 진단 직후 |
| G5~G6 | 3~6시간 | seed 학습과 receipt 생성 직후 |
| UI·전체 회귀·브라우저 QA | 2~4시간 | 빌드·브라우저 증거 확보 직후 |

실제 소요는 데이터 정합성, GPU/CPU 학습시간, 기존 frontend 인코딩 문제에 따라 달라진다. 시간 추정은 완료 약속이 아니라 현재 범위의 작업량 추정이다.

## 12. 이번 사이클의 판정 기준

| 등급 | 의미 | 허용 표현 |
|---|---|---|
| `IMPLEMENTED` | G1~G6 코드·테스트·receipt 완성 | “연구 모델을 생성하고 재현 가능하게 실행했다” |
| `CALIBRATED` | synthetic known-policy를 seed 반복에서 학습 | “강화학습기가 알려진 환경을 학습한다” |
| `ECONOMIC_CANDIDATE` | 실제 chronological validation에서 비용 후 baselines/control 우월 | “Fresh OOS 후보” |
| `FRESH_OOS_PASS` | 별도 봉인 데이터 통과 | “paper-forward 후보” |
| `LIVE_READY` | broker·paper·human approval까지 통과 | 이번 범위에서는 사용 금지 |

코드가 완성돼도 실제 검증이 실패하면 최종 판정은 `IMPLEMENTED / CALIBRATED / NO_GO_ECONOMIC`일 수 있다. 이것은 개발 실패가 아니라 재현 가능한 연구 결과다. 반대로 train 수익 또는 한 seed의 좋은 결과만으로 `ECONOMIC_CANDIDATE`라고 부르지 않는다.

## 13. 즉시 실행 결정

1. 이 문서를 별도 커밋으로 고정한다.
2. 전체 연구 부모 브랜치를 만들고 G1부터 TDD로 구현한다.
3. G3 실제 데이터 gate가 막혀도 G4 synthetic와 G5 학습기 calibration은 계속한다.
4. 실제 경제성 결과는 custody·chronological validation·controls를 모두 충족할 때만 후보로 올린다.
5. G7 Fresh OOS는 자동으로 열지 않는다.

