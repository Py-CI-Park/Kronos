# Kronos Gate-90 독립 재채점 결과 — 2026-07-12

## 결론

**Gate-90: FAIL (55/100)**

이 결과는 통합 SHA `d9aca8848a383873f1a49b291ccfbbb6ce3558b3`의 첫 유효 전체 재채점이다. 90점을 통과했다는 뜻이 아니며, 모델·실거래·브로커·주문·계좌·페이퍼 포워드·수익 준비성을 뜻하지 않는다. 모델 판정은 공학 점수와 분리된 **INCONCLUSIVE / NO-GO 계열**이다.

| 범주 | 점수 | Gate-90 하한 | 판정 |
|---|---:|---:|---|
| A 증거 진실성 | 12/20 | 19 | FAIL |
| B UI·성능·접근성 | 10/20 | 18 | FAIL |
| C 연구 엔지니어링 | 14/20 | 17 | FAIL |
| D 연구 무결성·재현성 | 10/20 | 18 | FAIL |
| E 릴리스·보안·품질 | 9/20 | 18 | FAIL |
| **합계** | **55/100** | **90** | **FAIL** |

활성 hard cap은 없다. 실패 원인은 총점과 모든 범주 하한 미달이다. 누락된 증거를 임의로 통과 처리하거나 양의 train/val 결과로 보충하지 않았다.

## 기준별 점수

| 기준 | 점수 | 핵심 근거 또는 0점 원인 |
|---|---:|---|
| A1–A4 | 각 3/5 | 계약·happy·failure 테스트는 통과. 정확한 현 SHA의 요구된 브라우저 시나리오와 독립 해시가 없어 runtime/review는 0. |
| B1 | 2/5 | 반응형 계약·측정 테스트만 인정. 24개 캡처는 `c008e52`에서 생성되어 엄격한 현 SHA 점수에는 미반영. |
| B2 | 2/5 | AA/ARIA/차트 대체 계약·happy만 인정. 음성 접근성 실패 fixture와 현 SHA 키보드 추적 없음. |
| B3 | 3/5 | 요청 세대 토큰과 카드 독립 상태 계약·happy·failure 인정. 현 SHA 주입 지연 브라우저 추적 없음. |
| B4 | 3/5 | 계약·happy와 현 SHA API latency runtime 인정. 명시적 임계치 위반 fixture 및 현 SHA 독립 재검토 없음. |
| C1 | 5/5 | close-slot 비용·동률·이벤트·test-OOS NO-GO 증거 완비. |
| C2 | 4/5 | adapter·E2E·fail-closed·독립 검토 인정. G018 option-B stop으로 >=200k full runtime은 0. |
| C3 | 5/5 | R5 결정론 재실행, seed42/sample5, tokenizer MSE, 해시와 독립 검토 완비. |
| C4 | 0/5 | G021 이전이라 Aim/rliable 소비자·검증·캡처·IQM/CI가 없음. |
| D1 | 4/5 | 사전등록·23bp/0/46·시간순·해시 runtime/review 인정. 모든 누락 조건을 한 번에 거부하는 failure fixture 없음. |
| D2 | 4/5 | test-OOS 기준선·control runtime/review 인정. control 누락 alpha claim 거부 fixture 없음. |
| D3 | 0/5 | G018 full SB3 3-seed가 실행되지 않았고 rliable IQM/CI도 없음. G019 D4 5×3만으로 대체하지 않음. |
| D4 | 2/5 | 명시적 promotion 계약과 테스트만 인정. NO-GO 완화 거부·실제 promotion+honesty audit·독립 해시 없음. |
| E1 | 3/5 | 계약, 1,196-pass full pytest, 현 SHA JUnit/LSP/build 해시 인정. deliberate-failure canary와 독립 검토 없음. |
| E2 | 3/5 | 보안 계약과 현 full-suite happy/failure 테스트 인정. 현 SHA runtime XSS/debug/bind 묶음과 독립 보안 검토 없음. |
| E3 | 2/5 | 현 npm audit/outdated 및 Gate-90 임시 reachability disposition 인정. high=0 계약은 미충족. |
| E4 | 1/5 | 현 SHA clean-tree·경계 감사만 인정. 최종 handoff와 4+2 리뷰 묶음은 아직 없음. |

100개 binary check 전체는 `.omo/evidence/task-20-gate90/gate90_evidence.json`에 PASS 근거 또는 명시적 0점 사유로 기록했다. 결정론 scorer 출력은 `.omo/evidence/task-20-gate90/gate90_scored.json`이며 반복 출력과 byte-identical이고 SHA-256은 `836659fed17fb7a51eeb000801c259de1230c0ead0eb0622d11ca28d3f29f76b`이다.

## 현 SHA 검증

- 전체 pytest: **1,196 passed, 2 skipped**, 실패 0 (`full_pytest_scoped.xml`).
- 별도 Gate-90 targeted pytest: **329 passed** (`pytest.xml`).
- Node 계약 테스트: **49 passed**.
- `svelte-check`: **284 files, 0 errors, 0 warnings**.
- Vite production build: 성공, 789 modules. 대형 chunk 경고는 실패가 아니며 후속 품질 항목에 남긴다.
- 변경·명시 대상 Python LSP diagnostics: 모두 `OK`.
- 네 핵심 API: cold 모두 5초 이하, warm 모든 표본 2초 이하; HTTP 200 유효 JSON.
- 실행 경계 검증: branch/base/clean-tree/Gate-A allowlist/108 route snapshot 모두 PASS.
- npm audit: high 1(dev-only Vite), moderate 4. 기존 Gate-90 임시 도달성 disposition은 유효하나 Gate-95 전 G022에서 해소해야 한다.

전체 pytest의 첫 시도에서 실제 결함 두 건을 발견해 수정했다. stale normalization 테스트가 제거된 contextual-bandit 이름을 참조하던 문제는 `4c3439e`에서 truthful linear-score 이름으로 고쳤다. pytest가 비테스트 CLI `finetune/qlib_test.py`를 수집하던 문제는 `d9aca88`에서 `tests/test_*.py`로 수집 범위를 명시했다. 수정 후 전체 suite가 통과했다.

## 연구 결과 분리

- G013: `TUNING_HARMFUL` — supervised attribution 결과이며 RL/alpha가 아니다.
- G015: test OOS **NO-GO**, filled slot 0.
- G017: 5k smoke plumbing/data PASS, 모델 promotion 아님.
- G018: 공학 `COMPLETE_OPTION_B_STOP`, 연구 `INCONCLUSIVE`, full model `NOT_RUN_NOT_PROMOTED`.
- G019: 15/15 D4 cells 완료, **SEED_NOISE_NO_GO**; checkpoint/model readiness는 false.

양의 val+test 산술값은 test OOS를 가리지 않으며 점수 보너스로 사용하지 않았다. 기본 거래비용은 왕복 23bp이다.

## 다음 소유 작업

| 소유 단계 | 해소 대상 |
|---|---|
| G021 | 로컬 Aim(default off), 동일-config seed 검증, rliable IQM/CI/profile, duplicate-seed 거부 |
| G022 | LSP/static 완결, Vite/ECharts 직접 의존성 호환 업그레이드, high/critical 0 |
| G023 | 현 최종 SHA 전체 탭·상태·테마·폭·키보드·axe·성능·2개 독립 시각 검토 |
| 추가 연구 사전등록 필요 | D3의 >=3 full SB3 seed가 계속 요구되면 G018 option-B 이후 새 동결 프로토콜로만 실행 가능 |
| G024–G025 | clean release candidate, 전체 gate, 최종 95 재채점과 handoff |

## 독립 판정

독립 architect `agent://82-Gate90IndependentScore`가 100개 check와 산술을 재계산해 **55/100, Gate-90 FAIL, PASS/CLEAR(점수 무결성)**로 승인했다. 과대·과소 채점은 발견되지 않았다. 이는 실패 결과의 정확성을 승인한 것이지 Gate-90 통과 승인이 아니다.
