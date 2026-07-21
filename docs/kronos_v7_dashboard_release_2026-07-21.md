# Kronos V7 대시보드 V6 기본 전환 Release — 2026-07-21

> 문서 ID: `KRONOS-V7-DASHBOARD-RELEASE-2026-07-21`
> 상태: `RELEASED_LOCAL_DEFAULT`
> 범위: 로컬 127.0.0.1:8122 기본 shell 전환
> 기준 브랜치: `review/dashboard-v7-full-audit`
> 기준 구현 commit: `8098b2f`
> 릴리스 태그: `fork-v1.6.0-dashboard-v7-rl-reports`

## 범위와 제외 범위

- query가 없는 `http://127.0.0.1:8122/`의 기본 shell을 V3에서 V6로 전환합니다.
- canonical V6 경로는 `/?ui=v6&tab=home`입니다.
- V3는 `/?ui=v3`, V5는 `/?ui=v5`로 유지합니다.
- 기존 명시적 query와 `ui_persist=1` 선택은 계속 우선합니다.
- live trading, broker/order, profitability, paper-forward, model promotion은 추가하지 않습니다.

## 변경 전·후

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| `/` 기본 shell | V3 | V6 |
| V6 접근 | `/?ui=v6&tab=home` opt-in | `/` 기본 + 기존 canonical 경로 |
| V3 rollback | 기본 | `/?ui=v3` |
| V5 비교 | `/?ui=v5` | 동일 |
| 연구 판정 | M1/M3 INCONCLUSIVE, M2 NO_GO | 동일 |
| untouched test | NOT_RUN | 동일 |

## Release gate

- V6 전수감사 correctness blocker 수정 완료
- project/cycle/run 보고서 chain `CHAIN_OK`
- Python dashboard/RL/security 100 tests 통과 기록
- frontend 363 tests 통과 기록
- Svelte 436 files 0 errors/warnings 기록
- 390px 주요 5페이지 horizontal overflow 0 기록
- V3/V5 명시적 rollback 경로 유지

## 사용자 확인 경로

- 기본: `http://127.0.0.1:8122/`
- V6 canonical: `http://127.0.0.1:8122/?ui=v6&tab=home`
- V3 rollback: `http://127.0.0.1:8122/?ui=v3`
- Report: `http://127.0.0.1:8122/?ui=v6&tab=rl&step=report`

## 알려진 제한

- 로컬 연구 대시보드 release이며 원격 배포나 push를 뜻하지 않습니다.
- 현재 RL 모델은 validation GO 후보가 없고 untouched test를 열지 않았습니다.
- V6 기본 전환은 사용성·증거 탐색 release이며 거래 준비도 승격이 아닙니다.

## Rollback

query에 `?ui=v3`를 지정하면 즉시 V3 shell을 사용할 수 있습니다. 코드 rollback은 이 release commit을 revert합니다.
