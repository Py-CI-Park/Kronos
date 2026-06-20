# Model Factory P1~P11 구축 결과 — 2026-06-11

## 결론

`docs/stom_model_factory_dev_pages_2026-06-11.md`의 11개 페이지를 모두 처리했다.
P6(Full-Train RL)은 사전등록 해석 경계에 따라 **착수하지 않고 차단을 기록**했다.

전체 회귀: **pytest 703 passed / 2 skipped / 0 failed (5분 7초)**,
`npm --prefix webui/v2_src run build` **0 errors** (기존 경고 4건만 유지,
DocsTab/ForecastWorkbench 기지 사항). 가드레일 위반 없음.

## 페이지별 결과

| 페이지 | 결과 | 산출물 |
|---|---|---|
| P1 Episode Store | 완료 | `stom_rl/factory/episode_store.py` — 전 universe 테이블/세션 열거, read-only 강제, parquet 캐시(소스 DB 제거 후에도 적중 검증), 선행 0 보존, 결정적 샘플링 |
| P2 Run Registry/큐 | 완료 | `stom_rl/factory/run_registry.py`, `experiment_queue.py` — 사전등록 문서 없으면 enqueue 거부, cost≠23bp 거부, 상태 전이 검증, 계보 추적 (registry: `webui/rl_runs/factory_registry.sqlite`) |
| P3 Gate 진단 | 완료 | `opening_30m_rl_candidate_training/gate.py` 확장 — `action_distribution`/entropy 수집, `DEGENERATE_POLICY` 분류(`diagnostic_label`), `sample_power` 필드. 기존 verdict 의미 불변, 기존 테스트 전부 green |
| P4 Probability Lane | **완료 — verdict `NO-GO_BASELINE`** | 아래 별도 절 |
| P5 Walk-forward | 완료 | `stom_rl/factory/walk_forward.py` — expanding-window ≥5 folds 강제(`n_folds<5` 차단), 누수 테스트, `INCONCLUSIVE` 강제, verdict 합성 |
| P6 Full-Train RL | **차단 (계획대로)** | P4 verdict `NO-GO_*` → 사전등록 경계에 따라 미착수. `STOP_RL_EXPANSION` 유지. 해제 조건: lane 계열 `GO_CANDIDATE` |
| P7 Factory API | 완료 | `webui/rl_dashboard_factory.py` + `app.py` 라우트 4종 (`/api/rl/factory/queue`, `lane-runs`, `lane/<run>/calibration`, `lane/<run>/edge-ledger`) — read-only, traversal 차단, 서버 계산 요약 필드 |
| P8 대시보드 카드 | 완료 | `CalibrationCard`, `EdgeLedgerCard`, `FactoryStatusCard` (.svelte) + `rlApi.ts` 확장 — NO-GO 배지 노출, `supervised gate (NOT RL)` 라벨, 수익성 주장 문구 금지 테스트 포함 |
| P9 Session Replay | 완료 | `SessionReplayCard.svelte` — edge ledger 기반 세션 수동 스테핑, "observation tool, not evidence of profitability" 라벨 |
| P10 사이징/리스크 | 완료 | `stom_rl/factory/sizing_lab.py` + `docs/stom_rule_sizing_risk_design_2026-06-11.md` — 아래 별도 절 |
| P11 통합 검증 | 완료 | 본 문서. 703 passed, build 0 errors, 생성물/소스 분리 확인 |

## P4 핵심 결과 (상세: `docs/stom_probability_lane_result_2026-06-11.md`)

사전등록(`docs/stom_probability_lane_prereg_2026-06-11.md`) 후 실행. full-universe
로그 27,311 후보, 951 세션, 5-fold walk-forward, split hash `cc0483b81cbb486b`,
23bp.

| Gate | 결과 |
|---|---|
| G1 표본력 (OOS TAKE ≥100) | **통과 — 12,194건** (기존 실험 2~8건 대비 ~1,500배) |
| G2 절대 수익 | 통과 (+0.627%/trade) |
| G3 무선별 baseline | 통과 (+0.627% > +0.258%, 전 5 fold 일관) |
| G4 ts_imb RULE baseline | **실패** (+0.627% < +0.820%) → 차단 |
| G5 라벨셔플 컨트롤 | 통과 (셔플 시 선별 붕괴) |
| G6 보정 skill (Brier) | 통과 (0.1929 < 0.2044, 전 fold) |
| G7 Ablation 안정성 | 통과 (5/5 feature 전부 양의 기여 — 사상 첫 정합) |

verdict는 `NO-GO_BASELINE` 그대로 기록. 학습 모델이 통계적 표본력 위에서 선별·
보정 skill을 보인 것은 이 저장소 최초이나, 수작업 ts_imb RULE을 아직 이기지
못했다. 탐색적 관찰(총합 기준 모델 +7,645.9pp vs ts_imb +3,664.2pp)은 차기
사전등록 후보로만 기록.

## P10 핵심 결과 (상세: `docs/stom_rule_sizing_risk_design_2026-06-11.md`)

ts_imb RULE full-universe 부분집합 N=5,175 (2022-03~2026-02), +0.806%/trade @23bp,
idealized fill. 권고(연구 기본값): 고정 비율 0.5 (총 2,085pp/MDD 12.3pp),
변동성 타게팅 기각(우위 없음), 동시 보유 한도 10 (p95), 일중 중단 -5%
(비용 -2.4%), 전략 중단 = 롤링 200 trade 기대값 < 0.

## 검증 명령 (실제 실행 결과)

```powershell
py -3.11 -m pytest tests -q   # 703 passed, 2 skipped, 0 failed (307.79s)
npm --prefix webui/v2_src run build   # 0 errors, 4 pre-existing warnings
py -3.11 -m stom_rl.factory.probability_lane_cli --run-id probability_lane_tp5sl1_2026_06_11
py -3.11 -m stom_rl.factory.sizing_lab --instances .omx/artifacts/gap_up_full/instances.json --output webui/rl_runs/sizing_lab/ts_imb_sizing_2026_06_11/sizing_summary.json
```

## 신규/수정 파일 인벤토리

소스(신규): `stom_rl/factory/` 7개 모듈, `webui/rl_dashboard_factory.py`,
Svelte 카드 4종, 테스트 7개 파일.
소스(수정): `opening_30m_rl_candidate_{training,gate}.py`, `webui/app.py`(라우트만),
`rlApi.ts`, `RLTradingTab.svelte`, 해당 테스트 2개.
문서(신규): prereg 1, result 3(본 문서 포함), 설계/페이지 원장 2 — 모두 dated.
생성물(gitignore 영역): `webui/rl_runs/factory_registry.sqlite`,
`webui/rl_runs/probability_lane/...`, `webui/rl_runs/sizing_lab/...`,
`.omx/artifacts/factory_episode_cache/`(캐시), dist 재빌드.
`OpeningWorkflowCard.svelte`는 사용자 작업 중이므로 무접촉.

## 다음 유효 단계

1. (사전등록 필요) edge 임계치 상향 매칭 비교 또는 ts_imb 사전 필터 + 모델 2차
   선별 stacked gate — G4 재도전.
2. (사전등록 필요) realized / sl_gap_stress fill 모드로 lane 재검.
3. RULE 트랙: P10 권고 파라미터로 read-only forward/paper 검증 설계.
4. P6은 1~2가 `GO_CANDIDATE`를 만들 때까지 차단 유지.

## 가드레일 재확인

`ts_imb`는 RULE baseline(RL 아님) · 23bp 고정 · OOS 무튜닝 · `NO-GO` 가시화 ·
대시보드 read-only(주문/학습 side effect 없음) · 수익 보장/실거래 준비 주장 없음.
