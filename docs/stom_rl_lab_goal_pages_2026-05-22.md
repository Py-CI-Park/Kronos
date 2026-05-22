# STOM 독립 강화학습 실험실 장기 Goal 구현 페이지

작성일: 2026-05-22 KST  
브랜치: `feature/stom-rl-lab`  
목표: **Kronos를 사용하지 않고 STOM tick/back DB 기반 독립 강화학습 대시보드와 모델 생성·사용 흐름을 완성한다.**

---

## 1. 전체 Goal

최종 목표는 다음 한 문장으로 정의한다.

> STOM tick/back DB를 read-only로 사용하여 강화학습 환경, baseline, 비용 검증, 모델 학습, 웹 대시보드, 실제 사용 가능성 평가까지 연결하고, 비용 차감 후 기존 baseline과 Kronos 300초 결과보다 나은지 검증한다.

이 목표는 단일 커밋으로 끝낼 수 없으므로, 페이지 단위로 나눠 각 페이지마다 다음을 반복한다.

1. 구현 범위 고정
2. 코드/문서 수정
3. 테스트/검증
4. 커밋
5. 진행률 업데이트

---

## 2. 장기 페이지 계획

| 페이지 | 이름 | 핵심 산출물 | 완료 기준 | 상태 |
|---:|---|---|---|---|
| 1 | 설계와 기준 고정 | `stom_independent_rl_lab_plan_2026-05-22.md` | 실측 데이터, baseline, reward horizon 문서화 | 완료 |
| 2 | DB loader / episode manifest | `stom_rl.episode_manifest` | read-only DB 검증, train/val/test episode manifest 생성 | 완료 |
| 3 | `StomTickTradingEnv` | RL 환경 skeleton | reset/step/reward/invalid action 단위 테스트 | 남음 |
| 4 | baseline runner | no-trade/random/momentum 등 | baseline report와 trade/equity artifact 생성 | 남음 |
| 5 | reward / cost gate | 5/10/15/25bp 비용 검증 | 25bp cost gate와 rolling validation | 남음 |
| 6 | 1차 RL 모델 | contextual bandit 또는 DQN | 300초 reward horizon 기준 walk-forward 평가 | 남음 |
| 7 | backend API | `/api/rl/*` | manifest/run/metric/trade/equity API smoke | 남음 |
| 8 | 웹 대시보드 | `강화학습 실험실` 탭 | build + browser smoke | 남음 |
| 9 | 통합 QA / 리뷰 | 최종 보고서 | 테스트, 코드리뷰, 확장/보류 결정 | 남음 |

---

## 3. 페이지 2: DB loader / episode manifest 상세

### 3.1 목적

페이지 2의 목적은 모델을 학습하는 것이 아니다. **이후 모든 강화학습 실험이 사용할 episode 계약을 고정**하는 것이다.

### 3.2 입력

| 입력 | 경로/값 |
|---|---|
| 원본 DB | `_database/stock_tick_back.db` |
| 기존 export report | `finetune/qlib_exports/stom_1s_grid_pred60_2025/stom_qlib_export_report.json` |
| 기존 1초봉 CSV episode | `finetune/qlib_exports/stom_1s_grid_pred60_2025/qlib_csv/*.csv` |
| 기본 기간 | 2025-01-03 ~ 2025-12-30 |
| 기본 시간 | 09:00~09:30 |
| 기본 reward horizon | 300초 |

### 3.3 출력

| 출력 | 기본 경로 |
|---|---|
| manifest JSON | `webui/rl_runs/stom_1s_2025_episode_manifest/episode_manifest.json` |
| manifest CSV | `webui/rl_runs/stom_1s_2025_episode_manifest/episode_manifest.csv` |
| summary JSON | `webui/rl_runs/stom_1s_2025_episode_manifest/episode_summary.json` |

`webui/rl_runs/`는 런타임 산출물 성격이므로, 대규모 manifest artifact는 원칙적으로 커밋 대상이 아니라 재생성 대상이다.

### 3.4 검증 기준

| 검증 | 기대값 |
|---|---|
| DB 연결 | SQLite `mode=ro` |
| query-only | `PRAGMA query_only=ON` |
| write probe | 차단되어야 함 |
| split overlap | train/val/test session overlap 0 |
| chronological split | train → val → test 시간 순서 |
| manifest count | export report의 group 수와 일치 |
| unknown split | 0 |

---

## 4. 페이지 2 실행 명령

```powershell
C:\Python\64\Python3119\python.exe -m stom_rl.episode_manifest `
  --db _database\stock_tick_back.db `
  --export-report finetune\qlib_exports\stom_1s_grid_pred60_2025\stom_qlib_export_report.json `
  --output-dir webui\rl_runs\stom_1s_2025_episode_manifest `
  --reward-horizon-seconds 300 `
  --lookback-window 300
```

행 수까지 검증하려면 시간이 더 걸릴 수 있으므로 필요할 때만 다음 옵션을 추가한다.

```powershell
--count-csv-rows
```

---

## 5. 현재 진행률

| 기준 | 완료 페이지 | 전체 페이지 | 진행률 |
|---|---:|---:|---:|
| 설계 기준 | 1 | 9 | 11.1% |
| 페이지 2 코드/검증 | 2 | 9 | 22.2% |

---

## 6. 페이지 2 완료 기록

페이지 2에서 다음을 완료했다.

| 항목 | 결과 |
|---|---|
| read-only DB 연결 | `mode=ro`, `PRAGMA query_only=ON` |
| 쓰기 probe | `attempt to write a readonly database`로 차단 |
| episode manifest | 18,750 episodes |
| symbol 수 | 1,638 |
| session 수 | 240 |
| split | train 13,256 / val 2,764 / test 2,730 |
| split overlap | 0 |
| chronological split | true |
| manifest delta | export report 대비 0 |

검증 명령:

```powershell
C:\Python\64\Python3119\python.exe -m pytest tests\test_stom_rl_episode_manifest.py tests\test_stom_qlib_pipeline.py -q
```

결과:

```text
9 passed, 1 warning
```

다음 페이지는 **페이지 3: `StomTickTradingEnv`** 이다.

페이지 2가 테스트와 커밋까지 끝나면 전체 진행률은 **22.2%**로 본다.
