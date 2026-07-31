import { PROGRAM_SCORE_RUBRIC, programRubricScore } from "./programRubric";
import type { ProgramLane } from "./programTypes";

export * from "./programPages";
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
    evidence: "12개 페이지, D6R API, exact 60-evaluation custody",
    nextAction: "D6R2 MDP-specification falsification 연결",
  },
  {
    id: "rl-evidence",
    label: "RL Evidence",
    labelKo: "강화학습 증거",
    score: programRubricScore("rl-evidence"),
    weight: 30,
    state: "PARTIAL",
    evidence: "D6R 3M steps·5 folds·3 seeds → 1/10 gates, NO-GO",
    nextAction: "gamma=0 contextual 진단과 stateful portfolio MDP 분리",
  },
  {
    id: "engineering",
    label: "Engineering",
    labelKo: "엔지니어링",
    score: programRubricScore("engineering"),
    weight: 20,
    state: "STRONG",
    evidence: "D6R 60/60 평가, fail-closed verifier, terminal receipt",
    nextAction: "fold-local normalizer 계약 추가",
  },
  {
    id: "governance",
    label: "Governance",
    labelKo: "개발 거버넌스",
    score: programRubricScore("governance"),
    weight: 10,
    state: "STRONG",
    evidence: "D6R prereg·producer·custody·control 계보 완료",
    nextAction: "research→master→tag 계보 완료",
  },
  {
    id: "live",
    label: "Live Readiness",
    labelKo: "라이브 준비도",
    score: programRubricScore("live"),
    weight: 10,
    state: "BLOCKED",
    evidence: "D6R train falsification 실패; D7 Fresh OOS 봉인; 브로커 권한 없음",
    nextAction: "새 MDP 가설과 새 prereg 없이는 D7 진행 금지",
  },
] as const satisfies readonly ProgramLane[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(
    lanes.reduce((sum, lane) => sum + (lane.score * lane.weight) / 100, 0),
  );
}
