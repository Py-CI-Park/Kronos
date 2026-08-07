# Kronos v1.28.0 연구 플랫폼 릴리즈

- 릴리즈일: 2026-08-07 KST
- 릴리즈 태그: `v1.28.0`
- 통합 대상: `develop/v1.28.0-dev`
- 최종 기능 브랜치: `codex/v1.28.0-dev-ux-unification`
- 버전 고정 커밋: `2016f4e`
- 정적 번들 커밋: `0186bc6`
- 제품 경계: 읽기 전용 강화학습 연구·증거 플랫폼
- 모델 판정: `NO-GO`
- Fresh OOS: `NOT_RUN_NO_READ`
- 실거래: `BLOCKED`

## 1. 릴리즈 판단

`v1.28.0`은 연구 실행, 학습 telemetry, 평가, 데이터·모델·거버넌스 증거를 한 화면 체계로 검토할 수 있는 **연구 플랫폼 릴리즈**다. 버전 태그는 경제적으로 성공한 종가매매 정책, Fresh OOS 통과, paper 또는 실거래 준비를 뜻하지 않는다.

플랫폼 릴리즈와 모델 승격을 분리한다. 자동화·API·브라우저 게이트는 통과했으므로 플랫폼을 릴리즈하지만, 일봉 종가 RL은 외부 PIT·available-at·공식 가격·기업행사 권위와 비용 후 OOS 성능이 미확정이므로 `NO-GO`를 유지한다.

## 2. 포함 기능

| 영역 | 릴리즈 범위 | 결과 |
|---|---|---|
| 통합 현황 | 플랫폼·연구·경제 모델·실거래 점수 분리 | 완료 |
| 연구 라이브러리 | 98개 run, 24건 페이지, 필터, 판정/lane 차트, 영구 상세 | 완료 |
| 실시간 학습 | reward·equity·drawdown·loss·exploration, 행동 타임라인·전체 표 | 완료 |
| 평가·비교 | 같은 lane 비교, 9단계 종가매매 계약, 430px 비교 차트 | 완료 |
| 데이터·증거 | PIT·가용시각·Fresh OOS·원천 권위 상태 | 완료 |
| 모델·산출물 | 파일 존재·로드·경제성·승격 상태 분리 | 완료 |
| 보고서·거버넌스 | 사전등록·결과·hash·사람 승인 계보 | 완료 |
| 설정 | 테마, 90·100·110·125% 배율, 안전 경계 | 완료 |

## 3. 릴리즈 검증

| 검증 | 명령·범위 | 결과 |
|---|---|---:|
| RL·비용·대시보드 Python | core/orderbook/rule/gate 8개 파일 | 102 passed, 2 skipped |
| V6 API·라우팅 Python | platform/research/telemetry/governance/route/dist | 71 passed |
| 프런트 전체 | `bun test src` | 454 passed, 0 failed |
| Svelte 검사 | `npm run check` 및 build 사전 검사 | 0 errors, 0 warnings |
| 프로덕션 빌드 | `npm run build` | 1,059 modules transformed |
| 브라우저 8페이지 | 실제 사이드바 클릭·제목·URL·overflow | 8/8 PASS |
| 반응형 브라우저 | 375·768·1280px × 8페이지 | 24/24 PASS, 가로 넘침 0 |
| 연구 라이브러리 | 1→2페이지 실제 이동 | 98건·5페이지·페이지당 24건 PASS |
| 실시간 행동 | action timeline·접근성 표 | 224 events·최근 12건 PASS |
| 평가 상호작용 | 9단계 중 비용 단계 클릭 | 9개 버튼·0.230% 상세·430px 차트 PASS |
| 브라우저 오류 | error/warn log | 0건 |

## 4. 점수와 승격 경계

| 평가축 | 릴리즈 점수 | 판정 |
|---|---:|---|
| 제품 구현·UX | 94/100 | 플랫폼 릴리즈 가능 |
| 연구 프로그램 | 70/100 | 반복 연구 가능, 외부 권위 미완료 |
| 일봉 종가 RL 연구 gate | 78/100 | G2·G7·G8 미완료 |
| 경제 모델 | 20/100 | 비용 후 성공 정책 미생성, `NO-GO` |
| 실거래 준비 | 0/100 | broker·paper·위험 통제 없음 |

95점 목표는 하나의 숫자로 경제성 실패를 숨기지 않는다. 차기 개발선에서는 플랫폼/릴리즈 품질, 연구 파이프라인, 경제 모델, 실거래 준비를 별도 산식으로 유지하며 각 주장에 직접 증거를 요구한다.

## 5. 차기 개발선

`v1.28.0` 태그 뒤에는 `develop/v1.29.0-dev`를 새 장기 개발선으로 만든다. 작업은 `codex/v1.29.0-dev-<task>`에서 시작해 검증 후 `develop/v1.29.0-dev`에 `--no-ff`로 병합한다. 병합된 브랜치는 삭제하거나 재사용하지 않는다.

차기 P0 순서는 다음과 같다.

1. 현재 DB의 날짜·종목·OHLCV·available-at·수정주가 의미를 다시 감사한다.
2. 일봉 종가 run의 표준 telemetry, 비용 구성요소, manifest를 같은 run ID로 묶는다.
3. 고정 사전등록 아래 TRAIN/Validation/OOS와 rule/random/shuffle 통제군을 반복한다.
4. 경제성 게이트 통과 전에는 Fresh OOS·paper·broker 승격을 열지 않는다.
