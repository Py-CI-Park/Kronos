# Kronos v1.29.0-dev 실제 일봉 DQN/CQL 연구 결과

- 결과 확정일: 2026-08-10 KST
- 연구 ID: `DAILY_MARKET_CQL_2026_08_09_001`
- 사전등록: `docs/kronos_v1_29_0_market_cql_prereg_2026-08-09.md`
- 실행 브랜치: `codex/v1.29.0-dev-market-cql`
- 최종 판정: `NO_GO_HISTORICAL_ECONOMIC_GATE`
- Fresh OOS: `NOT_RUN_NO_READ`
- 승격·실거래: 차단

## 1. 결론

실제 로컬 한국 주식 일봉 전이로 DQN/CQL 계열 모델을 학습하고 숫자 전용 `.kq` 체크포인트 20개를 만드는 데 성공했다. 따라서 “강화학습 코드를 만들지 못했다” 또는 “모델 파일이 없다”는 상태는 끝났다.

그러나 경제적 성공은 아니다. 사전등록한 historical TEST에서 CQL 5시드 수익률 중앙값은 기본 비용 0.230% 기준 `-10.191550%`였고, 현금 대조군 0%를 넘지 못했다. 5개 시드 중 1개만 양수였으며 그 seed-3만 사후 선택하면 TEST 과적합이 된다. 모델 생성 성공과 경제 모델 성공을 분리해 판정한다.

| 구분 | 결과 | 완료도/점수 | 의미 |
|---|---|---:|---|
| 학습 파이프라인 구현 | 완료 | 100% | 실제 일봉 데이터부터 모델·평가·증거까지 실행 가능 |
| 모델 파일 생성 | 완료 | 20/20 | DQN 5, CQL 5, reward shuffle 5, action shuffle 5 |
| 대조군·경제 gate | 완료 | 7개 검사 | 2 PASS, 5 FAIL |
| 경제적 성능 | 실패 | 20/100 | 비용 후 안정적인 양수 성과 미확인 |
| Fresh OOS | 미실행 | 0% | 봉인 유지, 결과를 읽지 않음 |
| 라이브·브로커 | 차단 | 0/100 | 연구 산출물이며 주문 권한 없음 |

## 2. 실제 실행 범위

| 항목 | 관측값 |
|---|---:|
| TRAIN+VALIDATION 가용 일자 | 198 |
| TRAIN+VALIDATION 차단 일자 | 0 |
| historical TEST 가용 일자 | 45 |
| historical TEST 차단 일자 | 1 (`2026-06-11`, `002220:MISSING_EXIT_OPEN`) |
| 비중첩 TRAIN 결정 | 76 |
| 비중첩 VALIDATION 결정 | 24 |
| 비중첩 TEST 결정 | 23 |
| 50:50 행동 궤적 | 32개 |
| 학습 transition | 2,432 |
| 모델 입력 | 172차원 |
| 학습 모델 | 20개 |
| 행동 ledger | 1,058행 |
| 생성 파일 | 23개, 5,290,449 bytes |

행동은 `CASH`와 `INVEST_TOP10_EQUAL_SLOT` 두 가지다. D 종가 이후 결정하고 D+1 시가에 최대 10종목을 동일 슬롯로 매수한 뒤 다음 정확한 거래일 시가에 청산한다. 초기 NAV 6천만원, 주식 노출 상한 5천만원, 현금 하한 1천만원을 유지한다.

## 3. 5시드 실제 성과

단위는 비용 차감 후 수익률 `%`이며 MDD도 `%`다. `투자율`은 TEST 23개 결정 중 투자 행동 비율이다.

| 모델 | seed | VALIDATION | TEST 0.230% | TEST 0.460% | TEST MDD | 투자율 |
|---|---:|---:|---:|---:|---:|---:|
| DQN | 0 | +2.172282 | -3.820413 | -5.647729 | -9.235836 | 43.48% |
| DQN | 1 | +19.101453 | -4.187945 | -5.891631 | -9.630706 | 43.48% |
| DQN | 2 | +3.067949 | -4.251727 | -6.436456 | -13.171302 | 52.17% |
| DQN | 3 | -3.227012 | -4.781145 | -6.934429 | -10.048351 | 52.17% |
| DQN | 4 | -1.573954 | -6.999604 | -9.590806 | -15.339454 | 60.87% |
| CQL | 0 | +0.488469 | -13.625762 | -15.831571 | -14.808695 | 56.52% |
| CQL | 1 | +16.491742 | -8.056616 | -9.301760 | -9.658077 | 34.78% |
| CQL | 2 | +9.841921 | -15.025391 | -16.787405 | -20.530935 | 47.83% |
| CQL | 3 | -3.685874 | **+3.223953** | +1.717248 | -3.659768 | 34.78% |
| CQL | 4 | -1.573954 | -10.191550 | -12.391138 | -16.570414 | 56.52% |

VALIDATION이 +16~19%였던 시드도 TEST에서 음수가 됐다. 이는 학습 손실 감소가 경제적 일반화를 보장하지 않는다는 직접 증거다. CQL seed-3의 양수 결과는 사전등록된 5시드 집계 중 하나일 뿐이며 사후 채택하지 않는다.

## 4. 대조군과 경제 gate

| 대조군 | TEST 수익률 | MDD | 총비용 |
|---|---:|---:|---:|
| NO_TRADE | 0.000000% | 0.000000% | 0원 |
| ALWAYS_INVEST | -18.120282% | -25.370055% | 2,498,391원 |
| COST_AWARE_MOMENTUM_RULE | -18.120282% | -25.370055% | 2,498,391원 |

| gate | 관측값 | 판정 |
|---|---|---|
| CQL 중앙값 > 0%와 최고 대조군 | -10.191550% 대 0% | FAIL |
| 최소 4/5 시드가 최고 대조군 초과 | 1/5 | FAIL |
| 5,000회 bootstrap 95% 하한 > 0 | -15.025391% (`[-15.025391, +3.223953]`) | FAIL |
| 스트레스 비용 중앙값 > 0 | -12.391138% | FAIL |
| 모든 시드 MDD >= -20% | 최악 -20.530935% | FAIL |
| 최소 4/5 시드 행동 다양성 | 5/5 | PASS |
| 정상 CQL > 두 shuffle 중앙값 | -10.191550% > -15.025391%, -13.296462% | PASS |

shuffle 대조군보다 정상 CQL이 나았다는 점은 상태·행동·보상에 약한 구조가 있을 가능성을 보여준다. 하지만 현금 0%보다 나쁘므로 거래 가능한 alpha 증거는 아니다.

## 5. 왜 계속 실패하는가

| 원인 | 이번 실행의 증거 | 의미 |
|---|---|---|
| 경제 신호가 비용보다 약함 | 현금 0%가 모든 정책 중앙값보다 우수 | 더 오래 학습한다고 자동 해결되지 않음 |
| 일반화 불안정 | 높은 VALIDATION 시드도 TEST 음수 | validation 선택만으로 수익 모델을 만들 수 없음 |
| 유효 TEST 표본이 작음 | 비중첩 결정 23개 | 한 시드 양수 결과의 불확실성이 큼 |
| 행동 설계가 거침 | 전액 현금 또는 매일 고정 Top-10의 이진 행동 | 종목 수·노출 크기·abstention edge를 표현하기 어려움 |
| 규칙 기준이 무력함 | momentum RULE이 TEST 전체에서 always-invest와 동일 | 현재 threshold/score 의미가 비용 회피를 못함 |
| 데이터 권위 미확정 | `D0_PRICE_BASIS_NOT_VERIFIED`, `D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED` | 좋은 결과가 나와도 승격 불가 |
| Fresh OOS 미개봉 | `NOT_RUN_NO_READ` | 최종 일반화·실전 근접 증거 없음 |

강화학습은 보상을 크게 만들도록 최적화할 수 있지만, 과거 데이터에서 보상만 계속 올린다고 미래 수익이 생기지는 않는다. 학습 보상을 억지로 거래 친화적으로 바꾸면 실제 수수료·세금 후 경제 보상과 분리되어 과적합만 강화할 수 있다.

## 6. UX/UI와 대시보드 반영

실제 브라우저에서 `연구 라이브러리 → DAILY_MARKET_CQL_2026_08_09_001 → 상세 보기`를 클릭해 다음을 확인했다.

| 화면 | 확인 결과 | 상태 |
|---|---|---|
| 연구 라이브러리 | 최신 run, CQL, dataset hash, NO-GO 노출 | PASS |
| 실행 상세 | 13개 정책/시드의 손익·비용·reward 표와 차트 | PASS |
| 판정 이유 | 실패 gate와 `D0_PRICE_BASIS_NOT_VERIFIED` 노출 | PASS |
| 모델·산출물 | `.kq` 20개를 로드하지 않고 bounded metadata로 표시 | 브라우저 PASS (`FILE PRESENT 20`) |
| 차트 축 | 긴 정책명은 축에서만 `DQN/s0`, `CQL/s0`, `MOMENTUM`처럼 축약 | 브라우저 PASS, 원문은 툴팁·표 유지 |
| 상태 문구 | “모델 미생성”을 “20개 체크포인트 생성·경제성 통과 모델 없음”으로 정정 | 브라우저 PASS |
| 시간순 telemetry | 현재 action ledger는 알고리즘·seed가 섞여 있어 단일 곡선으로 추정하지 않음 | `TELEMETRY MISSING` 유지 |

seed별 시간순 equity·행동 그래프는 다음 실행부터 `algorithm + seed + scenario` 차원을 보존한 telemetry 계약을 먼저 추가해야 한다. 현재 1,058행을 하나의 곡선으로 섞어 보여주는 것은 잘못된 시각화이므로 하지 않는다.

## 7. 전체 페이지 현황

| 페이지 | 현재 상태 | 이번 연구 반영 | 다음 핵심 행동 | 예상 소요 |
|---|---|---|---|---:|
| 통합 현황 | BUILT | 체크포인트 생성과 경제성 실패 분리 | 다음 가설·권위 상태 연결 유지 | 1~2시간 |
| 프로그램 점수 | BUILT | 프로그램 71, 제품 94, 경제 20, live 0 유지 | 증거 기반 재채점만 허용 | 1시간 |
| RL 발견 실험실 | BUILT | 과거 D계열과 새 일봉 CQL을 별도 run으로 보존 | 가설 간 성과 전이 금지 | 1시간 |
| 데이터 | PARTIAL | 실제 DB 사용, 198/45 가용 일자 확인 | 가격 basis·PIT universe 권위 확정 | 0.5~2일 |
| 실험 설계 | COMPLETE | 자금·행동·비용·7 gate 사전등록 실행 | 새 TEST 전 다음 가설 amendment | 2~4시간 |
| 학습 | COMPLETE | 모델 20개, transition 2,432 | seed별 telemetry 계약 | 2~4시간 |
| 평가 | COMPLETE / NO-GO | 5시드·기본/스트레스 비용·bootstrap | 동일 TEST 재튜닝 금지, 새 구간 설계 | 0.5~1일 |
| 비교 | COMPLETE / NO-GO | DQN/CQL/규칙/두 shuffle 비교 | TRAIN/VAL 전용 abstention·top-k 연구 | 0.5~1일 |
| 보고서 | COMPLETE | 이 문서·세 증거 hash·5개 독립 리뷰 PASS 연결 | 새 가설 실행 후 결과 추가 | 이번 단계 완료 |
| 인사이트 | DIAGNOSTIC | 종목 추천으로 승격하지 않음 | PIT universe 전 단일 종목 해석 금지 | 데이터와 동시 |
| 다른 레인 | BUILT | 인트라데이·호가 RL과 성과 혼합 안 함 | 독립 증거 유지 | 완료 |
| Kronos 모델 | AVAILABLE / NOT LOADED | 이번 CQL 정책과 별도 모델 계열 | 별도 사전등록 없이는 입력에 추가 금지 | 1~2일 |
| 설정 | BUILT | 읽기 전용·무주문 경계 유지 | 사용자 접근성 검수 | 1~2시간 |

예상 시간은 데이터 권위 자료가 이미 준비돼 있다는 가정의 작업 시간이다. 외부 승인·미래 데이터 대기·paper-forward 기간은 포함하지 않는다.

## 8. 다음 합법적 강화학습 연구

우선순위는 학습 횟수를 늘리는 것이 아니라 실패 원인을 분리하는 것이다.

1. `D0/D1` 권위: 현재 DB의 가격이 수정/비수정 중 무엇인지, 날짜별 투자 가능 universe가 무엇인지 receipt로 고정한다.
2. TRAIN/VALIDATION 전용 행동 개선: `CASH`, `TOP-3`, `TOP-5`, `TOP-10` 또는 기대 edge가 비용보다 클 때만 투자하는 abstention을 사전등록한다.
3. 다중 시장 국면: 상승·하락·횡보와 최소 2~3년을 포함하는 walk-forward를 만든다.
4. nested validation: 하이퍼파라미터와 정책 선택을 TRAIN/VALIDATION 안에서만 끝낸다.
5. 새 untouched TEST: 현재 TEST는 이번 가설에 사용됐으므로 다시 튜닝 기준으로 쓰지 않는다.
6. seed별 telemetry: 모델·seed·비용 시나리오별 equity, action, reward를 분리 기록한다.
7. Fresh OOS·paper-forward: 위 gate를 통과한 단 하나의 고정 정책만 사람 승인 후 검증한다.

## 9. 재현 증거

실행 명령:

```powershell
py -3.11 -m stom_rl.daily_market_rl_runner
```

| 파일 | SHA-256 |
|---|---|
| `summary.json` | `05FCB3C468F95DA93238107031FB15C7CC3B695676710BAA944074663C1AC9AE` |
| `experiment_receipt.json` | `1B3210AB5E488D615BC8BAE02742BD30C265106824835D3A0FD79A2DFF239859` |
| `action_ledger.jsonl` | `FABFBFBD1884A53B78A58A3302009B4AA2DBA96B564C81B324316774D5CB75DD` |

생성 산출물은 `webui/rl_runs/daily_market_offline_rl/DAILY_MARKET_CQL_2026_08_09_001/`에 보존하지만 Git에는 커밋하지 않는다. 소스·테스트·문서만 커밋한다.

## 10. 품질·독립 리뷰

| 검증 | 결과 | 경계 |
|---|---|---|
| Python 핵심 회귀 | **50 passed** | 일봉 데이터·학습·게이트·API·Windows junction |
| 프런트엔드 전체 테스트 | **466 passed, 0 failed** | `bun test src` |
| Svelte 정적 검사 | **0 errors, 0 warnings** | V6 원본 소스 |
| 생산 빌드 | **PASS** | Vite 1,063 modules |
| Ruff·Basedpyright | **PASS / 0 errors, 0 warnings** | 최종 변경 생산 Python |
| no-excuse 규칙 | **0 violations** | 최종 변경 Python·TypeScript |
| 런타임 API | **PASS** | `NO_GO` 검색에 대상 run 포함, 산출물 23개 중 `.kq` 20개 |
| 브라우저 UX | **PASS** | 연구·차트·모델 20개·NO-GO·미로드·미승격 표시 |

| 독립 검토 | 판정 | 주요 확인 |
|---|---|---|
| 목표·제약 검토 | **PASS** | 사전등록, 20개 모델, 비용, TEST/Fresh OOS 경계 |
| 코드 품질 검토 | **PASS** | 기존 MAJOR 0, 전체 466 frontend test 통과 |
| 보안 검토 | **PASS** | CRITICAL/HIGH/MEDIUM 0, 체크포인트·JSON junction 차단 |
| 실제 QA | **PASS** | 실제 `.kq` load, 손상 파일 거부, API·빌드·브라우저 |
| 요구사항 맥락 검토 | **PASS** | 연구-only·fail-closed 정책과 구현 일치 |

남은 낮은 위험은 두 가지다. 현재 status 필터가 부분 문자열 방식이라 미래의 `GO` 검색이 `NO_GO`까지 포함할 수 있으며, reparse guard는 Windows 구현이 주 대상이다. 현재 일봉 CQL 실행·판정·Windows 배포의 차단 조건은 아니지만 다음 개발 주기에 exact status-family 비교와 POSIX symlink 테스트를 추가한다.

## 11. Git·릴리스 경계

- 기능 브랜치: `codex/v1.29.0-dev-market-cql`, 삭제하지 않는다.
- 품질 gate와 독립 리뷰가 통과하면 `develop/v1.29.0-dev`에 `--no-ff` 병합한다.
- 경제 gate가 실패했으므로 `main` 병합, `v1.29.0` 정식 태그, live/paper 승격은 하지 않는다.
- 다음 연구는 새 가설 커밋 뒤 별도 기능 브랜치에서 진행하되 동일 `v1.29.0-dev` 개발선에 병합한다.
