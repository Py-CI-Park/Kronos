# STOM ts_imb RULE Sizing/Risk Operations Design - 2026-06-11

## Status

- Track: `RULE` (operations/sizing design) — NOT RL, NOT probability lane
- Strategy: `ts_imb RULE baseline — operations design, NOT RL`
- Cost: `23bp` (25bp 캐시 net pct에 +0.02pp 변환 적용)
- Data: full-universe 갭상승 인스턴스 캐시 `.omx/artifacts/gap_up_full/instances.json`
  (전체 29,139건 중 `pass_ts_imb == True` 부분집합 N=5,175, 세션 942개,
  구간 20220323–20260227)
- Evidence quality: idealized fill log (tp5/sl1 경로 체결 가정) — 슬리피지/부분체결
  미반영, in-sample 전체 구간 단일 통계
- Verdict 성격: 운영 파라미터 설계 근거. live-ready 주장 아님, 수익 보장 주장 아님.

이 문서는 `ts_imb` 갭상승 RULE 전략의 **운영 설계**(포지션 사이징, 동시 보유 한도,
일중 손실 중단)를 다룬다. 강화학습 결과가 아니며, 확률 레인(supervised gate)
결과도 아니다. 모든 수치는 비복리(non-compounded) 누적합 곡선 기준 퍼센트 포인트다.

## Exact command

```powershell
py -3.11 -m stom_rl.factory.sizing_lab --instances .omx/artifacts/gap_up_full/instances.json --output webui/rl_runs/sizing_lab/ts_imb_sizing_2026_06_11/sizing_summary.json
```

- Artifact: `webui/rl_runs/sizing_lab/ts_imb_sizing_2026_06_11/sizing_summary.json`
- Module: `stom_rl/factory/sizing_lab.py`
- Tests: `tests/test_stom_rl_factory_sizing_lab.py`

## 고정 비율(fixed fraction) 비교 — 23bp

각 트레이드가 `fraction × net_pct_23bp`만큼 누적합에 기여하는 비복리 곡선.
N=5,175, 트레이드당 평균 net +0.806% (23bp).

| Fraction | Total (pp) | Max drawdown (pp) | Longest losing streak |
|---:|---:|---:|---:|
| 0.25 | 1042.49 | 6.14 | 16 |
| 0.50 | 2084.98 | 12.29 | 16 |
| 1.00 | 4169.96 | 24.58 | 16 |

비복리 곡선에서 total과 MDD는 fraction에 정확히 선형이다. 따라서 fraction 선택은
수익률 대 MDD의 새로운 트레이드오프를 만드는 것이 아니라, **절대 MDD 허용치**를
어디에 둘 것인가의 문제다. 연속 손실 16회는 fraction과 무관하게 동일하다.

## 변동성 타게팅(vol target 1.0%/trade, window 50, max leverage 1.0) — 23bp

직전 트레이드까지의 롤링 표준편차(shift 1, min_periods 10)로 스케일을 정하는
인과적(causal) 사이징.

| Metric | Value |
|---|---:|
| Total (pp) | 1547.92 |
| Max drawdown (pp) | 10.43 |
| Mean scale | 0.375 |
| Longest losing streak | 16 |

비교: mean scale 0.375와 같은 크기의 **고정 비율 0.375**는 total ≈ 1563.7pp,
MDD ≈ 9.22pp가 된다(선형 스케일). 즉 이 로그에서 변동성 타게팅은 동일 평균
노출의 고정 비율보다 total은 낮고 MDD는 높다 — **우위 없음**. tp5/sl1 구조가
트레이드 분포의 꼬리를 이미 절단하고 있어 변동성 추정이 추가 정보를 주지 못하는
것으로 해석한다. 변동성 타게팅은 채택하지 않는다.

## 세션당 트레이드 수 분포 (동시 보유 한도 근거)

| Metric | Value |
|---|---:|
| Sessions | 942 |
| Max trades/session | 23 |
| p95 trades/session | 10.0 |
| Mean trades/session | 5.49 |

세션당 트레이드 수는 동시 보유 포지션 수의 상한(같은 세션의 모든 트레이드가
겹친다고 가정한 보수적 상한)이다.

## 일중 손실 중단(daily loss halt) 민감도 — 23bp, fraction 1.0 기준

세션 누적 net이 임계치 이하로 떨어지면 해당 세션 잔여 트레이드를 중단.

| Halt threshold | Total (pp) | No-halt total (pp) | Delta | Sessions halted | Trades skipped |
|---:|---:|---:|---:|---:|---:|
| -2.0% | 3161.99 | 4169.96 | -1007.97 (-24.2%) | 381 / 942 | 1234 |
| -3.0% | 3726.03 | 4169.96 | -443.93 (-10.6%) | 222 / 942 | 563 |
| -5.0% | 4071.69 | 4169.96 | -98.27 (-2.4%) | 59 / 942 | 127 |

이 idealized 로그에서는 평균 기대값이 양(+0.806%/trade)이므로 모든 중단 임계치가
total을 깎는다. 타이트한 -2.0% 중단은 total의 24.2%를 비용으로 치른다. -5.0%는
세션의 6.3%만 중단시키며 비용이 -2.4%에 그친다. 중단 규칙의 목적은 백테스트
수익 개선이 아니라 **로그에 없는 레짐 붕괴/시스템 오류에 대한 보험**이다.

## 권고 운영 규칙 (research defaults)

아래 권고는 idealized in-sample 증거에서 도출한 **연구용 기본값**이다. 어떤 실거래
적용 전에도 forward/paper 검증을 통과해야 하며, 그 자체로 live 준비 상태를
의미하지 않는다.

1. **사이징: 고정 비율 0.5.**
   트레이드오프: fraction 1.0 대비 total을 절반(4169.96 → 2084.98pp)으로 줄이는
   대신 MDD도 절반(24.58 → 12.29pp)이 된다. 연속 손실 16회 구간에서 fraction
   1.0의 노출은 자본 대비 과도하다고 판단한다. 변동성 타게팅은 동일 평균 노출의
   고정 비율 대비 우위가 없어 기각.
2. **동시 보유 한도: 10 포지션** (p95 trades/session = 10).
   세션의 95%를 제약 없이 수용하고, max 23 같은 꼬리 세션에서 집중 리스크를
   차단한다.
3. **일중 손실 중단: 세션 누적 -5.0% (fraction 1.0 명목 기준; fraction 0.5 적용
   시 실효 -2.5%).** -2.0%/-3.0%는 기대값을 과도하게 깎는다(-24.2%/-10.6%).
   -5.0%는 비용 -2.4%로 꼬리 세션 보험을 산다.
4. **전략 중단(stop-strategy) 조건: 롤링 200 트레이드 기대값(net_pct_23bp 평균)
   < 0 이면 신규 진입 중단 후 전략 재검토.** 이 로그의 전체 평균은
   +0.806%/trade이므로, 롤링 기대값이 0 아래로 내려가는 것은 레짐이 캐시 구간과
   달라졌다는 신호다. 재검토 없이 재가동 금지.

## Guardrails

- `ts_imb`는 RULE baseline이다. RL이 아니며 RL로 표기하지 않는다.
- 비용 기준: `23bp via +0.02pp conversion from 25bp cache`.
- idealized fill log 기반 in-sample 설계 증거다. OOS/walk-forward 검증 아님.
- live trading readiness 주장 없음. broker readiness 주장 없음. 수익 보장 주장 없음.
- 대시보드/아티팩트는 read-only evidence이며 수익성 증명이 아니다.
- 권고 운영 규칙은 forward/paper 검증 전까지 research default다.
