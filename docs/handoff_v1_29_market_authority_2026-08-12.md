# Kronos v1.29.0-dev 일봉 강화학습 권위·계보 연구 핸드오프

- 작성일: 2026-08-12 KST
- 작업 성격: **미완료 연구 체크포인트**
- 기능 브랜치: `codex/v1.29.0-dev-market-authority`
- 작업 워크트리: `D:\Chanil_Park\Project\Programming\Kronos.wt-v1.29-market-authority`
- 데이터·생성물 기준 루트: `D:\Chanil_Park\Project\Programming\Kronos`
- 분기 기준: `develop/v1.29.0-dev@38b4270`
- 체크포인트 이전 HEAD: `9329541`
- 정식 릴리스 상태: **아님**
- develop/main/tag 상태: **미병합·미생성**

## 1. 재시작할 때 가장 먼저 알아야 할 결론

현재 브랜치에는 DQN 5개와 CQL 5개의 4행동 일봉 종가 의사결정 연구를 다시 실행하기 위한 입력 custody, 권위 receipt, 모델·ledger·telemetry·manifest 검증, 001↔002 재현 비교, V6 시각화 보정이 구현되어 있다.

그러나 아직 002를 실행하면 안 된다. 다음 두 연구 정직성 결함이 남아 있다.

1. authority 002 감사도 전체 candidate CSV를 읽으면서 historical TEST 46일의 날짜·종목·eligibility를 파싱한다. 그런데 authority receipt와 runner는 아직 `historical_test_read=false`라고 기록한다.
2. 002의 실제 상태는 `REPRODUCTION_ONLY_VALIDATION_CONSUMED` 또는 `REPRODUCTION_MISMATCH_VALIDATION_CONSUMED`인데, Run Detail의 TEST feature 오염 경고 조건이 001 또는 상태 문자열의 `TEST_FEATURES_CONSUMED`만 인식해 002 상세 화면에서는 경고가 누락된다.

이 둘을 고치고 전체 검증을 다시 통과하기 전에는 authority 002, allocation 002, develop 병합, main 병합, 태그 생성을 하지 않는다.

## 2. 현재 Git·워크트리 상태

| 항목 | 현재 상태 | 재시작 규칙 |
|---|---|---|
| 기능 브랜치 | `codex/v1.29.0-dev-market-authority` | 새 브랜치를 만들지 말고 여기서 이어간다. |
| 체크포인트 커밋 | 이 문서를 포함한 최신 HEAD | `git log -1 --oneline`으로 확인한다. |
| 소스·테스트·UI source | 체크포인트 커밋에 포함 | reset/rebase로 버리지 않는다. |
| `webui/static/v2/dist` | 이전 빌드의 dirty 생성물 | 소스 수정 완료 뒤 한 번만 재빌드하고 별도 build 커밋한다. |
| 001 결과 문서 초안 | `docs/kronos_v1_29_0_market_authority_allocation_result_2026-08-10.md` | TEST 미열람 주장이 낡았다. 그대로 커밋하지 말고 002 결과까지 반영해 전면 갱신한다. |
| authority 002 생성물 | 없음 | P0/P1 수정과 소스 커밋 후 explicit main root로 실행한다. |
| allocation 002 생성물 | 없음 | authority 002 완료 후 실행한다. |
| 기능 브랜치 push/PR | 아직 완료로 간주하지 않음 | 최종 독립 감사 PASS 뒤 진행한다. |

## 3. 이번 체크포인트까지 구현한 것

| 영역 | 구현 내용 | 현재 판정 |
|---|---|---|
| 권위 입력 custody | descriptor-bound read/hash/copy, DB snapshot 종료 후 검증, bounded stockinfo canonical query | 구현됨 |
| signed review | 신뢰 루트가 없으면 D0/D1 `VERIFIED`를 구조적으로 거부 | 구현됨·D0/D1은 계속 BLOCKED |
| 후보 자격 | authority와 model loader 모두 `true/1`, `false/0`만 허용 | 구현됨 |
| 직접 입력 custody | candidate/manifest/panel/authority/001 receipt 5종을 불변 snapshot으로 소비 | 구현됨 |
| 모델 계약 | DQN 5 + CQL 5, 행동 4개, 행동 시드 1000..1031, optimizer 전체 결속 | 구현됨 |
| 행동·회계 | CASH/Top3/Top5/Top10별 슬롯·노출·비용 불변식, 중첩 포지션 금지 | 구현됨 |
| 001↔002 재현 | 001 receipt SHA와 canonical 10모델·checkpoint·gate 지문을 비교 | 구현됨 |
| 재현 판정 | exact match와 mismatch를 별도 verdict로 게시 | 구현됨 |
| publication | 14파일 manifest, typed receipt/summary, ledger/telemetry 재계산, 001/002 digest 재검산 | 구현됨 |
| telemetry | 단일 descriptor bounded read, invalid line·head/tail sample의 live 승격 금지, cross-poll 증가 확인 | 구현됨 |
| V6 UX | 이전 NO-GO·001 소비·002 재현·Fresh OOS를 분리, stale async 응답 차단, TEST feature 오염 공개 | 대부분 구현, Run Detail 002 경고 누락 |

## 4. 가장 중요한 연구 해석 정정

001과 같은 데이터 적재 경로는 historical TEST의 reward·시가 체결 DB를 열지 않았지만 candidate score와 state feature 46일을 파싱했고 score/state dataset hash에도 포함했다. 따라서 기존 historical TEST는 untouched OOS가 아니다.

정확한 상태는 다음과 같다.

| 데이터 | 실제 사용 상태 | 앞으로의 처리 |
|---|---|---|
| TRAIN | 상태·행동·reward 학습 사용 | 허용 |
| VALIDATION | 정책 평가와 gate에 이미 소비 | 재튜닝 금지 |
| 기존 historical TEST | 후보 점수·상태 feature 소비, reward·가격 체결·행동 평가는 미열람 | 독립 경제 증거에서 영구 제외 |
| Fresh OOS | 상태·행동·reward 모두 미열람 | 유일한 다음 독립 경제 검증 후보 |

002는 새 경제 성능 검증이 아니다. 001과 같은 오염 경계에서 코드·입력·설정·산출물의 결정성을 확인하는 `POST_HOC_CUSTODY_REPRODUCTION`이다. 002가 exact match여도 경제 모델 점수 20/100과 live readiness 0/100은 올리지 않는다.

## 5. 마지막 검증 증거

아래 수치는 마지막으로 완료된 명령의 결과다. 이후 재시작 시 반드시 다시 실행한다.

| 검증 | 마지막 결과 |
|---|---:|
| 일봉 RL·V6 Python 확대 회귀 | `154 passed, 1 skipped` |
| telemetry·publication·reproduction 표적 | `41 passed` |
| 프런트 전체 Bun | `473 passed, 0 failed` |
| Svelte check | `0 errors, 0 warnings` |
| scoped BasedPyright | `0 errors, 0 warnings` |
| Ruff·format·diff check | PASS |

마지막 검증 이후 handoff 문서만 추가했다. 다만 알려진 authority disclosure와 Run Detail 002 경고 결함이 남아 있으므로 이 수치를 최종 릴리스 PASS로 해석하지 않는다.

## 6. 재시작 후 작업 순서

| 순서 | 우선순위 | 작업 | 완료 기준 |
|---:|---|---|---|
| 1 | P0 | authority receipt의 historical TEST disclosure를 실제 candidate parsing과 일치시킨다. | `false` 단일 boolean 과장을 제거하고 `FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED`와 동등한 typed 상태를 receipt·summary·runner·테스트에 반영 |
| 2 | P1 | Run Detail에서 001과 002 모두 TEST feature 오염 경고를 표시한다. | 002 match/mismatch 상세 화면 모두 danger 경고와 Fresh OOS-only 문구 표시 |
| 3 | P1 | `tests/daily_market_allocation_fixtures.py` 등 변경 파일의 250 pure-LOC 경계를 재감사한다. | 새 production 모듈 250 pure LOC 이하, fixture가 너무 크면 기능별 분리 |
| 4 | P0 | 오래된 결과 문서를 001 정정 + 002 결과 구조로 갱신한다. | `NOT_RUN_NO_READ`, `TEST 봉인`, `TEST 미개봉` 과장 0건 |
| 5 | P0 | 전체 Python/TS/Svelte 회귀를 다시 실행한다. | 실패 0, 타입 경고 0, `git diff --check` PASS |
| 6 | P0 | 최종 소스·사전등록 커밋을 만든다. | `stom_rl`과 prereg 경로가 clean이고 lineage가 HEAD를 읽을 수 있음 |
| 7 | P0 | canonical main data root를 명시해 authority 002를 실행한다. | immutable authority 002 receipt·summary 생성, D0/D1 BLOCKED와 TEST feature disclosure 일치 |
| 8 | P0 | allocation 002 10모델을 실행한다. | 10 checkpoint, 14-file manifest, 001 exact match/mismatch 명시, TEST reward 미열람, Fresh OOS 미열람 |
| 9 | P1 | UI source와 결과 문서를 갱신·커밋한다. | 8페이지 상태·점수·run identity 일치 |
| 10 | P1 | 최종 Vite build 후 tracked dist를 별도 build 커밋한다. | `webui/app.py`가 최신 bundle을 실제 서빙 |
| 11 | P0 | 서버 재시작과 8페이지 브라우저 클릭 QA를 수행한다. | 콘솔 오류 0, overflow 0, 설정 배율·모델·증거·평가·학습 화면 확인 |
| 12 | P0 | 독립 review-work 감사 후 push·비FF develop 병합을 결정한다. | 모든 리뷰 PASS. main/tag는 경제·Fresh OOS gate 전까지 금지 |

## 7. 정확한 재시작 명령

```powershell
Set-Location "D:\Chanil_Park\Project\Programming\Kronos.wt-v1.29-market-authority"
git status --short --branch
git log -5 --oneline
Get-Content -LiteralPath "docs\handoff_v1_29_market_authority_2026-08-12.md"
Get-Content -LiteralPath "docs\kronos_v1_29_0_market_authority_allocation_prereg_002_2026-08-10.md"
```

P0/P1 수정 뒤 검증:

```powershell
$tests = @(Get-ChildItem -LiteralPath tests -Filter 'test_stom_rl_daily_market_*.py' | ForEach-Object { $_.FullName })
$tests += @(Resolve-Path tests/test_v6_research_api.py, tests/test_v6_research_catalog.py, tests/test_v6_run_telemetry.py, tests/test_v6_telemetry_api.py, tests/test_webui_direct_app_import.py | ForEach-Object { $_.Path })
py -3.11 -m pytest @tests -q --disable-warnings

Set-Location "webui\v2_src"
bun test src
npm run check
Set-Location "..\.."
git diff --check
```

실행 전 출력 디렉터리가 없는지 읽기 전용으로 확인:

```powershell
$dataRoot = "D:\Chanil_Park\Project\Programming\Kronos"
Test-Path -LiteralPath "$dataRoot\webui\rl_runs\daily_market_authority\DAILY_MARKET_AUTHORITY_2026_08_10_002"
Test-Path -LiteralPath "$dataRoot\webui\rl_runs\daily_market_allocation\DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
```

두 명령은 모두 `False`이고 최종 소스가 커밋된 뒤에만 실행한다. 기능 worktree의 `_database`는 Junction이므로 무인자 실행하지 말고 canonical main data root를 반드시 인자로 준다.

```powershell
py -3.11 -m stom_rl.daily_market_authority_runner "D:\Chanil_Park\Project\Programming\Kronos"
py -3.11 -m stom_rl.daily_market_allocation_runner "D:\Chanil_Park\Project\Programming\Kronos"
```

보안 가드를 우회하기 위해 Junction 허용 로직을 완화하지 않는다.

## 8. 커밋·브랜치·병합 규칙

1. 같은 `v1.29.0-dev` 개발선과 현재 기능 브랜치를 유지한다.
2. 생성 run은 Git에 넣지 않는다.
3. source/docs/test, UX/API, 결과 문서, final dist를 논리 커밋으로 분리한다.
4. 커밋 메시지는 한글 Conventional Commit 형식을 사용하고 상세 body에 검증·한계를 기록한다.
5. 기능 브랜치는 병합 후 삭제하지 않는다.
6. 모든 감사 PASS 뒤에만 `develop/v1.29.0-dev`로 `--no-ff` 병합한다.
7. 경제 성능·Fresh OOS·paper/live·사람 승인 전에는 main 병합과 `v1.29.0` 태그를 만들지 않는다.

## 9. 절대 하지 말아야 할 것

- 기존 001 결과를 수정해 immutable artifact를 재작성하지 않는다.
- 002를 새 성능 사전검증이나 수익성 성공으로 표현하지 않는다.
- 기존 historical TEST를 독립 OOS로 다시 사용하지 않는다.
- D0/D1을 해시 존재만으로 `VERIFIED`로 바꾸지 않는다.
- 같은 002 ID를 실패 후 덮어쓰지 않는다. 실패하면 보존하고 새 ID를 사전등록한다.
- stale `dist`나 낡은 결과 문서를 무심코 staging하지 않는다.
- 기능 worktree Junction을 통과시키기 위해 custody 검사를 약화하지 않는다.

## 10. 재시작 프롬프트

아래 프롬프트를 새 Codex 작업에 그대로 붙여 넣는다.

```text
D:\Chanil_Park\Project\Programming\Kronos.wt-v1.29-market-authority 의
codex/v1.29.0-dev-market-authority 브랜치에서 이전 작업을 처음부터 다시 만들지 말고 이어서 진행하세요.

먼저 docs/handoff_v1_29_market_authority_2026-08-12.md 전체와
docs/kronos_v1_29_0_market_authority_allocation_prereg_002_2026-08-10.md 전체를 읽고,
git status와 최신 커밋을 실제 확인하세요.

핵심 경계:
- 002는 새 성능 검증이 아니라 POST_HOC_CUSTODY_REPRODUCTION입니다.
- 기존 historical TEST는 후보 점수·상태 feature 46일이 이미 소비되어 독립 OOS 자격이 없습니다.
- TEST reward·가격 체결·행동 평가는 읽지 않았고 Fresh OOS는 전체 미열람입니다.
- authority 002 receipt의 historical TEST disclosure가 아직 실제 candidate parsing과 충돌합니다.
- Run Detail은 002 match/mismatch에서 TEST feature 오염 경고가 아직 누락됩니다.
- 이 두 결함과 250 pure-LOC 감사를 먼저 해결하기 전에는 002를 실행하거나 develop에 병합하지 마세요.

수정 후 Python 전체 표적, Bun 전체, Svelte check, Ruff, BasedPyright, diff-check를 실행하세요.
소스와 사전등록이 커밋되어 clean해진 뒤에만 기능 worktree에서 canonical data root
"D:\Chanil_Park\Project\Programming\Kronos"를 명시하여 authority 002와 allocation 002를 순서대로 실행하세요.
Junction 보안 가드를 완화하지 마세요.

001 receipt SHA 및 10모델·checkpoint·gate canonical digest와 002를 자동 비교하여
MATCH/MISMATCH를 구분하고, 어느 경우에도 경제 모델 점수 20/100과 live 0/100을 올리지 마세요.
오래된 결과 문서의 TEST NOT_RUN_NO_READ/봉인 표현을 전부 정정하고,
8페이지 UI·API·문서·bundle을 실제 브라우저로 검증하세요.

마지막에는 독립 review-work 감사가 모두 PASS한 경우에만 한글 커밋, push,
develop/v1.29.0-dev 비FF 병합을 진행하고 기능 브랜치는 보존하세요.
main 병합과 태그는 금지합니다.

작업 중에는 단계별 진행률, 발견한 실패, 남은 시간, 모델 성과와 연구 한계를 표로 주기적으로 보고하세요.
```
