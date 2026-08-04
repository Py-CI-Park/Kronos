# Kronos 강화학습 전체 진행용 재사용 프롬프트

이 문서는 `kronos_rl_v1_21_to_v1_29_master_execution_plan_2026-08-04.md`를 실제 개발·연구로 이어가기 위한 사용자 프롬프트다.

## 1. 권장 전체 진행 프롬프트

```text
Kronos 저장소의 다음 문서를 먼저 모두 읽고 현재 Git 상태와 실제 artifact를 다시 확인하세요.

1. docs/kronos_rl_economic_research_design_review_2026-08-04.md
2. docs/kronos_version_branch_release_policy_2026-08-04.md
3. docs/kronos_rl_v1_21_to_v1_29_master_execution_plan_2026-08-04.md
4. docs/kronos_daily_close_rl_recovery_result_2026-08-02.md

목표는 일봉을 이용해 일정 금액과 최대 10종목을 관리하는 종가 의사결정 강화학습 후보를 만드는 것입니다. 모델 파일 생성과 경제적 성공, Fresh OOS, paper/live 상태를 항상 분리하세요.

현재 master와 미커밋 변경을 확인하고 사용자 변경은 보존하세요. 작업은 codex/ 접두사의 단계별 브랜치에서 진행하고, 계획의 G1부터 순서대로 실행하세요. 각 단계는 테스트 우선, 구현, 검증, 결과 문서, 한글 Conventional Commit 순으로 완료하세요. 각 단계의 목표 minor 버전과 기존 버전 정책을 지키고 fix는 PATCH를 올리세요.

비용은 사용자 화면에서 %를 기본으로 사용하세요. 일반 KRX 주식 0.230%, NXT 주식 0.229%, 국내주식형 ETF 0.030%를 기본 명시비용으로 분리하고, spread/slippage/market impact와 이벤트 계좌 수수료를 별도 구성요소로 기록하세요. 기존 base_23bp artifact ID는 호환성을 위해 보존하되 UI 설명을 추가하세요.

당일 공식 종가를 feature와 동일 체결가격으로 동시에 사용하지 마세요. CLOSE_AUCTION_CAUSAL 또는 NEXT_SESSION_AFTER_DAILY_CLOSE 계약 중 하나를 결과 보기 전에 동결하세요. PIT universe, identity, available_at, total return custody가 통과하기 전 대규모 RL을 실행하지 마세요.

RL 환경은 cash, holdings, units, average price, holding age, exposure가 다음 상태에 유지되는 stateful MDP여야 합니다. 행동은 HOLD_CASH, HOLD, ADD_ONE, EXIT_ONE, REPLACE_ONE, REDUCE_RISK의 작은 공간을 우선하세요. reward는 비용이 반영된 self-financing NAV 변화로 계산하고 비용을 중복 벌점으로 차감하지 마세요. 최대 10종목·5천만원 노출·1천만원 reserve는 hard constraint로 구현하세요.

새 feature/horizon은 supervised signal floor를 먼저 통과해야 합니다. G3와 G4가 모두 통과할 때만 DQN과 CQL 중심의 최소 offline RL pilot을 실행하세요. PPO는 신뢰 가능한 다양한 trajectory simulator가 생기기 전 primary로 반복하지 마세요.

평가는 chronological nested 5-fold, 최소 3 seeds, shuffled controls, no-trade, RULE, supervised-only baseline, IQM와 bootstrap CI, turnover, MDD, cost drag를 포함하세요. 동일 validation을 본 뒤 threshold, seed, feature를 다시 맞추지 마세요.

Fresh OOS는 자동으로 열지 마세요. G6를 통과한 단 하나의 frozen candidate가 생기면 정확한 candidate SHA, preregistration, 실행 명령, 데이터 범위, 예상 비용을 표로 제시하고 별도 승인을 요청하세요. 승인 전에는 NOT_RUN_NO_READ를 유지하세요.

대시보드 13페이지에 모델 생성, 학습 완료, 현재 후보 경제성, 연구 계속 가능, 다음 허용 행동을 연결하세요. 상태 token은 한글 설명을 제공하고 1024/768/390px overflow와 console error를 실제 브라우저에서 검증하세요.

각 단계 종료 시 다음을 표로 보고하세요.
- 현재 브랜치와 목표 버전
- 변경 파일과 커밋
- 테스트·빌드·브라우저 QA
- 모델/경제성/OOS/paper/live 상태
- 페이지별 반영률
- 실패 이유와 다음 허용 단계
- 예상 남은 시간

push, PR, merge, tag는 사용자가 승인한 범위에서만 진행하세요. 연구 실패를 숨기지 말고 append-only 결과 문서와 artifact receipt로 보존하세요. 경제적 성과를 보장하지 말되, 안전한 다음 행동이 있는 동안 G1부터 G6까지 지속적으로 진행하세요.
```

## 2. 단계 재개 프롬프트

중단 후에는 다음처럼 짧게 재개할 수 있다.

```text
Kronos 강화학습 master plan의 현재 완료 단계와 Git 상태를 실제 저장소에서 확인하고, 다음 미완료 G단계를 해당 codex/ 브랜치에서 이어서 진행하세요. 기존 커밋과 artifact를 중복 생성하지 말고, 단계 gate와 버전 정책을 지키세요. Fresh OOS는 별도 승인 전에는 읽지 마세요. 구현·테스트·문서·한글 커밋까지 완료한 뒤 13페이지 표와 모델/경제성/OOS 상태를 보고하세요.
```

## 3. GPT 외부 아키텍트 검토 프롬프트

`gpt-pro-architect-loop`를 사용할 경우 외부 ChatGPT에는 원본 저장소 전체가 아니라 승인된 redacted packet만 보낸다.

```text
당신은 Kronos 일봉 종가매매 강화학습의 외부 아키텍트입니다. 첨부 패킷의 계획·비용·인과성·MDP·보상·검증 설계를 비판적으로 검토하세요. 수익을 보장하거나 OOS 결과에 맞춘 튜닝을 제안하지 마세요. 데이터 누출, 잘못된 비용, contextual problem을 sequential RL로 오인한 부분, reward double-counting, offline distribution shift, baseline 누락, 통계 불확실성을 우선 찾으세요.

응답 형식:
1. Decision: APPROVE / REVISE / BLOCK
2. Critical findings: 우선순위·근거·영향
3. Required changes: 파일·계약·테스트 단위
4. Falsification tests
5. Remaining uncertainty
6. Explicitly prohibited next actions
```

외부 전송 전에 packet 파일, 목적지, 데이터 범주, 제외할 민감정보를 사용자에게 명시한다. ChatGPT 답변은 자문이며 로컬 Git evidence와 사용자 승인이 최종 권위다.

## 4. 이 프롬프트로 가능한 것

| 가능 | 불가능·별도 승인 |
|---|---|
| 단계별 브랜치와 한글 커밋 관리 | 수익성 보장 |
| 비용·상태·보상 계약 구현 | 사용자의 실제 계좌 수수료 자동 추정 |
| 합성 환경 의도적 과적합 검증 | 합성 성공을 시장 alpha로 주장 |
| supervised floor와 offline RL pilot | 실패한 validation 반복 튜닝 |
| 전체 페이지 UX 연결과 QA | 승인 없는 Fresh OOS 접근 |
| 실패 증거·receipt·보고서 보존 | 승인 없는 paper/live broker 주문 |
| GPT 외부 아키텍트 redacted review | secrets·계좌·원본 private data 전송 |
