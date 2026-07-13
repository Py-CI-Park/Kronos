# STOM RL R7 신뢰도 결과 — 2026-07-12

## 판정

**SEED_NOISE_NO_GO · RESEARCH_ONLY**

이 문서는 G019의 실제 D4 안정성 스윕 중 동일 설정의 128-episode 코호트만 사용한 신뢰도 보고서다. 라이브·페이퍼·브로커·수익성·모델 준비 완료를 주장하지 않는다. 테스트 OOS가 주 결과이며 왕복 비용은 23bp다.

## 입력 계보

| 항목 | 값 |
|---|---|
| 입력 | `webui/rl_runs/daily_ohlcv_portfolio/_scenario_runs/daily_d4_stability_2026_07_12/stability_summary.json` |
| 입력 SHA-256 | `57f7568d1ea6aa681d337199307876c1943f86efe8462f892a4a150182636644` |
| 원본 실행 SHA | `c008e52c96f9792a88329bd3da0708e9b267de2c` |
| 분할 | test OOS |
| 비용 | 23bp round trip |
| episodes | 128 |
| 실제 seed | 7, 17, 29, 41, 53 |
| config cohort hash | `37be440ad21e4172b029516750e12203176c802e56f1fe3e7df8a278ddb0190f` |
| 생성 시각 | `2026-07-12T12:38:33Z` (원본 summary 기록값) |

각 실행의 `config_hash`, source hash map, artifact hash map을 검증했다. 별칭과 중복 run ID는 seed 표본으로 세지 않았고, 동일 seed의 여러 run ID도 독립 표본으로 취급하지 않는다.

## rliable 1.2.0 결과

10,000회 seed-stratified bootstrap, bootstrap seed 0을 사용했다.

| 지표 | 점 추정 | 95% CI |
|---|---:|---:|
| IQM test-OOS total net return | 0.000000 | [-0.254419, 0.000000] |
| 평균 | -0.076326 | — |
| 중앙값 | 0.000000 | — |

| total net return 임계값 | 초과 비율 | 95% CI |
|---:|---:|---:|
| -0.10 | 0.8 | [0.4, 1.0] |
| -0.05 | 0.8 | [0.4, 1.0] |
| 0.00 | 0.0 | [0.0, 0.0] |
| 0.05 | 0.0 | [0.0, 0.0] |
| 0.10 | 0.0 | [0.0, 0.0] |

양의 테스트 OOS 수익 임계값을 넘은 seed가 없고 하방 불확실성이 크므로 G019의 `SEED_NOISE_NO_GO`를 유지한다. 이 결과로 모델 승격이나 라이브 준비 상태가 바뀌지 않는다.

## 재현성과 Aim

- 보고서 생성기: `scripts/rl_report_rliable.py`
- 동일 입력·설정의 연속 두 실행은 완전한 JSON 바이트가 동일했다.
- 결과 파일 SHA-256: `d86d27489a26f07880b1b0c937bd908bcd75dd7df99e1825e5048b85653c80ca`
- deterministic payload hash: `521b0e265e70f8c71e6cfc83626b366f022af06035c8f46e32eb0b8692b4fe44`
- Aim 3.29.1은 `127.0.0.1` loopback에서 실행했고 `kronos-stom-rl-research / g021-d4-rliable-2026-07-12` run을 확인했다.
- `KRONOS_USE_AIM` 기본값은 비활성이며 Aim이 설치되지 않은 환경에서도 import와 학습 실행이 가능하다.
- Windows에는 `aimrocks` 네이티브 wheel이 없어 `scripts/aim_up.bat`가 native Aim을 먼저 확인한 뒤 WSL Ubuntu의 로컬 Aim으로 안전하게 전환한다. 외부 업로드나 외부 바인딩은 사용하지 않는다.

## 검증 증거

- `.omo/evidence/task-21-r7/rliable_report.json`
- `.omo/evidence/task-21-r7/rliable_report_repeat.json`
- `.omo/evidence/task-21-r7/aim_repo/`
- `.omo/evidence/task-21-r7/aim_ui.png`
- `.omo/evidence/task-21-r7/aim_ui_evidence.json`

롤백은 optional Aim adapter, 연구 전용 requirements, 보고서 생성기와 이 문서만 되돌리면 된다. 기본 대시보드 의존성에는 Aim을 추가하지 않았다.
