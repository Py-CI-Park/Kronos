# Kronos 일봉 종가매매 강화학습 복구 결과

- 기준일: 2026-08-02 KST
- 작업 브랜치: `codex/rl-close-recovery-v1`
- 부모 브랜치: `codex/rl-etf-stateful-mdp-v1`
- 선행 감사: `docs/kronos_daily_close_rl_recovery_audit_2026-08-02.md`
- 성격: 로컬 연구·백테스트·증거 대시보드
- 라이브 주문·수익성·브로커 준비도: **주장하지 않음**

## 1. 최종 결론

강화학습 모델 생성은 이미 성공해 있었다. `type1-close-20260803-005 / train_type1-public-005` 아래에 실제 Sequential MaskablePPO 주 모델 5개와 shuffled-reward 통제 모델 5개가 있고, 각 seed는 200,000 step을 기록한다.

이번 작업은 Windows 줄바꿈과 과거 보고서 검증 규칙 때문에 이 모델이 `MISSING` 또는 `TYPE1_CATALOG_INVALID`로 숨겨지던 문제를 복구했다. 실제 API와 학습 화면은 이제 다음을 동시에 표시한다.

| 질문 | 최종 답 | 근거 |
|---|---|---|
| 강화학습 모델이 만들어졌는가 | **예** | 주 5개 + 셔플 통제 5개 `final_model.zip`, seed당 200,000 step |
| 학습 실행은 완료됐는가 | **예** | `state=COMPLETE`, `training_state=COMPLETE` |
| 모델이 경제적으로 성공했는가 | **아니오** | `verdict=NO_GO`, local control gate miss |
| Fresh OOS를 열었는가 | **아니오** | `NOT_RUN_NO_READ` 유지 |
| 라이브 매매가 가능한가 | **아니오** | 여섯 promotion/live/profit 잠금 모두 false |
| Kronos가 사라졌는가 | **아니오** | `available=true`, `loaded=false`; 별도 예측 모델 페이지로 복원 |

따라서 이 결과는 **모델 생성 성공 + 증거 노출 복구 성공 + 경제적 성능 NO-GO**이다. 세 판정을 합치거나 모델 파일 존재를 수익성 성공으로 재명명하면 안 된다.

## 2. 왜 수많은 커밋 뒤에도 성공하지 못했는가

| 원인 | 실제 현상 | 이번 조치 | 남은 연구 |
|---|---|---|---|
| 모델과 수익성의 정의 혼합 | 모델 파일은 있는데 화면은 `MISSING`, 사용자는 모델 미생성으로 이해 | 생성·학습·경제 판정을 분리 | 성능 GO는 별도 OOS gate로만 판단 |
| Windows CRLF와 LF 영수증 SHA 불일치 | 정상 Git blob을 로컬 raw bytes가 다르다고 차단 | source SHA를 LF 기준으로 정규화하고 `.gitattributes` 고정 | 다른 증거 경로도 동일 원칙 유지 |
| 현재 builder SHA를 과거 revision에 요구 | 코드가 발전할수록 과거 커밋 보고서가 무효화 | 과거 revision은 당시 builder SHA에 결속 | append-only revision 유지 |
| 낮은 신호 대비 23bp 비용 | 네이티브 정책과 supervised floor가 비용 후 음수 | NO-GO를 숨기지 않고 대시보드 노출 | 새 feature 가설과 PIT 데이터 필요 |
| 반복 실험이 새 정보보다 구현을 늘림 | 많은 커밋이 guardrail·UI·custody 개선이고 alpha 정보 증가는 적음 | 플랫폼 점수와 모델 점수 분리 | 같은 top-5/14-feature 반복 종료 |
| API 요청 결합 | 느린 discovery/registry 하나가 전체 화면을 `MISSING`으로 유지 | 독립 로딩과 `LOADING` 상태 도입 | 장기적으로 증거 인덱스 최적화 가능 |
| 같은 모델 묶음 중복 해시 | 여러 탭과 학습 화면이 약 540MB 증거를 동시에 반복 검증 | 프런트 in-flight 공유 + 서버 single-flight | 영구 캐시는 무결성 약화 때문에 도입하지 않음 |
| 상세 manifest 자동 조회 | 목록 뒤 다시 SHA 검증해 초기 화면이 68초까지 지연 | 요약은 `/runs`, 상세는 사용자 선택 뒤 조회 | 상세 버튼의 검증 시간은 계속 명시 |
| Type1 adapter 필드 우선순위 오류 | `status=OK`를 학습 상태로 읽어 `NOT COMPLETED` 표시 | `state=COMPLETE`와 `training_state` 우선 | 새 schema 추가 시 adapter 계약 테스트 |

커밋 수가 많다는 것은 연구 성능이 높다는 뜻이 아니다. 이번 복구 전 커밋의 상당수는 증거 보존, 실패 차단, 화면, 테스트, 브랜치 전달선에 쓰였다. 이것은 플랫폼 품질에는 의미가 있지만 시장 예측 신호를 새로 만들지는 않는다.

## 3. 실제 모델 증거

| 항목 | 값 |
|---|---|
| dataset | `type1-close-20260803-005` |
| train | `train_type1-public-005` |
| family | `TYPE1` |
| algorithm | `Sequential MaskablePPO` |
| 상태 | `COMPLETE` |
| 경제 판정 | `NO_GO` |
| evidence mode | `RECOVERED_AFTER_BLOCK` |
| primary seeds | 0, 1, 2, 3, 4 |
| shuffled-reward seeds | 0, 1, 2, 3, 4 |
| seed당 step | 200,000 |
| 총 모델 artifact | 10 |
| retraining | 수행하지 않음; 저장 모델 재평가 복구 |
| Fresh OOS | `NOT_RUN`, read=false |
| 기준 자본 | 60M fixed-notional |
| 슬롯 | 최대 10, 슬롯당 5M, 예비 10M |
| 실행 가격 | exact 15:20 close proxy; 공식 종가 아님 |
| primary cost | 왕복 23bp |

주 seed validation NAV는 약 37.46M~96.97M으로 seed 분산이 매우 크며, 5-seed IQM은 약 45.46M이다. no-trade 60M보다 낮고 exposure-matched random p95 gate도 통과하지 못했다. 셔플 통제 IQM 약 48.22M보다도 우월하지 않다. 모델 파일이 정상이어도 경제 판정이 NO-GO인 직접 이유다.

## 4. UI/UX 복구 결과

| 화면/문제 | 변경 전 | 변경 후 | 검증 |
|---|---|---|---|
| RL 단계 상태 | 비동기 요청 중 `MISSING` | 완료 전 `LOADING`, 완료 후 원본 상태 | 브라우저 재현 |
| Experiment | draft 없음이 ID/family/state/run_count `MISSING` | `새 사전등록 초안 없음`, 동결 5건, amendment 안내 | old 4-MISSING 없음 |
| Training | Type1 표 `COMPLETE`인데 상단 `NOT RUN` | `NO GO`, 학습 `COMPLETE`, primary 5, shuffled 5, 200,000 | 실제 API와 화면 일치 |
| Training 상세 | 진입 즉시 무거운 상세 SHA 재검증 | 상세 버튼 선택 뒤에만 조회 | `상세 검증 대기` 표시 |
| Kronos | Other Lanes 아래 묻힘 | 독립 V6 페이지 | 사용 가능·미로드·RL 아님 |
| Insights | 입력값 `005930` 한 종목만 노출 | 수급 목록 기반 8개 빠른 종목 선택 | `005930 → 271050` 전환 확인 |
| 글자 넘침 | 1024px 단계 칩과 상태 텍스트가 넘침 | 칩 줄바꿈·반응형 3/2열·브랜드 wrapping | 1024/768/390 문서 넘침 0 |
| 페이지 감사 | 12페이지, 이전 브랜치 | 13페이지, 현재 복구 브랜치 | scorecard 13 PAGES |

브라우저 콘솔의 warning/error는 0건이었다. 차트 접근성용 숨김 설명은 `clientWidth=1`인 screen-reader 텍스트로 확인했으며 문서 폭을 늘리지 않는다.

## 5. 성능 측정

| 시나리오 | 관측 시간 | 의미 |
|---|---:|---|
| 복구 전 다중 요청 + 자동 상세 | 62.52초 | 목록 표시까지 중복 모델 해시 |
| 자동 상세까지 기다린 화면 | 68.51초 | 목록 뒤 상세가 다시 전체 증거 검증 |
| 서버 single-flight 다중 탭 측정 | 18.75초 | 동시 동일 검증 공유, 약 70% 단축 |
| 최종 요약 화면 실측 | 35.30초 | 다른 열린 탭 요청이 있는 조건의 보수적 측정 |

최종 화면은 무거운 상세를 자동 실행하지 않는다. 변동이 큰 로컬 디스크 조건에서도 사용자는 목록 검증 완료 시 `COMPLETE / NO_GO / 5+5 / 200,000` 요약을 먼저 확인할 수 있다. 상세 SHA·seed 표는 명시적 버튼을 눌렀을 때만 다시 검증한다.

## 6. 13개 전체 페이지 진행표

| 번호 | 페이지 | 현재 상태 | 이번 결과 | 남은 행동 | 예상 시간 |
|---:|---|---|---|---|---:|
| 1 | Home | BUILT | 안전 경계·공식 83점 유지 | 실시간 artifact와 snapshot 분리 강화 | 2~4시간 |
| 2 | Program Scorecard | BUILT | 13페이지·현재 브랜치 전달선 반영 | PR URL·태그를 결과 문서와 동기화 | 30분 |
| 3 | Discovery Lab | BUILT / NO-GO | D6R2 70/70, 2/13 gates 유지 | 동일 top-5/14 feature 반복 중단 | 완료 |
| 4 | Data | BUILT / PARTIAL | PIT 부족과 proxy 한계 유지 | PIT universe·identity·available_at·total return | 1~2일+데이터 확보 |
| 5 | Experiment | BUILT / FROZEN | `MISSING` 대신 empty draft·동결 5건 | 새 가설 amendment 동결 | 4~8시간 |
| 6 | Training | BUILT / COMPLETE | Type1 5+5 모델과 NO-GO 정확히 표시 | 새 가설 gate 전 재학습 금지 | gate 후 1~3일 |
| 7 | Evaluation | BUILT / TEST_NOT_RUN | 모델 존재와 OOS 미실행 분리 | Q1 뒤 supervised floor 재검증 | 1~2일 |
| 8 | Compare | BUILT | Type1/M3E/RULE family 분리 | 23bp primary·9bp diagnostic 병렬 표시 | 2~4시간 |
| 9 | Report | BUILT / COMMITTED | Windows에서도 Type1 revision 복구 | 다음 결과 append-only revision | 실행별 1~2시간 |
| 10 | Insights | BUILT / DIAGNOSTIC | 8종목 quick picks와 전환 | 심볼 이름·필터·기간 북마크 | 4~8시간 |
| 11 | Other Lanes | BUILT | 인트라데이·외부 설계 분리 | RL 성과와 합산 금지 유지 | 유지관리 |
| 12 | Kronos | BUILT / AVAILABLE_NOT_LOADED | 독립 페이지와 역할 설명 | PIT feature 가설을 별도 사전등록 | 가설 4~8시간 |
| 13 | Settings | BUILT / READ_ONLY | 기존 안전 상태 유지 | artifact root·cutoff 읽기 전용 표시 | 1~2시간 |

## 7. 점수

### 공식 대시보드 스냅샷

| 점수 | 값 | 해석 |
|---|---:|---|
| 연구 프로그램 완성도 | **83/100** | reviewed snapshot; live artifact나 모델 성능 점수가 아님 |
| 모델 성능 | **18/100** | 23bp 비용, seed 안정성, control, drawdown 기준 실패 |
| ETF 연구 준비도 | **44/100** | Q1 PIT custody와 Q2-A가 막힘 |
| 플랫폼/대시보드 | **90/100** | 증거 표시는 강하지만 긴 무결성 검증과 데이터 custody가 남음 |

### 이번 복구 작업 평가

| 평가 축 | 점수 | 근거 |
|---|---:|---|
| 모델 존재 증명 | 98 | 10개 모델, SHA 결속, API·화면 확인 |
| 판정 정직성 | 97 | COMPLETE와 NO_GO, Fresh OOS NOT_RUN 동시 노출 |
| UX 직관성 | 89 | MISSING/LOADING 분리, Kronos 독립, 다종목 전환 |
| 반응형 UI | 94 | 1024/768/390 문서 넘침 0 |
| 조회 성능 | 76 | 중복 검증 제거와 상세 지연; 단일 전체 SHA 검증은 여전히 무거움 |
| 경제적 성능 | 18 | 기존 공식 실패 판정을 변경할 새 alpha 증거 없음 |

공식 83점을 이번 UX 수정만으로 임의 상향하지 않았다. UI 완성도와 모델 경제성은 별도 축이다.

## 8. 검증 결과

| 검증 | 결과 |
|---|---|
| Type1 report suite | 90 passed |
| V6 platform/API suite | 54 passed |
| Type1 전용 platform report | 7 passed |
| single-flight 및 관련 API | 6 passed |
| V6 프런트 전체 | 408 passed |
| Svelte/TypeScript check | 0 errors, 0 warnings |
| Vite production build | 975 modules transformed, 성공 |
| 실제 run detail | `status=OK`, `state=COMPLETE`, `verdict=NO_GO` |
| 브라우저 | Kronos·Experiment·Training·Insights 시나리오 통과 |
| 콘솔 | warning/error 0 |
| 반응형 | 1024/768/390 문서 폭 초과 0 |

## 9. 다음 강화학습 연구 단계

| 순서 | Gate | 목적 | 통과 조건 | 실패 시 행동 | 예상 시간 |
|---:|---|---|---|---|---:|
| 1 | Q1 데이터 custody | 생존편향·시점 누수 제거 | PIT universe, official identity, available_at, total return 4개 모두 확보 | RL 재학습 금지 | 1~2일+외부 데이터 |
| 2 | Q2-A signal floor | RL 전에 학습 가능한 신호 존재 확인 | 23bp에서 supervised OOS가 no-trade/control 우월, fold 안정 | feature/horizon 가설 폐기 또는 새 amendment | 1~2일 |
| 3 | Q2-B execution/accounting | 종가 전략과 시뮬레이터 일치 | 공식 종가 또는 명시적 proxy, 5M×최대10, fill/cost 일관 | 공식 종가 데이터 확보 전 proxy 연구로 제한 | 0.5~1일 |
| 4 | 새 amendment | 사후 튜닝 방지 | feature·horizon·reward·cost·stop·control 동결 | 기존 결과 수정 금지 | 4~8시간 |
| 5 | Q3 최소 모델 | 과적합 가능성을 통제한 새 모델 | Residual MLP floor 우선, 이후 MaskablePPO 5 seeds + 3 shuffles | 실패 결과 커밋 후 중단 | 1~3일 |
| 6 | Fresh OOS | 최종 반증 | 사전등록 gate 통과 뒤 one-time read | 실패 시 NO-GO 확정 | 데이터 창 형성 뒤 1일 |

가장 빠른 성공 경로는 PPO를 더 오래 돌리는 것이 아니다. 먼저 23bp에서 supervised floor가 살아 있는 새 상태 표현을 찾고, 그 신호가 있을 때만 RL이 포트폴리오 제약·슬롯 선택·보유/교체 결정을 개선하는지 검증해야 한다.

## 10. Git 관리 규칙

앞으로 커밋은 한글 제목과 한글 본문을 사용할 수 있으며 다음 형식을 권장한다.

```text
feat(영역): 사용자가 확인할 수 있는 결과를 한글로 요약하다

무엇을 바꿨는지, 어떤 실패를 막는지, 어떤 테스트로 검증했는지 기록한다.
모델 GO·라이브 준비도와 관계없는 변경이면 그 경계도 명시한다.
```

브랜치는 `codex/<연구-단계>-<목적>-vN` 형태로 만들고, 기능·테스트·문서·생성 번들을 논리적으로 분리한다. 부모 연구 브랜치로 PR을 만들고 전체 테스트와 브라우저 QA 뒤에만 병합한다. 태그는 연구 플랫폼 전달점을 뜻하며 모델 GO를 뜻하지 않는다.

## 11. 이번 브랜치의 주요 커밋

| 커밋 | 목적 |
|---|---|
| `c524e44` | 종가매매 강화학습 실패와 복구 기준 감사 문서 |
| `0d37fff` | Windows에서도 Type1 증거 복구 |
| `e5ea621` | 모델 존재·연구 판정·Kronos·Insights UX 분리 |
| `446fcc7` | 느린 검증을 MISSING으로 오인하지 않도록 비동기 분리 |
| `4b16e83` | 완료된 Type1을 NO_GO로 정확히 요약 |
| `9cfe77b` | 프런트 동시 runs 요청 공유 |
| `130d994` | 서버 동시 Type1 검증 single-flight |
| `e3be94e` | Type1 학습 완료 상태 필드 정정 |
| `5dc688f` | 무거운 상세 검증을 사용자 선택 뒤로 이동 |

정적 번들은 각 관련 소스 커밋 뒤 별도 `build(dashboard)` 커밋으로 보존했다.

