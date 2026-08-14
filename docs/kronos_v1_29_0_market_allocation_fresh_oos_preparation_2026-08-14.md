# Kronos v1.29.0-dev Fresh OOS 준비 계약

- 작성일: 2026-08-14 KST
- 상태: `DRAFT_NOT_REGISTERED_NO_READ`
- 목적: 유일한 다음 독립 경제 증거를 열지 않은 채 등록 capability를 고정
- Fresh OOS state/action/reward: 모두 미열람
- promotion/paper/live: 금지

## 1. 현재 상태

Historical TEST의 후보 점수와 상태 feature 46일은 이미 파싱되어 오염됐다. reward·가격·체결·행동 평가는 미열람이지만 독립 OOS로 다시 사용할 수 없다. Fresh OOS만 다음 독립 경제 증거 후보이며, 이 문서와 구현은 Fresh payload 경로·행·feature·action·price·reward를 받거나 읽지 않는다.

현재는 공식 KRX calendar authority, 첫 eligible session, 실제 policy/checkpoint/config hash, 별도 사람 승인 trust root, 외부 custodian이 확정되지 않았으므로 실제 registration을 만들지 않는다.

## 2. 등록 시 고정할 계약

- 한 개의 정확한 window 길이: 20~60 거래일 중 사전 고정, 권고값 60일
- 첫 eligible KRX session: 공식 calendar authority로 사전 고정
- 행동: `CASH`, `INVEST_TOP3_EQUAL_SLOT`, `INVEST_TOP5_EQUAL_SLOT`, `INVEST_TOP10_EQUAL_SLOT`
- candidate: CQL seed 0..4, 각 checkpoint/config/implementation SHA-256 고정
- controls: no-trade/CASH 1개, deterministic rule 1개, random seed 0..4, CQL seed와 1:1 shuffle seed 0..4
- 비용: 기본 23bp, stress 46bp
- historical TEST: `CONTAMINATED_FORBIDDEN`
- registration 이후 retune·seed 선택·window 단축·fallback 금지
- 한 번 읽기 이후 retry 금지

Descriptor에는 Fresh data path, URI, payload, row count, feature, action sequence, price 또는 reward 필드를 두지 않는다. canonical descriptor bytes와 SHA-256 commitment만 immutable registration 디렉터리에 create-exclusive로 기록한다.

## 3. 실행 전 필수 gate

1. Authority 003에서 D0/D1이 실제 외부 서명 증거로 `VERIFIED`
2. 정확한 20~60 거래일 window와 calendar identity 확정
3. CQL 5개와 control matrix의 실제 hash 확정
4. 별도 Fresh-OOS 사람 승인 공개키 registry와 principal 확정
5. external custodian의 sealed-window attestation 및 atomic single-use token 계약 확정
6. descriptor·preregistration·evaluator hash 독립 검토
7. 사람 승인 기록

하나라도 없으면 상태는 `REGISTERED_SEALED_NO_READ` 또는 그 이전이며 one-read authorization을 만들지 않는다.

## 4. 현재 구현 범위

현재 단계는 typed descriptor, exact evaluation matrix, deterministic commitment, create-exclusive metadata registration, 그리고 다음 세 blocker를 기록하는 no-read receipt까지만 구현한다.

- `D0_D1_AUTHORITY_NOT_VERIFIED`
- `SEALED_WINDOW_ATTESTATION_MISSING`
- `HUMAN_ONE_READ_APPROVAL_MISSING`

Fresh evaluator, payload reader, custodian token consumer, reward 계산, 성능 gate, promotion, paper/live/broker 경로는 구현하지 않는다. 이는 미완성 기능을 성공으로 포장하는 것이 아니라 의도적인 보안 경계다. 실제 registration은 위 입력이 확정된 새 FROZEN preregistration에서만 수행한다.

## 5. 이후 단발 경제 검증

모든 gate와 20~60 거래일 축적이 끝난 뒤 별도 승인으로 단 한 번 읽는다. no-trade·rule·random·shuffle·5-seed·23/46bp 결과를 모두 게시하며, 실패도 `NO-GO`로 보존한다. 결과 확인 후 threshold·policy·seed·window를 바꾸거나 같은 evidence를 다시 독립 OOS로 부르지 않는다.
