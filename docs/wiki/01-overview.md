# Kronos 프로젝트 개요

## 한 줄 요약

**Kronos**는 K-line(캔들차트) 시계열 데이터를 양자화(Tokenizer) → 다음 step 예측(Predictor) 2단계 모델로 학습·추론하는 금융 시장 데이터 분석 도구입니다.

## 누구를 위한 것인가

- **사용자 1명** — ML 엔지니어 (단일 개발자, Windows 11)
- **하드웨어**: NVIDIA RTX 4080 SUPER, 16 GiB VRAM, Python 3.11.13
- **목적**: 한국 주식 시장(STOM 데이터셋)에 대해 K-line 패턴 학습 후 다음 60 step 예측

## 핵심 아키텍처 (2단계 학습)

```
   원본 K-line (OHLCV)
        ↓
  ┌────────────────────┐
  │  Tokenizer 학습     │  ← Stage 1
  │  (양자화 코드북)     │
  └────────────────────┘
        ↓ token sequence
  ┌────────────────────┐
  │  Predictor 학습     │  ← Stage 2
  │  (자기회귀 예측)     │
  └────────────────────┘
        ↓
  다음 K-line 예측 결과
```

## 기술 스택 총정리

| 영역 | 기술 |
|---|---|
| **백엔드** | Python 3.11 + Flask + Jinja2 (legacy templates) |
| **모델** | PyTorch + Hugging Face (Kronos-base / mini / tiny) |
| **데이터** | STOM SQLite DB (29.7 GiB, 2,425 호환 테이블, 9595만 추정 샘플) |
| **프론트엔드 v2** | Svelte 5 + Vite 5 + TypeScript + Tailwind prebuilt |
| **차트** | ECharts 5.5 (eager) + Plotly 2.35 (STOM dynamic import, 예정) |
| **디자인** | Pretendard Variable + JetBrains Mono, OKLch 토큰, light+dark |
| **GPU 모니터링** | nvidia-smi (read-only) |

## 라우트 구조 (2026-05-18 cutover 후)

| URL | 용도 |
|---|---|
| `/` | **신 통합 대시보드** (v2 SPA, 7 탭) |
| `/v1/` | v1 메인 예측 화면 (legacy, 6개월 archive) |
| `/v1/training` | v1 학습 모니터 (legacy) |
| `/v1/stom` | v1 STOM 진단 (legacy) |
| `/v2` | → `/` 로 301 리다이렉트 (호환) |
| `/api/*` | 24개 read-only 엔드포인트 |

## 목표

1. **단기**: predictor 학습 성공 → backtest 검증 → 실전 활용 가능 모델 확보
2. **중기**: 1-tick / 1-min / 1-day 다중 시간프레임 동시 학습
3. **장기**: 실시간 예측 API + 대시보드 통합 자동매매 (이건 아직 비전 단계)

## 파일 시스템 위치

```
D:\Chanil_Park\Project\Programming\Kronos\
├── webui/              # Flask 백엔드 + v2 SPA
│   ├── app.py          # 24+ API 엔드포인트
│   ├── v2/             # /v2 → / Blueprint
│   ├── v2_src/         # Svelte 소스 (이 wiki 도 여기서 렌더링됨)
│   ├── static/v2/dist/ # 빌드 산출물
│   └── templates/      # v1 legacy templates
├── finetune/           # 학습 코드 + outputs
├── model/              # Kronos 모델 코어
├── _database/          # STOM SQLite (29.7 GiB)
└── docs/wiki/          # ← 본 문서
```

## 관련 문서

- [02-architecture](02-architecture) — 더 자세한 아키텍처
- [08-setup](08-setup) — 환경 설정 + 실행
- [10-dashboard-guide](10-dashboard-guide) — v2 대시보드 사용법
