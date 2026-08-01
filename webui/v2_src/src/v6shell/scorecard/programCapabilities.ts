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
    state: "PARTIAL",
    boundary: "설계·prereg 필요; fold-local normalizer; D7 read 금지",
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
