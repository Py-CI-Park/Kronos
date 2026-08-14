# Kronos v1.29.0-dev 프로그램 closure 성과 보고

- 완료일: 2026-08-14 KST
- 기준: `develop/v1.29.0-dev@5393bd4`
- 작업 브랜치: `codex/v1.29.0-dev-program-closure`
- 성격: 연구 플랫폼 closure 및 다음 gate 준비
- 수익성·paper/live·정식 release 판정: 아님

## 1. 완료 성과

| 영역 | 이전 | 완료 결과 |
|---|---|---|
| 공식 페이지 정의 | 8페이지와 13 capability/7 workflow 표현 혼재 | 공식 navigation은 `V6_PAGES` 8개로 고정, capability와 workflow stage를 별도 명칭으로 분리 |
| bundle closure | marker 중심 검사 | index의 local script/link와 전체 tracked dist SHA/size를 `kronos_v1_29_0_dashboard_bundle_closure_2026-08-14.json`에 고정하고 missing/untracked/stale 0건 검증 |
| build hygiene | generated chunk trailing whitespace가 diff-check를 깨뜨릴 수 있음 | Vite render 단계에서 deterministic trailing-whitespace 정규화 후 content hash 생성 |
| D0/D1 서명 권위 | global boolean 때문에 VERIFIED를 안전하게 지원할 수 없음 | boolean 제거, pinned public trust store·Ed25519·JCS·domain-separated raw-to-normalized review 검증 구현 |
| 실제 D0/D1 증거 | signed trust/receipt 없음 | 계속 `BLOCKED`; production trust store는 의도적으로 empty keys이며 pin 고정 |
| Fresh OOS 준비 | 미열람 상태만 문서화 | payload locator가 없는 typed descriptor, 20~60일 exact window, CQL/control matrix, 23/46bp, create-exclusive no-read registration capability 구현 |
| Fresh OOS 실행 | 미수행 | 계속 미수행; authority·sealed attestation·사람 승인 blocker를 명시하고 reader/evaluator/authorization은 만들지 않음 |

## 2. 보안·연구 정직성 경계

Authority 003 capability는 세 review를 요구한다.

- `D0_PRICE_PROVENANCE`
- `D1_CURRENT_METADATA`
- `D1_PIT_MEMBERSHIP`

각 review는 repository-pinned Ed25519 공개키와 JCS statement로 raw SHA/size/available-at, normalized role/SHA/size/profile, reviewer principal/key/scope/time, policy, receipt UUID와 nonce를 결속한다. evidence가 공개키나 local path를 선택할 수 없고, private key·signer·hash-only fallback은 repository에 없다.

Production trust store는 canonical 60 bytes이며 SHA-256은 `009c959493337799750dcfbca842e445f35308f83a178054b476d633faac072c`다. 현재 keys가 비어 있으므로 external reviewer evidence 없이 VERIFIED가 될 수 없다. 003은 `NOT_RUN`이며 실제 trust/evidence 준비 전 실행하지 않는다.

Fresh OOS framework는 descriptor와 registration receipt만 기록한다. Fresh path, payload, feature, action sequence, price, reward를 입력받지 않는다. Historical TEST feature는 계속 contaminated/forbidden이고, Fresh OOS state/action/reward는 unread다.

## 3. 검증 성과

| 검증 | 결과 |
|---|---:|
| expanded daily-market/V6/security Python | `211 passed` |
| authority/Fresh OOS/bundle 보안 집중 회귀 | `59 passed` |
| bundle/route closure | `18 passed` |
| Bun frontend 전체 | `473 passed, 0 failed` |
| Svelte check | `620 files, 0 errors, 0 warnings` |
| scoped BasedPyright | `0 errors, 0 warnings` |
| Ruff check/format | PASS |
| `git diff --check` | PASS |
| Vite production build | `1064 modules transformed`, PASS |
| 8페이지 Chromium QA | 8/8 identity PASS, 1440/1440, overflow 0, 화면 오류 0 |

브라우저에서 확인한 고유 route는 `command`, `research`, `live`, `evaluation`, `evidence`, `models`, `governance`, `settings`다.

검증 명령은 다음과 같다.

```powershell
py -3.11 -m pytest tests/test_stom_rl_daily_market_*.py tests/test_v6_research_api.py tests/test_v6_research_catalog.py tests/test_v6_run_telemetry.py tests/test_v6_telemetry_api.py tests/test_v6_governance_api.py tests/test_v6_governance_catalog.py tests/test_v6_insight_api.py tests/test_webui_local_security.py tests/test_v2_route.py tests/test_v2_dist_marker.py -q --disable-warnings

py -3.11 -m pytest tests/test_stom_rl_daily_market_authority_local_verdict.py tests/test_stom_rl_daily_market_authority_review.py tests/test_stom_rl_daily_market_authority_v3.py tests/test_stom_rl_daily_market_authority.py tests/test_stom_rl_daily_market_authority_runner.py tests/test_stom_rl_daily_market_allocation_runner.py tests/test_stom_rl_daily_market_allocation_lineage.py tests/test_stom_rl_daily_market_allocation_fresh_oos.py tests/test_v2_dist_marker.py tests/test_v2_route.py -q --disable-warnings

py -3.11 -m pytest tests/test_v2_dist_marker.py tests/test_v2_route.py -q --disable-warnings
py -3.11 scripts/generate_dashboard_bundle_closure.py --check

Set-Location webui/v2_src
bun test src
npm run check
npm run build
```

실행은 2026-08-14 KST의 clean closure worktree에서 수행했다. bundle receipt는 build source commit, commit 시각, `vite.config.ts`, `package-lock.json`, index 및 모든 tracked dist 파일 SHA-256/size를 포함한다.

새 production 모듈 pure LOC는 다음과 같이 250 미만이다.

- `daily_market_authority_review.py`: 127
- `daily_market_authority_review_contract.py`: 179
- `daily_market_authority_review_custody.py`: 88
- `daily_market_allocation_fresh_oos.py`: 204

Frontend dependency 설치 시 Node `22.23.2`는 허용 범위였으나 npm `12.0.2`는 package 권고 `9~11` 밖이라는 warning이 있었다. build/test 결과에는 실패가 없었지만 release 환경은 npm 11 이하로 맞춰야 한다.

## 4. 100점 기준 재평가

대시보드가 소비하는 canonical rubric을 단일 기준으로 유지한다.

| 구분 | 점수 | 이번 closure의 영향 |
|---|---:|---|
| 제품·UI 구현 | **94/100** | bundle·페이지 정합성은 개선됐지만 broker 운영은 의도적으로 미구현 |
| 프로그램 진행 | **71/100** | 보안 capability는 추가됐지만 실제 data-custody/Fresh OOS gate가 아직 false |
| 경제 모델 증거 | **20/100** | 변화 없음; historical 경제 gate `NO-GO` |
| live readiness | **0/100** | 변화 없음; Fresh OOS·paper·broker·risk 운영 미수행 |

초기 감사 문서의 72점은 별도 가중 감사표였으며 canonical dashboard program rubric을 대체하지 않는다. 이번 작업의 **즉시 실행 가능한 closure 항목은 100% 완료**됐지만, 외부 증거가 필요한 프로그램 criterion은 완료로 바꾸지 않았다. 따라서 수익성 또는 실거래 점수 상승은 0점이다.

## 5. 남은 외부·시간 gate

### G1 실제 D0/D1 권위

- external reviewer public key 독립 승인
- official raw source와 available-at 확보
- 세 extraction receipt 실제 서명
- local price-basis/database/PIT coverage와 함께 Authority 003 단발 실행

현재: `BLOCKED`, 실행 금지.

### G2 Fresh OOS FROZEN 등록

- official KRX calendar로 first eligible session 확정
- exact 20~60일 중 하나 고정(권고 60)
- CQL 5개 및 no-trade/rule/random/shuffle 실제 hash 고정
- 별도 사람 승인 trust root와 external custodian 확정
- 새 FROZEN preregistration 독립 승인

현재: `DRAFT_NOT_REGISTERED_NO_READ`.

### G3 단발 경제 검증

전체 window가 sealed되고 D0/D1·사람 승인이 PASS한 뒤 한 번만 읽는다. 23bp/46bp와 모든 control/seed 결과를 게시하며, 실패는 그대로 `NO-GO`다. 재튜닝·seed 선택·window 변경·retry는 금지한다.

### G4 paper/live

Fresh OOS PASS 뒤 별도 paper-forward를 수행한다. broker/order 권한, reconciliation, kill switch, risk limit, monitoring, incident/rollback 및 사람 release 승인이 모두 PASS하기 전에는 live readiness를 올리지 않는다.

## 6. 최종 판정

즉시 수행 가능한 dashboard/release closure와 authority/Fresh OOS 준비 capability는 완료됐다. 실제 시장 권위와 경제 검증은 외부 reviewer evidence, 시간 축적, custodian, 사람 승인 없이는 완료할 수 없다. 따라서 develop 병합 후보로서 source quality는 검증됐지만, main 병합·정식 태그·paper/live·수익성 주장은 계속 금지한다.
