# Kronos Wiki — 통합 지식 베이스

> **Kronos** 프로젝트의 모든 노하우와 시행착오를 한 곳에 정리합니다. 사용자가 직접 작성·갱신하는 살아있는 문서입니다.

이 wiki는 `/` 대시보드의 **문서** 탭에서 직접 읽을 수 있고, 마크다운 원본은 `docs/wiki/` 에 보관됩니다. 파일을 수정하면 `/api/docs/read?slug=...` 로 즉시 반영됩니다 (Flask 재시작 불필요).

---

## 카테고리

### 🌅 기초 (00~02)
- [00-index](00-index.md) — 이 문서 (목차)
- [01-overview](01-overview) — Kronos 무엇인가 / 누구를 위한가 / 목표
- [02-architecture](02-architecture) — 시스템 아키텍처 (백엔드/프론트엔드/모델/데이터 흐름)

### 📊 STOM 데이터 활용 (03~05)
- [03-stom-1tick](03-stom-1tick) — **1-tick (틱)** 데이터 활용법
- [04-stom-1min](04-stom-1min) — **1-min (분봉)** 데이터 활용법
- [05-stom-1day](05-stom-1day) — **1-day (일봉)** 데이터 활용법

### 🛠 운영 (06~08)
- [06-know-how](06-know-how) — 노하우 (학습 팁, GPU 최적화, OOM 회피)
- [07-trial-and-error](07-trial-and-error) — 시행착오 기록
- [08-setup](08-setup) — 환경 설정 / 실행 가이드

### 🔌 레퍼런스 (09~10)
- [09-api-reference](09-api-reference) — 24개 `/api/*` 엔드포인트
- [10-dashboard-guide](10-dashboard-guide) — v2 대시보드 7개 탭 사용 가이드

---

## 빠른 시작

```powershell
# 1. Flask 가동 (v2 SPA dist 모드)
cd D:\Chanil_Park\Project\Programming\Kronos
$env:KRONOS_WEBUI_PORT = "5070"
$env:KRONOS_V2_DIST = "1"
C:\Python\64\Python3119\python.exe webui\run.py

# 2. 브라우저
# http://127.0.0.1:5070/        ← 새 통합 대시보드 (이 wiki 도 여기 "문서" 탭에서 읽음)
```

## 문서 작성 가이드

- 파일명: `NN-slug.md` 형식 (NN = 정렬용 2자리 숫자, slug = kebab-case)
- 첫 줄에 `# 제목` (H1) 필수 — 사이드바 라벨로 사용됨
- 한국어 우선, 코드 블록은 ` ```언어 ` 사용
- 새 문서 추가 시 본 `00-index.md` 의 카테고리 목록에도 링크 추가
- 이미지는 권장하지 않음 (마크다운 인라인 SVG 또는 ASCII 다이어그램 사용)

## 갱신 이력

| 날짜 | 항목 |
|---|---|
| 2026-05-18 | 초기 골격 10개 문서 작성 (Claude 자동) |
