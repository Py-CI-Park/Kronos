# Kronos 연구 실행 런북 (컴퓨팅-게이트 WP 사전등록) — 2026-07-10

> **역할**: 상세 구현 계획서([`kronos_rl_rebuild_implementation_plan_2026-07-10.md`](kronos_rl_rebuild_implementation_plan_2026-07-10.md))의 WP 중 **장시간 GPU 학습/대형 평가가 필요해 코드로는 완성돼도 "실행"이 별도인** 항목(R3b·R5a·R6 스윕·F14)의 **사전등록(prereg) + 실행 커맨드 + 판정 기준**. 계약 C9(사전등록)·C10(스모크→풀 스테이징) 준수.
> **원칙**: 모든 런은 연구 전용. false-lock 7종 불변. 결과가 "개선 없음/신호 없음"이어도 그것이 유효한 결과다 — 성공을 조작하지 않는다.
> **주의**: 실제 CLI 플래그는 해당 WP 코드(R5b 등)가 최종 확정하므로, 착수 시 `--help`로 확인 후 아래 파라미터를 매핑한다.

---

## RB-1 · R5a — Kronos zero-shot 귀속 실험 (결정적 실험, 최우선·값쌈)

**질문**: STOM 파인튜닝이 실패한 것인가, 애초에 1초봉 60s 지평에 신호가 없는 것인가? (현재 구분 불가 — 사전학습 원본을 같은 윈도우에서 평가한 적 없음.)

**사전등록**:
- 데이터: `finetune/qlib_exports/stom_1s_grid_pred60_2025/processed_datasets` (플래그십과 동일 681 윈도우, 36×3×50 walk-forward — `docs/stom_2025_full_small_walkforward_eval_dashboard.md` 참조)
- 비교군: (a) finetuned 플래그십 (기존 기록: dir 0.4479 / net -0.2041% / cum -19.86%), (b) **사전학습 원본** `NeoQuasar/Kronos-small` + `NeoQuasar/Kronos-Tokenizer-base`, (c) random, (d) persistence
- 결정론: WP-R5b 반영 후 — seed 고정 + `sample_count=5`
- **판정 규칙** (착수 전 고정):
  - `pretrained ≈ finetuned ≈ random` → **"신호 부재"** 우세 (재튜닝 무의미, Kronos 트랙 동결 문서화)
  - `finetuned < pretrained` → **"튜닝이 유해"** (파이프라인/토크나이저 결함 우선 조사 = R5c)
  - `finetuned > pretrained` (둘 다 게이트 실패) → **"튜닝 유효하나 지평-비용 불일치"** → F14(300s) go

**실행**:
```bash
python finetune/evaluate_stom_1s_checkpoint.py \
  --model-path NeoQuasar/Kronos-small \
  --tokenizer-path NeoQuasar/Kronos-Tokenizer-base \
  --seed 42 --sample-count 5 \
  --prefix stom_1s_pred60_2025_pretrained_zeroshot_eval \
  <36x3x50 walk-forward 플래그 동일 적용>
```
**산출**: `docs/stom_kronos_attribution_report_2026-07-<dd>.md` — finetuned/pretrained/random/persistence 4열 비교표 + 위 판정 규칙 적용 결론 + F14 go/no-go. 연구용 라벨, 수익 주장 없음.
**규모**: 681 윈도우 × 5샘플 추론. GPU 권장. 스모크: 27-윈도우 축소 먼저.

---

## RB-2 · R5c — 토크나이저 재구성 평가 (M)

**질문**: 플래그십 예측기가 소비한 `latest_train_model` 토크나이저(검증 미완료)가 STOM 1초봉을 제대로 재구성하는가?

**실행** (WP-R5c 신규 스크립트):
```bash
python finetune/evaluate_tokenizer_reconstruction.py --tokenizer-path NeoQuasar/Kronos-Tokenizer-base --data <test_data.pkl> --seed 42
python finetune/evaluate_tokenizer_reconstruction.py --tokenizer-path finetune/outputs/stom_1s_grid_pred60_2025_full_small/finetune_tokenizer/checkpoints/latest_train_model --data <test_data.pkl> --seed 42
```
**판정**: base 대비 latest_train_model의 재구성 MSE가 유의하게 나쁘면 → 예측기 결과의 상당부가 토크나이저 열화 탓 → 토크나이저 재학습(검증 포함) 선행. 비슷하면 → 토크나이저는 무죄, 신호 문제로 귀속.

---

## RB-3 · R3b — SB3 PPO 실데이터 학습 (L, 첫 "진짜 RL" 아티팩트)

**질문**: PPO가 우리 일봉 데이터에서 학습하는가? (현재 SB3는 합성 픽스처 512스텝 스모크뿐, 일봉 데이터 학습 0회.)

**사전등록**:
- 어댑터: WP-R3b 신규 `stom_rl/daily_portfolio_sb3_dataset.py` — D3 예측 런 `predictions.csv` → PortfolioEnv candidate 스키마(dates, 6자리 zero-padded codes 문자열, scores, future_return_1d). 결측 next-day는 fail-closed 제외 + 카운트.
- 시드: ≥3 (예: 7, 17, 29). 비용: 23bp. device: auto(GPU).
- 스케줄: `total_timesteps` 스모크 5,000 → 풀 ≥200,000, `EvalCallback` 10k step마다 val NAV → 기존 `RlLiveEventWriter`로 방출(phase='eval').
- **판정 규칙**: val NAV가 no-trade·momentum 베이스라인 대비 **열위면 NON_IMPROVING (유효 결과, 정직 기록)**. 우위여도 OOS 수익 주장 금지 — D5 게이트가 최종.
- MaskablePPO 트리거(invalid action rate) 발화 시 `sb3-contrib` 도입은 **별도 결정**으로 기록(자동 설치 금지).

**실행** (스모크 → 풀):
```bash
# 스모크
python -m stom_rl.portfolio_sb3_train --candidate-path <adapter_out.csv> --total-timesteps 5000 --seed 7 --device auto
# 풀 (사전등록 승인 후)
python -m stom_rl.portfolio_sb3_train --candidate-path <adapter_out.csv> --total-timesteps 200000 --seed 7 --device auto
```
**산출**: 런 디렉토리(자동으로 R2 시그니처로 대시보드·라이브 카드 노출) + `docs/stom_daily_sb3_ppo_prereg_2026-07-<dd>.md`(사전등록 원본) + 결과 요약. `device_used`가 cuda 표기 확인.
**규모**: 200k timestep GPU 학습 = 수십 분~수 시간. 반드시 스모크 선행.

---

## RB-4 · R6 — 시드×에피소드 민감도 스윕 (M)

**질문**: D4 표 Q-러너의 8ep-hold vs 12ep-loss 급반전이 노이즈인가?

**사전등록**: 그리드 seeds {7,17,29,41,53} × episodes {8,32,128}, `run_and_write_daily_rl` 재사용(R3a의 NAV·비개선 판정 포함).
**실행** (WP-R6 확장 `stom_rl/daily_scenario_batch.py`):
```bash
python -m stom_rl.daily_scenario_batch --sweep-seeds 7,17,29,41,53 --sweep-episodes 8,32,128
```
**산출**: `webui/rl_runs/daily_ohlcv_portfolio/_scenario_runs/stability_summary.json` (셀별 val+test net return·trade count·never-trade flag) + factory registry 등록(stage=smoke/full).
**판정**: 셀 간 부호/거래여부가 시드에 좌우되면 "정책은 시드 노이즈" 문서화 — 더 깊은 방법 제안의 전제.
**규모**: 15셀 × (480×에피소드) CPU. 128ep 셀이 최대 부하 — 순차 실행 권장.

---

## RB-5 · F14 — 300s 전용 재튜닝 (L, R5a·R5c 결과로만 착수)

**게이트**: RB-1(R5a) 판정이 "튜닝 유효 + 300s 엣지 유지" AND RB-2(R5c) 토크나이저 무죄일 때만.
**사전등록**: `qlib_stom_pipeline.py --horizon-seconds 300` 신규 export, budget 규모 선행, 비용 게이트 **23bp 기준**(0/23/46 그리드, C4)으로 정렬(레거시 25bp 아님).
**판정**: 300s가 결정론 평가에서도 손익분기 근접(현재 rolling net -0.0052%)을 유지·개선하는지. 아니면 Kronos 재튜닝 동결 문서화.

---

## RB-6 · R7 — Aim(self-host) + rliable 백본 (M, = 대시보드 plan P8)

**실행**:
```bash
pip install -r stom_rl/requirements-research.txt   # aim, rliable (대시보드 서버 의존성과 분리)
scripts/aim_up.bat                                  # localhost, 데이터 반출 0
KRONOS_USE_AIM=1 <학습 실행>                          # 기본 off, env flag로 opt-in
python scripts/rl_report_rliable.py --sweep <R6 stability_summary.json>   # IQM·CI·performance profile
```
**산출**: `artifacts/rl_reliability_report_2026-07-<dd>.json` + docs 요약. 전부 연구용, 수익 주장 없음.
**주의**: 기존 `stom_rl/experiment_tracking.py`(NOT WIRED MLflow 심) 대체 결정은 ADR 한 단락 기록 후 Aim으로 통일.

---

## 실행 우선순위 (컴퓨팅 예산 배분)

1. **RB-1 (R5a)** — 값싸고 결정적. Kronos 트랙의 모든 후속 결정을 가른다. **먼저.**
2. **RB-3 (R3b) 스모크** — PPO 배관이 실데이터에서 도는지 5k로 확인.
3. **RB-4 (R6) 스윕** — D4 안정성 판정.
4. **RB-2 (R5c)** — 토크나이저 무죄 여부.
5. **RB-3 풀 / RB-5 (F14)** — 앞 결과가 "가치 있음"을 가리킬 때만 대형 학습 투입.
6. **RB-6 (R7)** — 스윕 데이터가 쌓인 뒤 통계 리포트.

*각 런 착수 전 dated prereg 문서를 남기고, 스모크 아티팩트/스키마를 검증한 뒤 풀 런으로 확대한다(C10). 결과는 대시보드가 미화하지 않는다.*
