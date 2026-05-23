# STOM 강화학습 성과 모델 고도화 페이지 계획

작성일: 2026-05-23 KST  
브랜치: `feature/stom-rl-lab`  
OMX 계획: `.omx/ultragoal/goals.json`  
목표: **STOM tick/back data로 smoke가 아닌 full test split 기준 강화학습 성과를 검증하고, 실제 사용 가능한 모델 후보와 대시보드 비교 체계를 만든다.**

---

## 1. 이번 단계의 핵심 목적

이전 9페이지 작업은 “강화학습 실험실이 가능한가?”를 증명했다. 이번 단계는 한 단계 더 나아가 “실제로 쓸 만한 모델인가?”를 검증한다.

| 구분 | 이전 단계 | 이번 단계 |
|---|---|---|
| 목적 | RL 실험실 구축 | 수익성 검증과 모델 고도화 |
| 데이터 | STOM 2025 1초봉 episode manifest | 동일 데이터의 full test split 중심 |
| 모델 | contextual bandit smoke | contextual bandit full 평가 + DQN/PPO 확장 준비 |
| 검증 | 동작 확인, smoke cost gate | 전체 test split, baseline 대비, 비용 반영, drawdown |
| 대시보드 | run 단위 결과 확인 | 모델별 leaderboard와 smoke/full 구분 |
| 자동매매 판단 | 보류 | 지표 기반 사용/보류 판단 |

---

## 2. 오픈소스 참고 원칙

새 dependency는 바로 추가하지 않는다. 먼저 현재 STOM 전용 구현을 full 검증으로 확장하고, 필요한 경우에만 별도 단계에서 dependency를 검토한다.

| 참고 자료 | 활용 방식 | 현재 적용 방향 |
|---|---|---|
| Gymnasium | `reset/step` 환경 인터페이스 표준 | 기존 `StomTickTradingEnv` 계약 유지 |
| Stable-Baselines3 | DQN/PPO 등 표준 RL 알고리즘 후보 | P006에서 dependency 필요성 판단 |
| FinRL | 금융 RL에서 data split, transaction cost, risk metric 중요 | baseline/cost gate/rolling validation 강화 |
| RLTrader | 주식 매매 action, reward, portfolio 평가 아이디어 | action/reward 확장 후보로 참고 |
| 기존 STOM/Kronos 결과 | 이전 예측·파인튜닝 실험의 실패/한계 | 비교 baseline으로만 사용, Kronos 의존은 제거 |

참고 링크:

- Gymnasium: https://gymnasium.farama.org/
- Stable-Baselines3: https://stable-baselines3.readthedocs.io/
- FinRL: https://github.com/AI4Finance-Foundation/FinRL
- RLTrader: https://github.com/quantylab/rltrader

---

## 3. 현재 데이터 기준

현재 강화학습의 기준 데이터는 이미 생성된 STOM 2025 1초봉 episode manifest다.

| 항목 | 값 |
|---|---:|
| 전체 episode | 18,750 |
| 종목 수 | 1,638 |
| 거래일/session | 240 |
| train episode | 13,256 |
| val episode | 2,764 |
| test episode | 2,730 |
| 원본 export row | 33,360,325 |
| 시간 범위 | 09:00~09:30 |
| lookback | 300초 |
| reward horizon | 300초 |
| split overlap | 0 |
| DB 접근 | read-only |

---

## 4. 성공/실패 판정 기준

이번 단계는 “모델이 좋아 보인다”가 아니라, 아래 기준을 통과해야 성공으로 본다.

| 판정 항목 | 성공 기준 |
|---|---|
| baseline 대비 | no-trade/random/buy-and-hold/momentum 중 핵심 baseline보다 비용 후 우위 |
| 비용 반영 | 25bp 이상 비용에서 평균 episode net return 양수 |
| 거래 안정성 | trade count가 0에 가깝거나 과도하지 않음 |
| 리스크 | max drawdown이 허용 범위 이내 |
| 일반화 | train이 아니라 test split에서 성과 확인 |
| 반복성 | rolling fold에서 positive fold rate 기준 충족 |
| 대시보드 | smoke/full run이 명확히 구분되고 leaderboard에 표시 |

실패 기준도 명확히 둔다.

| 실패 유형 | 해석 |
|---|---|
| buy-and-hold보다 낮음 | 모델 사용 보류 |
| 비용 전에는 양수, 비용 후 음수 | 실거래 부적합 |
| 특정 일자/종목에만 편중 | 과최적화 의심 |
| 거래가 너무 많음 | 수수료/슬리피지에 취약 |
| 거래가 거의 없음 | 모델이 실질적으로 no-trade와 유사 |

---

## 5. OMX 페이지 계획

| 페이지 | 이름 | 목표 | 완료 기준 | 상태 |
|---:|---|---|---|---|
| 1 | 성과 기준 재정의 | smoke/full 구분, 성공 기준, 오픈소스 참고 원칙 문서화 | 본 문서 작성, 검증, 커밋 | 완료 |
| 2 | full baseline/cost gate | test split 전체 baseline과 비용 관문 실행 | full artifact 생성, 요약 수치 확보 | 남음 |
| 3 | contextual bandit full eval | train 기반 모델을 test split 대규모로 평가 | baseline 대비 성과 산출 | 남음 |
| 4 | leaderboard artifact | baseline/RL/cost gate 결과 통합 | JSON/CSV leaderboard 생성 | 남음 |
| 5 | dashboard leaderboard | 웹에서 smoke/full 및 모델별 성과 비교 | build/browser smoke 통과 | 남음 |
| 6 | DQN/PPO 확장 설계 | SB3/Gymnasium 확장 여부 판단 | dependency/리스크/구현안 문서화 | 남음 |
| 7 | 최종 리뷰 | QA, code review, 사용/보류 판단 | 최종 보고서와 checkpoint | 남음 |

현재 진행률: **1 / 7 = 14.3%**

`█░░░░░░ 14.3%`

---

## 6. 바로 다음 실행 후보

페이지 2에서는 기존 smoke run이 아니라 test split 전체 episode 기준 baseline/cost gate를 실행한다.

권장 명령:

```powershell
omx ultragoal complete-goals
```

페이지 2 내부에서 우선 실행할 실제 후보 명령은 다음과 같다.

```powershell
C:\Python\64\Python3119\python.exe -m stom_rl.baselines `
  --manifest webui\rl_runs\stom_1s_2025_episode_manifest\episode_manifest.json `
  --output-dir webui\rl_runs\stom_1s_2025_baselines_full_test `
  --split test `
  --max-episodes 0 `
  --cost-bps 25 `
  --slippage-bps 0

C:\Python\64\Python3119\python.exe -m stom_rl.cost_gate `
  --manifest webui\rl_runs\stom_1s_2025_episode_manifest\episode_manifest.json `
  --output-dir webui\rl_runs\stom_1s_2025_cost_gate_full_test `
  --split test `
  --max-episodes 0 `
  --cost-bps-values 5,10,15,25 `
  --slippage-bps-values 0 `
  --target-cost-bps 25
```

주의: full test split은 2,730 episode 전체를 사용하므로 smoke보다 시간이 더 걸린다. 하지만 이 단계가 있어야 “실제 성과가 있는 모델인가?”를 말할 수 있다.

---

## 7. 현재 판단

현재 강화학습은 **가능**하다. 그러나 현재 성과 모델은 **아직 실거래 사용 가능 모델로 확정되지 않았다.**

이번 새 goal의 핵심은 다음이다.

1. 전체 test split에서 기준선을 먼저 고정한다.
2. RL 모델이 그 기준선을 이기는지 본다.
3. 비용과 drawdown을 반영한다.
4. 웹 대시보드에서 모델별로 비교한다.
5. 성과가 부족하면 “왜 부족한지”를 지표로 문서화한다.
