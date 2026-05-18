# Kronos v2 SPA — webui/v2_src

Vite + Svelte 5 + TypeScript + Tailwind prebuilt 으로 빌드되는 통합 대시보드 SPA. `webui/static/v2/dist/` 빌드 산출물을 Flask 가 정적 서빙하며 P6 cutover 이후 루트 `/` 로 자동 진입한다.

## 빠른 시작

```powershell
# 1. 의존성 (최초 1회)
cd D:\Chanil_Park\Project\Programming\Kronos\webui\v2_src
npm ci --prefer-offline --no-audit --no-fund

# 2. 개발 빌드 (변경 후 매번 — Vite dev server 가 아닌 dist 빌드 사용)
npm run build
# 산출물: ../static/v2/dist/index.html, assets/*.css, assets/*.js

# 3. Flask 재시작 + dist 모드 활성화
cd D:\Chanil_Park\Project\Programming\Kronos
$env:KRONOS_WEBUI_PORT = "5070"
$env:KRONOS_V2_DIST = "1"
C:\Python\64\Python3119\python.exe webui\run.py

# 4. 브라우저
# http://127.0.0.1:5070/ → v2 SPA (디자인 시스템 v2)
# http://127.0.0.1:5070/v1/ → v1 메인 예측 화면 (legacy archive)
# http://127.0.0.1:5070/v2 → 301 redirect → /
```

## 환경 변수

| 변수 | 기본 | 설명 |
|---|---|---|
| `KRONOS_V2_DIST` | `0` | `1` 이면 Vite dist 산출물 서빙, `0` 이면 P1 SSR Jinja shell 폴백 |
| `KRONOS_WEBUI_PORT` | `7070` | Flask 포트 (운영은 5070 사용) |
| `KRONOS_WEBUI_HOST` | `0.0.0.0` | 바인드 호스트 |
| `KRONOS_WEBUI_OPEN_BROWSER` | `1` | `0` 이면 자동 브라우저 안 띄움 |

## 디렉터리 구조

```
webui/v2_src/
├── index.html              # Vite entry — SSR meta marker + Pretendard/JetBrains Mono 폰트
├── package.json
├── package-lock.json
├── vite.config.ts          # base: '/static/v2/dist/'
├── svelte.config.js
├── tailwind.config.js      # CSS 변수 alias 로 light/dark 자동 전환
├── postcss.config.js
├── tsconfig.json
└── src/
    ├── main.ts             # Svelte 부트스트랩
    ├── App.svelte          # app-shell + 7 탭 라우팅
    ├── app.css             # core.css + components.css + Tailwind 디렉티브
    ├── styles/
    │   ├── core.css        # OKLch 토큰 (light + dark 자동)
    │   └── components.css  # .card / .metric / .pill / .stepper / .hero 등
    ├── lib/
    │   ├── api.ts          # /api/* fetch + 타입 정의
    │   ├── stores.ts       # Svelte writable: trainingStatus, history, gpu, theme 등
    │   ├── polling.ts      # 5s 자동 폴링 + refreshSeconds watcher
    │   ├── theme.ts        # 디자인 토큰 + applyThemeToDocument + ECharts 베이스
    │   ├── format.ts       # fmt.int/num/pct/bytes/duration/kst*
    │   ├── icons.ts        # 26개 inline SVG (Lucide 풍)
    │   └── readinessMap.ts # readiness.level → 색/카피 매핑
    ├── layout/
    │   ├── Sidebar.svelte  # 232px → 72px collapse + 모바일 drawer
    │   ├── Header.svelte   # sticky + breadcrumb + 시계 + 테마 토글
    │   └── HeroStrip.svelte # Live Training hero (stepper + 도넛)
    ├── charts/
    │   └── EChartsRenderer.svelte
    ├── widgets/
    │   ├── W1_StageStepper.svelte
    │   ├── W2_ReadinessCountdown.svelte
    │   ├── W3_LossCurve.svelte
    │   ├── W4_EtaTimeline.svelte
    │   ├── W5_GpuSparkline.svelte
    │   ├── W6_LossVolatility.svelte
    │   ├── W7_StatusBadge.svelte
    │   └── W8_BacktestGallery.svelte
    └── tabs/
        ├── LiveTrainingTab.svelte
        ├── ForecastWorkbenchTab.svelte   # /api/predict 통합
        ├── StomDiagnosticsTab.svelte     # /api/stom/* 9개
        ├── ArtifactsModelsTab.svelte     # /api/training/artifacts
        ├── HistoryRunsTab.svelte         # /api/training/runs
        ├── SystemHealthTab.svelte        # /api/training/gpu
        └── SettingsTab.svelte            # localStorage 클라이언트 설정
```

## 디자인 시스템

- **베이스**: 라이트 cool-tint `oklch(98% 0.004 240)` / 다크 `oklch(16% 0.02 250)`
- **액센트**: 민트 `oklch(56% 0.12 170)` — 페이지당 최대 2회 등장 원칙
- **폰트**: Pretendard Variable (디스플레이/본문) + JetBrains Mono (숫자)
- **글로우**: 진행 중 RUN 카드 + Hit ratio 메트릭에만 (2곳 제한)
- **이모지 사용 금지** — 모든 아이콘은 inline SVG (icons.ts)
- 자세한 토큰은 `src/styles/core.css` 의 `:root` / `[data-theme="dark"]` 참조

## SSR Meta Marker

Vite 빌드된 `dist/index.html` 과 P1 SSR `v2_shell.html` 모두 다음 meta tag 를 보존한다 (테스트 자동 검증):

```html
<meta name="kronos-v2-shell" content="hero,live-training,stom,forecast,artifacts,history,system-health" />
<meta name="kronos-v2-version" content="p1-5-spa" />
```

서버측 grep 으로 빌드 산출물 검증 가능. SPA 가 마운트되어도 `<head>` 의 meta 는 그대로 유지된다.

## 모드 전환 (P1 SSR ↔ P1.5 dist)

| 환경변수 | 동작 |
|---|---|
| `KRONOS_V2_DIST=0` (기본) | Flask 가 `webui/templates/v2_shell.html` 의 P1 SSR Jinja shell 을 반환 |
| `KRONOS_V2_DIST=1` | `webui/static/v2/dist/index.html` 의 Vite SPA 산출물을 반환 (있을 때만) |

두 모드 모두 SSR meta marker 동일하게 노출. 빌드 산출물이 손상되면 자동으로 P1 SSR 폴백.

## Rollback

| 상황 | 명령 |
|---|---|
| dist 깨짐 | `$env:KRONOS_V2_DIST = "0"` 후 Flask 재시작 → P1 SSR 복귀 |
| 디자인 만족 안 됨 | `git revert <designer-commit-hash>` → 이전 상태 복원 |
| 완전 비활성화 | `webui/static/v2/dist/` 삭제 → 자동 P1 SSR 폴백 |
| v1 페이지로 임시 회귀 | 사용자는 `http://127.0.0.1:5070/v1/` 로 접속 |

## API 의존성

모든 데이터는 기존 Flask `/api/*` endpoint 에서 읽음 — SPA 측 신규 endpoint 추가 0:

| 그룹 | 사용 endpoint |
|---|---|
| 학습 | `/api/training/{status,history,artifacts,gpu,runs}` |
| STOM | `/api/stom/{summary,prediction-files,qlib-backtests,filter-reports,diagnostics,recommendations,backtest-report,prediction}` |
| 예측 | `/api/{data-files,available-models,load-model,load-data,predict,model-status}` |

`webui/app.py` 의 라우트 시그니처를 변경하지 않는 한 SPA 코드 무영향.

## 테스트

```powershell
cd D:\Chanil_Park\Project\Programming\Kronos
C:\Python\64\Python3119\python.exe -m pytest `
  tests/test_v2_route.py `
  tests/test_v2_dist_marker.py `
  tests/test_v2_blueprint_isolation.py `
  -v
```

10개 테스트 — 루트 v2 서빙, /v1/ legacy, /v2 redirect, /api/* 무변경, global catch-all 부재, SSR marker dist 보존 모두 검증.

## 빌드 산출물 크기 (참고)

- `index.html` ~1.5 KB
- `index-*.css` ~49 KB (gzip 9.9 KB)
- `index-*.js` ~1.18 MB (gzip 391 KB) — ECharts 가 대부분
- 소스맵 `index-*.js.map` ~6.5 MB (commit 포함)

Plotly 도입 시 dynamic import 로 STOM 탭 진입 시점에 로드 (현재 미통합).

## 디버깅 팁

- Svelte runes 경고: 컴포넌트 상단에 `$state` / `$derived` / `$effect` 만 사용
- ECharts 색상이 light/dark 전환 시 안 바뀌면: `theme` store subscribe → palette 재계산 흐름 점검
- 빌드 후 SSR marker 안 보이면: `index.html` 의 `<meta>` 가 통째로 누락된 게 아닌지 검사
- pytest 실패 시: 환경변수 `KRONOS_V2_DIST` 가 셸에 남아있는지 확인 (`Remove-Item Env:KRONOS_V2_DIST`)
