# Kronos 버전·브랜치·커밋·태그 운영 정책

- 정책 ID: `KRONOS-VERSION-GOVERNANCE-2026-08-04`
- 상태: `ADOPT_FOR_NEXT_RELEASE`
- 현재 기준: master `30297a0`, tag `research-rl-close-recovery-v1.0.0`
- 다음 통합 후보: `v1.21.0`

## 1. 권장 버전 형식

앞으로 공식 프로그램 버전은 Semantic Versioning 형태를 사용한다.

```text
vMAJOR.MINOR.PATCH
```

| 자리 | 의미 | 증가 조건 | 예시 |
|---|---|---|---|
| `MAJOR` | 호환성·연구 계약의 큰 세대 | API·artifact·연구 계약의 호환 불가 변경 | `v2.0.0` |
| `MINOR` | 사용자 기능 또는 독립 연구 단계 | 새 페이지, 비용 계약, 새 연구 gate, 새 모델 family | `v1.21.0` |
| `PATCH` | 동일 minor의 수정 | 버그, 문서, 스타일, 오탈자, 회귀 수정 | `v1.21.1` |

사용자가 원하는 두 번째 숫자의 3자리·4자리 확장은 SemVer에서 자연스럽게 지원된다.

```text
v1.21.0
v1.99.0
v1.100.0
v1.999.0
v1.1000.0
```

`v1.021.0`처럼 앞에 0을 채우지 않는다. 숫자 정렬·도구 해석·SemVer 호환성을 복잡하게 만들기 때문이다.

## 2. PATCH를 fix에 사용하는 규칙

| 변경 | 버전 예시 | 커밋 예시 |
|---|---|---|
| 새 비용 설정 UI | `v1.22.0` | `feat(cost): 상품별 실제 비용 계약을 표시하다` |
| 같은 UI의 계산 오류 수정 | `v1.22.1` | `fix(cost): ETF 매도세금 중복 계산을 막다` |
| 같은 UI의 모바일 넘침 수정 | `v1.22.2` | `fix(ui): 모바일 비용표의 가로 넘침을 제거하다` |
| 새 offline RL family | `v1.26.0` | `feat(rl): 보수적 오프라인 정책 학습기를 추가하다` |
| 호환 불가 manifest v3 | `v2.0.0` | `feat(schema)!: 연구 manifest 계약을 v3로 전환하다` |

문서만 바뀌어도 외부에 공개된 사용법·판정이 바뀌면 PATCH를 올린다. 내부 초안 문서만 추가하고 릴리스하지 않으면 태그를 만들지 않는다.

## 3. 사전 릴리스

```text
v1.21.0-alpha.1   # 기능 골격, 증거 불완전
v1.21.0-beta.1    # 기능 완료, 회귀·브라우저 QA 진행
v1.21.0-rc.1      # 릴리스 후보
v1.21.0           # 검증 완료 릴리스
```

사전 릴리스 태그도 모델 수익성 GO를 뜻하지 않는다. tag annotation에 플랫폼 릴리스, 모델 판정, OOS 상태를 각각 기록한다.

## 4. 버전과 연구 판정 분리

| 값 | 답하는 질문 |
|---|---|
| 프로그램 버전 `v1.26.0` | 어떤 기능·계약·UI가 포함됐는가? |
| run ID | 어떤 데이터·seed·설정으로 실행했는가? |
| verdict `GO/NO_GO` | 해당 후보가 사전등록 기준을 통과했는가? |
| lifecycle `TRAIN_ONLY/OOS/PAPER` | 어느 증거 단계인가? |

`v2.0.0`이라고 해서 모델이 수익을 낸다는 뜻이 아니며, `NO_GO`라고 해서 프로그램 버전을 되돌리지 않는다.

## 5. 기존 태그 마이그레이션

기존 태그는 삭제하거나 이름을 바꾸지 않는다. 이미 배포된 Git 객체의 의미를 보존한다.

| 기존 계보 | 처리 |
|---|---|
| `fork-v1.1.0` ~ `fork-v1.20.0` | 역사적 연구 단계 태그로 보존 |
| `research-*-vX.Y.Z` | 특정 연구 전달점으로 보존 |
| `stom/vN-*` | STOM 역사적 실험 tag로 보존 |
| 새 공식 프로그램 tag | 단순 `vMAJOR.MINOR.PATCH`로 통일 |

첫 새 공식 버전은 기존 `fork-v1.20.0` 다음 번호인 `v1.21.0`을 권장한다. 이 문서 커밋 자체에서는 tag를 만들지 않는다. 계획 구현·검증·통합이 완료됐을 때 annotated tag로 발행한다.

## 6. 계획된 minor 버전 계보

| 버전 | 계획 범위 | 모델 GO 의미 |
|---|---|---|
| `v1.21.0` | 연구 원리·비용·버전·실행계획 문서 기준선 | 없음 |
| `v1.22.0` | 상품별 비용 계약과 비용 UX | 없음 |
| `v1.23.0` | 인과적 종가·PIT 데이터 custody | 없음 |
| `v1.24.0` | 신규 horizon supervised signal floor | 결과에 따라 후보 종료 가능 |
| `v1.25.0` | synthetic stateful MDP calibration | 시장 수익 증거 아님 |
| `v1.26.0` | 최소 offline RL pilot | TRAIN/validation 후보 |
| `v1.27.0` | nested walk-forward·rliable 평가 | Fresh OOS 진입 후보 가능 |
| `v1.28.0` | 승인된 sealed OOS 결과 | 해당 run 판정만 의미 |
| `v1.29.0` | paper-forward 운영 증거 UI | live 승인 아님 |

단계가 실패해도 minor 버전은 실패 증거와 플랫폼 기능을 기록할 수 있다. 실패를 숨기거나 성공 tag처럼 표현하지 않는다.

## 7. 브랜치 전략

| 브랜치 | 역할 | 병합 대상 | 수명 |
|---|---|---|---|
| `master` | 검증된 통합 기준선 | 없음 | 장기 |
| `research/<lane>-<hypothesis>-vN` | 사전등록된 연구 계보와 공식 판정 | `master` | 중장기 |
| `codex/<scope>-vX-YY` | 한 작업 패키지 구현·문서·테스트 | 부모 `research/*` 또는 integration | 단기 |
| `release/vX.Y.Z` | 회귀·빌드·문서·릴리스 후보 안정화 | `master` | 단기 |
| `hotfix/vX.Y.Z-<scope>` | 이미 발행한 버전의 긴급 수정 | `master` | 단기 |

권장 흐름:

```text
master
  └─ research/daily-close-offline-rl-v2
       ├─ codex/cost-contract-v1-22
       ├─ codex/causal-data-v1-23
       ├─ codex/signal-floor-v1-24
       └─ codex/offline-rl-pilot-v1-26
            ↓ PR
       research integration
            ↓ 검증 PR
       release/v1.26.0
            ↓ PR
       master
            ↓ annotated tag v1.26.0
```

Fresh OOS를 읽는 브랜치는 일반 구현 브랜치와 분리하고 별도 사전등록·승인·receipt를 요구한다.

## 8. 커밋 형식

제목과 본문은 한글로 작성할 수 있다. Conventional Commit type과 scope만 영문 소문자로 유지하면 검색과 자동화가 쉽다.

```text
<type>(<scope>): <한글 명령형 요약>

변경 이유:
- ...

검증:
- ...

연구 경계:
- 모델 GO, Fresh OOS, live 승인과의 관계
```

| type | 사용처 |
|---|---|
| `docs` | 연구·계획·운영 문서 |
| `feat` | 사용자 기능·연구 capability |
| `fix` | 재현 가능한 오류 수정 |
| `test` | 테스트·oracle·fixture |
| `perf` | 측정된 성능 개선 |
| `refactor` | 동작 유지 구조 변경 |
| `build` | 생성 번들·빌드 산출물 |
| `chore` | 개발환경·도구 관리 |
| `merge` | 계보 통합 |

한 커밋에는 한 목적만 포함한다. source, 생성 dist, 연구 결과 문서는 가능하면 별도 커밋으로 유지한다.

## 9. PR 규칙

PR 본문에는 다음 표를 필수로 넣는다.

| 항목 | 내용 |
|---|---|
| 목표 버전 | 예: `v1.24.0` |
| 부모 브랜치 | 연구 계보 |
| 변경 범위 | 파일·페이지·API |
| 사전등록 | 문서·SHA |
| 테스트 | 명령과 결과 |
| 브라우저 QA | viewport·console·overflow |
| 모델 판정 | `NOT_RUN`, `TRAIN_ONLY`, `NO_GO`, `GO_CANDIDATE` |
| Fresh OOS | `NOT_RUN_NO_READ` 여부 |
| rollback | revert 가능한 커밋 경계 |

## 10. 태그 규칙

모든 공식 버전 tag는 annotated tag로 만든다.

```powershell
git tag -a v1.22.0 -m "Kronos v1.22.0 상품별 비용 계약과 UX"
```

태그 전 필수 조건:

1. 대상 PR이 승인·병합됐다.
2. Git 작업트리가 깨끗하다.
3. 관련 Python·frontend 테스트와 build가 통과했다.
4. 실제 브라우저에서 desktop·tablet·mobile을 확인했다.
5. result 문서에 commit·PR·verdict·OOS 상태가 기록됐다.
6. tag message가 플랫폼 릴리스와 모델 경제성을 구분한다.

push, PR, merge, tag push는 사용자의 명시적 요청 또는 해당 단계의 승인 범위에서만 수행한다.
