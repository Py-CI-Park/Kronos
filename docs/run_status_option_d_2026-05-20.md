# 옵션 D 재학습 실행 상태 기록 — 2026-05-20

## 목적

STOM 1초봉 `pred60` 2025 전체 샘플을 Kronos Small 토크나이저→프리딕터 순서로 다시 학습한다. 사용자는 웹 대시보드에서 학습 진행률, GPU 상태, 로그를 직접 확인할 수 있어야 한다.

## 이번 실행에서 확인한 사실

| 시간(KST) | 항목 | 결과 |
|---|---|---|
| 2026-05-20 10:12 | 이전 실패 산출물 보관 | `finetune/outputs/stom_1s_grid_pred60_2025_full_small_failed_OOM_archive_20260520_101227` 로 이동 |
| 2026-05-20 10:12 | 웹 대시보드 재시작 | `http://127.0.0.1:5070/` HTTP 200 확인 |
| 2026-05-20 10:14 | 옵션 D 학습 1차 시작 | `tokenizer.progress.json` 생성 및 `status=running` 확인 |
| 2026-05-20 10:16 | 옵션 D 학습 1차 실패 | GPU/OOM 문제가 아니라 Windows CP949 stdout 인코딩 문제로 `UnicodeEncodeError` 발생 |
| 2026-05-20 10:20 | 대시보드 직접 경로 보완 | `http://127.0.0.1:5070/training` HTTP 200 확인 |

## 실패 원인

1차 재시작은 데이터 로딩까지 정상 진행되었다.

- 학습 샘플: `18,806,883`
- 검증 샘플: `3,925,397`
- 토크나이저 batch size: `64`
- validation batch size: `1`
- train steps/epoch: `293,858`

그러나 `train_tokenizer.py`의 진행 로그 문자열에 포함된 em dash(`—`)를 Windows CP949 stdout이 인코딩하지 못해 학습 step 0 전에 종료되었다.
따라서 이번 실패는 STOM 데이터, Qlib dataset, CUDA 연산, VRAM 부족, Kronos 모델 구조 문제가 아니다.

## 적용한 수정

1. `finetune/train_tokenizer.py`
   - AMP/torch.compile 진행 로그의 em dash를 ASCII hyphen으로 변경했다.
2. `finetune/run_stom_1s_finetune.py`
   - 자식 학습 프로세스에 `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1` 기본값을 주입해 Windows 콘솔/파이프 인코딩 실패 가능성을 낮췄다.
3. `webui/v2/__init__.py`
   - `/training`, `/dashboard` 직접 접속 경로가 v2 학습 대시보드 shell을 반환하도록 추가했다.
   - 전역 catch-all은 추가하지 않았다. API/static 오류를 숨기지 않기 위해서다.
4. `tests/test_v2_blueprint_isolation.py`
   - `/training`, `/dashboard`가 200 및 `kronos-v2-shell`을 반환하는 회귀 테스트를 추가했다.

## 검증

```powershell
C:\Python\64\Python3119\python.exe -m py_compile finetune\train_tokenizer.py finetune\run_stom_1s_finetune.py
C:\Python\64\Python3119\python.exe -m pytest tests\test_v2_blueprint_isolation.py tests\test_v2_route.py -q
```

결과: `8 passed`.

## 다음 실행 원칙

1. CP949 실패 run을 archive로 보관한다.
2. 같은 옵션 D 명령을 다시 시작한다.
3. 시작 후 5~10분 내 다음을 확인한다.
   - `/api/training/status`가 `status=running`인지
   - `step > 0`인지
   - `samples_per_second > 0`인지
   - GPU 사용률/VRAM이 증가하는지
4. 만약 batch 64에서 실제 CUDA OOM이 발생하면 이 기록과 분리하여 batch 32 또는 16 fallback을 진행한다.
