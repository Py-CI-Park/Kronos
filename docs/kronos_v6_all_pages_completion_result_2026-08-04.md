# Kronos V6 전체 페이지 완료 결과

- 기준일: 2026-08-04 KST
- 개발 브랜치: `codex/rl-all-pages-v1-28`
- 부모 연구 브랜치: `research/daily-close-offline-rl-v2`
- 기준 커밋: `8d46310`
- 후보 버전: `v1.28.0-rc.1`
- 연구 판정: `IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY`

## 1. 결론

V6의 사용자 진입 화면 13개에 공통 연구 결정 레일을 연결했다. 각 화면은 목적, 현재 증거, 다음 행동, 예상 시간, 완료 조건을 같은 순서로 표시한다. 전역 안전 배너와 연구 상태를 과거 D6R2 중심 문구에서 일봉 G1~G6 최신 결과로 교체했고, 깨진 한글과 과거 브랜치 정보를 정리했다.

화면 구현 완료와 강화학습 경제 모델 성공은 분리한다. 합성 환경 CQL 보정 모델은 생성됐지만 실제 시장 데이터로 검증된 경제 모델은 생성되지 않았다. 원인은 학습 횟수 부족이 아니라 G2 데이터 관리 증거 부족이다.

| 평가 축 | 점수 | 판정 | 의미 |
|---|---:|---|---|
| 전체 프로그램 성숙도 | 63/100 | PARTIAL | 플랫폼, 연구 증거, 엔지니어링, 거버넌스, 실거래 준비의 가중 합계 |
| 구현 완성도 | 75/100 | IMPLEMENTED | 일봉 계약·환경·학습·평가·UI 구현 수준 |
| 경제 모델 성과 | 20/100 | NOT CREATED | 실제 시장에서 재현 가능한 수익 모델은 아직 없음 |
| V6 페이지 제공 | 13/13 | COMPLETE | 모든 화면에서 페이지별 결정 레일 제공 |
| Fresh OOS | 0/100 | NOT_RUN_NO_READ | 봉인 유지, 별도 승인 전 읽지 않음 |
| 실거래 준비 | 0/100 | BLOCKED | 주문·브로커·운영 위험 통제 없음 |

## 2. 전체 페이지 결과

여기서 진행률 100%는 해당 화면과 연구 안내가 제공된다는 뜻이며 수익성 또는 GO를 뜻하지 않는다.

| # | 페이지 | 제공 | 현재 증거 | 다음 행동 | 예상 시간 |
|---:|---|---:|---|---|---|
| 1 | 홈 | 100% | `DAILY_CLOSE_G1_G6_IMPLEMENTED_75` | G2 데이터 관리 증거 확보 | 화면 완료 |
| 2 | 프로그램 점수 | 100% | `PROGRAM_63_IMPLEMENTATION_75_ECONOMIC_20` | 정적 스냅샷을 영수증 API로 교체 | 1~2시간 |
| 3 | RL 발견 실험실 | 100% | `HISTORY_PRESERVED_DAILY_CLOSE_V2_ACTIVE` | 과거 D계열과 CQL 근거 혼합 금지 | 화면 완료 |
| 4 | 데이터 | 100% | `G2_BLOCKED_5_CUSTODY_GATES` | PIT universe, available_at, 기업행사, source hash 등록 | 1~2일 |
| 5 | 실험 설계 | 100% | `G1_G6_EXECUTED_G7_LOCKED` | G2 통과 후 시장 모델 amendment 동결 | 1~2시간 |
| 6 | 학습 | 100% | `SYNTHETIC_CQL_CREATED_MARKET_MODEL_NOT_CREATED` | G2·G3 전 실제 시장 모델 생성 금지 | 통과 후 3~6시간 |
| 7 | 평가 | 100% | `G3_DIAGNOSTIC_PASS_4_OF_4_UNVERIFIED_CUSTODY` | 같은 평가를 PIT 데이터에서 재실행 | G2 후 2~4시간 |
| 8 | 비교 | 100% | `CQL_IQM_0_1195_SHUFFLED_NEG_0_00524` | 시장 모델에도 shuffle·random 통제 적용 | 학습과 동시 |
| 9 | 보고서 | 100% | `IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY` | 문서와 JSON receipt 판정 동기화 | 화면 완료 |
| 10 | 인사이트 | 100% | `CURRENT_UNIVERSE_DIAGNOSTIC_NOT_PIT` | PIT top-20 전까지 추천 표현 금지 | G2와 동시 |
| 11 | 다른 레인 | 100% | `SEPARATE_LANES_NO_CLAIM_TRANSFER` | 레인 간 성과 전이 금지 | 화면 완료 |
| 12 | Kronos 모델 | 100% | `AVAILABLE_NOT_LOADED_NOT_RL_POLICY` | embedding 가설은 별도 사전등록 | 별도 1~2일 |
| 13 | 설정 | 100% | `READ_ONLY_ARTIFACT_ROOT_VISIBLE` | 표시 설정만 허용 | 화면 완료 |

## 3. UX/UI 변경

| 변경 | 결과 |
|---|---|
| 공통 결정 레일 | 페이지 목적 → 현재 증거 → 다음 행동 → 완료 조건을 한 줄 흐름으로 통일 |
| 점수 분리 | 프로그램 63, 구현 75, 경제 모델 20을 별도 카드로 표시 |
| 안전 경계 | `NO-GO`, `READ-ONLY`, `FRESH OOS: NOT RUN`, `NO LIVE` 상시 표시 |
| 한글 정리 | 전역 셸, 안전 배너, 연구 상태, 점수표, Kronos, 다른 레인, 설정의 깨진 문구 제거 |
| 반응형 | 결정 레일 4→2→1열, 점수표 내부 가로 스크롤, 좁은 화면 줄바꿈 유지 |
| Kronos 경계 | `Kronos 예측 모델 ≠ 강화학습 정책`을 명시하고 미로드를 코드 소실로 오해하지 않게 설명 |
| 인사이트 경계 | 현재 universe가 PIT가 아니며 매수 추천이 아니라는 안내 유지 |

## 4. 강화학습 연구 성과

| 항목 | 관측 결과 | 해석 |
|---|---:|---|
| 사용 종목 | 20종목 | 현재 데이터에서 읽은 진단 universe이며 PIT 증명 아님 |
| 표본 | 131,838 | G3 신호 바닥 진단에 사용 |
| 거래일 | 10,462 | 데이터 범위의 관측값 |
| 신호 진단 | 4/4 fold 양수 | 학습 진행 가치가 있다는 진단이지 수익 증명은 아님 |
| 평균 순수익 | +0.7574% | 현재 관리 미검증 데이터의 진단값 |
| shuffle 평균 | +0.2335% | 통제군도 양수이므로 데이터 구조·편향 점검 필요 |
| 차이 | +0.5239%p | 신호와 shuffle 차이의 관측값 |
| 합성 CQL | 3/3 seed | 학습 파이프라인과 보정 가능성 확인 |
| CQL IQM | 0.1195 | 합성 환경 성능 |
| shuffled CQL IQM | -0.00524 | negative control 분리 |
| random IQM | -0.02695 | 무작위 정책보다 합성 CQL이 높음 |
| 실제 시장 경제 모델 | 미생성 | G2 관리 통과 전 생성하면 과적합 모델을 성공으로 오해할 위험 |

## 5. 검증 증거

| 검증 | 결과 |
|---|---|
| 새 페이지·점수·계보 단위 테스트 | 13 passed |
| 전체 프런트 회귀 | 413 passed |
| Svelte/TypeScript | 0 errors, 0 warnings |
| 프로덕션 빌드 | 980 modules transformed |
| 일봉·대시보드 Python 회귀 | 79 passed, 2 skipped |
| 실행 서버 | `127.0.0.1:5070`, PID `177292` |
| 점수표 HTTP | 200, 1,476 bytes |
| 최신 JS 자산 | `assets/index-BFZVwmaf.js`, HTTP 200, 1,263,603 bytes |
| dist index SHA-256 | `4F1B2ED89A4E529F87BFDD87BE1050FE95A715DADCD76A293A0292D54E9828FA` |

직접 브라우저의 1024/768/390 시각 캡처는 이번 완료 증거에 포함하지 않는다. 자동화 브라우저의 loopback 접근 제한을 우회하지 않았고, 대신 정적 검사·프로덕션 빌드·실제 Flask HTTP와 자산 응답을 검증했다.

## 6. 다음 연구 게이트

| 순서 | 단계 | 목적 | 완료 조건 | 예상 |
|---:|---|---|---|---|
| 1 | G2 데이터 관리 | 미래정보·생존편향·수정주가 오류 차단 | PIT universe, identity, available_at, total-return, source hash 5개 PASS | 1~2일 |
| 2 | G3 재실행 | 진단 신호가 관리된 데이터에서도 유지되는지 확인 | 4개 fold, 비용, shuffle 통제 재검증 | 2~4시간 |
| 3 | 시장 offline RL 생성 | 실제 6-action 종가 정책 학습 | 사전등록된 seed와 artifact 저장, 통제군 포함 | 3~6시간 |
| 4 | 설계/OOS 평가 | 과적합과 비용 민감도 판정 | DQN/CQL/random/shuffle, 비용 0·기준·스트레스 비교 | 2~4시간 |
| 5 | G7 승인 | Fresh OOS 봉인 해제 여부 결정 | 사람 승인과 prereg hash 고정 | 별도 승인 |
| 6 | G8 paper-forward | 실시간이 아닌 전진 검증 | 운영 기간·위험 한도 충족 | 수 주 |

신호 바닥 또는 G2가 실패하면 학습 횟수만 늘리는 것은 중단한다. 이 경우 보상, 네트워크 크기, seed를 반복 변경하는 대신 데이터 계약과 가설을 새로 사전등록해야 한다.

## 7. Git 전달 계획

1. `codex/rl-all-pages-v1-28`에서 UI·상태 모델과 테스트를 커밋한다.
2. 이 문서와 결과 표를 별도 문서 커밋으로 남긴다.
3. 프로덕션 dist 산출물을 별도 빌드 커밋으로 남긴다.
4. 로컬 부모 `research/daily-close-offline-rl-v2`를 fast-forward 한다.
5. 원격 push, Draft PR, `v1.28.0-rc.1` 태그, master 병합은 사용자 승인 또는 원격 권한 확인 후 진행한다.

태그는 프로그램 릴리스 계보이며 강화학습 모델 성공 또는 실거래 승인을 뜻하지 않는다.
