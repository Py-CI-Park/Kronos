# Kronos V6 P0~P2 통합 강화학습 연구 플랫폼 최종 보고

- 기준일: 2026-08-05 KST
- 개발 버전: `v1.28.0-dev`
- 통합 개발선: `develop/v1.28.0-dev`
- 판정: **플랫폼 P0~P2 구현 완료 / 경제적 강화학습 모델 NO-GO / 실거래 BLOCKED**
- 감사 문서: `docs/kronos_dashboard_v6_unified_platform_audit_2026-08-05.md`
- 실행 계획: `docs/kronos_dashboard_v6_p0_p2_development_plan_2026-08-05.md`

## 1. 결론

Kronos V6는 연구 실행을 찾고, 학습 로그와 성과 곡선을 보고, 같은 증거 lane 안에서 비교하고, 데이터·모델·보고서 계보를 검토할 수 있는 **읽기 전용 강화학습 연구 플랫폼**으로 정리됐다. 기존 화면의 서로 다른 포맷, 한글 깨짐, 무거운 첫 화면 API, 영구 실행 상세 부족, Kronos Core와 trading policy 혼동을 공통 셸·공통 컴포넌트·경량 typed API로 교체했다.

제품 구현·UX 점수는 94/100까지 높아졌지만 연구 프로그램 전체는 70/100, 경제 모델은 20/100, 실거래 준비는 0/100이다. UI 완성과 수익 모델 성공은 별개의 결과다. 현재 DQN/CQL 모델 파일과 학습 기록은 존재하지만, 외부 권위가 증명된 PIT 데이터에서 비용 후 경제성 gate와 Fresh OOS를 통과한 종가매매 정책은 아직 없다.

## 2. 100점 점수표

| 평가 영역 | 점수 | 계산·직접 증거 | 현재 판정 |
|---|---:|---|---|
| 제품 구현·UX | **94** | 플랫폼 90점과 엔지니어링 100점을 각 가중치 30:20으로 정규화: `(90×30 + 100×20) ÷ 50 = 94` | 강함 |
| 연구 프로그램 전체 | **70** | 플랫폼 90×30% + RL 증거 55×30% + 엔지니어링 100×20% + 거버넌스 60×10% + live 0×10% = 69.5, 반올림 | 부분 완료 |
| 플랫폼·UX | 90 | 8개 통합 페이지, 공통 셸, 반응형 규칙, 브라우저 QA. 브로커 운영 UI는 범위 밖 | 강함 |
| RL 증거 | 55 | DQN/CQL artifact·negative control·진단 fold 존재. PIT 승격 신호·경제 모델·Fresh OOS 없음 | 부분 완료 |
| 엔지니어링 | 100 | typed API, bounded catalog, 대용량 telemetry sampling, 테스트·build·실제 런타임 | 강함 |
| 연구 거버넌스 | 60 | 사전등록·실패 공개·claim 분리·브랜치 계보. 외부 custody·Fresh OOS 승인·원격 릴리스 없음 | 부분 완료 |
| 경제 모델 | **20** | 모델 파일 존재는 성공으로 계산하지 않음. 비용 후 GO 정책 미생성 | NO-GO |
| 실거래 준비 | **0** | Fresh OOS, paper-forward, broker, 운영 위험 통제 미완료 | BLOCKED |

94점은 “플랫폼을 사용하고 검토할 수 있는 제품 구현 품질” 점수다. 95점은 원격 PR·릴리스 증거와 추가 접근성·반응형 사용자 검수가 있어야 부여한다. 연구 전체 90점은 PIT 데이터 권위, 경제성, Fresh OOS, paper-forward가 실제로 통과해야 가능하다.

## 3. 전체 페이지 P0~P2 결과

| 우선순위 | 공식 페이지 | 목적 | 완료 기능 | 직접 검증 | 구현 | 남은 연구 행동·예상 |
|---|---|---|---|---|---:|---|
| P0 | 통합 현황 | 현재 연구·성과·실패·다음 행동을 한 화면에서 확인 | 4종 분리 점수, run·telemetry·NO-GO·OOS 상태, 할 수 있는 것, 성공 gate, 8개 페이지 표 | 98 runs, 21 telemetry, 9 NO-GO, 표 8행, alert/overflow 0 | 100% | 릴리스 증거 유지; 화면 완료 |
| P0 | 연구 라이브러리 | 모든 experiment/run 검색과 영구 상세 | 검색·lane·판정 filter, pagination, artifact metadata, 영구 `run` URL | 98개 카탈로그, orderbook DQN NO-GO 노출, 직접 URL·뒤로가기 통과 | 100% | PIT 데이터 재실행을 새 run으로 연결; G2 후 |
| P1 | 실시간 학습 | 학습 진행과 성과를 단순 그래프로 추적 | 실행 선택, 5초 follow, reward·equity·drawdown·loss·exploration, 최근 action | 21 telemetry runs, canvas 3개, 59.1MB head-tail sampling 검증 | 100% | 신규 시장 학습 실행에 같은 event 계약 사용; G2 후 3~6시간 |
| P1 | 평가·비교 | 동일 증거 lane에서 비용 후 비교 | same-lane selector, 공식 NO-GO, 기술 통계, 2개 비교 그래프, 종가매매 9단계 흐름 | canvas 2개, 다른 lane 순위화 금지, POST_CLOSE_NEXT_OPEN 표시 | 100% | 동일 PIT 데이터에서 DQN/CQL/rule/random/shuffle 재평가; 2~4시간 |
| P2 | 데이터·증거 | DB 존재와 외부 데이터 권위를 분리 | source/dataset/telemetry/corrupt 집계, PIT·available-at·KRX·Fresh OOS gate | local file PRESENT, external KRX NO-GO, Fresh OOS SEALED | 100% | 외부 원천·수정주가·기업행사 custody; 키·승인 후 1~2일 |
| P2 | 모델·산출물 | 파일 존재·로드·승격과 모델 계열을 분리 | Kronos Core와 trading policy 분리, 모델 파일 검색, metadata-only 조회 | `dqn_model.zip` 직접 관측, LOADED/PROMOTED 분리, NO-GO 유지 | 100% | 경제성 gate 통과 policy 생성; G2·G3 뒤 |
| P2 | 보고서·거버넌스 | 사전등록→실행→판정→hash→사람 승인 계보 | 경량 governance ledger, SHA-256, FROZEN/DRAFT, 결과 문서 custody | 5 FROZEN, 프로젝트 보고서 1, 결과 문서 20, Fresh OOS SEALED | 100% | G2·G3 통과 후 Fresh OOS 별도 승인; 1~2시간 |
| P2 | 설정 | 통일된 표시·접근성과 안전 경계 | V6 테마, 90~125% 배율, 전역 명암, legacy 링크, read-only gate | 테마 light→dark→light 복원, alert/overflow 0 | 100% | 360~520px 실제 기기 사용자 검수; 약 1시간 |

## 4. 종가매매 강화학습 계약

| 항목 | 고정 내용 | 현재 상태 |
|---|---|---|
| 시장 | 한국 주식 일봉 기반 종가 의사결정 | 설계·UI 구현 |
| 의사결정 시각 | 거래일 D 종가 이후 feature freeze | 설계·UI 구현 |
| 체결 시각 | 미래 누수 방지를 위해 D+1 시가 체결 | `POST_CLOSE_NEXT_OPEN` 표시 |
| 연구 자금 | 6천만원 | 환경 계약 존재 |
| 포트폴리오 | 최대 10종목, 종목당 5백만원, 현금 예비 1천만원 | 환경 계약 존재 |
| 정책 후보 | DQN·CQL, rule/random/shuffle 통제군 | 학습 artifact 존재 |
| 비용 | 왕복 23bp = **0.230%** | 모든 비교의 기본 비용 |
| 보상 | 비용 반영 포트폴리오 NAV 변화와 위험 패널티 | 보정·연구 단계 |
| 승격 | validation gate → 사람 승인 → Fresh OOS 1회 → paper-forward | 아직 차단 |

`NO-GO`는 학습 코드를 더 실행하지 말라는 뜻이 아니다. 해당 결과를 운영·수익 모델로 승격하지 말라는 뜻이다. train/validation 안에서 가설·환경·보상·알고리즘을 바꾼 후 새 사전등록으로 연구를 계속할 수 있다. 다만 실패한 동일 설정을 반복하거나 Fresh OOS를 튜닝 데이터로 사용하면 강화학습이 아니라 과적합을 강화하게 된다.

## 5. 실행·성능·브라우저 증거

| 검증 | 결과 |
|---|---|
| V6 프런트 회귀 | `79 passed, 0 failed` |
| 관련 Python API/대시보드 회귀 | `26 passed` |
| Svelte 진단 | `0 errors, 0 warnings` |
| production build | 1,051 modules transformed, 성공 |
| no-excuse checker | TypeScript 7 files, Python 2 files 위반 0 |
| 공식 런타임 | `http://127.0.0.1:5070`, PID 67348, loopback only |
| 경량 첫 화면 API | 재시작 직후 병렬 1.498초, warmed 병렬 0.486초; 719/4,334/4,779 bytes |
| 실제 브라우저 8페이지 | 모든 페이지 shell·영구 URL 정상, alert 0, mojibake 0, 가로 overflow 0 |
| 그래프 | 실시간 학습 canvas 3, 평가 canvas 2 |
| 상호작용 | 테마 전환·복원, 전체 페이지 8개 열기 버튼, history back 정상 |

기존 5070 프로세스는 새 정적 bundle만 읽고 새 Flask route는 로드하지 않아 `/api/v6/summary`가 404였다. PID와 실행 경로를 확인한 뒤 동일 loopback·debug off·reloader off 설정으로 PID 361196을 67348로 교체했고 API 200과 최신 점수를 확인했다.

## 6. Git 계보와 버전 정책

| 단계 | 보존 작업 브랜치 | develop 비FF 병합 |
|---|---|---|
| 감사·계획 | `codex/v1.28.0-dev-dashboard-audit-plan` | `29be78d` |
| P0 공통 셸 | `codex/v1.28.0-dev-dashboard-foundation` | `7b93aa4` |
| P0 연구 라이브러리 | `codex/v1.28.0-dev-research-library` | `43146c2` |
| P1 학습 telemetry | `codex/v1.28.0-dev-live-training` | `27bab84` |
| P1 평가·종가 흐름 | `codex/v1.28.0-dev-evaluation-flow` | `61004b7` |
| P2 증거·거버넌스 | `codex/v1.28.0-dev-evidence-governance` | `356c7ef` |
| 최종 하드닝 | `codex/v1.28.0-dev-hardening` | `82e8b3b` |
| 최종 보고 | `codex/v1.28.0-dev-final-report` | 이 문서 커밋 후 비FF 병합 |

모든 병합된 작업 브랜치는 삭제하지 않고 이력으로 보존한다. `v1.28.0-dev`는 개발 버전으로 동결한다. 원격 push·PR, RC, `main/master` 병합, `v1.28.0` tag는 플랫폼 릴리스 gate와 사용자 승인이 있기 전에는 만들지 않는다. 버전 tag는 모델 GO나 실거래 준비를 뜻하지 않는다.

## 7. 다음 단계와 현실적 예상

| 순서 | 다음 단계 | 목적 | 시작 조건 | 예상 | 완료 gate |
|---:|---|---|---|---|---|
| 1 | G2 외부 데이터 권위 | 현재 DB를 날짜별 PIT 연구 데이터로 승격 | KRX/OpenDART 또는 동등한 원천 권위·키·사용 승인 | 외부 준비 후 1~2일 | universe, available-at, 공식 가격 identity, 기업행사 4 gate PASS |
| 2 | G3 시장 재학습 | 실제 종가매매 policy 생성 가능성 검증 | G2 PASS와 새 사전등록 FROZEN | 3~6시간/실험 묶음 | 3+ seeds, 통제군, 0.230% 비용, drawdown gate |
| 3 | G4 동일 lane 평가 | 정책이 rule/random/shuffle보다 나은지 확인 | G3 artifact 완료 | 2~4시간 | 사전등록 수치 gate 전부 PASS 또는 정직한 NO-GO |
| 4 | G7 Fresh OOS | 튜닝에 쓰지 않은 최종 일반화 검사 | G2~G4 PASS + 사람 승인 | 1~2시간 | 1회 개봉 receipt와 판정 고정 |
| 5 | paper-forward | 실제 시간 흐름에서 체결·운영 안정성 검사 | Fresh OOS GO + 별도 승인 | 최소 20 거래일 권장 | 비용·체결·drawdown·운영 장애 gate |
| 6 | 릴리스·PR·tag | 플랫폼 버전을 공식 배포 | 전체 회귀·브라우저·보안·사용자 승인 | 1~2시간 | draft PR 검토 후 `v1.28.0-rc.1`, 이후 `v1.28.0` |

가장 빠른 다음 행동은 학습 횟수를 무작정 늘리는 것이 아니라 **G2 외부 권위 4개를 닫고 같은 G3 코드를 다시 실행하는 것**이다. 이 조건이 충족되면 Kronos는 즉시 새 run과 telemetry를 기록하고 모델·평가·거버넌스 페이지에서 결과를 연결해 검토할 수 있다.
