# Kronos v1.29.0-dev 개발선·릴리즈 계보

- 기준일: 2026-08-07 KST
- 직전 릴리즈: [`v1.28.0`](https://github.com/Py-CI-Park/Kronos/releases/tag/v1.28.0)
- 장기 개발선: `develop/v1.29.0-dev`
- 작업 브랜치: `codex/v1.29.0-dev-release-lineage`
- 모델 판정: `NO-GO`
- Fresh OOS: `NOT_RUN_NO_READ`
- 실거래: `BLOCKED`

## 계보

```text
v1.28.0
└─ develop/v1.29.0-dev
   ├─ codex/v1.29.0-dev-release-lineage      현재 작업·병합 후 보존
   └─ codex/v1.29.0-dev-<task>               이후 작업별 신규 브랜치
```

작업 브랜치는 최신 `develop/v1.29.0-dev`에서 생성하고 검증 후 `--no-ff`로 병합한다. 병합된 브랜치는 삭제·재사용하지 않는다. 하나의 기능 브랜치에서 기능·테스트·문서·생성 번들을 논리 커밋으로 분리하며, 같은 목적을 위해 새 브랜치를 연속 생성하지 않는다.

## 점수 변경

| 영역 | v1.28.0 릴리즈 전 | 현재 | 변경 근거 |
|---|---:|---:|---|
| 제품 구현·UX | 94 | 94 | 기능 변경 없음 |
| 프로그램 가중 성숙도 | 70 | 71 | 원격 개발·기능 브랜치, 주석 태그, GitHub Release 실제 게시 |
| 연구 거버넌스 | 60 | 70 | `remote-pr-release` 10점 직접 증거 확보 |
| 경제 모델 | 20 | 20 | 비용 후 시장 정책 성과 변화 없음 |
| 실거래 준비 | 0 | 0 | Fresh OOS·paper·broker 계속 차단 |

이번 1점 상승은 릴리즈 계보 증거만 반영한다. 모델 성능 점수나 수익성 점수를 올리지 않는다.

## 검증

- 프런트 전체: 454 passed, 0 failed
- Svelte: 0 errors, 0 warnings
- 프로덕션 빌드: 1,059 modules
- TypeScript 엄격 규칙: 위반 0건
- 개발선 UI 버전: `v1.29.0-dev`
- 최근 릴리즈 표시: `v1.28.0`
