# V7 P6 데이터 확장 검증 결과 — 수집 중복 판정 — 2026-07-20

> 문서 ID: `KRONOS-V7-P6-DATA-COVERAGE-RESULT-2026-07-20`
> 상태: `COMPLETE / COLLECTION_SKIPPED_BY_DUPLICATION`
> 근거 artifact: `docs/kronos_v7_p6_flow_coverage_2026-07-20.json`
> 검증 방식: 오프라인 read-only 감사(`scripts/verify_daily_flow_coverage_v7.py`), 네트워크 0

## 판정

| 후보 수집기 (Quant-Insight 패턴) | 판정 | 근거 |
|---|---|---|
| 투자자 수급 (`pykrx_flow_aggregate` 상당) | **DUPLICATE_SKIP** — 수집하지 않음 | universe 500 테이블 전수에서 `기관순매수`·`외국인현보유비율` 컬럼 커버리지 100%, 2024-01-01 이후 non-null 100.0% |
| 외국인 보유/한도 (`pykrx_foreign_ratio` 상당) | **DUPLICATE_SKIP** | `외국인현보유수량`·`외국인주문한도수량`·`상장주식수` 동일 커버 |
| 공매도 (`pykrx_shortselling` 상당) | **ABSENT_DEFERRED** — 이번에 수집하지 않음 | 일봉 DB에 공매도/대차/잔고 계열 컬럼 0건. 신규 데이터가 맞으나, **소비하는 사전등록이 없는 수집은 금지** 원칙에 따라 해당 feature를 명시한 새 prereg 승인 시점으로 이연 |

## 원칙 확인

- 계획서 P6 규칙 "중복이면 수집 생략하고 검증 보고서만" 적용.
- 기존 dataset 계약(`kronos_v6_joined_dataset.v1`)의 수급 feature(`foreign_ratio_prev`, `foreign_ratio_delta_5`, `inst_netbuy_norm_5`)는 이미 이 컬럼들에서 생성되므로 M1 v2(P7)는 추가 수집 없이 진행 가능.
- 수급 값의 공시·정정 시차(point-in-time) 미검증 캐비앗은 유지되며, 사용은 D-1 이하 feature 전용.

## 변경 히스토리

| 날짜 | 변경 | 작성자 |
|---|---|---|
| 2026-07-20 | 최초 기록 — 수집기 신설 없이 P6 종결 | GJC |
