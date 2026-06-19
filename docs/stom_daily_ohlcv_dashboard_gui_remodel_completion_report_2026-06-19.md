# Kronos Trading 대시보드 GUI 리모델링 완료 보고서 (2026-06-19)

## 결론

- 상태: `COMPLETED_RESEARCH_ONLY_DASHBOARD_REMODEL`
- 범위: Trading / RL Trading, Daily OHLCV, Daily RL Guide 화면의 IA, URL routing, first-viewport status, progressive disclosure, evidence cockpit 개선
- 실행 브랜치: `feature/dashboard-research-command-center`
- 기준 커밋: `3ad8c33` (`feature/daily-artifact-selection-hardening` 완료 상태)
- 공개/사용자 명칭: `Kronos 대시보드` / `Kronos Dashboard`

이 작업은 dashboard UX/IA 개선입니다. 실거래, 브로커 주문, 계좌, paper-forward, 모델 생성 GO, 수익성 주장은 모두 계속 금지/잠금입니다.

## 완료된 변경

### 1. URL routing / history 동기화

- `/rl`, `/daily-ohlcv`, `/daily-rl-guide`를 canonical route로 고정했습니다.
- sidebar click이 `activeTab`만 바꾸던 문제를 고쳐 URL도 함께 변경합니다.
- browser back/forward가 URL, sidebar active state, header breadcrumb, content를 다시 동기화합니다.
- `/daily-ohlcv/rl-guide`, `/v2/rl-trading` 같은 alias/legacy route는 canonical route로 정규화됩니다.

### 2. 공통 research-only status shell

세 Trading 계열 화면 모두 첫 검토 흐름에서 다음을 먼저 표시합니다.

- verdict
- research-only / read-only lock
- live trading / broker-order-account / paper-forward / model-build / profit lock = `false`
- 기본 비용 가정 `23bp`
- 현재 blocker
- 다음 inspection 순서

### 3. Daily RL Guide compact remodel

기존 약 15,249px 길이의 항상 펼쳐진 화면을 overview-first 구조로 바꿨습니다.

- 기본 화면 scroll height: `2571px`
- workflow center / intent ledger / rejection analytics / scenario generator / replay-performance / raw checks는 explicit section button 뒤에 숨겼습니다.
- replay는 기본 `paused`이며 start/pause와 next-frame 제어가 있습니다.
- `prefers-reduced-motion`에서는 자동 재생하지 않습니다.
- state/action/reward marker(`position_count`, `top_score_bucket`, `hold/buy/add/sell/reduce`, `future_return_1d`)는 유지했습니다.

### 4. Daily OHLCV evidence cockpit

Daily OHLCV 화면은 raw cards 전에 다음을 한 줄 cockpit으로 먼저 표시합니다.

- D0-D9 stage tile 10개
- `API_UNAVAILABLE`와 `NOT_STARTED` 분리
- leading-zero code 예시 `000250 string preserved`
- D5 `NO-GO / model_build_allowed=false`
- `live/model/paper/profit false / 0%`

### 5. RL Trading evidence cockpit

RL Trading 화면은 raw tables 전에 다음을 먼저 표시합니다.

- Rule/RL distinction
- selected verdict
- cost assumption (`23bp`)
- baseline (`ts_imb RULE baseline`)
- drawdown
- trade count
- `model/live/paper/profit locks remain false`

`ts_imb`는 계속 RULE baseline이며 RL 결과로 부르지 않습니다.

## 검증

### Python/source marker tests

```powershell
py -3.11 -m pytest tests/test_v2_route.py tests/test_stom_rl_dashboard_tab.py tests/test_daily_ohlcv_dashboard_tab.py tests/test_v2_dist_marker.py -q
```

결과: `19 passed in 5.35s`

### Frontend check

```powershell
cd webui/v2_src
npm run check
```

결과: `0 ERRORS`, 기존 경고 4개 유지 (`ForecastWorkbenchTab.svelte`, `DocsTab.svelte`)

### Frontend build / committed dist

```powershell
cd webui/v2_src
npm run build
```

결과: `0 ERRORS`, Vite build 성공. 생성 dist asset:

- `webui/static/v2/dist/assets/index-Cv359cZm.css`
- `webui/static/v2/dist/assets/index-6wTWTrq2.js`
- `webui/static/v2/dist/assets/index-6wTWTrq2.js.map`

### Browser QA evidence

- Direct routes verified: `/rl`, `/daily-ohlcv`, `/daily-rl-guide`
- Sidebar click URL sync verified: RL Trading → Daily OHLCV → Daily RL Guide
- Browser back sync verified: Daily RL Guide → Daily OHLCV → RL Trading
- Daily RL Guide default compact state verified: verbose sections hidden by default, height `2571px`
- Replay controls verified: paused by default, manual next-frame available
- Screenshot artifacts:
  - `artifacts/dashboard_remodel_g006_final_rl.png`
  - `artifacts/dashboard_remodel_g006_final_daily_ohlcv.png`
  - `artifacts/dashboard_remodel_g006_final_daily_rl_guide.png`
  - `artifacts/dashboard_remodel_g006_image_verdict.png`

## 안전/정직성 상태

| 항목 | 상태 |
|---|---|
| Dashboard API write side effect | 없음 |
| Live trading readiness | `0%` / blocked |
| Broker/order/account readiness | `0%` / blocked |
| Paper-forward readiness | `0%` / blocked |
| Model-build GO | `false` |
| Profitability claim | 없음 |
| Default cost assumption | `23bp` |
| Rule/RL distinction | 유지 (`ts_imb`는 RULE baseline) |

## 남은 비고

- 이 보고서는 GUI/IA/routing 리모델링 완료 보고서입니다.
- Trading research 자체의 D0/D1/D5 blocker는 UX 개선으로 해제되지 않았습니다.
- 운영 서버/PR/push/merge는 별도 승인 없이 수행하지 않았습니다.
