# Kronos v1.28.0-dev 브랜치 교정 및 G2 연구 결과

- 기준일: 2026-08-04 KST
- 고정 개발 버전: `v1.28.0-dev`
- 장기 개발 브랜치: `develop/v1.28.0-dev`
- 이번 작업 브랜치: `codex/v1.28.0-dev-g2-custody`
- 연구 ID: `DAILY_CLOSE_OFFLINE_RL_G2_SOURCE_SNAPSHOT_V1`
- 연구 판정: `IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY`

## 1. 버전·브랜치 방식 교정

기존에는 G1~G6와 화면 작업마다 `v1-21`, `v1-22`, `v1-24`, `v1-26`, `v1-27`, `v1-28` 브랜치를 연속 생성했다. 커밋 추적에는 유리했지만 하나의 개발 버전 안에서 진행되는 연구를 여러 버전처럼 보이게 했다.

앞으로 다음 규칙을 적용한다.

```text
master
  └─ develop/v1.28.0-dev                 장기 개발 기준
       ├─ codex/v1.28.0-dev-g2-custody   짧은 작업 브랜치
       ├─ codex/v1.28.0-dev-pit-authority 다음 작업 예시
       └─ v1.28.0-rc.1                   전체 릴리스 게이트 후에만 생성
```

| 항목 | 교정 규칙 |
|---|---|
| 개발 버전 | 연구 진행 중에는 `v1.28.0-dev`로 고정 |
| 작업 시작 | 항상 `develop/v1.28.0-dev`에서 짧은 `codex/v1.28.0-dev-<task>` 생성 |
| 작업 완료 | 테스트 후 기능·문서·빌드 커밋을 develop에 `--no-ff` 병합 |
| 작업 브랜치 | 병합 후 로컬·원격 작업 브랜치 삭제 |
| RC | 기능·연구·UI·문서·검증 게이트가 모두 닫힐 때만 `v1.28.0-rc.1` 생성 |
| 정식 버전 | RC 승인 후 `v1.28.0` 태그와 master PR 진행 |
| 수정 버전 | 정식 릴리스 후 호환 버그 수정만 `v1.28.1` 사용 |
| minor 증가 | 다음 독립 연구 플랫폼 범위가 시작될 때만 `v1.29.0-dev` 사용 |

숫자를 `v1.028.0`처럼 0으로 채우지 않는다. SemVer 정렬과 일반 도구 호환성을 위해 `v1.28.0-dev` 형식을 사용한다.

## 2. 정리된 과거 로컬 브랜치

다음 브랜치는 모든 커밋이 develop의 조상임을 확인한 후 브랜치 포인터만 삭제했다. 커밋과 파일은 삭제되지 않았다.

| 삭제한 브랜치 | 마지막 커밋 | 보존 위치 |
|---|---|---|
| `codex/rl-research-governance-v1-21` | `f5e3ae3` | `develop/v1.28.0-dev` 이력 |
| `codex/rl-daily-close-contracts-v1-22` | `f1563c8` | 동일 |
| `codex/rl-daily-close-signal-env-v1-24` | `681fb23` | 동일 |
| `codex/rl-daily-close-cql-eval-v1-26` | `5343e6d` | 동일 |
| `codex/rl-daily-close-dashboard-v1-27` | `8d46310` | 동일 |
| `codex/rl-all-pages-v1-28` | `380c21a` | 동일 |

## 3. G2에서 실제로 진행한 연구

기존 G2는 5개 관리 증거가 모두 미확인이라 0/15점이었다. 이번에는 원천 SQLite를 수정하지 않고 전체 파일 해시와 연구 입력 범위를 영수증에 결속했다.

| 항목 | 실제 결과 |
|---|---|
| 원천 DB | `_database/Stock_Database_ohlcv_1day.db` |
| 파일 크기 | 1,009,057,792 bytes |
| SHA-256 | `9a363b33a9c2d125f3df7010e54efcec9d53fd6a40dbf16a39b538c20247a09c` |
| 해시 기준 | `SHA256_FULL_SQLITE_FILE` |
| 접근 | SQLite `mode=ro`, `query_only=ON` |
| 실행 중 변경 방지 | 데이터 사용 전·후 전체 SHA-256 재검증, 불일치 시 fail-closed |
| 요청 종목 | 20 |
| 확인된 테이블 | 20/20 |
| 핵심 컬럼 | 20/20 모두 date·OHLCV 확인 |
| 가격 기준 | `UNKNOWN_CONFIRMED` |
| 기존 Type1 identity 비교 | 동일 SHA-256 확인 |

### G2 게이트

| 게이트 | 이전 | 현재 | 근거 |
|---|---|---|---|
| `IMMUTABLE_SOURCE_HASH` | FAIL | PASS | 전체 SQLite SHA-256 결속 |
| `POINT_IN_TIME_UNIVERSE` | FAIL | FAIL | 현재 고정 20종목은 날짜별 구성 종목 증거가 아님 |
| `AVAILABLE_AT_PROVEN` | FAIL | FAIL | DB 행에 권위 있는 가용시각 필드 없음 |
| `OFFICIAL_PRICE_IDENTITY` | FAIL | FAIL | close가 공식/원시/수정 가격인지 독립 증거 없음 |
| `CORPORATE_ACTION_CONTRACT` | FAIL | FAIL | 분할·배당·합병 처리 정책과 참조 데이터 없음 |

기존 Type1 권위 artifact는 로컬 서명 무결성은 제공하지만 스스로 `not KRX/external attestation`이라고 명시한다. 또한 기준시점 안정 종목 방식이므로 현재 20종목 전체의 날짜별 PIT 구성 증거로 사용할 수 없다.

## 4. 실제 연구 재실행 결과

| 항목 | 결과 | 해석 |
|---|---:|---|
| G2 | 1/5 PASS, 3/15점 | 원천 재현성 개선, 외부 권위 미완료 |
| 전체 구현 성숙도 | 78/100 | 이전 75에서 원천 SHA 3점 증가 |
| 프로그램 성숙도 | 63/100 | 외부 custody·운영 준비가 남아 유지 |
| 경제 모델 성과 | 20/100 | 실제 시장 모델 미생성 |
| G3 신호 | 4/4 folds | 이전 진단 결과 재현 |
| 비용 후 평균 | +0.7574% | 관리 미완료 데이터의 진단값 |
| shuffle 평균 | +0.2335% | 생존편향·시장 방향 가능성 경고 |
| native-shuffle | +0.5239%p | 추가 연구 가치는 있으나 수익 증명 아님 |
| 합성 CQL | 3/3 seeds | 파이프라인 보정 성공 |
| 실제 경제 모델 | `false` | G2 전체 통과 전 생성 금지 |
| Fresh OOS | `NOT_RUN_NO_READ` | 봉인 유지 |

## 5. 왜 다음 시장 RL 학습을 실행하지 않았는가

반복 학습 자체는 가능하지만 현재 실행하면 다음 문제를 구분할 수 없다.

1. 현재 살아남은 대형주 20개를 과거에도 알고 선택한 생존편향
2. 분할·배당이 가격 수익률로 잘못 계산되는 기업행사 왜곡
3. 의사결정 시점 이후에 확정되는 데이터를 사용한 미래정보 누수
4. 공식 종가와 로컬 DB close의 정체성 불일치

따라서 지금 시장 CQL/DQN 모델 파일을 만들면 “강화학습을 실행했다”는 사실만 늘고 경제적 성능 증거는 늘지 않는다. G2 5/5와 같은 G3 재통과 후에만 실제 시장 offline controller를 사전등록한다.

## 6. 전체 13개 페이지 상태

| # | 페이지 | 화면 | 연구 상태 | 다음 행동 |
|---:|---|---:|---|---|
| 1 | 홈 | 100% | `DAILY_CLOSE_G2_SOURCE_HASH_BOUND_78` | 외부 권위 4개 확보 |
| 2 | 프로그램 점수 | 100% | 프로그램 63·구현 78·경제 20 | receipt API 동적화 |
| 3 | RL 발견 실험실 | 100% | 과거 NO-GO 보존 | 새 가설만 별도 사전등록 |
| 4 | 데이터 | 100% | G2 1 PASS·4 BLOCKED | PIT·가용시각·가격·기업행사 확보 |
| 5 | 실험 설계 | 100% | G7 잠금 | G2 통과 후 amendment 동결 |
| 6 | 학습 | 100% | 합성 CQL만 생성 | 시장 모델 생성 금지 유지 |
| 7 | 평가 | 100% | G3 4/4 진단 재현 | PIT 데이터에서 동일 평가 |
| 8 | 비교 | 100% | CQL·shuffle·random 분리 | 시장 모델에도 같은 통제 적용 |
| 9 | 보고서 | 100% | NO-GO·SHA·브랜치 흐름 표시 | 동적 receipt 연결 |
| 10 | 인사이트 | 100% | 현재 universe 관찰용 | PIT 전 추천 표현 금지 |
| 11 | 다른 레인 | 100% | 성과 전이 금지 | 독립 증거 유지 |
| 12 | Kronos 모델 | 100% | 예측 모델, RL 아님 | 별도 가설 전 결합 금지 |
| 13 | 설정 | 100% | read-only | 표시 설정만 허용 |

모든 페이지의 전역 실행 스트립에는 `DEV: v1.28.0-dev`가 표시된다.

## 7. 남은 단계와 예상 시간

| 우선 | 단계 | 필요한 입력 | 예상 |
|---:|---|---|---|
| P0 | 날짜별 PIT universe | KRX/KOSPI/KOSDAQ 종목 구성 이력 또는 검증된 공급자 파일 | 데이터 확보 1~2일 |
| P0 | available_at 증거 | 필드별 공표·수신 시각과 의사결정 cutoff | 0.5~1일 |
| P0 | 가격 정체성 | 공식/원시/수정 가격 필드 정의와 원천 hash | 0.5~1일 |
| P0 | 기업행사 계약 | 분할·배당·합병 event와 adjustment 방식 | 0.5~1일 |
| P1 | G3 재실행 | 위 4개 통과 데이터 | 2~4시간 |
| P1 | 실제 시장 offline RL | 동결된 G2/G3 receipt | 3~6시간 |
| P1 | 비용·통제 평가 | DQN·CQL·shuffle·random, 비용 0/기준/스트레스 | 2~4시간 |
| 승인 | Fresh OOS | 사람 승인·prereg SHA | 별도 승인 |

다음 코드 작업 브랜치는 외부 권위 데이터가 준비된 뒤 `codex/v1.28.0-dev-pit-authority`로 만들며 버전은 계속 `v1.28.0-dev`를 유지한다.

## 8. 검증 결과

| 검증 | 결과 |
|---|---|
| Python 일봉·대시보드 회귀 | 58 passed, 2 skipped |
| 새 G2 계약 집중 테스트 | 10 passed |
| 프런트 전체 회귀 | 413 passed |
| Svelte/TypeScript | 0 errors, 0 warnings |
| 프로덕션 빌드 | 980 modules transformed |
| 변경 Python no-excuse | 0 violations |
| 변경 파일 크기 | 최대 177 pure LOC, 전부 250 이하 |
| Flask | PID `125616`, `127.0.0.1:5070` |
| 점수표 | HTTP 200 |
| 최신 JS | `assets/index-D0Mz6uV2.js`, HTTP 200 |
| dist index SHA-256 | `8E1399755CEEB5D783211298955D8A67B840A8CC0F551ED1E6BFB516DC4C62D0` |

TypeScript 보조 no-excuse 스크립트는 스킬 설치 경로에서 저장소의 `typescript` 패키지를 찾지 못해 실행되지 않았다. 저장소 권위 검증인 전체 Bun 테스트, 생성 타입 검사, `svelte-check`, Vite production build는 모두 통과했다.
