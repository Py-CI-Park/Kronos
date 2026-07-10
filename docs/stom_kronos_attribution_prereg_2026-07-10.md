# WP-R5a 사전등록 — Kronos zero-shot 귀속 실험 (2026-07-10)

> 계약 C9(사전등록)·C10(스모크→풀)·C4(비용 기준) 준수. 연구 전용 — 수익성/GO/모델빌드 주장 없음.
> 실행 코드: `finetune/run_zeroshot_attribution_eval.py` (테스트 `tests/test_stom_kronos_attribution.py`, 7 passed). 무거운 eval은 `finetune/evaluate_stom_1s_checkpoint.py`에 위임.

## 1. 질문 (결정 차단 미지수)

플래그십 파인튜닝 체크포인트는 681-윈도우 walk-forward에서 방향정확도 **0.4479 vs 랜덤 0.4493**(랜덤보다 못함), 누적 -19.86%로 비용 게이트 전부 실패했다. 그러나 **사전학습 원본(NeoQuasar/Kronos-small)을 동일 윈도우에서 평가한 적이 없어**, "파인튜닝이 실패한 것"인지 "1초/60s 지평에 애초에 신호가 없는 것"인지 구분 불가하다. 이 실험이 그 유일한 미지수를 해소한다.

## 2. 방법

- 동일 데이터셋·동일 36×3×50 walk-forward(681 윈도우): `finetune/qlib_exports/stom_1s_grid_pred60_2025/processed_datasets`, lookback 300 / predict 60 / max-symbols 50 / max-asofs 3 / max-sessions 36 / stride 300 / top-k 5.
- 비교군: **finetuned**(기존 산출물) · **pretrained zero-shot**(신규) · **random** · **persistence**.
- 결정론(WP-R5b): `--seed 42 --sample-count 5` (플래그십 평가는 단일 확률 샘플·무시드였음 — 재현·저분산 확보).

## 3. 실행 커맨드

```bash
# 스모크(축소, max-symbols/sessions 소량으로 배관 확인) 후 풀
py -3.11 finetune/run_zeroshot_attribution_eval.py --run --seed 42 --sample-count 5 --device cuda:0
# 위가 zero-shot eval을 실행하고 귀속 리포트를 생성한다. eval을 이미 돌렸다면:
py -3.11 finetune/run_zeroshot_attribution_eval.py --report-only
```
산출물: `webui/stom_predictions/stom_1s_pred60_zeroshot_attribution.json` + `docs/stom_kronos_attribution_report_generated.md`.

## 4. 사전등록 판정 규칙 (착수 전 고정 — 코드 `decide()`와 일치, ε=0.005)

| 조건 | 판정 | 다음 행동 |
|---|---|---|
| finetuned·pretrained 둘 다 랜덤 ±0.005 이내 | **NO_SIGNAL** | Kronos 재튜닝 동결 문서화. 60s에 신호 없음 — 파인튜닝 탓 아님. 300s(F14)는 탐색용만 |
| finetuned < pretrained − 0.005 | **TUNING_HARMFUL** | WP-R5c 토크나이저 재구성 + 데이터 표현(close_only/O=H=L=C) 수정 선행 |
| finetuned > pretrained + 0.005 | **TUNING_HELPED_COST** | 파인튜닝은 유효하나 60s가 비용 못 이김 → **F14(300s 전용 재튜닝, 23bp 게이트)** |
| finetuned ≈ pretrained (랜덤 위) 또는 결측 | **INCONCLUSIVE** | 시드/sample_count 늘려 재실행 |

## 5. 무결성 경계

- 이 실험은 **방향 신호 귀속**만 판정한다. 어떤 결과도 수익성/실거래/GO 주장으로 확장되지 않는다(false-lock 7종 불변).
- "NO_SIGNAL"은 실패가 아니라 **유효한 연구 결과**다 — 조작하지 않는다.
- 비용 게이트는 플랫폼 주 기준 **23bp**로 정렬(레거시 25bp 아님, C4). 방향정확도 판정은 비용 무관하나, 후속 Top-K/게이트 분석은 23bp를 쓴다.

## 6. 규모

681 윈도우 × 5 샘플 추론(GPU). 스모크(축소 max-symbols/sessions)로 배관 먼저 확인 후 풀 실행.
