# Kronos v1.29.0-dev D0/D1 서명 권위 감사 003 사전등록

- 사전등록일: 2026-08-14 KST
- 연구 ID: `DAILY_MARKET_AUTHORITY_2026_08_14_003`
- 실행 상태: `NOT_RUN`
- 목적: signed reviewer trust root와 raw-to-normalized extraction receipt 검증 능력 확인
- 승격·수익성·paper/live 상태: 모두 금지

## 1. 목적

003은 002 경제 결과를 다시 평가하지 않는다. D0 가격 기준과 D1 시점별 종목군을 해시 존재만으로 승인하지 않고, repository-pinned Ed25519 공개키와 canonical JCS extraction review가 실제 원본과 정규화 입력을 정확히 결속하는지 감사하는 권위 capability 단계다.

현재 production trust store는 의도적으로 빈 `keys` 배열이며 SHA-256은 `009c959493337799750dcfbca842e445f35308f83a178054b476d633faac072c`다. 따라서 코드 구현과 테스트가 완료되어도 실제 외부 reviewer 공개키와 서명 영수증이 들어오기 전에는 003의 올바른 결과가 `BLOCKED_DATA_AUTHORITY`다.

## 2. 고정 검증 계약

세 extraction review가 모두 필요하다.

1. `D0_PRICE_PROVENANCE`
2. `D1_CURRENT_METADATA`
3. `D1_PIT_MEMBERSHIP`

각 review는 다음을 Ed25519로 서명해야 한다.

- signing domain `KRONOS-DAILY-MARKET-EXTRACTION-REVIEW-V1\0`
- raw source SHA-256, byte size, source system, URL, available-at
- normalized target 역할, SHA-256, byte size, normalization profile
- reviewer principal, key ID, role, scope, review 시각
- receipt UUID와 32-byte nonce
- policy `KRONOS_DAILY_MARKET_AUTHORITY_EXTRACTION/1`
- `REAL` evidence와 `APPROVE` decision

공개키는 evidence 디렉터리나 receipt가 지정할 수 없다. repository에 고정된 trust store와 pin만 신뢰한다. private key와 signing utility는 repository에 넣지 않는다.

Extraction review는 one-time 실행 토큰이 아니라 **동일한 raw/normalized byte identity에 재사용 가능한 content attestation**이다. receipt UUID와 nonce는 한 authority proof bundle 안에서 중복될 수 없지만, byte identity가 완전히 같은 후속 감사에서 다시 검증할 수 있다. 다른 raw set, normalized target, 역할, profile 또는 policy로 복사하면 서명 binding이 실패한다. Authority 003 실행 자체의 단발성은 receipt nonce가 아니라 기존 output 경로를 포함한 create-exclusive publication으로 보장한다.

## 3. 실패 조건

다음 중 하나라도 있으면 해당 D0/D1은 `BLOCKED`다.

- 빈/미등록/revoked/기간 외/wrong-scope 공개키
- 비정규 JSON·base64url·UUID·UTC timestamp
- signature/domain 불일치
- raw 또는 normalized hash/size/role/profile 불일치
- raw available-at이 review보다 늦음
- 누락·추가·교체 raw source
- reparse/junction/path traversal 또는 불안정한 file descriptor
- local price-basis column, database binding 또는 PIT coverage 실패

## 4. 연구 정직성 경계

- historical TEST score/state feature는 이미 오염되어 독립 OOS가 아니다.
- historical TEST reward·가격·체결·행동 평가는 미열람이다.
- Fresh OOS state/action/reward는 전체 미열람이다.
- authority VERIFIED는 데이터 출처·추출 권위를 뜻할 뿐 수익성·모델 승격을 뜻하지 않는다.
- 23bp 기본 및 46bp stress 경제 gate, Fresh OOS, paper-forward, 사람 승인은 별도 단계다.

## 5. 실행 전 gate

003 실행은 다음을 모두 만족한 뒤 한 번만 허용한다.

- 실제 reviewer 공개키 변경과 trust-store pin이 독립 검토됨
- 공식 raw source와 세 canonical signed receipt가 준비됨
- 출력 디렉터리 `DAILY_MARKET_AUTHORITY_2026_08_14_003`가 없음
- source/test/type/security 감사가 PASS
- 실행자가 external reviewer principal과 source custody를 확인함

현재는 외부 trust/evidence가 없으므로 003을 실행하지 않는다. 이 사전등록은 구현 capability를 고정하며, 차단 조건을 우회하는 synthetic production evidence를 허용하지 않는다.
