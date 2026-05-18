# 시스템 아키텍처

## 전체 흐름도

```
[브라우저]
    ↓ HTTP
[Flask :5070]
    ├─ / ────────────→ v2 Blueprint ──→ webui/static/v2/dist/index.html (SPA)
    ├─ /v1/* ─────────→ webui/templates/{index,training,stom}.html (legacy)
    └─ /api/* ────────→ JSON 응답 (read-only)
                            ↓ 데이터 읽기
                ┌───────────┼───────────┐
        finetune/outputs/  _database/  log files
        (progress.json,    (STOM DB)    (stdout)
         checkpoints)
```

## 데이터 흐름 (학습 시)

```
1. 학습 시작 (finetune/run.py 등)
       ↓
2. STOM SQLite 에서 OHLCV 로드 (_database/*.db)
       ↓
3. Tokenizer 단계 — K-line 을 토큰 시퀀스로 양자화
       ↓
4. progress.json 갱신 (step/loss/eta_seconds)
       ↓
5. /api/training/status 가 progress.json 읽음
       ↓
6. v2 SPA 가 5초마다 polling → Live Training 탭 업데이트
       ↓
7. Tokenizer 100% → Predictor 단계 자동 진입 (현재 OOM 으로 미진입)
       ↓
8. Predictor checkpoint 생성 → readiness gate `ready` 로 전환
       ↓
9. /api/predict 로 새 모델 사용 가능
```

## 백엔드 (webui/app.py · 1186 줄)

### 핵심 구성
- `Flask(__name__)` (static_folder=`webui/static`, static_url_path=`/static`)
- `CORS(app)` 활성화
- v2 Blueprint 등록 (P6 cutover)

### 라우트 분류
| 카테고리 | 개수 | 예시 |
|---|---|---|
| Page (legacy) | 3 | `/v1/`, `/v1/training`, `/v1/stom` |
| Page (v2) | 1 | `/` (v2 SPA) |
| Training API | 6 | `/api/training/{status,history,artifacts,gpu,runs,logs}` |
| STOM API | 9 | `/api/stom/{summary,prediction-files,qlib-backtests,filter-reports,prediction,diagnostics,recommendations,backtest-report,recommendation-export}` |
| Model API | 5 | `/api/{data-files,available-models,load-model,load-data,predict,model-status}` |
| Docs API (신규) | 2 | `/api/docs/{list,read}` |

## 프론트엔드 (webui/v2_src/)

### 진입 흐름
```
index.html
   ↓ <script type="module" src="/src/main.ts">
main.ts
   ↓ mount(App, target)
App.svelte
   ├─ Sidebar (8개 nav)
   ├─ Header (breadcrumb + clock + theme toggle)
   └─ Tab content (활성 tab 에 따라 분기)
        ├─ LiveTrainingTab (HeroStrip + W1~W7 + 메트릭)
        ├─ ForecastWorkbenchTab (4 슬라이더 + 결과 차트)
        ├─ StomDiagnosticsTab (KPI + 파일 브라우저)
        ├─ ArtifactsModelsTab
        ├─ HistoryRunsTab
        ├─ SystemHealthTab
        ├─ SettingsTab
        └─ DocsTab (← 본 wiki 표시)
```

### 데이터 흐름 (SPA)
```
App.svelte onMount
   ↓
polling.ts::startPolling()
   ├─ /api/training/status (5초)
   ├─ /api/training/history (5초)
   ├─ /api/training/gpu (5초)
   └─ /api/training/artifacts (30초)
        ↓ 응답
   stores.ts writable 갱신
        ↓ subscribe
   각 컴포넌트가 $state + $derived 로 반응
```

## 모델 (model/)

### Kronos 변형
| 모델 | 파라미터 | 컨텍스트 | 용도 |
|---|---|---|---|
| `kronos-base` | 102.3M | 512 | 더 높은 예측 품질 목표 |
| `kronos-mini` | (작음) | 2048 | 가벼운 모델로 빠른 예측 |
| `kronos-tiny` | (가장 작음) | (작음) | 디버깅 / 빠른 실험 |

### 학습 단계
1. **Tokenizer** — K-line OHLCV 시퀀스를 양자화 코드북으로 압축
2. **Predictor** — 양자화된 토큰 시퀀스를 자기회귀로 예측 (autoregressive)

## SSR Meta Marker (중요)

`/` 응답의 `<head>` 에 항상 다음 meta tag 가 포함됨:

```html
<meta name="kronos-v2-shell" content="hero,live-training,stom,forecast,artifacts,history,system-health" />
<meta name="kronos-v2-version" content="p1-5-spa" />
```

- 두 모드 (P1 SSR Jinja / P1.5 Vite dist) 모두에서 동일하게 노출
- pytest 가 grep 으로 검증
- SPA 가 mount 되어도 `<head>` meta 는 그대로 유지

## 환경변수 토글

| 변수 | 값 | 효과 |
|---|---|---|
| `KRONOS_V2_DIST` | `0` (기본) | `/` 가 P1 SSR Jinja shell 반환 |
| `KRONOS_V2_DIST` | `1` | `/` 가 P1.5 Vite SPA dist 반환 |
| `KRONOS_WEBUI_PORT` | `7070` (기본) | 5070 권장 (운영) |
| `KRONOS_WEBUI_OPEN_BROWSER` | `1` (기본) | `0` 으로 자동 브라우저 비활성화 |

## 관련 문서

- [08-setup](08-setup) — 실행 절차 상세
- [09-api-reference](09-api-reference) — API 엔드포인트 카탈로그
