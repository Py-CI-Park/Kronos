# Kronos 대시보드 UX 통일·전수검사 보고서

- 기준일: 2026-08-06 KST
- 개발선: `develop/v1.28.0-dev`
- 작업 브랜치: `codex/v1.28.0-dev-ux-unification`
- 대상: 공식 V6 8개 페이지
- 제품 경계: 읽기 전용 연구·증거 플랫폼, 실거래 및 수익성 주장 아님

## 1. 결론

설정의 글자 배율이 바뀌지 않던 직접 원인은 `v6Scale` 값을 저장만 하고 렌더링 루트에 적용하지 않았기 때문이다. V6 셸이 배율 store를 구독해 HTML 루트 글자 크기에 90%·100%·110%·125%를 적용하고, 셸을 벗어날 때 기존 값을 복원하도록 수정했다. CSS `zoom`은 사용하지 않는다.

탭 클릭 문제에서는 전체 화면을 덮는 공통 pointer 차단 요소는 발견되지 않았다. 다만 좁은 화면에서 상태 상세 팝오버가 인접 컨트롤을 덮을 수 있었고, 모바일 축소 사이드바의 터치·라벨 가독성이 낮았다. 모바일 탐색을 화면 하단 가로 탐색으로 바꾸고, 버튼 최소 높이 44px, `touch-action: manipulation`, 열린 상태 상세의 정적 배치를 적용했다.

통합 현황·연구 라이브러리·데이터·증거·모델·거버넌스에 접근 가능한 막대 시각화를 추가했다. 실시간 학습과 평가의 기존 ECharts 그래프를 포함하면 공식 V6에서 연구·성과·증거를 그래프로 확인할 수 있다. 모든 신규 그래프는 실제 API·점수표·artifact metadata만 사용하고, 접근 가능한 이름·설명·표 대체 보기를 제공한다.

## 2. 원인·조치·검증

| 문제 | 직접 원인 또는 감사 결과 | 조치 | 자동 검증 | 남은 사람 검수 |
|---|---|---|---|---|
| 설정 배율 무반응 | store 저장과 선택 상태만 있고 화면 소비자가 없음 | 셸 mount 시 root font-size 구독·적용, unmount 시 복원 | 90·100·110·125% 매핑 및 shell contract 테스트 PASS | 설정에서 네 배율을 순서대로 클릭해 육안 크기 변화 확인 |
| 일부 탭 클릭 불편 | 공통 클릭 차단 증거 없음, 모바일 터치 밀도와 라벨 축소가 큼 | 44px 버튼, 모바일 하단 가로 탐색, 활성 탭 강조 | navigation UX contract PASS | 375px·768px·1280px에서 8개 탭 왕복 클릭 |
| 상태 상세가 주변을 가릴 가능성 | `details > div`가 좁은 화면에서도 absolute·z-index 20 | 680px 이하에서는 문서 흐름의 정적 패널로 표시 | non-overlap contract PASS | 상태 상세를 연 채 다른 탭·버튼 클릭 |
| 페이지별 포맷 불일치 | 8개 페이지가 같은 root 리듬을 반복 정의 | 공통 `v6-page` 리듬과 reduced-motion 적용 | 8개 페이지 grammar contract PASS | 페이지 전환 시 간격·정렬·모션 일관성 |
| 차트 부족·연구 위치 불명확 | live/evaluation 외에는 수치가 카드·표 중심 | command/research/evidence/models/governance에 실제 데이터 막대 차트 | 접근성 이름·설명·표 fallback contract PASS | 테마 5종에서 색 대비·라벨 줄바꿈 확인 |
| 정상 API의 간헐적 false unavailable | summary가 한 번 약 13초, 클라이언트 제한 8초 | summary 요청만 20초의 유한 제한 적용 | timeout 상수·호출 contract PASS | 통합 현황 첫 로드가 느릴 때 정상 완료되는지 확인 |

## 3. 전체 페이지 진행·직접 확인표

> 아래 100%는 페이지 구현과 자동 검증 진행률이다. 강화학습의 경제적 성공, Fresh OOS, paper 또는 실거래 준비 완료를 뜻하지 않는다.

| 순서 | 페이지 | 목적 | 핵심 시각화·기능 | 구현 진행률 | 대시보드에서 반드시 클릭·확인할 곳 | 기대 결과 |
|---:|---|---|---|---:|---|---|
| 1 | 통합 현황 | 프로그램·연구·경제 모델·다음 gate 통합 | 5개 프로그램 영역 점수 차트, KPI, 8페이지 진행표 | 100% | 사이드바 `통합 현황`, 표의 각 `열기` 버튼 | 플랫폼과 경제 모델 점수가 분리되고 각 페이지로 이동 |
| 2 | 연구 라이브러리 | 98개 연구 run과 실패 이력 탐색 | 현재 필터 판정 분포, 검색·lane·상태 필터, 영구 상세 | 100% | 필터 적용, NO-GO run의 `상세 보기`, 뒤로가기 | 실패 기록이 숨지 않고 URL의 run id와 상세가 일치 |
| 3 | 실시간 학습 | 기록된 학습 telemetry 관찰 | reward·equity·drawdown·loss·exploration, 최근 행동 | 100% | 실행 선택, 자동 새로고침, 수동 새로고침 | 기록 스냅샷과 실제 변경 파일 상태가 구분됨 |
| 4 | 평가·비교 | 같은 evidence lane의 기술 비교 | 종가 의사결정 흐름, 동일 lane 비교 그래프·표 | 100% | 왼쪽 실행 변경, 오른쪽 후보, 비교 새로고침 | 다른 lane 비교가 섞이지 않고 NO-GO가 유지됨 |
| 5 | 데이터·증거 | 파일·identity·권위·OOS gate 분리 | 연구 판정 분포, 권위 matrix, 6단계 증거 흐름 | 100% | `권위와 누수 방지 gate`, 차트의 `표 데이터 보기` | KRX 외부 권위와 Fresh OOS가 차단 상태로 표시됨 |
| 6 | 모델·산출물 | 파일 존재·로드·경제 판정·승격 분리 | 선택 run 산출물 크기 지도, 모델 확장자 강조, metadata | 100% | run 검색·선택, `다시 확인`, 산출물 표 | FILE PRESENT가 성능·승격으로 오인되지 않음 |
| 7 | 보고서·거버넌스 | 사전등록·결과·hash·사람 승인 계보 | custody ledger 차트, 프로젝트 보고서·사전등록·문서 SHA | 100% | 보고서 보기, 사전등록 상태, Fresh OOS 항목 | FROZEN과 DRAFT가 분리되고 Fresh OOS는 0·SEALED |
| 8 | 설정 | 테마·배율·과거 화면·안전 경계 | 5개 V6 테마, 4개 배율, 즉시 적용 표시 | 100% | 90→100→110→125%, 테마 5종, 전역 명암 | 선택값과 실제 글자·간격이 즉시 함께 변경됨 |

## 4. 현재 점수와 강화학습 성과

| 평가축 | 현재 점수 | 이번 작업 영향 | 판정 |
|---|---:|---|---|
| 제품 구현·UX | 94/100 | 배율·모바일 탐색·시각화·접근성 계약 강화 | 자동 검증 완료, 새 변경의 사람 브라우저 검수 전까지 점수 상향 보류 |
| 전체 프로그램 성숙도 | 70/100 | 연구를 찾고 비교하는 관찰성 개선 | 제품 점수와 경제 모델 점수를 분리 유지 |
| 일봉 종가 RL 연구 gate | 78/100 | G1·G3·G4·G5·G6 근거는 유지, G2·G7·G8 미완료 | train/validation 진단은 있으나 공식 경제 모델 성공 아님 |
| 경제 모델 | 20/100 | 변경 없음 | 비용 후 승격 가능한 정책 미생성, NO-GO 유지 |
| 실거래 준비 | 0/100 | 변경 없음 | Fresh OOS·paper·broker·운영 위험 통제 미완료 |

현재 확인 가능한 실데이터는 연구 run 98개, telemetry run 21개, 사전등록 5개, 결과 문서 20개다. 연구 실행과 CQL/DQN artifact가 존재한다는 사실은 “강화학습 모델 파일 또는 학습 실험이 있다”는 뜻이지, 0.230% 왕복 비용 후 종가매매 모델이 경제적으로 성공했다는 뜻은 아니다.

## 5. 왜 다음 학습을 무작정 반복하지 않는가

NO-GO는 추가 연구 금지가 아니라 운영 승격 금지다. 현재 G2의 날짜별 PIT universe, available-at, 기업행사·수정주가 의미와 외부 원천 custody가 닫히지 않은 상태에서 같은 로컬 데이터로 반복 학습하면 validation에 더 맞춘 과적합 모델을 만들 수는 있어도, 미래 성과 증거는 강화되지 않는다.

다음 경제 연구는 아래 순서를 지켜야 한다.

| 우선순위 | 단계 | 목적 | 완료 기준 | 예상 시간 | 현재 상태 |
|---:|---|---|---|---:|---|
| P0 | 사람 브라우저 UX 승인 | 새 배율·탐색·차트의 실제 시각 품질 확인 | 375·768·1280px, 5개 테마, 4개 배율, 8개 탭 클릭 PASS | 30~45분 | 사용자 검수 필요 |
| P0 | G2 외부 데이터 권위 닫기 | 미래정보 누수 없는 날짜별 universe와 가격 의미 확정 | 원천 receipt·SHA·available-at·조정 규칙·누락 정책 동결 | 1~3일 | 외부 권위 4개 blocker |
| P1 | 동일 사전등록 train/validation 재실행 | 데이터·비용 계약을 바꾸지 않고 DQN·CQL·rule 비교 | seed별 로그·모델 SHA·비용 후 지표·중단 사유 기록 | 계산 4~12시간 | G2 후 가능 |
| P1 | 음성·shuffle·random 통제 | 학습이 실제 정보보다 우월한지 반증 | 동일 split·동일 비용에서 RL이 통제군과 rule baseline gate 통과 | 계산 4~8시간 | 재실행과 병렬 가능 |
| P1 | Fresh OOS 1회 개봉 | 튜닝하지 않은 최종 일반화 검증 | 사전등록 hash 일치·사람 승인·1회 실행·결과 봉인 | 승인 후 1~2시간 | SEALED |
| P2 | Paper forward | 실제 운영 시간·체결·결측 관찰 | 최소 20 거래일, 주문 없는 모의 ledger, 위험·오류 보고 | 4~6주 | G7 통과 후 |

## 6. 검증 증거

| 검증 | 결과 |
|---|---|
| 실패 우선 UX 계약 | 구현 전 6개 실패와 missing export 재현 |
| 프런트 전체 | `bun test src` → 447 passed, 0 failed |
| Svelte·프로젝트 TS 설정 | `npm run check` → 0 errors, 0 warnings; 현 프로젝트 `strict=false` 경계 포함 |
| 프로덕션 빌드 | 1,054 modules, build PASS |
| Python V6/API/route/dist | 71 passed |
| 실행 서버 | PID 84976, `python webui/run.py`, index 200 |
| 최신 정적 자산 | `assets/index-sZpB77ha.js` |
| 8개 직접 URL HTTP | 전부 200, 동일 최신 자산 제공, warm 31~36ms 관측 |
| 라이브 API | summary 98, telemetry 21, preregistration 5, result docs 20 |

독립 QA에서 `/api/v6/summary`가 한 번 약 13초 걸리는 변동성을 관측했다. 프런트의 summary 전용 제한을 20초로 늘려 정상 응답을 8초에 실패로 오인하는 문제는 막았지만, 응답 자체의 장기 성능 최적화는 별도 P1 과제로 남는다. `/api/v6/runs`와 `/api/v6/research-registry`의 느린 legacy 경로는 공식 8페이지의 신규 adapter 경로로 추가하지 않는다.

재현 명령과 결과:

```powershell
cd webui/v2_src
bun test src
# 447 pass, 0 fail

npm run check
# svelte-check found 0 errors and 0 warnings

npm run build
# 1,054 modules transformed, build PASS

cd ../..
py -3.11 -m pytest tests/test_v6_platform_api.py tests/test_v6_research_api.py tests/test_v6_telemetry_api.py tests/test_v6_governance_api.py tests/test_v6_governance_catalog.py tests/test_v2_route.py tests/test_v2_dist_marker.py -q
# 71 passed
```

세션 로컬 독립 QA·코드·보안 검토 원문은 `.omo/evidence/ux_qa_review/`, `.omo/evidence/kronos-dashboard-v6-ux-unification-code-review.md`, `.omo/evidence/kronos-ux-security-review-code-review.md`에 있다. `.omo`는 세션 상태이므로 릴리스 소스로 커밋하지 않으며, 위 재현 명령과 본 문서의 결과를 영구 검증 기준으로 사용한다.

## 7. 브라우저 검수 제한

이번 세션에서 Codex 인앱 브라우저가 localhost 탭 제어를 브라우저 URL 보안 정책으로 거부했다. 정책이 명시적으로 우회·다른 브라우저·raw CDP 사용을 금지하므로 자동 클릭 증거를 만들기 위해 우회하지 않았다. 따라서 HTTP·API·컴포넌트 계약·전체 테스트·빌드는 완료했지만, 새 변경의 실제 화면 클릭과 시각 확인은 사용자 검수 항목으로 남긴다.

직접 검수 시작 URL:

- `http://127.0.0.1:5070/?ui=v6&tab=command`
- `http://127.0.0.1:5070/?ui=v6&tab=research`
- `http://127.0.0.1:5070/?ui=v6&tab=live`
- `http://127.0.0.1:5070/?ui=v6&tab=evaluation`
- `http://127.0.0.1:5070/?ui=v6&tab=evidence`
- `http://127.0.0.1:5070/?ui=v6&tab=models`
- `http://127.0.0.1:5070/?ui=v6&tab=governance`
- `http://127.0.0.1:5070/?ui=v6&tab=settings`

## 8. 설계 근거

이번 변경은 새 디자인 시스템을 만들지 않고 다음 로컬 문서의 공통 원칙을 합쳤다.

- `DESIGN.md`: 기존 semantic token 재사용, 실제 데이터만 표시, 접근 가능한 차트
- `docs/kronos_dashboard_v6_unified_platform_audit_2026-08-05.md`: 중복 rail과 정보 과밀 완화
- `docs/kronos_dashboard_v6_p0_p2_development_plan_2026-08-05.md`: 8개 공식 페이지와 P0→P2 경계
- `docs/kronos_dashboard_v6_p0_p2_final_report_2026-08-05.md`: 94/70/20/0 분리 점수와 브라우저 기준선
- `docs/kronos_dashboard_p1_5_design_spec.md`: 차트 색·글꼴·상태 표현 일관성
- `docs/kronos_dashboard_v51_ux_audit_2026-07-19.md`: rail 겹침·정보 반복·인지 부하
- `docs/kronos_dashboard_v4_handoff_2026-07-14.md`: 반응형·실패 폐쇄·증거 중심 UX
- `docs/kronos_rl_dashboard_direct_review_guide_2026-08-01.md`: 사용자가 직접 확인할 근거·비용·판정 항목
