# V7 M1 tabular-Q v2 연구 결과 — 2026-07-20

> 문서 ID: `KRONOS-V7-M1-RESULT-2026-07-20`
> 사전등록: `docs/kronos_v7_prereg_m1_2026-07-20.json` (`KRONOS-V7-PREREG-M1-2026-07-20`, FROZEN)
> 판정: **`INCONCLUSIVE`** — 5개 seed 중 1개만 검증 기준 충족
> untouched test: **`NOT_RUN`** (GO 후보 아님 → 미개봉 유지)
> HTML 보고서: `webui/rl_runs/v6_daily_h1/v6_dataset_full_001/train_20260720T070920Z/report.html` (SHA `bf04fb81b612…`)
> 본 문서는 수익성·승격·실거래 주장을 하지 않는다.

## 실행

| 항목 | 값 |
|---|---|
| smoke | `v6_dataset_smoke_001` / `train_20260720T065420Z` → `INCONCLUSIVE`(1/1 seed) · **v1의 허위 NO_GO 트리거 재발 없음** |
| full | `v6_dataset_full_001`(786,872행, SHA `ae44c805…`) / `train_20260720T070920Z` · seeds 0–4 |

## full 검증 결과 @0.23%

| seed | val NAV | 수익률 | MDD | 거래 |
|---|---|---|---|---|
| 0 | ₩64,257,140 | +7.10% | 12.40% | 977 |
| 1 | ₩54,960,959 | −8.40% | 11.29% | 607 |
| 2 | ₩59,443,163 | −0.93% | 6.30% | 613 |
| 3 | ₩59,443,163 | −0.93% | 6.30% | 613 |
| 4 | ₩60,000,000 | 0.00% | 0.00% | 0 (무거래 수렴) |

기준선: no_trade ₩60.0M · rule_topk_ret5 ₩37.4M · rule_topk_low_vol ₩31.7M · rule_topk_inst ₩37.8M · random_topk ₩30.1M.

## 음성 대조군 (v2 exposure-matched)

5개 shuffled-label 대조군 전부 `control_fails=False` — 각 대조군 NAV가 `max(60M, exposure-matched 평균+2σ)` 이하. **v2 대조군 설계는 시장 표류에 의한 허위 발동 없이 라벨 누출 검사 기능을 유지함**(seed 0: 59.9M < 61.4M 등).

## 관측 (manifest 원문 요약)

- seed 분산 지속: 최종 NAV 범위 ₩54.96M~₩64.26M. seed 0만 기준 충족 — v1 full과 동일한 다수결 미달 패턴.
- seed 4는 무거래 정책으로 수렴(0 trades) — 탐색 경로 민감성이 여전한 핵심 한계.
- seed 2·3 동일 NAV — bucket 상태공간이 좁아 서로 다른 seed가 같은 정책에 도달.

## 판정과 후속

- 판정 원문: `INCONCLUSIVE` / "only 1 seed(s) satisfy validation criterion".
- 사후 재조정 금지 — 상태 표현·탐색 개선은 **새 사전등록 버전으로만**.
- untouched test는 계속 미개봉.

## 변경 히스토리

| 날짜 | 변경 | 작성자 |
|---|---|---|
| 2026-07-20 | 최초 기록 | GJC |
