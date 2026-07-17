# 문서 표준과 연구 보고서 양식

> 상태: `ACTIVE_DOCUMENT_STANDARD`  
> 적용: 2026-07-17 이후 새 문서  
> 원칙: 기존 문서는 보존하고 새 문서부터 적용

## 공통 문서 구조

모든 새 문서는 다음 순서를 권장합니다.

1. 제목
2. 상태·작성일·범위 metadata
3. 목차
4. 목적
5. 배경과 관련 결정
6. 본문
7. 결론 또는 판정
8. 한계·위험·미해결 항목
9. 검증
10. 관련 문서·artifact·commit
11. 변경 히스토리

## 공통 metadata

```markdown
# 문서 제목

> 문서 ID: `고유 식별자`
> 작성일: `YYYY-MM-DD KST`
> 상태: `DRAFT / PREREGISTERED / COMPLETE / NO-GO / INCONCLUSIVE / SUPERSEDED`
> 범위: `연구·기능·데이터 범위`
> 브랜치: `branch`
> 기준 commit: `SHA`
> 대체 문서: `없음 또는 path`
```

## 연구 결과 보고서 양식

```markdown
# [연구명] 결과 보고서 — YYYY-MM-DD

> 문서 ID:
> 실행 기간:
> 데이터 기간:
> 상태:
> 모델 판정:
> 연구 단계: smoke / full / diagnostic
> 브랜치·commit:

## 목차

## 1. 연구 목적
- 해결하려는 질문
- RL이 필요한 이유
- 성공해도 주장하지 않는 것

## 2. 사전등록과 가설
- prereg 문서와 SHA-256
- 주가설
- 귀무·negative control
- 성공·실패·중단 기준

## 3. 데이터와 계보
- DB/table/column
- 데이터 시작·종료일
- point-in-time universe
- 가격 기준과 공식 종가 여부
- train/validation/test
- purge/embargo
- source/session SHA-256

## 4. 환경
- observation
- action
- transition
- episode
- reward
- 경제 NAV 공식
- invalid action
- terminal liquidation

## 5. 자본·slot·비용
- 초기 자본
- slot 수와 slot당 금액
- reserve
- primary 비용(%)
- control 비용(%)
- 체결·슬리피지 가정

## 6. 알고리즘과 실행
- algorithm/version
- seed/fold/variant
- timesteps
- device
- checkpoint 규칙
- stop 조건

## 7. 비교 기준
- no-trade
- RULE baseline
- supervised baseline
- shuffle/negative control
- ablation

## 8. 결과
- validation
- untouched test OOS
- 수익률·MDD·turnover
- invalid-action rate
- seed별 결과
- IQM/bootstrap CI
- 비용 민감도

## 9. 원인 분석
- 성공·실패에 영향을 준 원인
- 데이터·환경·알고리즘·회계 분리
- 반증 또는 대체 설명

## 10. 결론과 판정
- GO / NO-GO / INCONCLUSIVE / NOT_RUN
- 판정 근거
- 승격 가능 여부

## 11. 한계와 blocker

## 12. 검증
- 실행 명령
- 테스트 결과
- ledger reconciliation
- browser/API 검증

## 13. Artifact
| 파일 | 역할 | SHA-256 |
|---|---|---|

## 14. 관련 문서

## 15. 관련 commit·branch·tag

## 16. 변경 히스토리
| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
```

## 사전등록 양식

사전등록은 결과를 보기 전에 다음을 수치로 고정합니다.

- 연구 질문과 가설
- 데이터·기간·universe·가격 시점
- feature와 label
- observation/action/reward
- 비용과 자본
- split/purge/embargo
- seed/fold/variant matrix
- baseline/control/ablation
- checkpoint 선택 규칙
- 성공·실패·중단 기준
- OOS 접근 정책
- 허용·금지 실행 명령
- source/protocol hash

사후에 정의를 변경하면 기존 사전등록을 수정하지 않고 새 버전 문서를 만듭니다.

## Incident 양식

```markdown
# [기능] Incident — YYYY-MM-DD

## 요약
## 발견 시각과 영향 범위
## 재현 조건
## 직접 원인
## 근본 원인
## 수정 내용
## 회귀 테스트
## 사용자 영향
## 재발 방지
## 관련 commit
## 변경 히스토리
```

## Release 양식

```markdown
# [제품/기능] Release — YYYY-MM-DD

## 범위와 제외 범위
## 변경 전·후
## 기능 점수 또는 gate
## 검증 결과
## 알려진 제한
## rollback
## branch·commit·tag
## 사용자 확인 경로
## 변경 히스토리
```

## 표기 규칙

- 사용자 화면과 새 한글 문서의 거래비용은 `%`로 표시합니다.
- 23bp는 0.23%, 46bp는 0.46%, 1.5bp는 0.015%입니다.
- 기존 schema/API/artifact의 `*_bp` 이름은 호환성을 위해 유지할 수 있습니다.
- RULE, supervised, portfolio RL, orderbook RL을 혼용하지 않습니다.
- smoke, validation, historical test OOS, fresh OOS를 구분합니다.
- 수익률과 shaped reward를 같은 지표처럼 표시하지 않습니다.
- 공식 종가와 15:20 종가 대용값을 구분합니다.
- `NO-GO`, `NOT_RUN`, `BLOCKED`를 완화하거나 숨기지 않습니다.

## HTML 보고 원칙

Markdown을 권위 원본으로 유지하고 대시보드는 read-only HTML을 생성합니다.

- `marked`로 Markdown 변환
- DOMPurify로 HTML 정화
- 임의 script, inline event, 외부 실행 콘텐츠 금지
- 표·목차·코드·관련 문서 탐색 지원
- 결과 원문 다운로드와 SHA-256 표시
- HTML 화면은 원본 판정을 변경하지 않음

## 기존 문서 이관 원칙

기존 문서를 일괄 수정하지 않습니다.

1. 연구 원장에 링크와 상태를 추가합니다.
2. 필요한 경우 sidecar metadata를 추가합니다.
3. 오래된 비용 표기는 원문 증거로 보존합니다.
4. 사용자 화면에서는 정확한 `%` 변환을 제공합니다.
5. 새로운 결과는 새 표준 문서로 작성합니다.
