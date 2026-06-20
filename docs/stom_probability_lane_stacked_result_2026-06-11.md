# Probability Lane Stacked Gate 결과 — `GO_CANDIDATE` — 2026-06-11

## Verdict

```text
주실험 A (stacked_ts_imb): GO_CANDIDATE  — 사전등록 gate A-G1~A-G7 전체 통과
보조실험 B (matched_threshold): SUPPORTING_FAIL (failed_count_match)
```

이 저장소 역사상 **처음으로 사전등록된 모든 gate를 통과한 학습 모델 후보**다.
단, 이것은 `supervised gate`(메타라벨) 연구 후보 자격이며 **수익 보장이 아니고,
실거래/브로커 준비 상태가 아니다.** RL이 아니며, `ts_imb`는 RULE baseline이다.
사전등록: `docs/stom_probability_lane_stacked_prereg_2026-06-11.md` (OOS 무수정).

## 모델 정의 (GO 후보)

```text
진입 후보 = ts_imb RULE (시초 등락율>=2% AND 체결강도>=100 AND 매수호가 imbalance>=0.5)
2차 선별 = 보정된 P(win) 엣지 회계: edge = P·E[win] + (1−P)·E[loss] > 0 일 때만 TAKE
모델     = HistGradientBoostingClassifier(seed 100, full-universe 27,311 학습) + isotonic
청산     = TP5 / SL1 / 09:25 (룰 그대로), 비용 23bp
```

## 실행

```powershell
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_stacked_2026_06_11 --mode stacked_ts_imb --prereg-doc docs/stom_probability_lane_stacked_prereg_2026-06-11.md --expected-split-hash cc0483b81cbb486b --parent-run probability_lane_tp5sl1_2026_06_11
```

split hash `cc0483b81cbb486b` (선행 실험과 동일, 동결 확인). 산출물:
`webui/rl_runs/probability_lane/probability_lane_stacked_2026_06_11/`.
Registry lineage: `probability_lane_tp5sl1_2026_06_11` → 본 run (walkforward, done).

## Gate 결과 (주실험 A)

| Gate | 기준 | 결과 | 통과 |
|---|---|---|---|
| A-G1 표본력 | OOS TAKE ≥ 100 | **3,609** | 통과 |
| A-G2 절대 수익 | TAKE 평균 > 0 | +0.954%/trade | 통과 |
| A-G3 증분 엣지 | TAKE 평균 > ts_imb 단독 | **+0.954% > +0.820%** (+0.134pp) | 통과 |
| A-G4 fold 일관성 | ≥3/5 fold | **5/5 fold 전부 양의 delta** | 통과 |
| A-G5 음성 컨트롤 | 셔플 시 A-G3 실패 | 셔플 = 전량 TAKE → delta 0 (선별 붕괴) | 통과 |
| A-G6 보정 skill | Brier ≤ 상수 | 0.2286 ≤ 0.2438 | 통과 |
| A-G7 Ablation | ≥3/5 우위 시 실패 | 1/5만 우위 | 통과 |

## Fold별 증거

| Fold | ts_imb n | TAKE | TAKE 평균% | ts_imb 평균% | delta | SKIP n | SKIP 평균% |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 743 | 366 | +1.454 | +0.979 | **+0.475** | 377 | +0.518 |
| 1 | 775 | 697 | +0.910 | +0.781 | +0.129 | 78 | −0.367 |
| 2 | 844 | 711 | +1.019 | +0.860 | +0.159 | 133 | +0.010 |
| 3 | 1,039 | 970 | +0.726 | +0.671 | +0.055 | 69 | −0.109 |
| 4 | 1,068 | 865 | +0.978 | +0.850 | +0.128 | 203 | +0.307 |

모델이 스킵한 860건의 평균은 +0.259%로 TAKE 평균(+0.954%)의 약 1/4 — 선별이
저가치 trade를 골라내고 있다는 직접 증거다.

## 의무 보고: 트레이드오프 (사전등록 보고 의무)

| 항목 | ts_imb 단독 | Stacked (모델) |
|---|---:|---:|
| OOS trade 수 | 4,469 | 3,609 |
| 평균 net/trade | +0.820% | **+0.954%** |
| 총합 net (비복리 pp) | **+3,664** | +3,441 |

평균은 +16% 개선되지만 **총합은 −6%**다 (스킵된 860건이 평균 +0.259%의 양수
가치를 갖기 때문). 이 모델의 가치는 "더 버는 것"이 아니라 **trade당 질을 높여
같은 위험 예산에서 더 큰 사이징을 가능하게 하는 것**이다. 자본이 제약이 아니라면
ts_imb 단독이 총합에서 우월하다. 이 트레이드오프를 숨기지 않는다.

## 보조실험 B (기록)

```powershell
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_matched_2026_06_11 --mode matched_threshold ...
```

verdict `SUPPORTING_FAIL` — TAKE 6,961건으로 ts_imb 4,469건 대비 1.56배
(허용 0.8~1.2 위반). validation 분위수 임계치가 OOS TAKE율로 이전되지 않았다.
방향성 기록: B의 TAKE 평균 +0.972% ≥ ts_imb +0.820%, 스킵 15,767건 평균 −0.057%.
사전등록 규칙대로 B는 성공 주장에 사용하지 않는다.

## 강건성 기록 (gate 아님, verdict 불변)

| Run | 캐시 | OOS TAKE | TAKE 평균% | ts_imb 평균% | 기록 |
|---|---|---:|---:|---:|---|
| `..._stacked_realized_...` | realized fill (N=1,349) | 138 | +1.249 | +1.017 | 전 gate 통과 (소표본) |
| `..._stacked_slgap_...` | sl_gap_stress (N=1,349) | 137 | +1.152 | +0.914 | 방향 양호하나 셔플 컨트롤 불안정(`failed_controls`) — 소표본 한계 명시 |

해석: 방향성은 fill 모드 전반에서 유지되나, N≈200 소표본에서 컨트롤이 흔들린다.
full-universe realized 재구축 검증이 필요하다 (아래).

## 이것이 의미하는 것 / 의미하지 않는 것

**의미하는 것:**
- 사전등록·OOS 무튜닝·5-fold·컨트롤·ablation 체계 아래에서, 학습 모델이 ts_imb
  RULE 위에 trade당 +0.134pp의 증분 엣지를 더한 백테스트 증거.
- P6(Full-Train RL) 차단 해제 **검토** 자격 발생 (사전등록 해석 경계).

**의미하지 않는 것:**
- 수익 보장 아님. idealized fill 로그 기반 백테스트다.
- 실거래/브로커 준비 아님. forward/paper 검증 전이다.
- "RL 성공" 아님 — 이것은 supervised gate다.

## 다음 단계 (우선순위)

1. **full-universe realized/sl_gap_stress 재검증**: 현재 강건성 기록은 N=1,349
   구캐시 기반. `gap_up_backtest.py`로 full-universe realized instances를 생성 후
   동일 사전등록 파이프라인 재실행.
2. **사이징 통합**: P10 운영 룰(고정 0.5, 동시 10, 일중 -5%)을 stacked TAKE
   집합에 적용한 운영 시뮬레이션 → "질 개선 → 사이징 상향" 가설의 정량화.
3. **read-only forward/paper 설계**: 신규 세션 도착 시 모델 P(win)/edge를 기록만
   하는 전향 검증 루프.
4. P6은 1~3 결과를 본 뒤 별도 사전등록으로만 재검토.

## 가드레일

`ts_imb`는 RULE baseline(RL 아님) · 23bp(+0.02%p 환산) · OOS 무튜닝 ·
대시보드 read-only · 수익 보장/실거래 준비 주장 없음 · `GO_CANDIDATE`는 연구
후보 자격이지 운영 승인이 아님.
