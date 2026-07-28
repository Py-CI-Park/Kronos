# Kronos 대시보드 V6 · Type1 연구 릴리즈 및 핸드오프

- 작성일: 2026-07-25
- 대상 브랜치: `research/type1-closing-rl-v1`
- 기준 구현 커밋: `6676dd0344b146067f06455445689c2b49cf0fe5`
- 이번 릴리즈 태그: `fork-v1.7.0-kronos-dashboard-v6-type1`
- 공식 로컬 주소: `http://127.0.0.1:8122/?ui=v6&tab=home`
- 제품 성격: 로컬·읽기 전용 연구 대시보드
- 연구 판정: `COMPLETE / NO_GO`
- Fresh OOS: `NOT_RUN`·미열람

## 1. 결론: 현재 대시보드는 무엇인가

현재 공식 로컬 대시보드 셸은 **V6**이다. 제품명은 버전과 분리하여 **Kronos Dashboard**로 부르고, 구현 셸/URL/API 계약을 구분할 때만 `V6`를 사용한다.

| 구분 | 현재 값 | 의미 |
|---|---|---|
| 제품명 | Kronos Dashboard | 사용자에게 안내할 제품명 |
| 공식 UI 셸 | V6 (`v6.0`) | 8122에서 기본으로 제공되는 화면 구조 |
| 공식 URL | `/?ui=v6&tab=home` | V6를 명시적으로 여는 정규 URL |
| 저장소 릴리즈 | `fork-v1.7.0-kronos-dashboard-v6-type1` | 이번 Type1 연구 통합 릴리즈 태그 |
| Type1 연구 버전 | `v1.0 RL 종가 매매 - Type 1` | 대시보드 버전이 아니라 연구 모델/계약 이름 |
| V8/M3E | 별도 연구 라인 | V6 셸 버전과 무관한 실험·증거 세대 |

### 왜 V7처럼 보였는가

이전 태그 `fork-v1.6.0-dashboard-v7-rl-reports`는 이름에 `dashboard-v7`이 들어가지만, 태그 메시지 자체가 **“V6 is the local 8122 default”**라고 명시한다. 여기서 V7은 당시 보고서 기능/계획 세대를 나타낸 레거시 릴리즈 이름이고, 실제 기본 UI 셸을 V7으로 전환한 릴리즈가 아니다.

따라서 다음 세 숫자를 섞어 읽으면 안 된다.

1. `fork-v1.7.0`: 저장소 릴리즈 SemVer
2. `V6`: 현재 공식 UI 셸과 API 경로
3. `Type1 v1.0`: 종가 매매 강화학습 연구 계약

이번 정리에서 V6 화면의 `v6.0-dev` 표기를 `v6.0`으로 바꾸어 릴리즈 상태를 명시했다. 앞으로 릴리즈 태그에 `dashboard-v7`처럼 셸 버전과 오해될 표현을 쓰지 않는다.

## 2. 이전 릴리즈 이후 변경 범위

비교 기준은 `fork-v1.6.0-dashboard-v7-rl-reports` (`df58d56`)이며, 현재 Type1 기준 구현은 `6676dd0`이다. 그 사이에는 Type1 계약·환경·학습·권한·보관·보고서·V6 표시까지 30개 이상의 구현 커밋과 약 115개 파일 변경이 포함된다.

| 영역 | 완료 내용 | 상태 |
|---|---|---|
| 연구 계약 | 사전등록, 고정 비용·자본·행동·검증 계약 | 완료 |
| RL 환경 | 순차 포트폴리오 환경, 마스크, STOP, 2세션 시간 순서 | 완료 |
| 회계 | Decimal 기반 고정 명목금액, 왕복 23bp 비용 | 완료 |
| 학습 | MaskablePPO 기본 5 seed + 셔플 통제 5 seed | 완료 |
| 학습량 | 모델별 200,000 timesteps | 완료 |
| 권한 체인 | KRX 공개 근거, 동결 권한, 데이터 materialization | 완료 |
| 장애 보존 | 원본 BLOCK receipt를 byte 단위로 보존 | 완료 |
| 복구 | 저장 모델 append-only 재평가; 재학습 없음 | 완료 |
| Fresh OOS | 봉인 상태 `NOT_RUN/no-read` 유지 | 완료 |
| 보고서 | SHA 고정 7탭 HTML, 카탈로그, custody chain | 완료 |
| V6 API | runs, run-detail, reports, exact-SHA HTML 투영 | 완료 |
| V6 화면 | Home/Data/Experiment/Training/Evaluation/Compare/Report | 완료 |
| 검증 | Type1 통합 회귀 180개 통과 | 완료 |
| 최종 판정 | 검증 기준 미충족으로 `NO_GO` | 완료된 연구 결과 |

## 3. 현재 증거 식별자

| 증거 | 값 |
|---|---|
| 데이터셋 | `type1-close-20260803-005` |
| 실행 | `train_type1-public-005` |
| 모델 | Primary 5 + shuffled-reward control 5 |
| 원본 BLOCK receipt SHA-256 | `db9c6b6b0e92dc6ca4514aa43b4063ffc506ec50e731b57a08da6d2000defec9` |
| Recovery manifest SHA-256 | `5bb355005ff3edc88122e2d34a2bc8c74834061488f60df6eedf74403cd5b312` |
| Publication receipt SHA-256 | `4db3d1bdbd363c944fc2ebb99e3d68cfd926890e5079b048e9b3e13d59ebedd3` |
| HTML 보고서 SHA-256 | `bb60bf426235387999cc75a6aae461330053a9664cf02a63e527142e8fc777d1` |
| 실행 상태 | `COMPLETE` |
| 판정 | `NO_GO` |
| 복구 모드 | `RECOVERED_AFTER_BLOCK` |
| Fresh OOS | `NOT_RUN/no-read` |

`COMPLETE`는 파이프라인이 끝났다는 뜻이고, `NO_GO`는 모델이 채택 기준을 통과하지 못했다는 뜻이다. 수익성·실거래·브로커 연결·운용 준비 완료를 의미하지 않는다.

## 4. 이번 릴리즈에서 정리한 버전 규칙

### 4.1 반드시 사용할 표현

- 제품: `Kronos Dashboard`
- 현재 셸: `V6` 또는 `V6 shell`
- 저장소 릴리즈: `fork-v1.7.0-kronos-dashboard-v6-type1`
- 모델: `Type1 sequential MaskablePPO`
- 결과: `COMPLETE / NO_GO`
- 미개봉 검증: `Fresh OOS NOT_RUN/no-read`

### 4.2 사용하지 않을 표현

- 현재 UI를 `V7 대시보드`라고 부르지 않는다.
- Type1을 수익 모델, 실거래 모델, 운영 준비 완료 모델이라고 부르지 않는다.
- `COMPLETE`를 `GO`와 같은 의미로 쓰지 않는다.
- V8 M3E contextual-bandit 결과를 Type1 순차 RL 결과와 합치지 않는다.

### 4.3 다음 릴리즈 태그 원칙

`fork-v<저장소 버전>-kronos-dashboard-v6-<기능>` 형식을 사용한다. 실제 V7 셸을 만들기 전에는 태그에 `dashboard-v7`을 넣지 않는다. V7 전환은 별도 ADR, URL/라우팅 계약, 마이그레이션 계획, 회귀 테스트를 갖춘 경우에만 진행한다.

## 5. 운영 및 재현 명령

### 5.1 대시보드 시작

```bat
start_kronos_dashboard_quiet.bat
```

정규 접속 주소:

```text
http://127.0.0.1:8122/?ui=v6&tab=home
```

상태 확인:

```powershell
py -3.11 -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8122/api/v6/status', timeout=30); print(r.status)"
```

주의: 현재 8122는 로컬 Flask 개발 서버다. 로컬 연구 용도에는 맞지만 외부 공개 운영 서버로 간주하지 않는다. 긴 `/api/v6/runs` 호출이 단일 서버 처리에서 지연된 사례가 있으므로 향후 성능 작업에서는 프로파일링·캐시·WSGI 전환을 별도 검토한다.

### 5.2 핵심 회귀 테스트

```powershell
py -3.11 -m pytest tests/test_daily_type1_public_run.py tests/test_daily_type1_publication.py tests/test_daily_v1_type1_report.py tests/test_v6_platform_type1_reports.py -q
```

최종 관측 결과: `180 passed`.

V6 API 집중 검증:

```powershell
py -3.11 -m pytest tests/test_v6_platform_api.py tests/test_v6_platform_type1_reports.py -q
```

### 5.3 프런트엔드 검증과 빌드

```powershell
cd webui/v2_src
npm run check
npm run build
```

Node는 프로젝트 규칙에 따라 20 또는 22, npm은 9 이상을 사용한다. `webui/static/v2/dist/`는 생성물이며 소스 변경 뒤에만 갱신한다.

## 6. 작업 재개 시 읽을 순서

1. 이 문서
2. `docs/kronos_type1_closing_implementation_2026-07-23.md`
3. `docs/kronos_type1_g002_public_protocol_2026-07-23.json`
4. 최신 recovery amendment인 `docs/kronos_type1_g002_recovery_amendment_v4_2026-07-24.json`
5. `stom_rl/daily_type1_contract.py`
6. `stom_rl/daily_type1_env.py`
7. `stom_rl/daily_type1_public_run.py`
8. `stom_rl/daily_type1_publication.py`
9. `stom_rl/daily_v1_type1_report.py`
10. `webui/v6_platform_api.py`
11. `webui/v2_src/src/v6shell/`

생성된 `webui/rl_runs/` 한 건만 보고 설계를 바꾸지 않는다. 사전등록·권한 envelope·receipt·카탈로그를 함께 확인한다.

## 7. 앞으로 해야 할 일

현재 승인된 Type1 v1.0 구현 범위에는 필수 잔여 작업이 없다. 다음 작업은 새 연구 또는 운영 품질 개선이며, 현재 완료 상태와 구분한다.

| 우선순위 | 추천 작업 | 목적 | 시작 조건 | 완료 기준 |
|---:|---|---|---|---|
| P0 | 8122 성능 계측 | `/api/v6/runs` 지연 원인 규명 | 현재 증거를 변경하지 않는 별도 브랜치 | p50/p95, 병목, 개선 전후 수치와 회귀 테스트 |
| P0 | 릴리즈 메타데이터 단일화 | package/UI/tag 혼동 제거 | 버전 ADR 승인 | 한 파일에서 제품 릴리즈·셸·API 계약을 명시하고 테스트 |
| P1 | Type1 실패 분석 | NO_GO 원인 분해 | Fresh OOS를 열지 않는 새 사전등록 | seed·보상·회전율·비용·통제군 기여 보고서 |
| P1 | 보상/행동 가설 Type2 | Type1과 독립된 후속 RL 연구 | 새 가설과 acceptance gate 사전등록 | reused-validation까지 완료; 실패도 보존 |
| P1 | 보고서 시각화 개선 | seed 분산, 비용, turnover, controls 비교 강화 | 기존 SHA 보고서 불변 유지 | 새 revision으로만 발행, 과거 보고서 미변경 |
| P2 | WSGI 로컬 운영 옵션 | Flask 개발 서버 장기 점유 완화 | 성능 계측 결과 | loopback 전용, start/stop 문서, health check |
| P2 | 실제 Fresh OOS 실행 | 최종 일반화 검증 | 외부 권한과 명시적 승인 | 단 한 번 실행, append-only receipt; 재선택 금지 |

Fresh OOS 실행은 자동 다음 단계가 아니다. 외부 권한과 명시적 승인 전에는 계속 `NOT_RUN/no-read`로 둔다.

## 8. 권장 브랜치와 병합 전략

다음 작업은 이번 릴리즈 태그에서 새 브랜치를 만든다.

```powershell
git switch -c perf/v6-api-observability fork-v1.7.0-kronos-dashboard-v6-type1
```

권장 순서:

1. `perf/v6-api-observability`: 읽기 전용 API 계측과 성능 개선
2. `research/type1-failure-analysis`: 기존 NO_GO의 원인 분석만 수행
3. `research/type2-prereg`: 새 보상/행동 가설 사전등록
4. `feature/v6-report-visuals`: 불변 보고서 revision과 시각화

브랜치마다 소스·테스트·문서를 하나의 검증 단위로 유지하고, 생성 실험 산출물은 소스 커밋과 분리한다. 이전 연구 판정과 receipt를 수정하거나 squashing으로 숨기지 않는다.

## 9. 다음 작업자 핸드오프 체크리스트

- [ ] 현재 브랜치와 기준 태그를 확인한다.
- [ ] `git status --short`가 깨끗한지 확인한다.
- [ ] 공식 셸은 V6임을 확인한다.
- [ ] Type1 결과가 `COMPLETE / NO_GO`인지 확인한다.
- [ ] Fresh OOS가 `NOT_RUN/no-read`인지 확인한다.
- [ ] 원본 BLOCK receipt SHA가 보존되는지 확인한다.
- [ ] 새 실험이면 새 사전등록과 새 브랜치를 만든다.
- [ ] 23bp 비용, fixed-notional, 5-seed, shuffle controls를 임의로 바꾸지 않는다.
- [ ] 대시보드 시각화를 투자 성과 증거로 해석하지 않는다.
- [ ] 변경 후 집중 테스트, 전체 관련 테스트, 브라우저 검증을 수행한다.

## 10. 현재 완료 판정

| 범위 | 진행률 | 잔여 |
|---|---:|---:|
| Type1 v1.0 계약·환경 | 100% | 없음 |
| 학습·통제군 | 100% | 없음 |
| 공개 권한·보관 | 100% | 없음 |
| 불변 보고서 | 100% | 없음 |
| V6 대시보드 통합 | 100% | 없음 |
| 내구성 목표·품질 게이트 | 100% | 없음 |
| 수익성/실거래 준비 | 0%로 간주 | 현재 `NO_GO`; 별도 연구 필요 |

이번 릴리즈의 의미는 **연구 시스템과 증거 관리가 완료되었다**는 것이다. 모델의 채택 또는 수익성이 입증되었다는 뜻은 아니다.
