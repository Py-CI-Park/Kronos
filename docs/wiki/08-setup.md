# 환경 설정 / 실행 가이드

## 최초 설정 (Fresh Install)

### 1. Python 환경
```powershell
# Python 3.11.13 권장 (현재 작업 환경)
C:\Python\64\Python3119\python.exe --version  # Python 3.11.13

# 의존성 설치
cd D:\Chanil_Park\Project\Programming\Kronos
C:\Python\64\Python3119\python.exe -m pip install -r requirements.txt
```

### 2. Node.js (v2 SPA 빌드용)
```powershell
node --version  # v20+ 권장
npm --version   # 10+ 권장

# v2_src 의존성 설치 (최초 1회)
cd webui\v2_src
npm ci --prefer-offline --no-audit --no-fund
```

### 3. v2 SPA 빌드
```powershell
# webui/v2_src/ 에서
npm run build
# 산출물: ../static/v2/dist/index.html, assets/*.css, assets/*.js
```

## 일상 실행

### Flask 서버 가동
```powershell
cd D:\Chanil_Park\Project\Programming\Kronos
$env:KRONOS_WEBUI_PORT = "5070"
$env:KRONOS_WEBUI_HOST = "127.0.0.1"
$env:KRONOS_WEBUI_OPEN_BROWSER = "0"
$env:KRONOS_V2_DIST = "1"
C:\Python\64\Python3119\python.exe webui\run.py
```

| 환경변수 | 기본 | 권장 |
|---|---|---|
| `KRONOS_WEBUI_PORT` | 7070 | **5070** |
| `KRONOS_WEBUI_HOST` | 0.0.0.0 | 127.0.0.1 (로컬 전용 시) |
| `KRONOS_WEBUI_OPEN_BROWSER` | 1 | 0 (수동 제어) |
| `KRONOS_V2_DIST` | 0 | **1** (P1.5 SPA 모드) |

### 브라우저 접속
- 새 통합 대시보드: `http://127.0.0.1:5070/`
- v1 legacy: `http://127.0.0.1:5070/v1/`, `/v1/training`, `/v1/stom`

## 학습 시작 (Finetune)

### finetune/ 디렉토리 구조
```
finetune/
├── configs/           # YAML 설정
├── outputs/<run-name>/
│   ├── logs/
│   │   ├── tokenizer.progress.json  ← /api/training/history 가 읽음
│   │   ├── tokenizer.stdout.log
│   │   └── predictor.*  (predictor 단계 후)
│   ├── checkpoints/
│   └── model_weights/
└── run.py             # 학습 실행 진입점
```

### 학습 명령 (예시 — 사용자 환경에 맞춤)
```powershell
cd D:\Chanil_Park\Project\Programming\Kronos
C:\Python\64\Python3119\python.exe finetune\run.py --config finetune/configs/stom_1min.yaml
```

## v2 SPA 변경 후 워크플로우

1. **소스 수정**: `webui/v2_src/src/**/*.svelte` 또는 CSS
2. **빌드**: `cd webui/v2_src && npm run build`
3. **확인**: 브라우저에서 `Ctrl+Shift+R` (강제 새로고침)
4. **테스트**: `pytest tests/test_v2_*.py -v`
5. **commit**: `git add webui/v2_src/ webui/static/v2/dist/ && git commit`

## 빠른 검증 명령

### 모든 라우트 200 확인
```powershell
$urls = "/", "/v1/", "/v1/training", "/v1/stom", "/api/training/status", "/api/training/gpu"
foreach ($u in $urls) {
  $code = curl -s -o NUL -w "%{http_code}" "http://127.0.0.1:5070$u"
  Write-Output "$u = $code"
}
```

### SSR marker 검증
```powershell
curl -s http://127.0.0.1:5070/ | findstr kronos-v2-shell
```

### pytest 전체
```powershell
cd D:\Chanil_Park\Project\Programming\Kronos
C:\Python\64\Python3119\python.exe -m pytest tests/ -v
```

### Playwright 캡처 (디버깅)
```powershell
C:\Python\64\Python3119\python.exe .omc\tmp\v2_root_screenshot.py
# 결과: .omc\tmp\root_full.png, root_fold.png
```

## Rollback 절차

### Quick (1초)
```powershell
$env:KRONOS_V2_DIST = "0"
# Flask 재시작 → P1 SSR Jinja shell 로 자동 폴백
# /v1/*, /api/* 모두 그대로 작동
```

### Hard (git revert)
```powershell
git log --oneline -10  # 되돌릴 commit 찾기
git revert <commit-hash>
# 또는 git reset --hard <commit-hash> (위험 — 사용자 확인 후)
```

## 트러블슈팅

| 증상 | 확인 |
|---|---|
| `/` 가 404 | Flask 가 실행 중인지 + v2 Blueprint 등록 여부 |
| `/` 가 빈 화면 | DevTools Console → ECharts/Svelte 에러 확인 |
| 차트가 그려지지 않음 | `/api/training/*` 응답이 200 + JSON 정상인지 |
| KST 시간이 다름 | 사용자 OS 의 timezone 설정 (Asia/Seoul 권장) |
| 빌드 후에도 변경 안 보임 | `Ctrl+Shift+R` 강제 새로고침 + dist 파일이 실제로 갱신됐는지 |

자세한 트러블슈팅은 [07-trial-and-error](07-trial-and-error) 참조.

## 관련 문서

- [02-architecture](02-architecture) — 시스템 구조
- [07-trial-and-error](07-trial-and-error) — 시행착오 + 해결책
- [10-dashboard-guide](10-dashboard-guide) — 대시보드 사용
