# Kronos v1.29.0-dev 데이터 권위·4행동 종가배분 RL 결과

- 결과 문서 갱신일: 2026-08-13 KST
- 기능 브랜치: `codex/v1.29.0-dev-market-authority`
- 사전등록: `docs/kronos_v1_29_0_market_authority_allocation_prereg_002_2026-08-10.md`
- 연구 등급: `POST_HOC_CUSTODY_REPRODUCTION`
- 경제 모델 점수: **20/100**
- live readiness: **0/100**
- 수익성·paper/live 주장: **금지**

## 1. 현재 결론

001은 DQN 5개와 CQL 5개, 총 10개 4행동 모델을 TRAIN/VALIDATION에서 만든 보존된 exploratory candidate다. 001 적재 경로는 historical TEST의 후보 점수와 상태 feature 46일을 파싱했으므로 기존 historical TEST는 독립 OOS가 아니다. reward, 가격 체결, 행동 평가는 읽지 않았다. 이 사실은 001의 VALIDATION 숫자를 경제적 성공으로 승격하지 않으며, historical TEST를 앞으로 경제 판정에 사용할 수 없게 한다.

D0 가격 기준과 D1 시점별 종목군은 signed reviewer trust root·공식 원본에서 정규화 입력으로 이어지는 extraction receipt가 없으므로 계속 `BLOCKED`다. Fresh OOS는 상태·행동·reward 모두 미열람이며, 다음 유일한 독립 경제 증거 후보다.

002는 새 성능 검증이 아니라 같은 오염 경계를 보존한 코드·입력·설정·산출물 결정성 검사다. 2026-08-13 KST에 canonical root `D:/Chanil_Park/Project/Programming/Kronos`에서 authority 다음 allocation 순서로 한 번씩 실행했다. 002 exact match는 보관된 001 evidence의 결정성만 확인하며 경제 점수와 live readiness를 바꾸지 않는다.

| 질문 | 확인된 답 |
|---|---|
| 001 모델은 만들어졌는가? | 예. DQN 5개 + CQL 5개, 총 10개 checkpoint가 보존돼 있다. |
| 001 historical TEST는 독립적인가? | 아니오. candidate score/state feature 46일이 이미 파싱되어 오염됐다. |
| historical TEST reward·가격·행동 평가는 읽었는가? | 아니오. 이 경로에서는 미열람이다. |
| Fresh OOS는 읽었는가? | 아니오. 상태·행동·reward 전체 미열람이다. |
| D0/D1 권위는 확인됐는가? | 아니오. 둘 다 `BLOCKED`다. |
| 현재 수익성 또는 live 준비가 확인됐는가? | 아니오. 경제 20/100, live 0/100을 유지한다. |

## 2. 001 보존 결과의 올바른 해석

001의 관측은 TRAIN/VALIDATION 로컬 후향 연구에 한정된다. 행동은 `CASH`, `INVEST_TOP3_EQUAL_SLOT`, `INVEST_TOP5_EQUAL_SLOT`, `INVEST_TOP10_EQUAL_SLOT`이고 초기 NAV는 60,000,000원, 기본/스트레스 왕복 비용은 각각 0.230%/0.460%다. 보상은 비용 차감 후 `log(final NAV / previous NAV)`다.

10개 모델과 validation ledger가 존재한다는 것은 모델 생성과 고정된 validation 재생을 뜻할 뿐이다. validation은 이미 후보 선택과 gate에 소비됐고, CQL seed 간 결과도 균일하지 않다. D0/D1 차단, historical TEST feature 오염, Fresh OOS 미열람 때문에 001은 `LEGACY_EXPLORATORY_CANDIDATE`로만 남는다.

## 3. 002 실행 결과 기록 구조

002는 최종 소스·사전등록이 커밋되고 canonical root `D:/Chanil_Park/Project/Programming/Kronos`의 두 출력 디렉터리가 존재하지 않는 것이 확인된 뒤에만 authority 먼저, allocation 다음 순서로 실행한다. 실패한 immutable 002를 덮어쓰지 않는다.

| 확인 항목 | authority 002 | allocation 002 |
|---|---|---|
| 실행 ID | `DAILY_MARKET_AUTHORITY_2026_08_10_002` | `DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002` |
| 실행 상태 | `BLOCKED_DATA_AUTHORITY` | `REPRODUCTION_ONLY_VALIDATION_CONSUMED` |
| D0/D1 | 모두 `BLOCKED` | authority receipt의 `BLOCKED`를 결속 |
| historical TEST disclosure | score/state feature parsed; rewards/prices/action evaluation not read; contaminated | score/state feature consumed; rewards/prices/action evaluation not read; contaminated |
| Fresh OOS | 미열람 (`false`) | 미열람 (`NOT_RUN_NO_READ`) |
| 검산 | receipt·summary immutable 생성 | 10 checkpoint, 14-file manifest, 001 receipt SHA/evidence digest exact match |
| 경제 해석 | 권위 custody 검사 | 새 경제 검증 아님 |

authority receipt와 summary, allocation validation receipt, 14-file manifest, 10 checkpoints를 생성했다. allocation의 001 reference receipt SHA는 `6dfb4d6703af6f0d26b18b00feb85fc17c8bb2ffc7e2b866296d9d5468cdd09d`이고 reference/observed evidence digest는 모두 `751b82d9f67c2df08c8cf8062320f35b842d0980ba785088b81448b30f1fee0b`로 exact match다. economic score 20/100과 live readiness 0/100은 변경하지 않는다. mismatch였으면 재현 실패로 차단하고 동일 ID를 다시 실행하지 않았어야 한다.

## 4. 계속 차단되는 행동

- historical TEST를 독립 OOS나 수익성 근거로 사용하지 않는다.
- Fresh OOS를 별도 승인·사전등록 없이 열지 않는다.
- D0/D1을 해시 존재만으로 `VERIFIED`로 바꾸지 않는다.
- paper/live/broker 주문 또는 자동 승격을 하지 않는다.
- 002 exact match를 수익성·live readiness·경제 모델 점수 상승으로 해석하지 않는다.

## 5. 2026-08-13 대시보드 QA

Flask는 `KRONOS_V6_RESEARCH_RUNS_ROOT`로 canonical `webui/rl_runs`를 read-only
catalog root로 받도록 재시작했다. API는 allocation 002
`REPRODUCTION_ONLY_VALIDATION_CONSUMED`와 authority 002 `BLOCKED_DATA_AUTHORITY`를
각각 실제 run identity로 반환했다. Vite 최종 bundle은
`index-QdNxgJi0.js`이며, bundle diff의 trailing whitespace를 제거해
`git diff --check 929fc47^..HEAD`를 통과시켰다.

1440×1000 Chromium에서 통합 현황, 연구 라이브러리, 실시간 학습, 평가·비교,
데이터·증거, 모델·산출물, 보고서·거버넌스, 설정 URL을 매 navigation 뒤 새
page observation으로 확인했다. 각 확인 viewport에는 horizontal overflow가 없었다.
연구 library의 deterministic source test는 002 exact/mismatch
상태 모두 `HISTORICAL TEST CONTAMINATED` danger warning과 Fresh OOS-only 문구를
요구한다. canonical artifact receipt는 exact 002 identity, 10 checkpoint, 14-file
manifest, D0/D1 BLOCKED, economic 20/100, live 0/100을 유지한다.

Research detail의 canonical allocation 002를 실제로 열었을 때
`REPRODUCTION_ONLY_VALIDATION_CONSUMED`, 15 bounded artifacts, CQL identity,
`KNOWN LIMITATION · HISTORICAL TEST CONTAMINATED`, reward·가격·체결·행동 평가
미열람 및 Fresh OOS-only 문구가 보였다. 브라우저 runtime diagnostics는 이
navigation들에서 console/page error를 보고하지 않았다.

검사 가능한 session transcript는
`.omx/artifacts/v1.29.0-dev-market-authority/browser-qa-20260813.json`이며
SHA-256은 `c510e830037afad4862dc53c1108dfe37398901527161901bd1377950caf485e`다.
이 생성 QA evidence는 Git에 넣지 않았다.
