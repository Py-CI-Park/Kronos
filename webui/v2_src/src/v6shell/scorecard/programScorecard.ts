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
    evidence: "12개 페이지, D6 API, exact 6-evaluation custody",
    nextAction: "D6R train-only falsification 연결",
  },
  {
    id: "rl-evidence",
    label: "RL Evidence",
    labelKo: "강화학습 증거",
    score: programRubricScore("rl-evidence"),
    weight: 30,
    state: "PARTIAL",
    evidence: "D5S train success → D6 validation 1/7 gates, NO-GO",
    nextAction: "D6R 무거래·거래 페널티와 walk-forward train-only 검증",
  },
  {
    id: "engineering",
    label: "Engineering",
    labelKo: "엔지니어링",
    score: programRubricScore("engineering"),
    weight: 20,
    state: "STRONG",
    evidence: "D6 실패 snapshot 복구, 6/6 평가, terminal receipt",
    nextAction: "schema registry 분리로 대형 파일 경고 해소",
  },
  {
    id: "governance",
    label: "Governance",
    labelKo: "개발 거버넌스",
    score: programRubricScore("governance"),
    weight: 10,
    state: "STRONG",
    evidence: "D6 prereg·실패 보존·recovery·custody 완료",
    nextAction: "research→master→tag 계보 완료",
  },
  {
    id: "live",
    label: "Live Readiness",
    labelKo: "라이브 준비도",
    score: programRubricScore("live"),
    weight: 10,
    state: "BLOCKED",
    evidence: "D6 validation 실패; D7 Fresh OOS 봉인; 브로커 권한 없음",
    nextAction: "D6R 이후 새 확인 가설 없이는 D7 진행 금지",
  },
] as const satisfies readonly ProgramLane[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(
    lanes.reduce((sum, lane) => sum + (lane.score * lane.weight) / 100, 0),
  );
}
