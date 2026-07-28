import type { DiscoveryArmEvidence, DiscoveryEvidence } from './discoveryEvidence';

const arm = (
  id: string,
  seed: number,
  ratio: number,
  accuracy: number,
  dominant: number,
  shuffledReward = false,
): DiscoveryArmEvidence => ({
  id,
  model: `${id}/seed-${seed}`,
  seed,
  trainingTimesteps: 16_384,
  oracleRewardRatio: ratio,
  exactBasketAccuracy: accuracy,
  dominantActionRate: dominant,
  invalidActionCount: 0,
  blockCount: 0,
  noFillCount: 0,
  shuffledReward,
});

export const REVIEWED_DISCOVERY_SNAPSHOT: DiscoveryEvidence = {
  authority: 'REVIEWED_SNAPSHOT',
  evidenceManifest: 'ef4403f2e7926008e2e58f1c83d04ccb5191ff43fba245479a80cbae4c117ede',
  runName: 'type2-d1-primary-v3-20260728',
  status: 'PRIMARY_COMPLETE',
  verdict: 'D1_ACTION_REWARD_CONFIRMED',
  profile: 'PRIMARY',
  freshOos: 'NOT_RUN_NO_READ',
  type1Outcome: 'COMPLETE_NO_GO',
  primaryRoundTripCostBp: 23,
  preregSha256: '58de192fe007d0a976bd4a364dd8085e47935f50ead263382560de6bf2b33100',
  promotionAllowed: false,
  profitabilityClaimAllowed: false,
  arms: [
    arm('A_BINARY_NATIVE', 0, 1, 1, .75),
    arm('A_BINARY_NATIVE', 1, 1, 1, .75),
    arm('A_BINARY_NATIVE', 2, 1, 1, .75),
    arm('B_BINARY_DIAGNOSTIC', 0, 1, 1, .75),
    arm('B_BINARY_DIAGNOSTIC', 1, 1, 1, .75),
    arm('B_BINARY_DIAGNOSTIC', 2, 1, 1, .75),
    arm('C_BINARY_SHUFFLED', 0, 0, .25, 1, true),
    arm('C_BINARY_SHUFFLED', 1, 0, .25, 1, true),
    arm('C_BINARY_SHUFFLED', 2, 0, .25, 1, true),
  ],
};
