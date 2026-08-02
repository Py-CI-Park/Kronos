import { PROGRAM_SCORE_RUBRIC, programRubricScore } from "./programRubric";
import type { ProgramLane } from "./programTypes";

export * from "./programPages";
export { PROGRAM_CAPABILITIES } from "./programCapabilities";
export { PROGRAM_SCORE_RUBRIC, programRubricScore };
export type * from "./programTypes";

export const PROGRAM_LANES = [
  {
    id: "platform",
    label: "Platform",
    labelKo: "플랫폼",
    score: programRubricScore("platform"),
    weight: 30,
    state: "STRONG",
    evidence: "12개 페이지, D6R2 70-evaluation custody, ETF Q0~Q2 receipt",
    nextAction: "ETF result SHA와 12페이지 gate 상태 유지",
  },
  {
    id: "rl-evidence",
    label: "RL Evidence",
    labelKo: "강화학습 증거",
    score: programRubricScore("rl-evidence"),
    weight: 30,
    state: "PARTIAL",
    evidence: "기존 모델 18/100; ETF Q2-A 23bp -9.23bp·1/5 fold NO-GO",
    nextAction: "Q1 custody와 새 supervised floor 없이는 PPO 금지",
  },
  {
    id: "engineering",
    label: "Engineering",
    labelKo: "엔지니어링",
    score: programRubricScore("engineering"),
    weight: 20,
    state: "STRONG",
    evidence: "ETF read-only DB·11 tests·5-fold/3-shuffle·stateful accounting",
    nextAction: "공식 point-in-time metadata adapter 추가",
  },
  {
    id: "governance",
    label: "Governance",
    labelKo: "개발 거버넌스",
    score: programRubricScore("governance"),
    weight: 10,
    state: "STRONG",
    evidence: "Q0 prereg→Q1/Q2 receipt→실행/부모 브랜치 계보",
    nextAction: "실행 브랜치→부모 연구 브랜치 PR·검토",
  },
  {
    id: "live",
    label: "Live Readiness",
    labelKo: "라이브 준비도",
    score: programRubricScore("live"),
    weight: 10,
    state: "BLOCKED",
    evidence: "ETF Q1·Q2-A 차단; Q3 NOT_RUN; D7 봉인; 브로커 권한 없음",
    nextAction: "PIT 데이터와 23bp signal floor 전까지 Q3·D7 금지",
  },
] as const satisfies readonly ProgramLane[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(
    lanes.reduce((sum, lane) => sum + (lane.score * lane.weight) / 100, 0),
  );
}
