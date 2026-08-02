import type { ProgramCapability } from "./programTypes";

export const PROGRAM_CAPABILITIES = [
  {
    id: "d0-d3-history",
    capability: "D0~D3 검증 증거 조회",
    state: "AVAILABLE",
    boundary: "기존 판정은 변경하지 않음",
  },
  {
    id: "d4-primary",
    capability: "D4 4-algorithm × 2-reward × 3-seed",
    state: "AVAILABLE",
    boundary: "DQN train-only 확인; 수익성 근거 아님",
  },
  {
    id: "d5-primary",
    capability: "D5 DQN × 2-reward × 5-seed · 23bp",
    state: "AVAILABLE",
    boundary: "10개 실제 RL 모델; full-train gate NOT_CONFIRMED",
  },
  {
    id: "d5r-primary",
    capability: "D5R DQN × 2-reward × 3-seed × 2-checkpoint",
    state: "AVAILABLE",
    boundary: "capacity gate NOT_CONFIRMED",
  },
  {
    id: "d5s-primary",
    capability: "D5S DQN × 2-reward × 3-seed × 6-checkpoint",
    state: "AVAILABLE",
    boundary: "100K TRAIN_ONLY stability CONFIRMED",
  },
  {
    id: "d6-validation",
    capability: "D6 reused validation × 2-reward × 3-seed",
    state: "AVAILABLE",
    boundary: "6 evaluations; validation NO-GO; D7 locked",
  },
  {
    id: "artifact-audit",
    capability: "prereg·receipt·custody 감사",
    state: "AVAILABLE",
    boundary: "로컬 연구 evidence",
  },
  {
    id: "d6r-research",
    capability: "D6R train-only falsification",
    state: "AVAILABLE",
    boundary: "60 models·3M steps·5 folds; 1/10 gates; D7 locked",
  },
  {
    id: "d6r2-research",
    capability: "D6R2 MDP-specification falsification",
    state: "AVAILABLE",
    boundary: "70 evaluations·2/13 gates·18/100 NO-GO; D7 read 금지",
  },
  {
    id: "etf-q0-prereg",
    capability: "ETF stateful MDP Q0 사전등록",
    state: "AVAILABLE",
    boundary: "23bp primary·5-fold·3-shuffle·Q3 lock 고정",
  },
  {
    id: "etf-q0-q2-foundation",
    capability: "ETF Q0~Q2 foundation runner",
    state: "PARTIAL",
    boundary: "Q1 BLOCKED·Q2-A NO-GO·Q2-B 3/3 PASS; diagnostic only",
  },
  {
    id: "etf-q1-data",
    capability: "ETF point-in-time data readiness",
    state: "BLOCKED",
    boundary: "PIT universe·identity·available_at·total return 없음",
  },
  {
    id: "etf-q2a-signal",
    capability: "ETF 20일 momentum signal floor",
    state: "BLOCKED",
    boundary: "23bp -9.23bp·native-shuffle -2.33bp·positive folds 1/5",
  },
  {
    id: "etf-q2b-environment",
    capability: "ETF stateful accounting synthetic gate",
    state: "AVAILABLE",
    boundary: "cash·units·position·23bp invariant; known policy 3/3 PASS",
  },
  {
    id: "etf-q3-ppo",
    capability: "ETF Residual MLP PPO pilot",
    state: "BLOCKED",
    boundary: "Q1·Q2-A 미통과; NOT_RUN; model score 변경 없음",
  },
  {
    id: "fresh-oos",
    capability: "D7 Fresh OOS 조회",
    state: "BLOCKED",
    boundary: "NOT_RUN_NO_READ",
  },
  {
    id: "live-trading",
    capability: "브로커 주문·라이브 운영",
    state: "BLOCKED",
    boundary: "권한·검증·운영 체계 없음",
  },
] as const satisfies readonly ProgramCapability[];
