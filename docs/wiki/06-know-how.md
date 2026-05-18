# Kronos 운영 노하우

> 학습/예측/대시보드 운영 중 얻은 일반 노하우 모음. 시행착오는 [07-trial-and-error](07-trial-and-error) 참조.

## 학습 노하우 (사용자 작성 영역)

### GPU VRAM 절약
- (사용자 채울 자리: gradient checkpointing, mixed precision, batch size 축소 등)

### Tokenizer 단계 빠르게 끝내기
- (사용자 채울 자리)

### Predictor 단계 안정화
- (사용자 채울 자리)

## 데이터 노하우 (사용자 작성 영역)

### 한국어 컬럼명 처리
- 일부 테이블은 `close` 대신 `종가` 만 존재 → 학습 코드가 자동 매핑하지만 SQL 직접 조회 시 주의
- `/api/stom/summary` 의 `warnings` 필드로 확인 가능

### 결측 처리
- (사용자 채울 자리)

### 정상화 (Normalization)
- (사용자 채울 자리)

## 대시보드 노하우

### 라이트/다크 모드
- 우상단 sun/moon 아이콘 또는 설정 탭에서 토글
- 차트 색상이 자동 재계산 (CSS 변수 → ECharts palette)
- 야간 작업 시 다크 모드 권장 (눈 피로 ↓)

### 새로고침 주기 최적화
- **빠른 모니터링**: 2초 (디스크 IO 많음, 학습 중에는 비추천)
- **표준**: 5초 (기본, 학습과 무관)
- **저빈도**: 30~60초 (장시간 백그라운드 관찰)

### Live Training 탭 빠른 진단
1. **W7 상태 배지** → 학습 단계 + readiness
2. **W3 Loss Curve** → 손실 추세 (감소/정체/발산)
3. **W5 GPU 트렌드** → util 50% 미만이면 데이터 로더 병목 의심
4. **메트릭 스트립의 LR** → cosine scheduler 가 작동 중인지 확인

### History 탭 비교
- 정렬: "진척순" → 가장 멀리 간 run 부터 표시
- 필터: "실패" → OOM/interrupted 만 모아보기
- run name 의 prefix (예: `stom_1s_grid_pred60_2025_*`) 로 동일 실험군 추적

## 빌드 / 배포 노하우

### v2 SPA 변경 후 반드시
```powershell
cd webui\v2_src
npm run build
# webui/static/v2/dist/ 가 갱신됨
# 브라우저 강제 새로고침 (Ctrl+Shift+R) 권장 (asset hash 가 바뀌어도 캐시 영향 0)
```

### Flask 재시작 없이 코드 반영
- Flask `debug=True` 모드라면 `app.py` 수정 시 자동 reload (Werkzeug)
- v2 SPA dist 변경은 Flask reload 와 무관 — 정적 서빙

### Rollback (1초)
```powershell
$env:KRONOS_V2_DIST = "0"
# Flask 재시작 → P1 SSR Jinja shell 로 자동 폴백
```

### 새 라이브러리 도입 시
- 가능하면 dynamic import 사용 (`const Lib = await import('lib')`)
- 진입 시점에만 로드 → 초기 번들 크기 영향 0
- 예시: Plotly 는 STOM 탭 진입 시에만 로드 예정

## 키보드 단축키 (브라우저 기본)

- `Ctrl + R` — 새로고침
- `Ctrl + Shift + R` — 강제 새로고침 (캐시 무시)
- `F12` — DevTools (Console / Network 탭에서 폴링 확인 가능)

## 디버깅 노하우

### Flask 응답이 비어있을 때
```powershell
curl -s http://127.0.0.1:5070/api/training/status | python -c "import sys,json;print(json.load(sys.stdin))"
# 빈 응답 → Flask 다운, 503 → 백엔드 에러, 200 + {} → 데이터 로딩 실패
```

### 차트가 안 그려질 때
- DevTools Console 에서 ECharts 에러 확인
- `theme` store subscribe 가 작동 중인지 확인
- `palette` derived 가 빈 객체 반환하는지 확인

### SSR marker 검증
```powershell
curl -s http://127.0.0.1:5070/ | findstr kronos-v2-shell
# 출력 있으면 OK, 없으면 빌드 산출물 손상
```

---

*기여 환영. 학습/운영하면서 발견한 노하우를 자유롭게 추가해주세요.*
