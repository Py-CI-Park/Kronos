import type { ProgramLaneId, ProgramScoreCriterion } from './programTypes';

export const PROGRAM_SCORE_RUBRIC: Readonly<Record<ProgramLaneId, readonly ProgramScoreCriterion[]>> = {
  platform: [
    { id: 'all-pages', points: 20, achieved: true, evidence: 'V6 13개 사용자 화면과 공통 결정 레일' },
    { id: 'research-status', points: 20, achieved: true, evidence: 'G1~G8와 75/63/20 점수 분리' },
    { id: 'evidence-viewer', points: 20, achieved: true, evidence: '비용·fold·seed·control·차단 원인 조회' },
    { id: 'readable-responsive', points: 15, achieved: true, evidence: 'UTF-8 한글·내부 표 스크롤·줄바꿈 규칙' },
    { id: 'tests-build', points: 10, achieved: true, evidence: '410 frontend tests와 production build 기준' },
    { id: 'direct-browser-qa', points: 5, achieved: false, evidence: 'loopback 브라우저 자동 QA 보안정책 차단' },
    { id: 'broker-operations', points: 10, achieved: false, evidence: '주문·브로커 UI는 범위 밖' },
  ],
  'rl-evidence': [
    { id: 'historical-rl', points: 15, achieved: true, evidence: 'D0~D6R2 기존 RL 실패·검증 기록 보존' },
    { id: 'cql-calibration', points: 15, achieved: true, evidence: 'DQN·CQL synthetic 3/3 seed 학습' },
    { id: 'negative-controls', points: 10, achieved: true, evidence: 'shuffled CQL과 random policy 분리' },
    { id: 'diagnostic-signal', points: 15, achieved: true, evidence: '5·10·20일 신호 진단 4/4 fold 양수' },
    { id: 'promotion-signal', points: 15, achieved: false, evidence: 'PIT·수정주가·available_at 미확인' },
    { id: 'economic-model', points: 15, achieved: false, evidence: '실제 시장 controller model 미생성' },
    { id: 'fresh-oos', points: 15, achieved: false, evidence: 'G7 NOT_RUN_NO_READ' },
  ],
  engineering: [
    { id: 'typed-contracts', points: 15, achieved: true, evidence: '비용·체결·custody typed 계약' },
    { id: 'portfolio-environment', points: 15, achieved: true, evidence: '6천만원·정수주·10슬롯 invariant' },
    { id: 'model-artifacts', points: 15, achieved: true, evidence: 'DQN·CQL 저장·복원과 JSON receipt' },
    { id: 'python-tests', points: 15, achieved: true, evidence: '125 passed, 2 skipped 통합 회귀' },
    { id: 'frontend-tests', points: 10, achieved: true, evidence: '410 passed, Svelte 0 오류' },
    { id: 'runtime-server', points: 5, achieved: true, evidence: '5070 HTTP 200과 최신 bundle 확인' },
    { id: 'dynamic-receipt-api', points: 10, achieved: false, evidence: '현재 reviewed snapshot, 전용 API 미연결' },
    { id: 'visual-browser-qa', points: 15, achieved: false, evidence: '자동 viewport QA 미수행' },
  ],
  governance: [
    { id: 'prereg-first', points: 15, achieved: true, evidence: 'G1~G8 설계와 실행 기준 사전 고정' },
    { id: 'failure-honesty', points: 15, achieved: true, evidence: '좋은 진단과 NO-GO를 동시에 공개' },
    { id: 'claim-separation', points: 15, achieved: true, evidence: 'artifact·calibration·economic·OOS 상태 분리' },
    { id: 'branch-lineage', points: 15, achieved: true, evidence: 'v1.21~v1.28 단계별 한국어 커밋 계보' },
    { id: 'data-custody', points: 20, achieved: false, evidence: 'G2 custody blocker 5개' },
    { id: 'fresh-oos-approval', points: 10, achieved: false, evidence: 'G7 별도 승인 필요' },
    { id: 'remote-pr-release', points: 10, achieved: false, evidence: 'push·PR·tag 미수행' },
  ],
  live: [
    { id: 'fresh-oos-pass', points: 30, achieved: false, evidence: 'G7 Fresh OOS 미실행' },
    { id: 'paper-gate', points: 20, achieved: false, evidence: 'G8 paper-forward 잠금' },
    { id: 'broker', points: 30, achieved: false, evidence: '브로커 권한·주문 없음' },
    { id: 'risk-operations', points: 20, achieved: false, evidence: '운영 위험통제 미구축' },
  ],
};

export function programRubricScore(laneId: ProgramLaneId): number {
  return PROGRAM_SCORE_RUBRIC[laneId].reduce((sum, item) => sum + (item.achieved ? item.points : 0), 0);
}
