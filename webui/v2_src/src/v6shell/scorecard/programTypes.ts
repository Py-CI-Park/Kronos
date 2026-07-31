export type ProgramLaneId =
  "platform" | "rl-evidence" | "engineering" | "governance" | "live";
export type ProgramState = "STRONG" | "PARTIAL" | "BLOCKED";
export type CapabilityState = "AVAILABLE" | "PARTIAL" | "BLOCKED";
export type PagePriority = "P0" | "P1" | "P2" | "HOLD";
export type ProgramScoreCriterion = {
  readonly id: string;
  readonly points: number;
  readonly achieved: boolean;
  readonly evidence: string;
};
export type ProgramLane = {
  readonly id: ProgramLaneId;
  readonly label: string;
  readonly labelKo: string;
  readonly score: number;
  readonly weight: number;
  readonly state: ProgramState;
  readonly evidence: string;
  readonly nextAction: string;
};
export type ProgramPageRow = {
  readonly id: string;
  readonly group: string;
  readonly page: string;
  readonly purpose: string;
  readonly delivery: "BUILT";
  readonly evidenceState: string;
  readonly progress: number;
  readonly priority: PagePriority;
  readonly nextAction: string;
  readonly eta: string;
  readonly mergeGate: string;
};
export type ProgramCapability = {
  readonly id: string;
  readonly capability: string;
  readonly state: CapabilityState;
  readonly boundary: string;
};
