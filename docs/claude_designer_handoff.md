# Kronos 통합 대시보드 — Claude Designer 리모델링 핸드오프

> **이 문서 하나로 Claude `frontend-design` 스킬이 전체 대시보드를 시각적으로 리모델링할 수 있도록 작성한 단일 핸드오프 파일이다. 기존 도메인 기능과 API는 그대로 두고 UI 표현 계층만 재구성한다.**

**작성일**: 2026-05-16 KST
**대상 스킬**: `document-skills:frontend-design`
**핸드오프 범위**: webui v2 SPA (`/v2`) 전체 시각 리모델링 + 미구현 탭(P2~P6) 디자인 사양 포함
**대상 디렉터리**: `D:\Chanil_Park\Project\Programming\Kronos\webui\v2_src\src\`
**금지 디렉터리**: `D:\Chanil_Park\Project\Programming\Kronos\webui\app.py`, `finetune/`, `model/`, `_database/` (백엔드/모델 무변경)

---

## 0. TL;DR (3문장 요약)

1. **무엇이 있는가**: Flask + 4개 라우트(`/`, `/training`, `/stom`, `/v2`) + 24개 read-only API + v2 SPA(Svelte5+Vite5+Tailwind+ECharts). v2의 7개 탭 중 4개만 구현됐고 3개는 placeholder.
2. **무엇을 원하는가**: v2 SPA를 **시각적으로 화려하고 직관적인** 모니터링 대시보드로 리모델링. 학습 곡선·GPU·예측 결과·아티팩트를 한 화면에서 즉시 읽히게.
3. **무엇을 건드리면 안 되는가**: Flask `app.py`, 학습 코드, DB, finetune outputs, readiness gate 정책. **모든 신규 UI는 read-only**.

---

## 1. 프로젝트 컨텍스트

### 1.1 Kronos가 무엇인가
- **도메인**: K-line(캔들차트) 시계열 예측 모델 (금융 시장 데이터 기반)
- **모델 아키텍처**: 2단계 학습 — **Tokenizer**(K-line 양자화) → **Predictor**(다음 step 예측)
- **사용 데이터**: STOM (Securities Time-series Open Market) 데이터셋, pred60 (60-step 예측)
- **사용자**: 단일 ML 엔지니어 (개인 연구 환경, Windows 11)
- **머신**: RTX 4080 SUPER, Python 3.11.13

### 1.2 학습 현황 (디자인 작업과 무관, 컨텍스트용)
- 마지막 run `stom_1s_grid_pred60_2025_full_small`: tokenizer ~75%에서 validation OOM으로 실패
- predictor 단계 미진입 → checkpoint 0개 → readiness gate `waiting`
- 향후 OOM 수정 후 재학습 예정 (디자인 작업은 학습 의존 없음)

---

## 2. 현재 진행 단계 (Phase Map)

| Phase | 상태 | 내용 | 영향받는 탭/위젯 |
|---|---|---|---|
| P0 | ✅ 완료 | ralplan 합의 계획 | docs only |
| P1 | ✅ 완료 | `/v2` SSR Jinja shell (npm 0, CDN ECharts/Alpine) | `webui/templates/v2_shell.html` (1418줄, P1 폴백용 보존) |
| P1.5 | ✅ 완료 | Vite + Svelte 5 + TypeScript + Tailwind prebuilt 빌드 도입 | `webui/v2_src/src/` 전체 (commit 2695151) |
| **P2** | ❌ 미구현 | Live Training/History 정식 패널 — loss brush, run 목록, 손실 통계 | `LiveTrainingTab`, `HistoryRunsTab`, W6 |
| **P3** | ❌ 미구현 | Forecast Workbench — `/api/predict` 통합 슬라이더, SEED=42 결정성 | `ForecastWorkbenchTab` |
| **P4** | ❌ 미구현 | STOM Diagnostics 통합 — Plotly dynamic import | `StomDiagnosticsTab`, W8 |
| **P5** | ❌ 미구현 | a11y/perf Lighthouse ≥ 90/≥ 80 + code-reviewer 메타-게이트 | 전 영역 |
| **P6** | ❌ 미구현 | Cutover — `KRONOS_V2_ENABLED=1`, v1 → `/v1/` 6개월 archive | Flask 라우트 매핑 |

**리모델링 요청 범위**: P1.5 완료된 영역의 **시각적 리모델링** + P2~P5의 placeholder 탭에 **시각 사양 + 데이터 바인딩 골격**까지 채우기.

---

## 3. 현재 기술 스택 (P1.5 확정)

### 3.1 백엔드 (무변경)
| 항목 | 버전 |
|---|---|
| Python | 3.11.13 |
| Flask | (requirements.txt) |
| Jinja2 | (Flask 동봉) |
| 정적 폴더 | `webui/static/` |
| 정적 URL | `/static/*` |

### 3.2 프론트엔드 (v2 SPA)
| 항목 | 버전 | 역할 |
|---|---|---|
| **Svelte** | 5.x | UI 컴포넌트 (runes 모드 자동 감지) |
| **Vite** | 5.x | 빌드 파이프라인, `base: '/static/v2/dist/'` |
| **TypeScript** | 5.x | 타입 안전성 (strict: false, noImplicitAny: false) |
| **Tailwind CSS** | 3.x (prebuilt) | 유틸리티 클래스, Play CDN 금지 |
| **ECharts** | 5.5+ | 학습 곡선, GPU 스파크라인 |
| **Plotly** | 2.35 (예정, P4) | STOM heatmap/scatter, dynamic import 전용 |
| **Node** | 20/22 LTS |  |

### 3.3 빌드/배포
- 소스: `webui/v2_src/src/`
- 산출물: `webui/static/v2/dist/` (commit 대상, REV-7)
- 환경변수 토글:
  - `KRONOS_V2_DIST=1` → Vite SPA dist 서빙
  - `KRONOS_V2_DIST=0` (기본) → P1 SSR Jinja 폴백
- SSR meta marker (두 모드 모두 보존 의무): `kronos-v2-shell`, `kronos-v2-version` (`p1-ssr` or `p1-5-spa`)

---

## 4. 라우트 맵

### 4.1 페이지 라우트 (4개)
| URL | 핸들러 | 템플릿 | 상태 | 역할 |
|---|---|---|---|---|
| `/` | `webui/app.py` | `index.html` (1802줄) | 보존 | 메인 예측 화면 (lookback/pred_len/temperature/top_p 슬라이더 + 예측 차트) |
| `/training` | `webui/app.py` | `training_dashboard.html` (623줄) | 보존 | 학습 모니터 (read-only, KST, GPU, history) |
| `/stom` | `webui/app.py` | `stom_dashboard.html` (827줄) | 보존 | STOM 진단/추천/백테스트 |
| `/v2` | `webui/v2/__init__.py` Blueprint | dist 모드: `webui/static/v2/dist/index.html` / SSR 모드: `webui/templates/v2_shell.html` | **리모델링 대상** | 통합 SPA 대시보드 (이번 리모델링 범위) |
| `/v2/<path:subpath>` | 동일 Blueprint | 동일 fallback | 보존 | SPA history-mode 라우팅 |

### 4.2 정적 자산
- `webui/static/v2/dist/index.html` — Vite 빌드 결과
- `webui/static/v2/dist/assets/index-*.css` — Tailwind + 컴포넌트 CSS (13.6KB)
- `webui/static/v2/dist/assets/index-*.js` — Svelte 번들 + ECharts (1.1MB raw / 368KB gzip)

---

## 5. v2 SPA 현재 구조

### 5.1 탭 (7개)
| 탭 ID (`data-tab`) | 라벨 | 현재 상태 | 파일 | Phase |
|---|---|---|---|---|
| `live-training` | 실시간 학습 | ✅ 정식 구현 | `src/tabs/LiveTrainingTab.svelte` (46줄) | P1.5 완료 |
| `forecast` | 예측 워크벤치 | 🔒 placeholder | `src/tabs/ForecastWorkbenchTab.svelte` (15줄) | **P3** |
| `stom` | STOM 진단 | 🔒 placeholder | `src/tabs/StomDiagnosticsTab.svelte` (15줄) | **P4** |
| `artifacts` | 아티팩트 & 모델 | ✅ 정식 구현 (read-only) | `src/tabs/ArtifactsModelsTab.svelte` (61줄) | P1.5 |
| `history` | 기록 & 런 | 🔒 안내문만 | `src/tabs/HistoryRunsTab.svelte` (14줄) | **P2** |
| `system-health` | 시스템 상태 | ✅ 정식 구현 (4 카드) | `src/tabs/SystemHealthTab.svelte` (68줄) | P1.5 |
| `settings` | 설정 | ⚠️ refresh 토글만 | `src/tabs/SettingsTab.svelte` (28줄) | P2~P5 분산 |

### 5.2 위젯 (8개, W1~W8)
| ID | 라벨 | 위치 | 상태 | 파일 |
|---|---|---|---|---|
| **W1** | Stage Stepper (tokenizer → predictor 2단계) | Hero Strip | ✅ 구현 | `src/widgets/W1_StageStepper.svelte` (47줄) |
| **W2** | Readiness 신호등 + 완료예상 카운트다운 | Hero Strip | ✅ 구현 | `src/widgets/W2_ReadinessCountdown.svelte` (27줄) |
| **W3** | Loss Curve (ECharts dataZoom + slider) | Live Training | ✅ 구현 | `src/widgets/W3_LossCurve.svelte` (81줄) |
| **W4** | ETA Timeline (학습 시작/현재/완료예상) | Live Training | ✅ 구현 | `src/widgets/W4_EtaTimeline.svelte` (57줄) |
| **W5** | GPU 스파크라인 (util/temp/VRAM × 3) | Live Training | ✅ 구현 | `src/widgets/W5_GpuSparkline.svelte` (64줄) |
| **W6** | Loss Volatility 통계 (mean/std/min/max) | Live Training | 🔒 placeholder | `src/widgets/W6_LossVolatility.svelte` (10줄) |
| **W7** | Status Badge (readiness message) | Hero Strip | ✅ 구현 | `src/widgets/W7_StatusBadge.svelte` (21줄) |
| **W8** | Backtest Gallery | STOM tab | 🔒 placeholder | `src/widgets/W8_BacktestGallery.svelte` (10줄) |

### 5.3 레이아웃 컴포넌트
| 파일 | 라인 수 | 역할 |
|---|---:|---|
| `src/App.svelte` | ~80 | 최상위 — Sidebar + Header + Tab content + Footer |
| `src/layout/Sidebar.svelte` | 55 | 좌측 NAV (≥md) / 상단 가로 NAV (<md) |
| `src/layout/HeroStrip.svelte` | 19 | Hero 영역 (W7 + W1 + W2 묶음) |
| `src/charts/EChartsRenderer.svelte` | 34 | ECharts 래퍼 (ResizeObserver) |

### 5.4 라이브러리 (TypeScript)
| 파일 | 라인 | 역할 |
|---|---:|---|
| `src/lib/api.ts` | 105 | fetch 헬퍼 + 응답 타입 정의 (TrainingStatus/HistoryResponse/ArtifactsResponse/GpuResponse) |
| `src/lib/stores.ts` | 77 | Svelte writable stores — trainingStatus, trainingHistory, artifacts, gpuStatus, gpuRing(720pt), lossPoints(1000pt), metricsLatest derived |
| `src/lib/polling.ts` | 81 | refreshSeconds 기반 자동 폴링 (status/history/gpu = 5s, artifacts = 30s) |
| `src/lib/theme.ts` | 82 | 디자인 토큰 owner, applyThemeToDocument, getEChartsBase, getPlotlyLayoutBase |
| `src/lib/kstFormat.ts` | 31 | KST 포맷터 (toKst, nowKst, finishKst, formatDuration) |
| `src/lib/readinessMap.ts` | 38 | readiness.level → 색/카피/Tailwind class 매핑 |
| `src/main.ts` | ~15 | Svelte mount 부트스트랩 |
| `src/app.css` | ~35 | Tailwind directives + CSS 변수 baseline + 신호등 글로우 |

---

## 6. API 엔드포인트 카탈로그 (24개, 모두 read-only)

### 6.1 학습 모니터링 (`/api/training/*`, 6개)
| 엔드포인트 | 메소드 | 사용처 | 응답 핵심 필드 |
|---|---|---|---|
| `/api/training/status` | GET | Hero/W1/W2/W4 | `status`, `latest_stage{train_stage, step, total_steps, overall_percent, stage_percent, eta_seconds, samples_per_second, updated_at}`, `readiness{level, label, message, predictor_started, predictor_complete}`, `stages[]` |
| `/api/training/history?limit=N` | GET | W3, P2 metrics | `points[{step, loss, learning_rate, epoch}]`, `latest_point`, `latest_progress`, `run_name`, `stage` |
| `/api/training/artifacts` | GET | Artifacts 탭 | `checkpoint_file_count`, `model_weight_file_count`, `predictor_started`, `label`, `message`, `recent_checkpoint_files[]`, `recent_model_weight_files[]` |
| `/api/training/gpu` | GET | W5, SystemHealth | `gpus[{name, utilization_gpu_percent, temperature_c, memory_used_mib, memory_total_mib, memory_used_percent, power_limit_watts, power_draw_watts, power_draw_available}]`, `total_memory_used_percent`, `generated_at`, `available` |
| `/api/training/runs` | GET | (P2 예정) | run 목록 (이름/경로/시작 시각/현재 stage) |
| `/api/training/logs?stage=&tail=` | GET | (P2 예정) | tokenizer/predictor stdout 마지막 N줄 |

### 6.2 STOM 진단/예측 (`/api/stom/*`, 9개)
| 엔드포인트 | 메소드 | 사용처 (P4 예정) |
|---|---|---|
| `/api/stom/summary` | GET | 전체 요약 |
| `/api/stom/prediction-files` | GET | 예측 파일 목록 |
| `/api/stom/qlib-backtests` | GET | 백테스트 목록 |
| `/api/stom/filter-reports` | GET | 필터 리포트 목록 |
| `/api/stom/prediction?file=` | GET | 예측 결과 상세 |
| `/api/stom/diagnostics?file=` | GET | 진단 지표 (MAE/RMSE/MAPE) |
| `/api/stom/recommendations?date=` | GET | top-k 추천 |
| `/api/stom/backtest-report?file=` | GET | 백테스트 상세 |
| `/api/stom/recommendation-export` | GET | 추천 CSV 다운로드 |

### 6.3 예측 모델 (`/api/*`, 5개)
| 엔드포인트 | 메소드 | 사용처 (P3 예정) |
|---|---|---|
| `/api/data-files` | GET | 데이터 파일 목록 |
| `/api/load-data` | POST | 데이터 로드 (body: file path) |
| `/api/predict` | POST | 예측 실행 (body: `{lookback, pred_len, temperature, top_p, T, device}`, device 기본 cpu) |
| `/api/load-model` | POST | 모델 로드 (body: `{model_path, device}`, device 기본 cpu) |
| `/api/available-models` | GET | 사용 가능 모델 목록 |
| `/api/model-status` | GET | 현재 로드된 모델 상태 |

---

## 7. 현재 디자인 토큰 (Dark Navy Operational)

### 7.1 색상 (theme.ts 정의)
```typescript
colors: {
  bg:            '#0f172a',  // slate-900 body
  card:          '#111827',  // gray-900 카드
  cardRaised:    '#0b1120',  // 중첩 카드
  border:        '#243244',  // 카드/nav 보더
  borderMuted:   '#1e293b',  // slate-800 서브 구분선
  text:          '#e2e8f0',  // slate-200 본문
  textMuted:     '#94a3b8',  // slate-400 보조
  textDim:       '#64748b',  // slate-500 더 약함
  textFaint:     '#475569',  // slate-600 최약 (섹션 제목)
  accent:        '#38bdf8',  // sky-400 액센트
  accentSubtle:  '#bfdbfe',  // blue-200 헤더 h1
  success:       '#22c55e',  // green-500
  warn:          '#f59e0b',  // amber-500
  danger:        '#ef4444',  // red-500
  info:          '#93c5fd',  // blue-300 링크
}
```

### 7.2 타이포그래피
- 본문: `'Segoe UI', 'Malgun Gothic', sans-serif` (Windows 우선)
- 모노: `'Consolas', 'D2Coding', monospace` (숫자 표시)
- 크기 스케일: 10/11/12/13/15/16/20/24px

### 7.3 라운딩/그림자/모션 (Tailwind config)
- 라운딩: 6 / 10 / 14px
- 그림자: 4단계 (sm/md/lg/xl)
- 트랜지션: fast 100ms / base 150ms / slow 400ms

### 7.4 현재 시각적 특징 (참고용)
- 모든 카드는 1px solid border + 14px radius
- Hero strip은 `linear-gradient(135deg, #0f172a 60%, #0c2045)` 으로 미묘한 깊이감
- 헤더는 `linear-gradient(135deg, #111827, #1d4ed8)` 으로 강조
- 신호등 도트는 글로우 효과 (`box-shadow: 0 0 8px <color>`)
- ECharts 차트는 그라디언트 영역 채우기 (rgba alpha 25% → 0%)

---

## 8. 절대 제약 사항 (Hard Constraints)

### 8.1 변경 금지 영역
| 경로 | 이유 |
|---|---|
| `webui/app.py` | 30+ API 엔드포인트 — 다른 v1 페이지와 공유 |
| `webui/templates/{index,training_dashboard,stom_dashboard,v2_shell}.html` | v1 페이지 보존 (v2 cutover 전까지 6개월 archive) |
| `finetune/`, `model/` | 학습 코드 + 모델 코어 |
| `_database/`, `webui/prediction_results/`, `webui/stom_predictions/` | 데이터/산출물 |
| `webui/v2/__init__.py` | Flask Blueprint 분기 로직 (KRONOS_V2_DIST toggle) |

### 8.2 행동 금지
- ❌ 신규 API 추가 (모든 데이터는 기존 24개 endpoint에서)
- ❌ POST/DELETE/PUT 호출 (UI는 GET만, 예외: `/api/predict`·`/api/load-model`·`/api/load-data`는 P3 본격 구현 시점)
- ❌ predictor 미완료 상태에서 정확도/수익률 ready 표시 금지 (readiness.level 정책 유지)
- ❌ Power draw 추정값 표시 금지 (`power_draw_available=false` 시 "실측 불가" 라벨)
- ❌ KST 변환을 API timestamp 자체에서 수행 금지 (표시 계층에서만)
- ❌ `eta_seconds` 원본 의미 변경 금지

### 8.3 행동 의무
- ✅ SSR meta marker (`kronos-v2-shell`, `kronos-v2-version`) 모든 변형에서 보존
- ✅ Vite `base: '/static/v2/dist/'` 유지 (Flask 정적 서빙과 매핑)
- ✅ 학습 중 GPU device 옵션 disable (학습 VRAM 충돌 방지 — `/api/load-model` body에서 device='cpu' 강제 또는 UI에서 GPU 옵션 숨김)
- ✅ Dist commit 정책 (REV-7) — `webui/static/v2/dist/`는 git에 포함

---

## 9. 리모델링 목표 (사용자 명시)

### 9.1 핵심 가치
1. **시각적으로 화려** — 단순 표/차트가 아니라 데이터가 "살아 움직이는" 모니터링 대시보드
2. **직관적 정보 전달** — 사용자가 한 화면에서 학습 상태/문제/예측 결과를 즉시 파악
3. **단일 진입점** — 7개 탭을 하나의 일관된 디자인 언어로 통일

### 9.2 디자이너에게 요청하는 개선 영역

#### A. 즉시 시각 개선 (현재 구현된 탭)
- [ ] **Hero Strip**: W7 상태 배지 + W1 단계기 + W2 신호등 + ETA를 한 시야에 더 강력하게 통합. 현재는 단순 카드 3개 분리.
- [ ] **메트릭 스트립** (`LiveTrainingTab.svelte` 4개 카드): 단순 숫자 표시에서 → 미니 트렌드 라인 / 변동률 화살표 / 색상 그라데이션 강화
- [ ] **W3 Loss Curve**: ECharts 기본 스타일 → 그라데이션 영역, 호버 시 큰 툴팁, 추세선, 임계값 표시 옵션
- [ ] **W4 ETA Timeline**: 세로 타임라인 → 가로 진척 바 + 마일스톤 마커 (tokenizer 100% / predictor 시작 / 완료) 시각화
- [ ] **W5 GPU 스파크라인**: 3개 미니 차트 → 통합 멀티-라인 차트 또는 풍부한 게이지/도넛
- [ ] **사이드바**: 단조로운 텍스트 메뉴 → 아이콘 강조 + 활성 상태 인디케이터 풍부화 + 하단 사용자/run 정보

#### B. 신규 디자인 사양 (placeholder 탭)
- [ ] **예측 워크벤치 (`ForecastWorkbenchTab`)**: 슬라이더(lookback/pred_len/temperature/top_p) + 입력 데이터 미리보기 + 예측 결과 캔들차트 + 실측 vs 예측 비교 + SEED 고정 토글
- [ ] **STOM 진단 (`StomDiagnosticsTab`)**: 진단 지표 카드 (MAE/RMSE/MAPE) + topk 추천 표 + Plotly heatmap (P4) + 백테스트 P&L 곡선
- [ ] **기록 & 런 (`HistoryRunsTab`)**: run 목록 (carousel/grid) + 각 run의 손실 곡선 미니어처 + 비교 모드 + checkpoint/artifact 인디케이터
- [ ] **설정 (`SettingsTab`)**: refresh 토글 외에 → 테마(현재 dark만, light 추가) / 언어 (한/영) / 알림 (브라우저 Notification API) / 데이터 표시 정밀도

#### C. 시스템적 시각 강화
- [ ] **micro-interaction**: 숫자 count-up, 카드 hover lift, 탭 slide/fade, 신호등 pulse
- [ ] **타이포그래피 정밀도**: 현재 단조로운 size scale → display/headline/body/caption 위계 명확화
- [ ] **아이콘 시스템**: 현재 이모지 사용 → SVG 아이콘 세트 (Lucide/Heroicons 또는 커스텀)
- [ ] **반응형**: 모바일 (≤640px) / 태블릿 (640~900px) / 데스크탑 / 와이드 (≥1536px) 각각 최적화
- [ ] **로딩 상태**: 단순 "불러오는 중..." → skeleton screen / shimmer
- [ ] **에러 상태**: API 실패 시 명확한 표시 + 재시도 버튼

### 9.3 디자인 영감 (참고)
- Datadog / Grafana / Linear / Vercel Analytics / GitHub Actions
- 단, 도메인은 **ML 학습 모니터링**이므로 금융 대시보드 스타일(Bloomberg/TradingView)도 부분 채택 가능
- Dark navy 톤은 유지 (학습 환경 운영 도구 컨텍스트)

---

## 10. 디자이너에게 요청하는 산출물

### 10.1 필수 (모든 작업 기본)
1. **수정/신규 작성된 모든 Svelte 파일** (`webui/v2_src/src/**/*.svelte`)
2. **수정된 theme.ts, app.css** — 새로운 디자인 토큰 + 글로벌 CSS
3. **수정된 tailwind.config.js** (필요 시 토큰 추가)
4. **빌드 검증**: `cd webui/v2_src && npm run build` 0 errors
5. **SSR marker 보존 검증**: `grep "kronos-v2-shell" webui/static/v2/dist/index.html` 통과
6. **pytest 통과**: `pytest tests/test_v2_route.py tests/test_v2_dist_marker.py tests/test_v2_blueprint_isolation.py -q` 모두 PASS

### 10.2 권장
7. **컴포넌트 트리 다이어그램** (Mermaid 또는 ASCII) — 신규 컴포넌트 추가 시
8. **변경 사항 요약** — 어떤 위젯이 어떻게 바뀌었는지
9. **스크린샷 캡처** (가능하면 Playwright `webapp-testing` 활용) — 데스크탑 1440x900 / 모바일 390x844 두 개

### 10.3 금지
- ❌ 신규 npm dependency 무단 추가 (목적/대안 명시 필요)
- ❌ `webui/app.py` 또는 `webui/templates/*.html` 수정
- ❌ 기존 API 시그니처 변경
- ❌ 학습 데이터/모델 파일 수정

---

## 11. 빠른 시작 (디자이너 워크플로우)

```powershell
# 1. 현재 상태 확인
cd D:\Chanil_Park\Project\Programming\Kronos
git status

# 2. v2_src 의존성 (이미 설치됨이면 skip)
cd webui\v2_src
npm install --prefer-offline --no-audit --no-fund

# 3. 디자인 작업 — Svelte/CSS 수정
# (Read/Edit webui/v2_src/src/**/*.svelte)

# 4. 빌드
npm run build
# 산출물: ../static/v2/dist/

# 5. Flask 재시작 (KRONOS_V2_DIST=1 로 dist 모드 활성화)
cd D:\Chanil_Park\Project\Programming\Kronos
$env:KRONOS_WEBUI_PORT = "5070"
$env:KRONOS_WEBUI_OPEN_BROWSER = "0"
$env:KRONOS_V2_DIST = "1"
C:\Python\64\Python3119\python.exe webui\run.py

# 6. 검증
curl http://127.0.0.1:5070/v2  # 200 + kronos-v2-shell marker
# 브라우저로 시각 확인

# 7. 테스트
C:\Python\64\Python3119\python.exe -m pytest tests/test_v2_route.py tests/test_v2_dist_marker.py tests/test_v2_blueprint_isolation.py -q

# 8. 폴백 검증
$env:KRONOS_V2_DIST = "0"
# Flask 재시작 후 /v2 가 P1 SSR Jinja shell 도 정상 작동 확인
```

---

## 12. 참고 파일 색인 (디자이너가 Read 할 가치 있는 파일)

### 12.1 디자인 결정 근거 (필독)
- `docs/kronos_dashboard_overhaul_plan.md` (544줄) — ralplan 합의 마스터 플랜, ADR, Pre-mortem, Revision Log
- `docs/kronos_dashboard_p1_5_design_spec.md` (618줄) — 디자인 토큰 상세, theme.ts 사양, 컴포넌트 트리, ECharts↔Plotly 공존 규칙
- `docs/kronos_dashboard_p1_5_build_checklist.md` (624줄) — 빌드 운영 체크리스트
- `docs/p1_5_nogo_reason.md` — 학습 실패 상황에서 P1.5 진행 결정 근거

### 12.2 현재 코드 (참고)
- `webui/v2_src/src/App.svelte` — 진입점, 탭 라우팅
- `webui/v2_src/src/lib/stores.ts` — 모든 상태 정의 (어떤 데이터가 흐르는지)
- `webui/v2_src/src/lib/theme.ts` — 현재 디자인 토큰
- `webui/templates/v2_shell.html` (1418줄) — P1 SSR 폴백 (시각 참고용, 동일 톤 유지)
- `webui/templates/training_dashboard.html` (623줄) — v1 학습 모니터 (디자인 영감)

### 12.3 git commit 히스토리
```
2695151 P1.5 Vite Svelte SPA 정식 전환
d0d58b2 P0 메트릭 스트립 (4 카드)
249a785 C 데스크탑 폴리시 (dataZoom, 신호등 카드, 아티팩트 카운트, 시스템 상태, 사이드바)
c6ca0ae A 모바일 반응형 (햄버거 nav rail, GPU 카드 1열, 푸터 wrap)
4e54f45 ETA 표시 버그 수정 (latest_stage 경로)
c1d24ee 탭 placeholder 카피 phase 번호 정정
888bb08 P1 SSR 골격 구축
5c46ccd ralplan 합의 계획 (P0)
```

---

## 13. 안전망 (rollback)

| 상황 | 명령 |
|---|---|
| 빌드 깨짐 | `git checkout HEAD -- webui/v2_src/ webui/static/v2/dist/` 후 재빌드 |
| 디자인 불만 | Flask 재시작 시 `KRONOS_V2_DIST=0` → P1 SSR 즉시 복귀 |
| 완전 복귀 | `git revert <designer-commit-hash>` |
| 긴급 | `webui/templates/v2_shell.html` (P1 SSR)은 항상 살아있음, dist 삭제만 해도 자동 폴백 |

---

## 14. 핸드오프 체크리스트 (디자이너가 시작 전 확인)

- [ ] `docs/kronos_dashboard_overhaul_plan.md` 읽음
- [ ] `webui/v2_src/src/lib/stores.ts` 읽음 (데이터 흐름 이해)
- [ ] `webui/v2_src/src/App.svelte` 읽음 (구조 이해)
- [ ] 현재 `/v2` 브라우저 캡처 1장 확인 (시각 baseline)
- [ ] `npm run build` 1회 성공 (환경 검증)
- [ ] 변경 금지 영역 8.1 표 숙지
- [ ] 행동 금지/의무 8.2/8.3 숙지

---

## 15. 한 줄 미션

> **"학습 모니터링 + 예측 워크벤치 + STOM 진단 + 아티팩트 + 시스템 상태 — 5개 도메인을 단 하나의 시각적으로 화려하고 직관적인 Svelte SPA로 통합하라. 학습 코드와 백엔드 API는 그대로 두고, 표시 계층만 다시 그려라."**

---

*핸드오프 작성자: Claude (현 세션)*
*작성일: 2026-05-16 KST*
*다음 단계: Claude `frontend-design` 스킬에 본 파일 전달 → 리모델링 PR*
