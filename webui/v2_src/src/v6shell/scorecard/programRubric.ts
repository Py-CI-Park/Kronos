import type { ProgramLaneId, ProgramScoreCriterion } from './programTypes';

export const PROGRAM_SCORE_RUBRIC: Readonly<Record<ProgramLaneId, readonly ProgramScoreCriterion[]>> = {
  platform: [
    { id: 'unified-pages', points: 20, achieved: true, evidence: 'V6 8개 페이지와 영구 URL을 공통 셸로 통합' },
    { id: 'research-status', points: 20, achieved: true, evidence: '프로그램·구현·경제·실거래 점수를 분리' },
    { id: 'evidence-viewer', points: 20, achieved: true, evidence: 'run·비용·seed·control·차단 원인을 직접 조회' },
    { id: 'readable-responsive', points: 15, achieved: true, evidence: '공통 토큰·반응형 grid·줄바꿈 규칙 적용' },
    { id: 'tests-build', points: 10, achieved: true, evidence: '프론트 회귀·Svelte check·production build' },
    { id: 'direct-browser-qa', points: 5, achieved: true, evidence: '실제 브라우저에서 URL·그래프·overflow 검증' },
    { id: 'broker-operations', points: 10, achieved: false, evidence: '주문·브로커 UI는 의도적으로 범위 밖' },
  ],
  'rl-evidence': [
    { id: 'historical-rl', points: 15, achieved: true, evidence: 'D0~D6R2 RL 실패와 검증 기록 보존' },
    { id: 'cql-calibration', points: 15, achieved: true, evidence: 'DQN·CQL synthetic 3/3 seed 학습' },
    { id: 'negative-controls', points: 10, achieved: true, evidence: 'shuffle CQL과 random policy 통제군 분리' },
    { id: 'diagnostic-signal', points: 15, achieved: true, evidence: '5·10·20일 신호 진단 4/4 fold 양수' },
    { id: 'promotion-signal', points: 15, achieved: false, evidence: 'PIT·수정주가·available-at 외부 권위 미확정' },
    { id: 'economic-model', points: 15, achieved: false, evidence: '비용 후 경제성 통과 시장 정책 미생성' },
    { id: 'fresh-oos', points: 15, achieved: false, evidence: 'Fresh OOS는 NOT_RUN_NO_READ' },
  ],
  engineering: [
    { id: 'typed-contracts', points: 15, achieved: true, evidence: 'Zod·Python 경계 계약과 fail-closed 응답' },
    { id: 'portfolio-environment', points: 15, achieved: true, evidence: '6천만원·10슬롯 종가매매 invariant' },
    { id: 'model-artifacts', points: 15, achieved: true, evidence: 'DQN·CQL 저장 모델과 평가 receipt' },
    { id: 'python-tests', points: 15, achieved: true, evidence: '백엔드·API 집중 회귀검증' },
    { id: 'frontend-tests', points: 10, achieved: true, evidence: 'V6 컴포넌트·계약 테스트와 Svelte check' },
    { id: 'runtime-server', points: 5, achieved: true, evidence: '공식 Flask 런타임과 최신 bundle 연결' },
    { id: 'dynamic-receipt-api', points: 10, achieved: true, evidence: 'catalog·telemetry·governance 경량 API' },
    { id: 'visual-browser-qa', points: 15, achieved: true, evidence: '실제 페이지·그래프·직접 URL을 브라우저 검수' },
  ],
  governance: [
    { id: 'prereg-first', points: 15, achieved: true, evidence: 'G1~G8 설계를 실행 전에 고정' },
    { id: 'failure-honesty', points: 15, achieved: true, evidence: 'NO-GO·실패·0거래를 숨기지 않음' },
    { id: 'claim-separation', points: 15, achieved: true, evidence: 'artifact·경제성·Fresh OOS·live 주장을 분리' },
    { id: 'branch-lineage', points: 15, achieved: true, evidence: '작업 브랜치 비FF 병합 및 병합 브랜치 보존' },
    { id: 'data-custody', points: 20, achieved: false, evidence: '외부 원천·PIT custody gate 미완료' },
    { id: 'fresh-oos-approval', points: 10, achieved: false, evidence: 'G7 별도 사람 승인 필요' },
    { id: 'remote-pr-release', points: 10, achieved: false, evidence: '원격 push·PR·release tag 미수행' },
  ],
  live: [
    { id: 'fresh-oos-pass', points: 30, achieved: false, evidence: 'Fresh OOS 미실행' },
    { id: 'paper-gate', points: 20, achieved: false, evidence: 'paper-forward 차단' },
    { id: 'broker', points: 30, achieved: false, evidence: '브로커 권한·주문 기능 없음' },
    { id: 'risk-operations', points: 20, achieved: false, evidence: '운영 위험 통제 미구축' },
  ],
};

export function programRubricScore(laneId: ProgramLaneId): number {
  return PROGRAM_SCORE_RUBRIC[laneId].reduce((sum, item) => sum + (item.achieved ? item.points : 0), 0);
}
