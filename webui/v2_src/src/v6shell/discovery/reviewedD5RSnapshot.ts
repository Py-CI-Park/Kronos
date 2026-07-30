import type { DiscoveryArmEvidence, DiscoveryEvidence } from './discoveryEvidence';

type Reward = 'NATIVE' | 'SHUFFLED';
type Row = readonly [Reward, number, number, number, number, number, number];
const rows: readonly Row[] = [
  ['NATIVE',0,400000,.541012,.682285,.682285,.693349], ['NATIVE',0,800000,.429319,.575516,.575516,.581809],
  ['NATIVE',1,400000,.661431,.830500,.830500,.834707], ['NATIVE',1,800000,.497382,.616686,.616686,.630270],
  ['NATIVE',2,400000,.685864,.850378,.850378,.858158], ['NATIVE',2,800000,.551483,.713745,.713745,.725673],
  ['SHUFFLED',0,400000,.617801,.793164,-.110886,-.071777], ['SHUFFLED',0,800000,.424084,.604667,-.029010,-.006757],
  ['SHUFFLED',1,400000,.623037,.812914,-.050150,-.018382], ['SHUFFLED',1,800000,.483421,.594245,-.082648,-.044525],
  ['SHUFFLED',2,400000,.684119,.846570,-.135101,-.095328], ['SHUFFLED',2,800000,.527051,.674138,-.077913,-.040196],
];
const arm = ([reward, seed, steps, accuracy, fitReward, nativeReward, zeroReward]: Row): DiscoveryArmEvidence => ({
  id:`D5R-C_DQN_DISCRETE/${reward}/${steps}`, model:`C_DQN_DISCRETE__${reward}/seed-${seed}/steps-${steps}`,
  seed, trainingTimesteps:steps, oracleRewardRatio:nativeReward, exactBasketAccuracy:accuracy, dominantActionRate:0,
  invalidActionCount:0, blockCount:0, noFillCount:0, shuffledReward:reward==='SHUFFLED', episodeCount:573,
  fitRewardRatio:fitReward, diagnosticCostRewardRatio:zeroReward,
});
export const REVIEWED_D5R_SNAPSHOT: DiscoveryEvidence = {
  authority:'REVIEWED_SNAPSHOT', evidenceManifest:'a2d71046a9636fc66c272fb95474c0529f39a5fe02367c8349efc35739742747',
  runName:'type2-d5r-primary-20260730-001', status:'COMPLETE', verdict:'D5R_CAPACITY_NOT_CONFIRMED', profile:'PRIMARY',
  freshOos:'NOT_RUN_NO_READ', reusedValidation:'NOT_RUN_NO_READ', type1Outcome:'D5R_CAPACITY_EVALUATED',
  primaryRoundTripCostBp:23, diagnosticRoundTripCostBp:0,
  preregSha256:'bd5e771b10c9e3551030848675b57afa9db9f3f9b71cfd7e898e1acdc9f6176f',
  promotionAllowed:false, profitabilityClaimAllowed:false, nativeAccuracyLift:-.1762652705061083,
  nativeRewardRatioLift:-.23369979489564807, nativeDeltaVsShuffled:.6945988493746474, improvingSeedFraction:0,
  arms:rows.map(arm),
};
