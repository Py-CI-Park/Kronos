# 연구 원장 · Research Ledger

> 상태: `ACTIVE_RESEARCH_INDEX`  
> 최종 갱신: 2026-07-18  
> 범위: Kronos 예측, 일봉 종가매매, 포트폴리오 RL, 대시보드·연구 인프라

## 목적

이 문서는 기존 연구 문서를 다시 쓰지 않고 찾기 쉽게 연결하는 Wiki 색인입니다. 원본 결과·판정·해시·비용·기간은 각 `docs/` 문서가 권위이며, 이 페이지는 탐색용입니다.

## 현재 연구 경계

- 기본 UI: V3 유지
- V5: 연구 프리뷰 및 직접 경로 검증용
- V5.1: `IMPLEMENTED_RESEARCH_FOUNDATION`, 직접 `?ui=v5` 확인용, 기본 전환 아님
- 일봉 종가매매 선형 정책: `NO-GO / WATCH_RESEARCH_ONLY`
- 일봉 PPO 5k: `INCONCLUSIVE_SMOKE_ONLY / NOT_PROMOTED`
- 일봉 PPO full: `INCONCLUSIVE — NOT RUN`
- `ts_imb`: RL이 아닌 RULE baseline
- 실거래·브로커·주문·수익성·paper-forward·모델 승격: 잠금 유지

## 최신 개발 기준점

| 날짜 | 문서 | 종류 | 상태 |
|---|---|---|---|
| 2026-07-18 | `docs/kronos_dashboard_v51_implementation_result_2026-07-18.md` | IMPLEMENTATION/RELEASE_RESULT | `IMPLEMENTED_RESEARCH_FOUNDATION`; RL/live `NOT_RUN / NO-GO`; V3 기본 유지 |
| 2026-07-17 | `docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md` | REQUIREMENTS | 구현 전 기준값 기록 |
| 2026-07-16~17 | `docs/kronos_dashboard_v5_development_result_2026-07-16.md` | RELEASE/RESULT | 기능 98/100, V3 기본 유지 |
| 2026-07-14 | `docs/stom_daily_sb3_ppo_v5_prereg_2026-07-14.json` | PREREGISTRATION | 50-cell, compute/fresh-OOS 잠금 |
| 2026-07-12 | `docs/stom_daily_sb3_ppo_result_2026-07-12.md` | RESULT | full `NOT_RUN`, protocol gap stop |
| 2026-07-12 | `docs/stom_daily_sb3_ppo_smoke_result_2026-07-12.md` | RESULT | 5k plumbing PASS, model 미승격 |
| 2026-07-12 | `docs/stom_daily_close_slot_truthful_result_2026-07-12.md` | RESULT | test OOS 무거래, `NO-GO` |

## V5.1 구현 결과 기준점

| 항목 | 값 |
|---|---|
| 문서 | `docs/kronos_dashboard_v51_implementation_result_2026-07-18.md` |
| 상태 | `IMPLEMENTED_RESEARCH_FOUNDATION` |
| RL 결과 | `NOT_RUN`; prior `NO-GO`/`INCONCLUSIVE` 보존 |
| 실거래·수익 준비도 | `0/100`; live/broker/order/paper/profit claim 없음 |
| 브랜치 | `feature/dashboard-v5-learning-evidence` |
| 기준 commit | `4c8ba1f` |
| 구현 commit 범위 | `9d8e2ad` through `c43ee9b` |
| 최초 결과 문서 commit | `1ec28bd` |
| 최종 브라우저 검증 대상 HEAD | `c43ee9b` |
| 핵심 증거 | V5.1 cumulative 281 passed, runtime integration 111 passed, API/schema 79 passed, frontend 353 passed, dashboard regression 33 passed, V3 snapshot 5 passed, Svelte 408 files 0 errors/warnings, build passed, npm audit 0 vulnerabilities, Chromium 3440×1440/2160×3840 horizontal overflow 없음 |
| full-suite 한계 | monolithic 2,298-test command는 한 프로세스로 완료되지 않음; 900초 timeout 81%, 재시도 84% 무 assertion output; tail partition 342 passed + 승인 snapshot 5 passed |
| 다음 연구 step | 새 사전등록으로 15:20 H1 smoke를 실행하고 H3/H5 validation variant, full-universe coverage/custody audit, RULE·supervised·shuffle controls를 순서대로 닫는다. |

## 연구 흐름

```text
데이터 권위(D0/D1)
  → 15:20 종가 대용값 계약
  → 신규 사전등록
  → 작은 smoke
  → RULE·supervised·shuffle signal gate
  → multi-seed PPO
  → untouched test OOS
  → 별도 승인된 paper-forward 검토
```

## 일봉 종가매매 V5.1 기준값

- 의사결정: D일 15:20
- 가격: 15:20 봉 종가를 연구용 종가 대용값으로 가정
- 공식 종가: 아님
- 초기 자본: 60,000,000원
- 최대 투자: 50,000,000원
- reserve: 10,000,000원
- slot: 10개, slot당 5,000,000원
- primary 왕복 비용 표시: 0.23%
- controls: 0.00%, 0.46%
- 공매도·레버리지: 초기 금지
- 15:20 source 후보: `_database/Stock_Database_ohlcv_5min.db`
- `A000250` 표본 15:20 범위: 2019-05-09~2026-06-12, 1,739행
- KOSPI/KOSDAQ 공식 지수 시계열: 로컬 DB에서 미확인, overlay `BLOCKED_INDEX_SERIES_SOURCE`

상세 계약은 `docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md`를 참조합니다.

## 문서 종류

| 종류 | 목적 | 실행 시점 |
|---|---|---|
| PREREGISTRATION | 가설·프로토콜·중단 기준 동결 | 실험 전 |
| RESULT | 결과·원인·판정 기록 | 실험 후 |
| INCIDENT | 결함·영향·수정·재발 방지 | 장애 발견 후 |
| ADR | 아키텍처 선택과 대안 기록 | 구현 전후 |
| HANDOFF | 재개에 필요한 상태 전달 | 작업 인계 시 |
| RELEASE | 변경·검증·rollback·tag 기록 | 릴리스 기준점 |
| RUNBOOK | 반복 가능한 실행 절차 | 운영 준비 시 |

## 문서 보존 정책

1. 과거 결과 문서의 `NO-GO`를 완화하거나 삭제하지 않습니다.
2. 새 증거는 새 날짜 문서로 추가합니다.
3. 기존 비용 내부 식별자는 호환성을 위해 유지하되 사용자 표시에는 정확한 `%` 변환을 사용합니다.
4. 생성 artifact는 `webui/rl_runs/` 또는 지정 artifact 디렉터리에 두고 결정 문서는 `docs/`에 둡니다.
5. Wiki는 원본 증거를 대체하지 않습니다.
6. 관련 commit, tag, run UID/revision, source/protocol/model SHA-256을 기록합니다.

## 관련 Wiki

- [문서 표준과 연구 보고서 양식](14-document-standard)
- [강화학습 실험실](11-reinforcement-learning)
- [포트폴리오 RL 로드맵](12-portfolio-rl-roadmap)
- [대시보드 가이드](10-dashboard-guide)
