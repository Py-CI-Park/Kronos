import type { ProgramLaneId, ProgramScoreCriterion } from "./programTypes";

export const PROGRAM_SCORE_RUBRIC: Readonly<
  Record<ProgramLaneId, readonly ProgramScoreCriterion[]>
> = {
  platform: [
    {
      id: "twelve-pages",
      points: 20,
      achieved: true,
      evidence: "V6 사용자 페이지 12개",
    },
    {
      id: "d6-api",
      points: 20,
      achieved: true,
      evidence: "D4~D6 전용 API와 변조 차단",
    },
    {
      id: "reviewed-snapshot",
      points: 20,
      achieved: true,
      evidence: "D6 6-evaluation custody snapshot",
    },
    {
      id: "global-research-ux",
      points: 18,
      achieved: true,
      evidence: "전 페이지 validation NO-GO/OOS 경계",
    },
    {
      id: "evidence-viewer",
      points: 20,
      achieved: true,
      evidence: "알고리즘·비용·control·split 조회",
    },
    {
      id: "broker-operations",
      points: 2,
      achieved: false,
      evidence: "브로커 운영 UI 범위 밖",
    },
  ],
  "rl-evidence": [
    {
      id: "real-rl-models",
      points: 18,
      achieved: true,
      evidence: "D5S 실제 DQN 6 lineages·36 checkpoints·2.4M steps",
    },
    {
      id: "negative-control",
      points: 15,
      achieved: true,
      evidence: "Native 대 Shuffled, 각 3 seeds",
    },
    {
      id: "algorithm-ablation",
      points: 12,
      achieved: true,
      evidence: "PPO·DQN·auxiliary PPO 비교",
    },
    {
      id: "supervised-ceiling",
      points: 10,
      achieved: true,
      evidence: "비-RL supervised 상한 분리",
    },
    {
      id: "cost-diagnostic",
      points: 10,
      achieved: true,
      evidence: "23bp Primary·0bp 진단",
    },
    {
      id: "train-only-stability",
      points: 10,
      achieved: true,
      evidence: "D5S 100K TRAIN_ONLY stability confirmed",
    },
    {
      id: "reused-validation",
      points: 15,
      achieved: false,
      evidence: "D6 1/7 gates pass; validation NOT_CONFIRMED",
    },
    {
      id: "fresh-oos",
      points: 10,
      achieved: false,
      evidence: "D7 NOT_RUN_NO_READ",
    },
  ],
  engineering: [
    {
      id: "held-inputs",
      points: 20,
      achieved: true,
      evidence: "held input hash 검증",
    },
    {
      id: "atomic-artifacts",
      points: 20,
      achieved: true,
      evidence: "원자적 summary·outcome·receipt 발행",
    },
    {
      id: "terminalization",
      points: 15,
      achieved: true,
      evidence: "실패·완료 terminal receipt",
    },
    {
      id: "matrix-identity",
      points: 15,
      achieved: true,
      evidence: "D4 24·D5 10·D5R 12·D5S 36·D6 6 exact matrix",
    },
    {
      id: "tests-build",
      points: 15,
      achieved: true,
      evidence: "Python·Svelte 검증",
    },
    {
      id: "signed-approval",
      points: 12,
      achieved: true,
      evidence: "Smoke HMAC 승인",
    },
    {
      id: "cross-process-resume",
      points: 3,
      achieved: true,
      evidence: "D6 실패 snapshot 통제 복구",
    },
  ],
  governance: [
    {
      id: "prereg-first",
      points: 25,
      achieved: true,
      evidence: "검증 읽기 전 prereg commit",
    },
    {
      id: "custody",
      points: 20,
      achieved: true,
      evidence: "commit·tree·artifact SHA",
    },
    {
      id: "failure-honesty",
      points: 15,
      achieved: true,
      evidence: "실패 run과 NO-GO 공개",
    },
    {
      id: "controls",
      points: 15,
      achieved: true,
      evidence: "shuffle control·3 seeds·6 evaluations",
    },
    {
      id: "claim-separation",
      points: 17,
      achieved: true,
      evidence: "RULE·supervised·RL 라벨 분리",
    },
    {
      id: "release-lineage",
      points: 8,
      achieved: true,
      evidence: "D6 prereg·producer·custody·release 계보",
    },
  ],
  live: [
    {
      id: "fresh-oos-pass",
      points: 30,
      achieved: false,
      evidence: "D7 Fresh OOS 미실행",
    },
    {
      id: "paper-gate",
      points: 20,
      achieved: false,
      evidence: "paper gate 잠금",
    },
    { id: "broker", points: 30, achieved: false, evidence: "브로커 권한 없음" },
    {
      id: "risk-operations",
      points: 20,
      achieved: false,
      evidence: "운영 리스크 체계 없음",
    },
  ],
};

export function programRubricScore(laneId: ProgramLaneId): number {
  return PROGRAM_SCORE_RUBRIC[laneId].reduce(
    (sum, item) => sum + (item.achieved ? item.points : 0),
    0,
  );
}
