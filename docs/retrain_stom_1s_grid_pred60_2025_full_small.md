# STOM tokenizer 재학습 runbook (2026-05-18 작성)

이전 실패 run (`stom_1s_grid_pred60_2025_full_small`) 의 OOM 원인을 commit `7742cb8` 의 안전 옵션으로 회피하면서 동일 dataset/quality 로 재학습한다.

---

## 0. 사전 점검 (모두 ☑ 후 시작)

- [x] **OOM 원인 파악**: train_tokenizer.py:196 rotary attention forward, step 4,701,000/4,701,721 (99.98%) 시점
- [x] **이전 commit 의 안전 코드 확인**: `tokenizer_save_pre_validation_checkpoint=True`, `--tokenizer-val-batch-size` CLI arg 존재
- [x] **데이터셋 무결성**: `finetune/qlib_exports/stom_1s_grid_pred60_2025/processed_datasets/{train,val,test}_data.pkl` 존재
- [x] **GPU 가용**: RTX 4080 SUPER, 16 GiB, 현재 사용 3.3 GiB (Flask 무관)
- [x] **디스크 가용**: D:\ 528 GB free (학습 산출물 약 20 GiB 예상)
- [x] **재학습 시간 인지**: 약 83시간 (3.5일) — 백그라운드 실행 필요

---

## 1. 실패한 run 디렉터리 archive

이전 실패 run 의 logs/manifest 를 보존하기 위해 이름 변경:

```powershell
cd D:\Chanil_Park\Project\Programming\Kronos\finetune\outputs
Rename-Item -Path 'stom_1s_grid_pred60_2025_full_small' -NewName 'stom_1s_grid_pred60_2025_full_small_failed_OOM_20260514'
```

이렇게 하면 동일 run-name 으로 재시작해도 충돌 없음. 실패 로그는 archive 디렉터리에 보존됨.

---

## 2. 재학습 실행 (백그라운드 권장)

### 2.1 핵심 PowerShell 명령

```powershell
cd D:\Chanil_Park\Project\Programming\Kronos

# 환경변수 — commit 7742cb8 Directive 에 따른 필수 안전 옵션
$env:KRONOS_TOKENIZER_VAL_BATCH_SIZE = "1"

# (선택) GPU OOM debug 정보
# $env:CUDA_LAUNCH_BLOCKING = "1"   # 디버그 시에만 — 학습 속도 저하

# 재학습 시작
C:\Python\64\Python3119\python.exe finetune\run_stom_1s_finetune.py `
  --horizon 60 `
  --mode full `
  --train-stage both `
  --dataset-dir finetune\qlib_exports\stom_1s_grid_pred60_2025\processed_datasets `
  --output-root finetune\outputs `
  --run-name stom_1s_grid_pred60_2025_full_small `
  --dataset-sample-mode full_sequential `
  --tokenizer-batch-size 4 `
  --tokenizer-val-batch-size 1 `
  --epochs 1 `
  --num-workers 0
```

### 2.2 백그라운드 실행 (권장 — 83시간이라 터미널 점유 불가)

```powershell
# Windows: Start-Job 으로 백그라운드 시작
$job = Start-Job -ScriptBlock {
    Set-Location 'D:\Chanil_Park\Project\Programming\Kronos'
    $env:KRONOS_TOKENIZER_VAL_BATCH_SIZE = "1"
    & 'C:\Python\64\Python3119\python.exe' 'finetune\run_stom_1s_finetune.py' `
        --horizon 60 `
        --mode full `
        --train-stage both `
        --dataset-dir 'finetune\qlib_exports\stom_1s_grid_pred60_2025\processed_datasets' `
        --output-root 'finetune\outputs' `
        --run-name 'stom_1s_grid_pred60_2025_full_small' `
        --dataset-sample-mode full_sequential `
        --tokenizer-batch-size 4 `
        --tokenizer-val-batch-size 1 `
        --epochs 1 `
        --num-workers 0
}
Write-Host "Job started — id=$($job.Id), name=$($job.Name)"
# 종료: Stop-Job -Id $job.Id; Remove-Job -Id $job.Id
```

또는 더 간단히 `nohup` 식의 별도 콘솔에서 실행 후 minimize:

```powershell
Start-Process powershell -ArgumentList '-NoExit', '-Command', @'
cd D:\Chanil_Park\Project\Programming\Kronos
$env:KRONOS_TOKENIZER_VAL_BATCH_SIZE="1"
C:\Python\64\Python3119\python.exe finetune\run_stom_1s_finetune.py --horizon 60 --mode full --train-stage both --dataset-dir finetune\qlib_exports\stom_1s_grid_pred60_2025\processed_datasets --output-root finetune\outputs --run-name stom_1s_grid_pred60_2025_full_small --dataset-sample-mode full_sequential --tokenizer-batch-size 4 --tokenizer-val-batch-size 1 --epochs 1 --num-workers 0
'@
```

---

## 3. 학습 진행 모니터링

### 3.1 웹 대시보드 (가장 편함)
- Flask 가 떠 있다면 `http://127.0.0.1:5070/` → 실시간 학습 탭이 자동으로 새 run 의 progress.json 을 폴링
- 만약 안 떠 있다면:
  ```powershell
  cd D:\Chanil_Park\Project\Programming\Kronos
  $env:KRONOS_WEBUI_PORT="5070"
  $env:KRONOS_V2_DIST="1"
  $env:KRONOS_WEBUI_OPEN_BROWSER="0"
  C:\Python\64\Python3119\python.exe webui\run.py
  ```

### 3.2 PowerShell 직접 모니터링 (대시보드 없이)

```powershell
# 학습 status 1줄 요약 (반복 호출)
Invoke-RestMethod -Uri 'http://127.0.0.1:5070/api/training/status' |
    Select-Object @{n='stage';e={$_.latest_stage.train_stage}}, `
                  @{n='status';e={$_.status}}, `
                  @{n='step';e={$_.latest_stage.step}}, `
                  @{n='pct';e={$_.latest_stage.overall_percent}}, `
                  @{n='sps';e={$_.latest_stage.samples_per_second}}

# progress.json 직접 tail (Flask 무관)
Get-Content 'finetune\outputs\stom_1s_grid_pred60_2025_full_small\logs\tokenizer.progress.json' | ConvertFrom-Json | Format-List
```

### 3.3 GPU 상태 (별도 콘솔에서)

```powershell
# 1초 간격 GPU util/VRAM/temp 표시
while ($true) {
    nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader
    Start-Sleep -Seconds 5
}
```

---

## 4. 학습 단계별 예상 일정

| 단계 | 예상 시간 | 누적 |
|---|---:|---:|
| tokenizer train loop (step 0 → 4.7M) | ~83h | 83h |
| tokenizer validation (batch=1 으로 OOM 회피) | ~2h | 85h |
| predictor train loop | ~20h | 105h |
| predictor validation | ~1h | 106h |

총 **약 4.5일** 예상.

---

## 5. OOM 재발 시 추가 안전망

이번 안전 옵션으로도 OOM 이 재발하면:

### 5.1 1차 조치: validation 비활성화 (학습은 보존)
```powershell
# 환경변수 추가 (실험적)
$env:KRONOS_TOKENIZER_SKIP_VAL = "1"   # train_tokenizer.py 가 이 변수 지원하지 않으면 무시됨
```

### 5.2 2차 조치: train batch size 축소
```powershell
# --tokenizer-batch-size 2 또는 1 로 축소 (학습 시간 2~4배 증가)
```

### 5.3 3차 조치: gradient checkpointing 활성화
finetune/train_tokenizer.py 의 model 생성 직후에 `model.gradient_checkpointing_enable()` 추가 (코드 수정 필요 — 별도 PR)

### 5.4 OOM 재발 시 산출물
이번에는 `tokenizer_save_pre_validation_checkpoint=True` 라 train loop 종료 직후 `latest_train_model` checkpoint 가 저장됨. 그 weights 는 OOM 후에도 살아남으니 `--finetuned-tokenizer-path` 로 재사용 가능.

---

## 6. 학습 시작 직전 마지막 체크

```powershell
# 1. 다른 Python 프로세스가 GPU 점유 중인지 확인
nvidia-smi

# 2. 디스크 여유 공간 (20 GiB 이상)
Get-PSDrive D

# 3. archive 완료 확인
ls D:\Chanil_Park\Project\Programming\Kronos\finetune\outputs

# 4. 안전 환경변수 확인
echo $env:KRONOS_TOKENIZER_VAL_BATCH_SIZE   # → "1" 이어야 함
```

---

## 7. 학습 종료 후 다음 단계

학습이 성공적으로 끝나면 (`/api/training/status` 가 `status=completed` + `readiness.predictor_complete=true`):

1. v2 대시보드의 **예측 워크벤치** 탭에서 새 모델로 실제 예측 검증
2. **예측 진단 (STOM)** 탭에서 새 prediction CSV 와 진단 지표 확인
3. **아티팩트 & 모델** 탭에서 checkpoint/weight 카운트 정상 표시
4. P5 Lighthouse + a11y 정식 측정 (별도 PR)

---

*작성: Claude (현 세션)*
*실패 run archive: `stom_1s_grid_pred60_2025_full_small_failed_OOM_20260514`*
*예상 완료: 2026-05-22 ~ 2026-05-23 KST (4~5일 후)*
