# v2 대시보드 사용 가이드

8개 탭이 사이드바에 그룹화되어 표시됩니다. 모든 탭은 5초마다 자동 갱신됩니다 (artifacts/runs 는 30~60초).

## 탭 개요

### 오버뷰

#### 🔴 실시간 학습 (live-training)
- **Hero strip**: 학습 단계 (Stage 1/2) + 진행률 도넛 + 처리속도/완료예상
- **메트릭 스트립**: 현재 손실 · 학습 진척 · 처리 속도 · LR (4 카드)
- **W3 손실 곡선**: ECharts dataZoom + 200-step rolling 평균
- **W6 손실 통계**: 평균/표준편차/최저/최고 + 안정/변동 진단
- **W4 ETA 타임라인**: 시작/중반/현재/완료 마일스톤 + 진행률 바
- **W5 GPU 트렌드**: 사용률/온도/VRAM 3 라인 + 미니 도넛
- **사용 API**: `/api/training/{status,history,gpu,artifacts}`

#### 🟣 예측 워크벤치 (forecast)
- **모델 선택**: kronos-base / mini / tiny 카탈로그
- **데이터 파일 선택**: `/api/data-files` 의 OHLCV CSV 등
- **4 슬라이더**:
  - lookback (과거 참조 구간 크기)
  - pred_len (예측 길이)
  - temperature (샘플링 무작위성, 0.1~2.0)
  - top_p (누클리어스 샘플링, 0.1~1.0)
- **Seed 고정 토글**: 결정성 보장
- **Device**: CPU / CUDA (학습 중에는 CPU 권장 — VRAM 충돌 회피)
- **결과 차트**: ECharts 라인 — 입력 / 예측 / 실측 비교
- **사용 API**: `/api/{available-models,data-files,load-model,load-data,predict}`

### 분석

#### 🟢 예측 진단 (stom)
- **KPI 4 카드**: DB 크기, 총 row, 학습 가능 그룹, 예상 샘플
- **3 탭 파일 브라우저**: 예측 결과 / 백테스트 / 필터 리포트
- **상세 패널**: 파일 선택 시 메타데이터 + (예측 파일이면) `/api/stom/diagnostics` 자동 조회
- **경고 카드**: STOM summary 의 warnings (한국어 컬럼명 매핑 등)
- **사용 API**: `/api/stom/{summary,prediction-files,qlib-backtests,filter-reports,diagnostics}`

#### 📦 아티팩트 & 모델 (artifacts)
- **3 카드**: Checkpoints(tokenizer 누적) · Model Weights(사전학습) · Predictor(결과물)
- **파일 row 리스트**: 최근 checkpoint / weight 파일
- **사용 API**: `/api/training/artifacts`

#### 📜 기록 & 런 (history)
- **4 KPI**: 총 run / 완료 / 실패 / 진행 중
- **필터**: 전체 / 완료 / 실패 / 진행 중
- **정렬**: 최신순 / 이름순 / 진척순
- **run 카드 그리드**: 각 run 의 이름·상태·진행률·경로·갱신시각
- **사용 API**: `/api/training/runs`

### 시스템

#### 🖥 시스템 상태 (system-health)
- **3 KPI**: GPU 활용률 / 온도 / VRAM (임계값 기반 색상 분기)
- **GPU 시계열**: 1시간 ring buffer 멀티 라인
- **하드웨어 표**: 모델명·VRAM 용량·전력 한계·실측
- **폴링 상태 표**: 간격·버퍼·마지막 갱신
- **사용 API**: `/api/training/gpu`

#### ⚙️ 설정 (settings)
- **테마 카드 2개**: light / dark (즉시 적용 + localStorage)
- **사이드바 기본 상태**: collapsed 토글
- **새로고침 주기**: 2/5/10/30/60초 segment
- **Notification API**: 권한 요청 + 테스트 알림 (미지원/차단/기본/허용 상태 표시)
- **초기화 버튼**: 모든 localStorage 클라이언트 설정 리셋

#### 📚 문서 (docs) — 이 wiki
- **좌측**: docs/wiki/ 의 마크다운 파일 목록
- **우측**: 선택한 문서의 마크다운 렌더링 결과
- **사용 API**: `/api/docs/{list,read}` (read-only)
- **편집**: `docs/wiki/*.md` 파일을 직접 수정하면 새로고침으로 즉시 반영

## 사이드바 / 헤더 / 푸터

### 사이드바 (좌측 232px, collapse 시 72px)
- **Brand mark**: Kronos 로고 (민트 그라데이션)
- **NAV 그룹 3개**: 오버뷰 / 분석 / 시스템 (모바일에서는 가로 스크롤 nav rail)
- **하단 run-card**: 현재 활성 run 의 이름·상태·진행률 (있을 때만)

### 헤더 (sticky 64px)
- 좌: 사이드바 토글 버튼 + breadcrumb (`Kronos > {현재 탭 라벨}`)
- 중: 상태 pill (`readiness.label`)
- 우: KST 시계 + 마지막 갱신 시각 + sun/moon 테마 토글

### 푸터
- Kronos v2 P1.5 SPA · 마지막 갱신 · 폴링 주기 · 현재 상태

## 키보드 단축키 (브라우저 기본)

| 키 | 동작 |
|---|---|
| `Ctrl + R` | 새로고침 |
| `Ctrl + Shift + R` | 강제 새로고침 (캐시 무시) |
| `F12` | DevTools |

## 모바일 (≤900px)

- 사이드바가 자동으로 상단 가로 nav rail 로 전환
- 모든 그리드 1열 적층
- KPI 카드 2×2 또는 1열
- 헤더 시계가 축소됨 (모바일 ≤640px)

## 자주 묻는 질문

### Q. 학습이 멈췄나? 5초 동안 step 변화가 없음
- W5 GPU util 확인 → 0% 면 학습 프로세스 죽은 것
- `/api/training/status` 의 `status` 가 `failed` 인지 확인
- terminal 에서 finetune 프로세스 상태 확인

### Q. 손실이 너무 흔들림
- W6 손실 통계 σ 확인 → 임계값 0.06 이상이면 "변동" 표시
- learning rate 가 너무 높을 가능성
- batch size 너무 작을 가능성

### Q. 다크모드가 안 바뀜
- 우상단 헤더의 sun/moon 아이콘 클릭
- 또는 설정 탭에서 테마 카드 선택
- 변경 안 되면 DevTools Console 의 `theme` 이벤트 발사 확인

### Q. /v1/ 페이지가 필요해
- 6개월간 archive 유지 — 직접 URL 입력으로 접근 가능
- `/v1/`, `/v1/training`, `/v1/stom`

## 관련 문서

- [02-architecture](02-architecture) — 시스템 구조
- [09-api-reference](09-api-reference) — API 카탈로그
- [06-know-how](06-know-how) — 운영 노하우
