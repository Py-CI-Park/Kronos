# Kronos v1.29.0-dev RL 증거 UX 개선 결과

- 작성일: 2026-08-07 KST
- 최종 검증일: 2026-08-09 KST
- 개발 브랜치: `codex/v1.29.0-dev-rl-evidence-ux`
- 부모 개발선: `develop/v1.29.0-dev`
- 범위: 연구 라이브러리, 실행 상세, 실시간 학습, 행동 시각화, 평가 비교
- 판정: **구현·자동 검증·실제 브라우저 QA PASS / 경제 모델 NO-GO 유지**

## 1. 사용자 관측 문제와 원인

| 화면 | 관측 문제 | 확인된 원인 | 이번 처리 |
|---|---|---|---|
| 연구 라이브러리 | 결과가 대충이고 실행별 차트가 부족함 | 상위 보관함을 실행 1건으로 취급하여 실제 하위 실행의 summary·artifact가 가려짐 | 일반 보관함을 직접 하위 실행 단위로 펼치고, 직접 summary의 숫자를 안전하게 추출 |
| 실행 상세 | 텔레메트리가 없으면 파일 목록만 보임 | 결과 숫자를 읽는 안전한 API 계약이 없었음 | 직접 metadata source 1개에서 허용된 손익·비용·reward·거래일·체결 슬롯만 bounded 추출 |
| 실시간 학습 | 최근 행동과 시간대별 패턴이 약함 | 최근 12개 카드와 개별 scatter만 존재하고 시간 구간 집계가 없음 | 최근 20개 결정, 한국 시간 1시간 단위 행동 누적 막대, 최대 500 point 표본 |
| 평가 1~9 | 숫자의 의미가 불명확하고 클릭되지 않는 것처럼 보임 | 실제 실행 진행률처럼 보였고 선택 상태·키보드 상호작용·상세 연결이 약함 | “설계 계약 순서”임을 명시하고 tab semantics, 선택 배지, 방향키/Home/End 탐색 추가 |
| 비교 그래프 | x축 겹침, 실행 하나가 작게 눌림, 차트가 작음 | 길이가 다른 run을 원시 step 축에 바로 겹침 | 기본 0~100% 진행률 정렬, 원본 step 전환, 차트 430→560px, 축·zoom 여백 확대 |
| 텔레메트리 단위 | 일봉 누적 손익이 `-100%` 낙폭처럼 보임 | 모든 `equity`를 초기값 1인 정규화 NAV로 가정했으나 해당 실행은 원화 누적 손익 | event의 `equity_kind/equity_unit`을 API까지 전달하고 NAV에만 낙폭 계산 |
| 모바일 긴 실행 ID | 연구 상세 제목이 내부 폭을 넓힘 | 공백 없는 run id에 공통 헤더 줄바꿈 계약이 없음 | 공통 PageHeader 제목·상태·설명에 bounded 줄바꿈 적용 |

## 2. 연구 결과 API 계약

`GET /api/v6/research-runs/<run_id>`는 기존 직접 파일 metadata에 다음 필드를 추가한다.

| 필드 | 의미 | 제한 |
|---|---|---|
| `observed_outcome.scope` | `DIRECT_SUMMARY_NUMERIC_ONLY` | 다른 파일·로그·모델로 연쇄 탐색하지 않음 |
| `headline` | `primary_headline`, `headline`, `guardrail` 중 직접 문자열 | 최대 400자 |
| `reasons` | 직접 기록된 reasons/blocker/error 문자열 | 최대 6개 |
| `series` | policy 또는 split별 숫자 행 | 최대 16행 |
| 허용 숫자 | 손익·비용·reward·거래일·체결 슬롯 | 미관측 값은 누락, 0으로 보간하지 않음 |

파서는 Pydantic v2 재귀 JSON 타입 경계를 사용한다. 파일은 직접 source, 비심볼릭 링크, 512 KiB 이하일 때만 읽는다. 이 결과는 시각화를 위한 관측값이며 공식 OOS 수익성 판정이 아니다.

## 3. 런타임 변화

| 지표 | 이전 관측 | 개선 후 실제 API | 해석 |
|---|---:|---:|---|
| 연구 catalog | 98개 수준의 상위/특수 항목 혼합 | 196개 실제 실행 단위 | 일반 보관함 하위 실행도 노출 |
| telemetry run | 21 | 24 | 일반 보관함 하위 event 파일 추가 발견 |
| daily-close telemetry | 0 | 2 | 일봉 실행 2개가 실시간/기록 화면에서 선택 가능 |
| 상세 구조화 결과 예시 | 없음 | truthful policy 9행 | policy/split 손익·비용·reward 차트 가능 |
| 정적 자산 | 이전 해시 | `index-BH_x6sV6.js` | 단위 안전·모바일 수정까지 새 UI build 반영 |
| 정적 자산 누락 | - | 0/5 | HTML 참조 자산 모두 HTTP 200 |

daily-close telemetry 2개에는 timestamp가 있으나 `action_name`은 아직 0건이다. 따라서 시간대 차트가 빈 상태를 정직하게 표시하는 것이 맞으며, 다음 실제 시장 전이/학습 단계에서 action event를 생성·연결해야 한다.

## 4. 텔레메트리 단위 안전 계약

| 기록 계약 | 화면 처리 | 비교 처리 |
|---|---|---|
| `normalized_nav / normalized` | 초기 NAV 1 대비 변화율과 표본 낙폭 표시 | 같은 kind/unit끼리 허용 |
| `krw_nav / krw` | 원화 NAV와 표본 낙폭 표시 | 같은 kind/unit끼리 허용 |
| `cumulative_pnl / krw` | 원화 누적 손익만 표시 | 같은 kind/unit끼리만 허용, 낙폭 미계산 |
| legacy metadata 없음 | 원값 + `단위 MISSING`, 비율·낙폭 미계산 | `OVERLAY BLOCKED` |
| 실행 내부 metadata 혼합 | 원값 + `단위 MIXED`, 비율·낙폭 미계산 | `OVERLAY BLOCKED` |

이 계약은 숫자를 숨기지 않는다. 개별 실행의 원값은 계속 보여주되, 의미가 다른 원화·비율·점수 값을 같은 축에 놓아 가짜 성과를 만드는 것만 차단한다. truthful daily-close 실행의 API 265 point는 `reward_kind=return_fraction`, `reward_unit=fraction`, `equity_kind=cumulative_pnl`, `equity_unit=krw`, `action_recorded=false`로 확인했다.

## 5. 검증 결과

| 검증 | 결과 |
|---|---:|
| 프런트 전체 Bun 테스트 | **462 passed** |
| Svelte/TypeScript 검사 | **0 errors, 0 warnings** |
| Vite production build | **1,062 modules transformed / PASS** |
| V6 Python 연구·catalog·텔레메트리·플랫폼 변경 회귀 | **67 passed** |
| 텔레메트리 API 단위 계약 집중 회귀 | **5 passed** |
| 변경 Python Ruff | **PASS** |
| outcome parser + telemetry reader Basedpyright | **0 errors, 0 warnings** |
| 실제 Flask 런타임 | `127.0.0.1:5070`, PID 310996 |
| API/정적 자산 smoke | **PASS** |
| 앱 내 브라우저 데스크톱 QA | **PASS** — 연구 5 canvas, 실시간 3 canvas, 평가 legacy overlay 2건 차단, 문서 가로 overflow 0 |
| 앱 내 브라우저 모바일 390×844 QA | **PASS** — 연구·실시간·평가 문서 overflow 0, 긴 run id 헤더 수정 후 main overflow 0 |

실제 브라우저에서 truthful daily-close 실행은 `누적 손익`, 원화 표시, “NAV가 아니므로 낙폭을 계산하지 않습니다” 문구를 노출했으며 `-100.00%`는 존재하지 않았다. 평가 화면의 legacy orderbook 실행은 단위 누락 때문에 equity/reward 두 비교 모두 `OVERLAY BLOCKED`와 `NOT_CALCULATED`를 표시했다.

## 6. 점수 영향

| 평가축 | 이전 | 현재 | 근거 |
|---|---:|---:|---|
| 연구 결과 발견성 | 60 | 88 | 실제 실행 단위 catalog, 196개 run, 영구 상세 URL |
| 결과 시각화 | 55 | 86 | 직접 outcome + telemetry + artifact 시각화 |
| 실시간 행동 관측 | 70 | 88 | 시간대 집계, 최근 20개, 500 point |
| 평가 비교 가독성 | 65 | 90 | 정규화 축, 대형 차트, 축 전환 |
| 이번 범위 UX 소계 | 63 | **92** | 실제 데스크톱·모바일 QA 및 단위 오해 차단 |
| 전체 프로그램 성숙도 | **73** | **73** | 경제 모델·데이터 권위·Fresh OOS·paper gate가 아직 미통과 |

화면 개선은 경제적 성능을 만들지 않는다. 따라서 전체 점수를 올리지 않았으며 경제 모델 20점, live 0점 경계도 유지한다.

## 7. 다음 우선 작업

| 순서 | 작업 | 완료 증거 |
|---:|---|---|
| 1 | 실제 일봉 시장 전이 builder | 미래 수익을 state에 넣지 않는 leakage 테스트, 6천만/5천만/1천만 NAV 산술 테스트 |
| 2 | `CASH` / `INVEST_TOP10_EQUAL_SLOT` 실제 행동 event | daily-close telemetry에 timestamp·action·reward·NAV·cost 존재 |
| 3 | CQL 5 primary + 5 shuffle seed | seed별 학습곡선, validation, 대조군, 비용 0.230/0.330/0.460% |
| 4 | metric metadata가 선언된 비교 run 생성 | 같은 kind/unit일 때만 560px 비교 차트가 열리고, 불일치는 계속 차단 |
| 5 | 기준선 재채점 | 하드캡 제거 증거가 있을 때만 73점 갱신 |

## 8. 사용자 확인 경로

서버는 `http://127.0.0.1:5070/?ui=v6&tab=research`에서 실행 중이다. 기존 연결 오류 탭을 직접 새로고침한 다음 아래를 확인한다.

1. **연구 라이브러리**: 전체 결과 수가 약 196개이고 run id가 `그룹/실행` 형태인지 확인한다.
2. truthful policy를 검색하여 상세로 들어가 **직접 관측 결과 요약**의 9행 차트를 확인한다.
3. **실시간 학습**: 시간대별 행동 빈도와 최근 20개 결정 영역을 확인한다.
4. **평가 비교**: 1~9 각 카드를 클릭하고 하단 입력·출력·통과 조건이 바뀌는지 확인한다.
5. 현재 orderbook legacy 2개는 단위가 없어 `OVERLAY BLOCKED`인지 확인한다. 이후 단위가 선언된 같은 lane 실행 2개를 고르면 **정규화 진행률 / 원본 step** 버튼과 560px 비교 차트가 열린다.

## 9. 완료 경계

이번 브랜치는 “연구 결과를 찾고, 원래 의미의 단위로 보고, 비교 가능한 것만 비교하는 UX”를 완료한다. 실제 종가 매매 RL 정책의 경제적 성공은 만들지 않았으며, 공식 판정은 계속 `NO-GO`, Fresh OOS는 `SEALED`, live readiness는 0점이다. 다음 브랜치의 첫 목표는 미래 정보를 쓰지 않는 시장 전이와 실제 행동·비용·NAV event 생성이다.
