# Kronos Dashboard V6 전면 재설계 계획 — 2026-07-19

> 문서 ID: `KRONOS-DASHBOARD-V6-REMODEL-PLAN-2026-07-19`
> 작성일: `2026-07-19 KST`
> 상태: `PLAN_RECORDED / IMPLEMENTATION_NOT_STARTED`
> 범위: 강화학습 workflow 중심 대시보드 전면 재설계(V6). 정보구조, 초보자 여정, 실행 staging, 비교 화면, 반응형.
> 정직성 경계: 이 문서는 계획이다. 수익성, 모델 승격, 실거래 준비, 브로커 주문, paper-forward, `GO`를 주장하지 않는다.
> 브랜치(계획 기준): `feature/dashboard-v5-learning-evidence`
> 기준 commit: `23b0edb`
> 대체 문서: 없음. 근거는 `docs/kronos_dashboard_v51_ux_audit_2026-07-19.md`.

## 목차

1. [목적](#1-목적)
2. [배경과 근거](#2-배경과-근거)
3. [설계 원칙](#3-설계-원칙)
4. [목표 정보구조](#4-목표-정보구조)
5. [실행 staging 정책](#5-실행-staging-정책)
6. [단계별 계획](#6-단계별-계획)
7. [비목표와 금지 사항](#7-비목표와-금지-사항)
8. [수용 기준](#8-수용-기준)
9. [위험과 완화](#9-위험과-완화)
10. [커밋·브랜치 경계](#10-커밋브랜치-경계)
11. [다음 실행 절차](#11-다음-실행-절차)
12. [관련 문서](#12-관련-문서)
13. [변경 히스토리](#13-변경-히스토리)

## 1. 목적

강화학습 초보자가 일봉 종가매매·기타 RL 실험을 **정의 → 실행 → 평가 → 비교 → 결정**까지
하나의 체계적 흐름으로 수행할 수 있는 대시보드로 재설계한다. 현재 V5.1은 정직한 증거 뷰어지만
workflow 제품으로는 미성숙(UX 51/100)하다.

## 2. 배경과 근거

`docs/kronos_dashboard_v51_ux_audit_2026-07-19.md`의 결론:

- 실험 정의·실행 흐름 부재(P1)
- `Training & System`이 실제 RL lifecycle과 미연결(P1)
- 효과 판단용 단일 비교 화면 부재(P1)
- 정보 과밀·반복(P1/P2)
- Daily/Intraday RL 재혼합(P1)
- 보고서·이력·artifact 분리(P2)
- Mission Control 개발자 용어 중심(P2)
- portrait/mobile에서 우측 rail이 콘텐츠를 가림(P1)

## 3. 설계 원칙

1. **Workflow-first**: 화면 순서가 연구 프로세스 순서와 일치한다.
2. **정직성 보존**: `NO-GO`/`NOT_RUN`/`BLOCKED`/six false locks/no-live/no-profit을 완화·은폐하지 않는다.
3. **점진적 실행 안전성**: 대시보드는 우선 read-only를 유지하고, 실행은 명시적 staging으로만 추가한다.
4. **초보자 layer와 Advanced layer 분리**: 기본은 평이한 언어, 원시 토큰·JSON은 disclosure.
5. **단일 run context**: 선택된 run 하나를 기준으로 monitor/evaluate가 일관된다. 비교는 별도 Matrix.
6. **반응형 우선**: mobile/portrait에서 안전 rail은 기본 닫힘 drawer, 핵심 콘텐츠 우선.
7. **V3/V4 불변**: V6는 opt-in shell이며 V3 기본과 기존 deep link를 보존한다.
8. **비용 % 우선**: 사용자 표기 `0.23%/0.46%/0.015%`, 내부 ID 병기.

## 4. 목표 정보구조

### 4.1 상위 흐름

```text
Overview → Data → Experiment → Training → Evaluation → Compare → Report
```

### 4.2 상위 내비게이션

```text
COMMAND
  Overview (RL Journey Home)

REINFORCEMENT LEARNING
  Daily Close RL
    Overview / Data / Experiment / Training / Evaluation / Compare / Report
  Intraday RL
    Opening 30m / Orderbook / Evidence
  RL Guide

KRONOS
  Kronos Research (Forecast / Diagnostics)

PLATFORM
  Training & System (RL run lifecycle + host telemetry)
  Reports & Provenance (Runs · Artifacts · Wiki 통합)

ADVANCED
  Version History / Settings
```

### 4.3 화면별 책임

- **Overview(RL Journey Home)**: 현재 단계, 가장 중요한 blocker 1개, 다음 행동 1개, 최근 run, 현재 verdict.
- **Data**: 15:20 coverage, universe, 누락 종목·날짜, PyKRX KOSPI/KOSDAQ, split, 데이터 hash.
- **Experiment**: 전략 종류, Daily/Intraday, H1/H3/H5, state/action/reward, 비용, 자본·슬롯, 알고리즘, seed/fold, 성공·실패 기준, preregistration freeze.
- **Training**: run UID, queued/running/failed/completed, episode, checkpoint, reward/loss, GPU/CPU/RAM, 중단 원인.
- **Evaluation**: validation, untouched test, 경제 NAV, MDD, turnover, trade count, invalid action, baseline delta.
- **Compare**: H1/H3/H5 × KOSPI/KOSDAQ × RL/RULE/no-trade × 0.00%/0.23%/0.46% × seed/fold Matrix. 지수 없으면 `BLOCKED_INDEX_SERIES_SOURCE` 명시.
- **Report**: 최종 verdict, 결과 보고서, artifact, source SHA-256, 관련 commit, 실패 원인, 다음 가설.

## 5. 실행 staging 정책

대시보드 read-only 계약을 한 번에 깨지 않는다. 3단계로 분리한다.

- **Stage A — Experiment Studio(read-only-safe)**: 환경값 입력, preregistration/manifest 생성,
  입력 검증, 실행 명령 미리보기, `Copy Command`. 직접 실행·broker·order 없음.
- **Stage B — Local research runner(별도 승인)**: 승인된 manifest만 로컬 queue 제출, 허용된 Python
  entrypoint만 실행, PID/log/checkpoint 추적, 중단·재시작. 브로커·주문 경로와 완전 분리.
- **Stage C — Daily Close H1 pilot(별도 승인)**: 작은 universe, H1 primary, 0.23% 비용, 다중 seed,
  validation, untouched test, KOSPI/KOSDAQ 비교. 실패해도 `NO-GO` 그대로 유지.

Stage B·C는 각각 별도 사전등록·별도 실행 승인 없이는 착수하지 않는다.

## 6. 단계별 계획

| Phase | 내용 | 실행 안전성 |
|---|---|---|
| P0 | 계획·정보구조 확정, V6 shell scaffold(opt-in), V3/V4 회귀 보호 | read-only |
| P1 | Overview(RL Journey Home) + 단계 stepper + blocker CTA | read-only |
| P2 | Daily/Intraday 분리, 화면 책임 재배치, 단일 run context | read-only |
| P3 | Compare Matrix(H1/H3/H5 × KOSPI/KOSDAQ), 지수 blocked 상태 표면화 | read-only |
| P4 | Reports & Provenance 통합(run UID 기준 report·artifact·hash·verdict) | read-only |
| P5 | 우측 rail을 기본 닫힘 drawer로, mobile/portrait 재설계, 헤더 안전 요약 | read-only |
| P6 | Experiment Studio(Stage A: manifest 생성·명령 미리보기) | read-only-safe |
| P7 | (별도 승인) Local research runner(Stage B) | 실행 staging |
| P8 | (별도 승인) Daily Close H1 pilot(Stage C) | 실행 staging |

P0–P6은 read-only 범위에서 UX를 성숙시키고, P7–P8은 별도 승인 게이트 이후에만 착수한다.

## 7. 비목표와 금지 사항

- 수익성·live-readiness·`GO`·paper-forward·broker·order 주장 금지.
- V3 기본 전환 금지(V6는 opt-in).
- 기존 route ID·deep link 파괴 금지.
- 기존 `NO-GO`/`NOT_RUN` 문서·판정 완화 금지.
- 별도 승인 전 Stage B/C 실행 기능 추가 금지.
- 감사·계획 단계에서 제품 코드 mutation 금지.

## 8. 수용 기준

- 초보자가 Overview에서 "현재 단계 / 막힌 이유 / 다음 행동"을 한 화면에서 읽는다.
- Daily Close RL이 `Data → Experiment → Training → Evaluation → Compare → Report`로 이동 가능하다.
- Compare Matrix가 H1/H3/H5와 KOSPI/KOSDAQ를 한 축에서 보여주고, 지수 없으면 `BLOCKED`를 명시한다.
- 특정 run UID에서 report·artifact·hash·verdict로 이어진다.
- mobile/portrait에서 안전 rail이 기본 닫힘이고 콘텐츠를 가리지 않는다.
- V3/V4 회귀·계약 테스트, 프론트 테스트, Svelte check 0/0, build 통과.
- 초보자 여정 점수 목표 ≥ 75/100(재감사 기준), 사용자 UX 종합 목표 ≥ 78/100.

## 9. 위험과 완화

| 위험 | 완화 |
|---|---|
| 대규모 재설계로 회귀 발생 | V6 opt-in shell, V3/V4 스냅샷 계약 테스트 유지, 단계별 커밋 |
| 실행 기능이 성급히 추가됨 | Stage A/B/C 분리, B/C는 별도 승인 게이트 |
| 정직성 후퇴 | six false locks·no-claim·NO-GO를 모든 화면 계약 테스트로 고정 |
| 지수 데이터 부재로 Compare 공백 | `BLOCKED_INDEX_SERIES_SOURCE`를 결과로 명시, PyKRX 오프라인 custody 유지 |
| 정보 과밀 재발 | 초보자 layer/Advanced disclosure 강제, 화면당 primary 1개 원칙 |

## 10. 커밋·브랜치 경계

- 계획·감사 문서는 현재 브랜치에 커밋하고 `master`에 병합한다.
- V6 구현은 별도 작업 브랜치(예: `feature/dashboard-v6-rl-workflow`)에서 Phase 단위로 커밋한다.
- Phase P0–P6은 read-only. P7–P8은 별도 사전등록·실행 승인 이후 착수.
- push/PR은 별도 승인 항목이다(본 계획은 로컬 병합·태그까지만 포함).

## 11. 다음 실행 절차

1. 본 계획과 감사 문서를 `master`에 병합하고 research-preview 태그를 남긴다.
2. `/skill:ralplan --deliberate`로 V6 P0–P2 상세 실행 계획을 합의하고 pending-approval에서 멈춘다.
3. 승인 후 `/skill:ultragoal`로 Phase 단위 실행을 추적한다.
4. P6 이후 Stage B/C는 별도 사전등록 문서와 별도 실행 승인으로만 착수한다.

## 12. 관련 문서

| 경로 | 역할 |
|---|---|
| `docs/kronos_dashboard_v51_ux_audit_2026-07-19.md` | V6 근거 감사 |
| `docs/kronos_dashboard_v51_implementation_result_2026-07-18.md` | V5.1 구현·검증 결과 |
| `docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md` | 연구 요구사항·고정값 |
| `docs/wiki/14-document-standard.md` | 문서 표준 |

## 13. 변경 히스토리

| 날짜 | 변경 | 작성자 | commit |
|---|---|---|---|
| 2026-07-19 | V5.1 UX 감사에 근거한 V6 workflow 중심 전면 재설계 계획 최초 기록. 7단계 흐름, 8 Phase, 3단계 실행 staging, read-only 우선. | GJC | `23b0edb` 기준 |
