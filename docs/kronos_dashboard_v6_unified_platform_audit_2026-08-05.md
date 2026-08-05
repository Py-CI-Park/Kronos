# Kronos V6 통합 강화학습 플랫폼 전수 감사

- 문서 ID: `KRONOS-V6-UNIFIED-PLATFORM-AUDIT-2026-08-05`
- 감사 기준 브랜치: `develop/v1.28.0-dev`
- 감사 기준 커밋: `685c3f3`
- 감사일: 2026-08-05 KST
- 판정 범위: V6 정보구조, 강화학습 연구 탐색성, 시각화, 실시간 관측성, 반응형, 유지보수성
- 연구 판정 경계: 이 문서는 UX·연구 플랫폼 감사이며 수익성, 실거래 준비도, Fresh OOS 승인을 증명하지 않는다.

## 1. 결론

현재 V6는 연구·증거·안전 경계 구현은 상당히 진행됐지만 사용자가 하나의 실험을 시작해 진행 상황을 보고 결과·모델·문서까지 추적하는 단일 제품 흐름이 없다. 기능 수와 페이지 수는 많지만 페이지별 정보 형식, 카드, 간격, 표, 반응형 규칙이 달라 여러 시기의 연구 화면을 이어 붙인 인상을 준다.

핵심 판정은 다음과 같다.

| 항목 | 현재 판정 | 근거 |
|---|---:|---|
| 연구 구현 완성도 | 78/100 | 환경·비용·DQN/CQL·통제군·증거 산출 구현 |
| 프로그램 종합 성숙도 | 63/100 | 기존 V6 프로그램 점수 |
| 대시보드 UX 성숙도 | 42/100 | 탐색성·일관성·반응형·관측성 감사 점수 |
| RL 시각화·관측성 | 25/100 | 일부 평가 차트는 있으나 통합 학습 모니터 부재 |
| 경제적 모델 성과 | 20/100 | synthetic calibration 모델과 실제 시장 모델을 분리 |
| 실거래 준비도 | 0/100 | 의도적으로 차단됨 |

따라서 다음 개발은 페이지 추가가 아니라 V6를 같은 버전 안에서 `Experiment -> Run -> Metric -> Artifact -> Gate` 계층으로 재구축하는 작업이어야 한다.

## 2. 감사 방법과 범위

### 2.1 소스 전수 목록화

`webui/v2_src/src/v6shell` 전체를 대상으로 Svelte·TypeScript 파일, 페이지 등록, API 호출, chart 사용, style block, media query, 대형 파일을 목록화했다.

| 측정 항목 | 결과 |
|---|---:|
| V6 Svelte 파일 | 31 |
| 개별 `<style>` 블록 | 31 |
| 개별 media query | 29 |
| 최상위 페이지 | 7 |
| RL 하위 단계 | 7 |
| 대형 핵심 파일 | `v6Api.ts` 573줄, `TrainingPage.svelte` 443줄, `ReportPage.svelte` 341줄 |

### 2.2 실행 화면 검사

현재 `http://127.0.0.1:5070`에서 다음을 직접 확인했다.

- 데스크톱 `Other Lanes`
- 데스크톱 `RL / Training`
- 390x844 모바일 `RL / Training`
- 브라우저 DOM과 실제 viewport screenshot
- `/api/v6/status`, `/api/v6/runs` 응답 시간

이번 검사는 대표 경로의 구조·가시성 감사다. 모든 버튼과 모든 데이터 조합에 대한 완전한 E2E는 P2 하드닝 단계의 별도 완료 기준으로 둔다.

## 3. 사용자가 연구를 찾기 어려운 이유

| 사용자의 질문 | 현재 위치 | 구조적 문제 |
|---|---|---|
| 최신 연구가 무엇인가 | Scorecard, Report, 문서 디렉터리 | 단일 latest run authority가 없음 |
| 어떤 모델을 학습했나 | Training, Models artifact, 문서 | 모델·run·dataset 연결 URL이 없음 |
| 학습이 좋아졌나 | Training 하단, Evaluation | reward와 경제 성과가 분리됨 |
| 왜 NO-GO인가 | 공통 상태, Data, Report | 같은 설명이 여러 화면에 반복됨 |
| 과거 연구는 어디 있나 | Other Lanes, V5 링크, docs | V6 안에서 통합 검색이 안 됨 |
| 결과 파일은 어디 있나 | report/artifact 링크 | run 상세에서 한 번에 열 수 없음 |

현재 정보구조는 페이지가 주체다. 연구 플랫폼은 run이 주체여야 한다. 모든 페이지에서 같은 run selector를 사용하고, run detail 하나가 summary·learning·performance·actions·evidence·artifacts·logs를 제공해야 한다.

## 4. 정보구조 감사

현재 최상위 메뉴는 Home, Program Scorecard, Reinforcement Learning, Insights, Kronos Model, Other Lanes, Settings다. RL은 Discovery, Data, Experiment, Training, Evaluation, Compare, Report로 다시 나뉜다.

문제는 다음과 같다.

1. Home과 Scorecard가 모두 프로그램 전체 상태를 설명한다.
2. Kronos Model은 최상위 페이지이면서 Other Lanes 안에 다시 렌더링된다.
3. Insights는 연구 입력 데이터이지만 어떤 run에 사용됐는지 연결되지 않는다.
4. RL의 7단계는 절차를 설명하지만 한 실행의 결과를 모아 보여주지 않는다.
5. 안전 상태, 프로그램 상태, 일봉 연구 상태가 모든 화면 상단에 누적돼 첫 viewport의 대부분을 차지한다.
6. 과거 V5 화면 링크가 V6 안에 남아 사용자가 제품 세대를 오가게 한다.

## 5. 시각 디자인·레이아웃 감사

### 5.1 장점

- Pretendard와 JetBrains Mono 조합이 이미 존재한다.
- 성공·경고·차단 색상 토큰과 chart token이 있다.
- NO-GO, READ-ONLY, Fresh OOS sealed 등 안전 경계가 시각적으로 명확하다.
- ECharts 기반 시각화 기반이 이미 포함돼 있다.

### 5.2 결함

| 결함 | 사용자 영향 |
|---|---|
| 31개 Svelte 파일이 모두 자체 style block 보유 | 카드·표·간격·radius·breakpoint가 화면마다 달라짐 |
| Shell 전체 `style:zoom` | 확대 설정이 layout·overflow 계산을 왜곡할 수 있음 |
| 공통 상태 3단 반복 | 실제 연구 내용이 첫 화면 아래로 밀림 |
| 페이지마다 다른 grid 최소폭 | 특정 해상도에서 카드가 잘리거나 과도하게 늘어남 |
| 표·코드 문자열 줄바꿈 규칙 불일치 | 긴 verdict·artifact id가 레이아웃을 침범 |
| Other Lanes 2열 병렬 배치 | 독립 레인 두 개가 한 페이지에서 경쟁 |
| 테마 수가 구조보다 먼저 확장됨 | 색만 달라지고 사용 흐름 문제는 남음 |

390px 검사에서 G3 이후 gate 카드의 우측 좌표가 최대 약 850px까지 확장됐지만 document scroll width는 375px였다. 이는 단순한 가로 스크롤 표가 아니라 일부 핵심 단계가 viewport 밖으로 배치돼 접근성이 떨어질 수 있다는 증거다.

## 6. 강화학습 시각화 감사

평가·비교·인사이트에는 NAV, 비용 민감도, 지수 overlay 등의 차트가 있다. 따라서 차트가 전혀 없는 것은 아니다. 그러나 사용자가 느끼기에 없는 것과 비슷한 이유는 다음과 같다.

- Training 첫 화면에 reward·loss·entropy가 보이지 않는다.
- 한 run의 학습곡선과 NAV가 같은 context에서 연결되지 않는다.
- 행동 분포, 종목 선택, turnover, cash/exposure가 없다.
- seed·fold·비용 조건을 통일해 비교하는 run selector가 없다.
- 차트에 run id·dataset·split·cost·seed lineage가 일관되게 붙지 않는다.
- Simple mode가 없어 핵심 3개 그래프보다 설명 카드가 먼저 노출된다.

필수 시각화는 다음과 같다.

| 그룹 | 필수 그래프 |
|---|---|
| 학습 | reward raw/EMA, actor/critic loss, entropy, Q-value |
| 행동 | Buy/Hold/Sell, position heatmap, 종목별 선택 빈도 |
| 경제성 | NAV vs no-trade/rule/random, drawdown, 비용 누적 |
| 강건성 | seed box plot, fold heatmap, cost sensitivity, shuffle gap |
| 데이터 | coverage, missing, PIT·available-at·corporate action 상태 |
| 실행 | step/episode, 처리속도, ETA, 마지막 event, stale 여부 |

## 7. 실시간 관측성·API 감사

현재 V6 RLWorkspace는 mount 시 status·runs·discovery를 조회하는 구조다. 구형 RL 화면 일부에는 polling이 있지만 V6 전체가 공유하는 telemetry store나 event stream은 없다.

2026-08-05 단일 실행 측정 결과:

| API | 결과 |
|---|---|
| `/api/v6/status` | 20초 timeout, 0 byte |
| `/api/v6/runs` | HTTP 200, 약 5.87초, 6,685 byte |

과거 프로파일에서는 `/api/v6/runs` 내부 Type1 report catalog 검증이 약 52.29초 걸린 사례가 기록돼 있다. 무거운 authority 검증과 화면용 요약을 같은 요청 경로에서 수행하면 실시간 화면은 안정적으로 동작할 수 없다.

필요한 분리는 다음과 같다.

- 경량 summary snapshot
- paginated run catalog
- 단일 run detail
- metric series
- append-only run events
- artifact/evidence detail
- SSE event stream과 polling fallback

## 8. 종가매매 연구 계약과 시각화 경계

현재 일봉 연구의 공식 모드는 `POST_CLOSE_NEXT_OPEN`이다.

1. D일 공식 종가 확인
2. PIT·available-at·종목군 검증
3. 특징 snapshot 고정
4. DQN/CQL 정책 추론
5. 6천만원·최대 10종목 target 구성
6. D+1 시가 체결
7. 수수료·세금·슬리피지 반영
8. NAV·reward·next state 계산
9. event·metric·artifact 저장

당일 공식 종가를 관측하고 같은 공식 종가에 체결하는 결과를 애니메이션이나 차트에서 정상 실행처럼 표현하면 안 된다. `PRE_CLOSE_PROXY`가 사용될 경우 proxy임을 명시하고 별도 색상·badge로 구분한다.

## 9. 기술 유지보수성 감사

| 파일 | 문제 | 요구되는 분리 |
|---|---|---|
| `v6Api.ts` | 상태·run·insight·report API 혼합 | `statusApi`, `runsApi`, `evidenceApi`, `insightApi`, schemas |
| `TrainingPage.svelte` | run 선택·상태·차트·artifact 표 혼합 | selector, telemetry, charts, artifact panel |
| `ReportPage.svelte` | 보고서 목록·detail·lineage·download 혼합 | report catalog, evidence timeline, document drawer |
| `ComparePage.svelte` | 압축된 소스와 복합 비교 로직 | comparison model, chart panels, selection controls |
| discovery evidence modules | 250줄 상회·근접 | parser, reviewed snapshot, domain view로 분리 |

새 코드와 수정되는 대형 파일은 순수 코드 250줄 이하를 기준으로 책임별 분리한다.

## 10. 감사 점수

| 평가 영역 | 점수 | 근거 |
|---|---:|---|
| 연구 결과 탐색성 | 40 | 기록은 존재하지만 통합 catalog와 run URL이 없음 |
| 정보구조 | 45 | 단계는 명확하지만 사용자 목표·run 중심이 아님 |
| 디자인 일관성 | 38 | 자체 style·grid·table 규칙 과다 |
| RL 시각화 | 30 | 일부 차트는 있으나 학습 관측성이 약함 |
| 실시간 관측성 | 20 | V6 공통 event store 부재, API 지연 |
| 모바일·반응형 | 35 | 실제 390px에서 핵심 단계 접근 문제 |
| 안전·증거 정직성 | 85 | NO-GO와 sealed 상태를 숨기지 않음 |
| 코드 유지보수성 | 45 | 대형 파일·중복 구조 존재 |
| 종합 UX 성숙도 | 42 | 위 항목을 제품 사용성 기준으로 종합 |

## 11. 목표 상태

목표는 기능을 더 붙이는 것이 아니라 다음 질문에 10초 안에 답할 수 있는 플랫폼이다.

1. 지금 실행 중인 연구는 무엇인가?
2. 학습이 실제로 진행 중인가, 멈췄는가, stale인가?
3. reward는 좋아졌는가?
4. 비용 후 NAV가 기준선을 이겼는가?
5. 어떤 데이터·seed·split·cost를 썼는가?
6. 어떤 모델 파일과 문서가 생성됐는가?
7. 왜 GO 또는 NO-GO인가?
8. 다음 실행 가능한 행동은 무엇인가?

대시보드 UX 90점 이상은 가능하다. 다만 경제 모델 점수와 실거래 준비도는 UI 개발과 별도이며 Fresh OOS·외부 권위 자료·paper-forward 증거 없이 올리지 않는다.

## 12. 다음 문서

구현 순서, 페이지별 acceptance criteria, 데이터 계약, branch/commit/merge 전략은 `docs/kronos_dashboard_v6_p0_p2_development_plan_2026-08-05.md`를 따른다.
