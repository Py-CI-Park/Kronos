# Kronos 강화학습 계속 진행 판단 및 대시보드 직접 검토 가이드

- 작성일: 2026-08-01 KST
- 기준 브랜치: `codex/rl-continuation-decision-review-v1`
- 기준 의사결정 커밋: `ff64dd44c978ce80b05f7f88c3b525878b2fbf0e`
- 기준 릴리스: `fork-v1.20.0-kronos-rl-d6r2-mdp-falsification`
- 공식 대시보드: `http://127.0.0.1:5070/`
- RL 연구 화면: `http://127.0.0.1:5070/rl`
- 운영 경계: loopback 전용 로컬 연구 화면, read-only evidence, 실거래 기능 아님

## 1. 가장 쉬운 현재 상태 설명

Kronos는 강화학습 모델을 만들고 학습시키고 비교하는 연구 장비는 잘 갖춰졌다. 실제 SB3 DQN 모델도 생성됐다. 문제는 현재 모델이 사용하는 top-5 후보, 14개 feature와 horizon에서 거래 비용 이후의 안정적인 예측 신호를 찾지 못했다는 점이다.

자동차에 비유하면 계기판과 엔진은 작동하지만 길 안내가 잘못된 상태다. 같은 길 안내를 두고 엔진을 더 오래 돌리거나 가속하는 것은 해결책이 아니다. 먼저 새로운 길 안내가 실제로 방향을 맞히는지 저비용 검사로 확인하고, 그 다음 운전 행동이 차량의 다음 상태를 바꾸는 제대로 된 시뮬레이터에서 강화학습이 가능한지 확인해야 한다.

| 구분 | 현재 상태 | 쉬운 뜻 |
|---|---:|---|
| D6R2 실행 완료율 | 100% | 계획했던 실험은 모두 끝남 |
| 연구 플랫폼 | 90/100 | 실패·성공·비용·데이터 경계를 추적 가능 |
| 재현성·증거 | 96/100 | 결과 해시·receipt·custody를 보존 |
| 대시보드 UX/UI | 90/100 | 결과와 실패 원인을 화면에서 검토 가능 |
| 현재 RL 모델 성능 | 18/100 | 거래 후보로 승격 불가 |
| 실거래 준비도 | 0~5/100 | 로컬 연구 단계 |

## 2. 현재 의사결정

전체 강화학습 연구를 중단하는 것이 아니라, 실패한 기존 lane을 종료하고 새 문제 정의로 피벗한다.

| 연구/작업 | 결정 | 이유 |
|---|---|---|
| 기존 top-5/14-feature DQN 반복 | `STOP` | validation·fold·seed·ridge signal floor 모두 실패 |
| 기존 validation을 보며 재튜닝 | `PROHIBITED` | 이미 읽은 데이터에 추가 과적합 |
| D7 Fresh OOS 즉시 실행 | `LOCKED` | 검증할 새 candidate가 없음 |
| 새 feature/horizon supervised floor | `GO` | 가장 싸게 비용 후 신호 존재 여부를 확인 |
| stateful portfolio MDP 합성검증 | `GO` | RL 환경 자체가 올바른지 시장 데이터 전에 검증 |
| 실제 시장 stateful RL | `HOLD` | 앞의 두 단계가 모두 통과해야 함 |
| 대시보드 compact index/cache | `GO` | 연구 결론과 독립적인 사용자 체감 성능 개선 |

## 3. 실행 및 접속 방법

### 실행 환경

```powershell
cd D:\Chanil_Park\Project\Programming\Kronos
$env:KRONOS_WEBUI_PORT = "5070"
$env:KRONOS_WEBUI_HOST = "127.0.0.1"
$env:KRONOS_WEBUI_OPEN_BROWSER = "0"
py -3.11 webui\run.py
```

### 접속 주소

| 주소 | 목적 |
|---|---|
| `http://127.0.0.1:5070/` | 공식 Kronos 홈 |
| `http://127.0.0.1:5070/rl` | 공식 RL 연구·증거 화면 |
| `http://127.0.0.1:5070/learning-now` | 읽기 전용 현재 학습/증거 화면 |
| `http://127.0.0.1:5070/v1/` | 과거 legacy 화면, 비교가 필요할 때만 사용 |

서버는 `127.0.0.1`에만 바인딩한다. 외부 네트워크에서 접속할 수 있는 운영 서버로 사용하지 않는다.

## 4. 직접 검토 권장 순서

| 순서 | 페이지 | 확인 질문 | 기대 상태 |
|---:|---|---|---|
| 1 | Home | 현재 연구가 성공인지 실패인지 즉시 이해되는가 | D6R2 NO-GO와 D7 잠금이 보여야 함 |
| 2 | Program Scorecard | 플랫폼 점수와 모델 성능이 분리되어 있는가 | 플랫폼 약 90, 모델 18을 혼동하지 않아야 함 |
| 3 | Discovery Lab | D4~D6R2 실패 계보와 최신 판정이 보이는가 | D6R2 70/70, 2/13 gate, NO-GO |
| 4 | Data | train/validation/OOS 경계와 비용·feature가 보이는가 | 573 TRAIN_ONLY, fold-local, D7 no-read |
| 5 | Experiment | 사전등록·seed·fold·control이 결과보다 먼저 고정됐는가 | prereg와 stop rule 확인 가능 |
| 6 | Training | 모델 생성과 모델 성공이 분리되어 있는가 | 60 DQN·3M steps와 NO-GO 동시 표시 |
| 7 | Evaluation | 보상·accuracy·drawdown·trade rate가 기준과 함께 보이는가 | 실패 수치를 숨기지 않아야 함 |
| 8 | Compare | RL·ridge·shuffle·no-trade·RULE이 섞이지 않는가 | 비교 가능 범위와 INELIGIBLE 명시 |
| 9 | Report | 결과·실패 사유·SHA·custody가 연결되는가 | 보고서와 증거 계보 확인 가능 |
| 10 | Insights | 관찰이 수익성 증거로 오해되지 않는가 | observation-only 경계 표시 |
| 11 | Other Lanes | `ts_imb` RULE을 RL로 부르지 않는가 | RULE/RL 분리 |
| 12 | Settings | 로컬·read-only·실행 권한 경계가 보이는가 | live/broker 기능 없음 |

## 5. 전체 12페이지 상세 검토표

| 페이지 | 현재 역할 | 현재 완료 상태 | 화면에서 확인할 항목 | 다음 개발 항목 | 예상 |
|---|---|---:|---|---|---:|
| Home | 전체 상태와 빠른 이동 | 100% | D6R2 NO-GO, D7 LOCKED, 연구/실거래 경계 | 기존 lane 종료와 새 Phase A 준비 상태 요약 | 30분 |
| Program Scorecard | 프로그램과 모델 점수 감사 | 100% | 플랫폼 90과 모델 18 분리, live readiness 0~5 | 새 연구 단계별 점수와 hard stop 표시 | 30분 |
| Discovery Lab | D0~D7 연구 계보 | 100% | D6R2 70/70, 13 gate 중 2 pass, ridge 비-RL | Phase A/B/C 상태와 잠금 조건 추가 | 1~2시간 |
| Data | 입력·기간·split·SHA | 100% | 573 TRAIN_ONLY, fold-local scaler, D6/D7 no-read | 새 feature/horizon registry | 4~8시간 |
| Experiment | 가설·사전등록·실험 행렬 | 100% | gamma 0/1, native/shuffle, 3 seeds, 5 folds | signal-floor prereg와 kill gate | 2~4시간 |
| Training | 실제 학습 실행과 모델 | 100% | DQN 60개, 총 3M steps, invalid action 0 | Phase A 통과 전 실제 RL 실행 잠금 | 2~4시간 |
| Evaluation | 비용·성과·안정성 평가 | 100% | 23bp, reward -0.1276, accuracy 0.16, DD 44.24% | 새 feature 5-fold+shuffle 자동 gate | 4~8시간 |
| Compare | 호환 가능한 증거 비교 | 100% | DQN/ridge/shuffle/no-trade/RULE 구분 | 기존 D6R2와 새 후보 side-by-side | 2~4시간 |
| Report | 판정·문서·custody | 100% | verdict, failures, producer, manifest, receipt SHA | 계속 진행 판단 문서 연결 | 1~2시간 |
| Insights | 종목·수급·시장 국면 관찰 | 76% | 관찰 전용, RL 점수에 합산 금지 | feature·기간별 실패 원인 설명 | 2~4시간 |
| Other Lanes | 인트라데이·Kronos·RULE 분리 | 73% | `ts_imb` RULE과 RL 성과 분리 | 비교 불가 lane을 더 명확히 표시 | 1~2시간 |
| Settings | 로컬 환경과 안전 경계 | 84% | loopback, read-only, no broker/live | compact evidence cache와 권한 분리 | 2~4시간 |

## 6. D6R2 화면에서 확인해야 할 정확한 수치

| 항목 | 기대값 | 해석 |
|---|---:|---|
| Verdict | `D6R2_TOP5_SIGNAL_FLOOR_NOT_CONFIRMED` | 현재 lane 종료 |
| Planned/complete units | `70/70` | 실험 실행 완료 |
| 실제 DQN 모델 | `60` | 모델 생성 성공 |
| DQN 학습량 | `3,000,000 steps` | 학습 자체는 실행됨 |
| ridge 모델 | `10` | 비-RL signal floor |
| Gate | `2/13 PASS` | 성능은 NO-GO |
| gamma=0 accuracy | `0.1600` | 6-action random 0.1667 부근 |
| gamma=0 reward ratio | `-0.127615` | 비용 후 음수 |
| gamma=0 vs gamma=1 | `-0.031489` | gamma=0 개선 없음 |
| gamma=0 vs shuffled | `+0.013654` | 등록 기준 +0.10 미달 |
| Positive folds | `0/5` | 시간 안정성 없음 |
| Positive seeds | `0/3` | 초기화 안정성 없음 |
| Trade rate | `0.90` | 과도 거래 |
| Drawdown | `0.442444` | 25% 상한 초과 |
| ridge reward ratio | `-0.152520` | 현재 feature 신호 바닥 실패 |
| D7 | `LOCKED` / `NOT_RUN_NO_READ` | 새 후보 전 데이터 개방 금지 |

표시값이 위와 다르거나 일부 artifact가 빠진 경우 성공으로 해석하지 말고 `BLOCKED/STALE/EVIDENCE_MISMATCH`로 검토한다.

## 7. UX/UI 검토 체크리스트

| 영역 | 확인 사항 | 합격 기준 |
|---|---|---|
| 첫 화면 이해 | 성공/실패 여부를 5초 안에 이해할 수 있는가 | NO-GO·18점·D7 잠금이 상단에 명확 |
| 용어 | DQN과 ridge, RULE이 구분되는가 | ridge는 비-RL, `ts_imb`는 RULE로 표시 |
| 색상 | 실패가 성공처럼 보이지 않는가 | FAIL/NO-GO는 danger 계열, 통과 수치와 분리 |
| 기준 비교 | 측정값만 있고 기준이 빠지지 않았는가 | 기준·측정·PASS/FAIL 동시 표시 |
| 데이터 경계 | TRAIN_ONLY와 OOS를 혼동하지 않는가 | split과 no-read 상태가 항상 보임 |
| 비용 | 0bp 결과가 primary로 보이지 않는가 | 23bp primary, 0bp diagnostic 명시 |
| 반응형 | 모바일에서 표·카드가 잘리지 않는가 | 360px에서 문서 가로 overflow 0 |
| 접근성 | 키보드와 상태 텍스트로 이해 가능한가 | 색상만으로 상태를 전달하지 않음 |
| 오류 상태 | API 지연/실패가 빈 화면이 되지 않는가 | loading, retry, blocked 메시지 제공 |
| 성능 | 최초 evidence 검증 지연이 설명되는가 | 로딩 상태 표시, 목표 first view <5초 |

## 8. 연구 타당성 검토 체크리스트

| 검토 질문 | 현재 답 | 다음 승인 조건 |
|---|---|---|
| 현재 feature에 비용 후 신호가 있는가 | 확인되지 않음 | 새 feature/horizon supervised floor 통과 |
| RL이 필요한 순차 문제인가 | 현재 환경은 contextual에 가까움 | action-dependent stateful MDP |
| 모델이 train 밖에서 유지되는가 | D6에서 실패 | 새 sealed 기간 전 nested fold 통과 |
| 비용만 제거하면 되는가 | 아님, 0bp도 음수 | gross signal 자체 양수 필요 |
| 학습량을 늘리면 되는가 | 아님, D5R에서 악화 | 추가 step sweep 금지 |
| seed를 늘리면 되는가 | 0/3 양수 | 가설 변경 없이 seed 추가 금지 |
| D7을 열 가치가 있는가 | 없음 | Phase A+B+C 통과 candidate 필요 |

## 9. 다음 연구 단계와 화면 연결

| 단계 | 연구 작업 | 주로 사용할 페이지 | 통과 조건 | 실패 시 |
|---:|---|---|---|---|
| A | 새 feature/horizon signal floor | Data → Experiment → Evaluation → Compare | 23bp 양수, shuffle delta, 4/5 folds, DD | 해당 가설 종료 |
| B | stateful MDP 합성 learnability | Experiment → Training → Evaluation | 전이 불변식 100%, 알려진 정책 3 seeds | 실제 데이터 RL 금지 |
| C | 최소 nested real-data pilot | Training → Evaluation → Compare → Report | prereg gate 전부 통과 | 후보 종료, D7 잠금 |
| D | 새 sealed OOS 단 1회 | Report 중심 | 비용·drawdown·baseline·control 통과 | 모델 폐기 |
| E | paper forward | 별도 운영 화면 필요 | 실제 시간·지연·체결 gate | live 금지 |

## 10. 검토 후 선택 가능한 액션

| 검토 결과 | 다음 액션 |
|---|---|
| 화면과 문서가 이해 가능하고 수치 일치 | 현재 문서 PR→master 병합 후 Phase A prereg 시작 |
| NO-GO가 잘 보이지 않음 | Home·Scorecard·Discovery UX부터 수정 |
| 수치 또는 SHA 불일치 | 연구 중단, custody/API 원인 조사 |
| 첫 화면이 지나치게 느림 | compact index/cache를 먼저 구현 |
| 새 feature 가설이 없음 | 시장 데이터 RL 중단, 합성 MDP 플랫폼 연구만 진행 |
| 새 feature floor 실패 | 해당 가설 종료, 실제 RL 실행하지 않음 |
| signal floor와 합성 MDP 모두 통과 | 작은 Phase C pilot만 승인 |

## 11. 예상 일정

| 작업 | 예상 |
|---|---:|
| 현재 문서·대시보드 직접 검토 | 30~60분 |
| compact evidence cache | 2~4시간 |
| 새 feature/horizon signal floor | 1~2일 |
| stateful MDP 합성검증 | 1.5~3일 |
| 최소 실제 데이터 pilot | 1~3일+연산 |
| 1차 피벗 연구 전체 | 약 4~8 작업일 |
| 수익 모델·실거래 | 현재 보장하거나 일정 산정할 수 없음 |

## 12. 검토 완료 체크박스

- [ ] Home에서 D6R2 NO-GO와 D7 LOCKED를 확인했다.
- [ ] Program Scorecard에서 플랫폼 점수와 모델 18점을 구분했다.
- [ ] Discovery Lab에서 70/70과 2/13 gate를 확인했다.
- [ ] Data에서 TRAIN_ONLY와 OOS no-read 경계를 확인했다.
- [ ] Training에서 모델 생성과 모델 성공이 다른 개념임을 확인했다.
- [ ] Evaluation에서 23bp·reward·accuracy·drawdown을 확인했다.
- [ ] Compare에서 DQN·ridge·shuffle·RULE 구분을 확인했다.
- [ ] Report에서 SHA·receipt·custody를 확인했다.
- [ ] 모바일 또는 좁은 화면에서 가로 overflow가 없는지 확인했다.
- [ ] 다음 액션을 기존 튜닝이 아니라 Phase A 또는 B로 선택했다.

## 13. 관련 문서

- [`kronos_rl_continuation_decision_review_2026-07-31.md`](kronos_rl_continuation_decision_review_2026-07-31.md): 계속 진행 타당성 및 kill gate 상세
- [`kronos_rl_discovery_type2_d6r2_result_2026-07-31.md`](kronos_rl_discovery_type2_d6r2_result_2026-07-31.md): D6R2 정량 결과
- [`kronos_rl_discovery_type2_d6r2_program_report_2026-07-31.md`](kronos_rl_discovery_type2_d6r2_program_report_2026-07-31.md): 프로그램 진행·UX/UI·Git 결과
- [`evidence/type2-d6r2-primary-20260731-001.custody.json`](evidence/type2-d6r2-primary-20260731-001.custody.json): 장기 증거 custody

이 검토의 핵심은 모델 점수를 억지로 20점 이상으로 높이는 것이 아니다. 새 신호가 있는지 먼저 확인하고, 올바른 순차 MDP가 합성 환경에서 학습되는지 확인한 뒤에만 실제 시장 RL 비용을 지출하는 것이다.

## 14. Quantylab ETF 신규 lane 검토 항목

외부 설계 검토 후 다음 대시보드 업데이트 후보가 추가됐다.

| 페이지 | 추가 검토 항목 |
|---|---|
| Home | `ETF STATEFUL MDP · CANDIDATE · NOT RUN` 표시 |
| Scorecard | 기존 모델 18과 ETF lane 연구 준비도 44를 분리 |
| Discovery | Q0~Q7 신규 lane, 기존 D7 잠금 유지 |
| Data | point-in-time ETF universe, raw/as-of timestamp, bfill 0 |
| Experiment | 9/23bp, reward 3-arm, Residual MLP first |
| Training | PPO entropy, policy std, action histogram, trade rate |
| Evaluation | 5fold×3seed, shuffle, no-trade, momentum, MDD/Sharpe/Calmar |
| Compare | 기존 stock top-5와 ETF lane cross-rank 금지 |
| Report | external design reference와 Kronos 실행 evidence 분리 |

상세 근거는 [`kronos_quantylab_rl_etf_content_review_2026-08-01.md`](kronos_quantylab_rl_etf_content_review_2026-08-01.md)를 따른다. 이 외부 자료는 성과 evidence가 아니라 신규 prereg 설계 입력이다.
