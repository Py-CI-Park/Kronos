# Kronos v1.28.0-dev G2 원천·권위성 감사 및 브랜치 보존 결과

- 기준일: 2026-08-04 KST
- 개발 버전: `v1.28.0-dev` 고정
- 장기 개발 브랜치: `develop/v1.28.0-dev`
- 현재 연구 브랜치: `codex/v1.28.0-dev-pit-authority`
- 최신 연구 판정: `AUDITED_LOCAL_ANCHOR_NO_GO_EXTERNAL_AUTHORITY`
- 경제 모델: 생성하지 않음
- Fresh OOS: `NOT_RUN_NO_READ`

## 1. 결론

프로그램은 일봉 종가매매 강화학습을 연구할 실행 계약, 비용 계약, 신호 진단, 합성 CQL 보정, 결과 대시보드를 갖췄다. 그러나 실제 시장 강화학습 모델을 정당하게 만들기 위한 날짜별 종목 구성, 정보 가용 시각, 공식 가격 동일성, 기업행사 조정 증거가 아직 없다.

이번 연구에서 로컬 일봉 DB 전체 해시와 기존 Type1 권위 자료를 다시 검증했다. 20개 등록 종목 중 19개는 2017-12-29 앵커 기준 유동성 상위 500에 속했지만 `068270`은 당시 상장 유효일 이전이라 제외됐다. 고정된 현재 종목 20개를 모든 과거 날짜에 그대로 적용하면 생존편향이 생긴다는 구체적 반례다.

따라서 구현은 진전됐지만 G2는 여전히 `NO-GO`다. 데이터 권위 없이 학습 횟수만 늘리면 잘못된 환경에 과적합한 모델을 더 정교하게 만들 뿐이다.

## 2. 브랜치 정책 정정

병합된 작업 브랜치를 삭제하지 않는다. 작업 브랜치는 비FF 병합 후 `MERGED` 이력으로 보존하고 다시 작업 기반으로 사용하지 않는다.

```text
master
  └─ develop/v1.28.0-dev
      ├─ codex/v1.28.0-dev-g2-custody       MERGED·보존
      ├─ codex/v1.28.0-dev-pit-authority    현재 작업·병합 후 보존
      └─ codex/v1.28.0-dev-<next-task>      다음 작업
```

| 구분 | 규칙 |
|---|---|
| 버전 | 릴리스 게이트 전까지 `v1.28.0-dev` 유지 |
| 작업 시작 | 항상 `develop/v1.28.0-dev`에서 `codex/v1.28.0-dev-<task>` 생성 |
| 병합 | 테스트·연구 영수증·문서·빌드 후 `--no-ff` 병합 |
| 병합 브랜치 | 삭제하지 않고 `MERGED` 이력으로 보존 |
| 후속 작업 | 보존 브랜치를 재사용하지 않고 develop에서 새 브랜치 생성 |
| RC·태그 | 전체 릴리스 게이트가 닫힌 뒤에만 `v1.28.0-rc.1` 생성 |
| master | RC 승인 전 병합 금지 |

복원한 브랜치는 다음과 같다.

| 브랜치 | 복원 커밋 | 상태 |
|---|---|---|
| `codex/rl-research-governance-v1-21` | `f5e3ae3` | 보존 |
| `codex/rl-daily-close-contracts-v1-22` | `f1563c8` | 보존 |
| `codex/rl-daily-close-signal-env-v1-24` | `681fb23` | 보존 |
| `codex/rl-daily-close-cql-eval-v1-26` | `5343e6d` | 보존 |
| `codex/rl-daily-close-dashboard-v1-27` | `8d46310` | 보존 |
| `codex/rl-all-pages-v1-28` | `380c21a` | 보존 |
| `research/daily-close-offline-rl-v2` | `380c21a` | 보존 |
| `codex/v1.28.0-dev-g2-custody` | `c406001` | `MERGED`·보존 |

## 3. 만들려는 강화학습 모델

| 항목 | 계약 |
|---|---|
| 시장 | 한국 주식, 일봉 |
| 의사결정 | 당일 장 종료 후 정보로 다음 거래일 시가 실행 |
| 자본 | 초기 6,000만 원 |
| 최대 노출 | 5,000만 원 |
| 포트폴리오 | 최대 10종목 슬롯 |
| 행동 | 종목별 보유·매수·매도·비중 조절 |
| 비용 | 주식 왕복 비용 0.230% 계약 |
| 보상 | 비용 차감 포트폴리오 가치 변화와 위험 페널티 |
| 후보 알고리즘 | CQL 중심 오프라인 RL, DQN·random·shuffle 대조군 |
| 현재 모델 범위 | 합성 데이터 파이프라인 보정 전용 |
| 금지 주장 | 수익성, 실거래 준비, Fresh OOS 성과 |

## 4. 실제 G2 원천 DB 감사

| 항목 | 결과 |
|---|---|
| DB | `_database/Stock_Database_ohlcv_1day.db` |
| 크기 | 1,009,057,792 bytes |
| SHA-256 | `9a363b33a9c2d125f3df7010e54efcec9d53fd6a40dbf16a39b538c20247a09c` |
| 접근 | SQLite `mode=ro`, `query_only=ON` |
| 등록 종목 | 20 |
| 테이블 | 20/20 존재 |
| 핵심 열 | 20/20 `date`, OHLCV 존재 |
| 실행 중 변경 방지 | 실행 전후 전체 파일 SHA-256 재검증 |
| 가격 기준 | `UNKNOWN_CONFIRMED` |
| 로컬 immutable hash | PASS |

## 5. 실제 Type1 권위성 감사

- 연구 ID: `DAILY_CLOSE_OFFLINE_RL_G2_PIT_AUTHORITY_AUDIT_V1`
- 생성 영수증: `.omx/artifacts/daily_close_rl_v1_28_dev_pit_authority/authority_audit.json`
- 권위 자료: `type1-krx-authority-20260724-004`
- 권위 자료 SHA-256: `eb88b30e89605e89ce5db5690bddda9f3c4d2a9fb779cc07c949c9e502219655`
- 범위: `LOCAL_2017_ANCHOR_CLASSIFICATION_ONLY`
- 무결성 표기: `local artifact integrity; not KRX/external attestation`

| 분류 | 종목 수 | 해석 |
|---|---:|---|
| 2017 앵커 상위 500 | 19 | 해당 시점 로컬 권위 자료에서 적격 |
| 적격이나 상위 500 밖 | 0 | 없음 |
| 앵커 시점 제외 | 1 | `068270`: `not_effective_at_anchor` |
| 미분류 | 0 | 없음 |

이 감사는 로컬 파일의 서명·재구성·원천 해시 결속을 검증한다. 외부 KRX가 현재 파일을 증명했다는 뜻은 아니다. 또한 단일 앵커 시점만 검증하므로 날짜별 PIT universe를 증명하지 않는다.

## 6. G2 게이트

| 게이트 | 현재 | 이유 | 통과 조건 |
|---|---|---|---|
| `IMMUTABLE_SOURCE_HASH` | PASS | 전체 SQLite SHA-256 결속 | 유지 |
| `POINT_IN_TIME_UNIVERSE` | BLOCKED | 단일 2017 앵커만 존재 | 거래일별 상장·상폐·보통주 적격 목록과 원본 해시 |
| `AVAILABLE_AT_PROVEN` | BLOCKED | 정보 공개·수신 시각 없음 | 각 필드의 공표·수신 시각과 의사결정 cutoff |
| `OFFICIAL_PRICE_IDENTITY` | BLOCKED | 로컬 close의 공식·원시·수정 기준 미확정 | KRX 원본 가격과 동일성·조정 정의·해시 |
| `CORPORATE_ACTION_CONTRACT` | BLOCKED | 분할·합병·배당 처리 계약 없음 | 이벤트 원본, 효력일, 조정식, 테스트 |

## 7. 공식 원천 확보 연구

| 원천 | 확인한 기능 | 현재 제약 | 사용 목적 |
|---|---|---|---|
| [KRX Open API 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd) | 2010년 이후 KOSPI·KOSDAQ 일별매매정보와 종목기본정보 | 인증키와 API 활용 승인 필요 | 날짜별 종목·공식 OHLCV 원본 |
| [KRX Open API 이용방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp) | 로그인, 인증키 신청, 서비스 활용 신청, 관리자 승인 절차 | 현재 환경에 키 없음 | 공식 수집 재개 조건 |
| [KRX 데이터 분배상품](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA002.jsp) | 종가·종목 이벤트 등 EOD 참조정보 | 일부 데이터는 상품·계약 필요 가능 | 기업행사와 종가 기준 보강 |
| [OpenDART 공시검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001) | 회사·날짜·공시유형별 검색 | 40자리 인증키 필요 | available_at와 접수시각 |
| [OpenDART 배당 API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019005) | 2015년 이후 배당 정보 | 인증키 필요 | 배당 이벤트 보강 |
| [OpenDART 주요사항보고서](https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS005) | 감자·분할·합병 결정 등 | 인증키 필요 | 기업행사 원본과 발표시점 |

로컬 환경에서 `KRX`·`DART` 관련 인증키는 발견되지 않았다. 키를 코드·문서·Git에 저장하지 말고 실행 환경의 비밀 변수나 로컬 비추적 설정으로 주입해야 한다.

## 8. 점수

| 점수 | 현재 | 의미 |
|---|---:|---|
| 화면 구현 | 100/100 | 13개 페이지 구현 완료 |
| 연구 구현 | 78/100 | 원천 해시와 로컬 권위 감사 완료 |
| 프로그램 성숙도 | 63/100 | 외부 데이터·운영·검증 게이트 미완료 |
| 경제 모델 성과 | 20/100 | 실제 시장 모델과 OOS 경제 성과 미생성 |

권위성 감사를 추가했지만 외부 게이트를 통과하지 않았으므로 점수를 올리지 않았다. 코드가 늘었다는 이유만으로 성숙도를 올리지 않는다.

## 9. 전체 13개 페이지

| # | 페이지 | 화면 | 현재 증거 상태 | 다음 작업 |
|---:|---|---:|---|---|
| 1 | 홈 | 100% | `DAILY_CLOSE_G2_LOCAL_AUTHORITY_AUDITED_78` | 공식 데이터 키·승인 상태 표시 |
| 2 | 프로그램 점수 | 100% | 프로그램 63·구현 78·경제 20 | 동적 감사 receipt 연결 |
| 3 | RL 발견 실험실 | 100% | 과거 NO-GO 보존 | 새 가설만 별도 사전등록 |
| 4 | 데이터 | 100% | 19 stable·1 excluded·4 external blockers | KRX·DART 공식 원본 수집 |
| 5 | 실험 설계 | 100% | G7 잠금 | G2 통과 후 amendment |
| 6 | 학습 | 100% | 합성 CQL만 생성 | 실제 시장 모델 생성 금지 유지 |
| 7 | 평가 | 100% | 기존 4/4 진단 folds | PIT 데이터로 재실행 |
| 8 | 비교 | 100% | CQL·shuffle·random 분리 | 동일 비용·체결 계약 적용 |
| 9 | 보고서 | 100% | 로컬 권위 감사 NO-GO | 외부 수집 영수증 연결 |
| 10 | 인사이트 | 100% | 현재 universe 관찰용 | PIT 추천으로 오인 금지 |
| 11 | 다른 레인 | 100% | 성과 전이 차단 | 외부 증거 유지 |
| 12 | Kronos 모델 | 100% | 예측 모델, RL 아님 | 결합 주장은 별도 검증 |
| 13 | 설정 | 100% | read-only | 비밀 키를 화면·Git에 노출 금지 |

## 10. 다음 단계와 예상 시간

| 우선순위 | 단계 | 시작 조건 | 작업 시간 |
|---:|---|---|---:|
| P0 | KRX 인증키·API 활용 승인 | 사용자 계정 신청·승인 | 외부 승인 시간 별도 |
| P0 | OpenDART 인증키 준비 | 사용자 키 발급 | 외부 발급 시간 별도 |
| P0 | 날짜별 PIT·가격·기업행사 수집기 | 두 키 준비 | 4~8시간 |
| P0 | 원본 응답·요청·수신시각·SHA 영수증 | 수집기 실행 | 2~4시간 |
| P0 | 기업행사 조정 계약·회귀 테스트 | 공식 이벤트 확보 | 3~5시간 |
| P1 | G2 5/5 재감사 | 위 자료 완성 | 1~2시간 |
| P1 | G3 신호 바닥 재실행 | G2 PASS | 2~4시간 |
| P1 | 실제 시장 offline CQL·DQN·대조군 | G2·G3 PASS 및 사전등록 | 4~8시간 |
| P1 | 비용·체결·walk-forward 평가 | 모델 생성 후 | 3~6시간 |
| 승인 | Fresh OOS | 별도 사람 승인과 prereg SHA | 승인 전 실행 금지 |

현재 즉시 가능한 연구는 로컬 데이터·권위 자료 감사, 계약·수집기·테스트 구현, 합성 보정이다. 공식 키 없이 날짜별 권위 데이터를 실제로 수집하거나 G2를 PASS로 바꾸는 일은 불가능하다.

## 11. 최종 검증

| 검증 | 결과 |
|---|---|
| 새 권위 감사 단위 테스트 | 4 passed |
| 일봉 연구 회귀 | 31 passed |
| RL·대시보드 회귀 | 102 passed, 2 skipped |
| 프런트 전체 테스트 | 413 passed |
| Svelte 검사 | 0 errors, 0 warnings |
| Python Ruff·basedpyright | 0 errors, 0 warnings |
| 프로덕션 빌드 | 980 modules transformed |
| 로컬 서버 | `127.0.0.1:5070`, root HTTP 200 |
| 최신 JS | `assets/index-DKukMerG.js`, HTTP 200 |
| dist index SHA-256 | `35F13FA1F4593FF9A19C9F39816D703ABFD5C4067B181FEE862920B70BBE0EB4` |

앱 내 브라우저 자동화는 로컬 주소 보안 정책에 의해 차단돼 자동 시각 검증을 완료하지 못했다. 서버와 새 번들은 정상 제공 중이므로 열린 대시보드 탭을 새로고침해 수동 확인할 수 있다.
