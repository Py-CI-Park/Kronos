# Type2-D5 전체 TRAIN·23bp 비용 연구 결과

## 판정

| 항목 | 결과 |
|---|---|
| 최종 verdict | **`NO-GO · D5_FULL_TRAIN_COST_NOT_CONFIRMED`** |
| 실제 강화학습 | SB3 DQN 10개 모델 학습 완료 |
| 학습 범위 | TRAIN_ONLY 573 세션, 278,097 eligible rows, 500 symbols |
| 학습/Primary 평가 비용 | 왕복 23bp |
| Native 통과율 | 0/5 = 0% (필수 60%) |
| Shuffled 통과율 | 0/5 = 0% (필수 60%) |
| Native–Shuffled native replay 차이 | 0.985472 (필수 0.20 이상, 통과) |
| Invalid action | 전 모델 0 (통과) |
| 재사용 validation | `NOT_RUN_NO_READ` |
| Fresh OOS | `NOT_RUN_NO_READ` |
| Promotion / 수익성 주장 | 차단 |

D5는 실제 강화학습을 수행하는 데 성공했지만, 사전등록한 “정확 행동 accuracy 0.90과 reward ratio 0.90을 동시에 3/5 seed에서 재현”하는 데 실패했다. 따라서 모델 생성 성공과 연구 가설 확인 실패를 분리한다.

## 모델별 결과

| Reward | Seed | Fit accuracy | Fit reward ratio (23bp) | Native replay (23bp) | Native replay (0bp) | Invalid | 동시 gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Native | 0 | 0.712042 | 0.872779 | 0.872779 | 0.875731 | 0 | FAIL |
| Native | 1 | 0.661431 | 0.850386 | 0.850386 | 0.855519 | 0 | FAIL |
| Native | 2 | 0.727749 | 0.903753 | 0.903753 | 0.904180 | 0 | FAIL (accuracy) |
| Native | 3 | 0.734729 | 0.902424 | 0.902424 | 0.906614 | 0 | FAIL (accuracy) |
| Native | 4 | 0.739965 | 0.907233 | 0.907233 | 0.911518 | 0 | FAIL (accuracy) |
| Shuffled | 0 | 0.668412 | 0.869210 | -0.104827 | -0.066483 | 0 | FAIL |
| Shuffled | 1 | 0.689354 | 0.845359 | -0.090722 | -0.052776 | 0 | FAIL |
| Shuffled | 2 | 0.678883 | 0.867859 | -0.107310 | -0.075251 | 0 | FAIL |
| Shuffled | 3 | 0.710297 | 0.867153 | -0.122051 | -0.084028 | 0 | FAIL |
| Shuffled | 4 | 0.738220 | 0.898084 | -0.065873 | -0.031260 | 0 | FAIL |

## 평균과 해석

| Arm | 평균 fit accuracy | 평균 fit reward ratio | 평균 native 23bp | 평균 native 0bp |
|---|---:|---:|---:|---:|
| Native | 0.715183 | 0.887315 | 0.887315 | 0.890712 |
| Shuffled | 0.697033 | 0.869533 | -0.098157 | -0.061960 |

## No-trade·RULE·baseline 비교

| 비교 대상 | 값/상태 | D5와 직접 비교 가능 | 해석 |
|---|---|---|---|
| No-trade | reward 합계 0, 거래 0, 비용 0 | 예 | D5 Native는 23bp 반영 평균 reward 합계 31.319786으로 no-trade보다 높지만 TRAIN_ONLY 결과다. |
| Oracle ceiling | reward ratio 1.000 | 예 | 관측 후보의 사후 최적 행동이며 RL 모델이 아니다. D5 Native 평균은 0.887315다. |
| D4 DQN | 128세션·0bp 학습, Native reward ratio 약 0.984 | 참고만 | D5는 573세션·23bp 직접 학습이므로 규모와 비용이 달라 승격 근거로 직접 비교하지 않는다. |
| `ts_imb` 갭상승 | 장초반 RULE baseline | 아니오 | universe·시간대·체결 가정이 다른 RULE이다. D5 RL 성과로 합산하거나 RL이라고 부르지 않는다. |

No-trade보다 높은 TRAIN_ONLY reward는 수익성 주장이 아니다. 재사용 validation과 Fresh OOS가 봉인된 상태이므로 D5의 유일한 결론은 “실제 DQN 학습은 완료했지만 등록 gate는 NO-GO”다.

관찰된 실패 구조는 다음과 같다.

1. **학습이 실행되지 않은 실패가 아니다.** 10개 DQN이 각각 200,000 step을 완료했고 모델·outcome·terminal receipt가 모두 존재한다.
2. **비용 포함 reward 근사는 유의미하지만 exact-action 복원은 부족하다.** Native 평균 reward ratio는 0.887이지만 정확 행동 accuracy는 0.715다. 여러 후보 행동이 비슷한 보상을 내는 상황에서 보상은 상당 부분 회수해도 oracle과 동일한 종목을 고르는 비율은 낮았다.
3. **negative control 분리는 강하다.** Shuffled 모델은 자체 shuffled fit에서 평균 0.870 reward ratio를 보이지만 원래 Native 보상으로 replay하면 -0.098이다. 평균 Native delta 0.985는 등록 기준을 크게 넘었다.
4. **D4의 128세션 확인은 573세션·23bp 학습으로 그대로 확장되지 않았다.** 데이터 규모 확대와 비용 직접 반영 후 DQN의 고정 200,000-step/256×128 용량으로는 exact-action 기준을 만족하지 못했다.
5. **사후 기준 완화는 하지 않는다.** reward ratio만 보고 GO로 바꾸거나 accuracy 기준을 낮추면 사전등록을 위반한다.

## 증거 보관

| 증거 | 값 |
|---|---|
| Run | `type2-d5-primary-20260729-001` |
| Prereg SHA-256 | `861360b06dc1107c053bbfe887a58bbd7c7e3b225fbc40d1e8d01eeb3a07319a` |
| Episode snapshot SHA-256 | `8a1b8c5f83087ddddf14ec606c5a744ee124f2fca2ef791483f477807956ce40` |
| Artifact manifest SHA-256 | `369e6f1ee4068012c31dffb30d9a32b3eaadeb2b0f582262f75076dd1d9964af` |
| Summary SHA-256 | `487ff3cbf01ddffd4d3c5bae378caaf9d14093441f5fa7bd17c965cc99c44e7c` |
| Terminal receipt SHA-256 | `d45ffe903f0f1417340d81556f36c24573c94ed7c58376d27388b6a931d63d33` |
| 모델 / outcome | 10 / 10 |
| Primary HMAC | 존재, 비밀 키는 저장하지 않음 |
| 장기 dashboard custody | `docs/evidence/type2-d5-primary-20260729-001.custody.json` |
| 연구 실행 producer commit | `48c73d281c9ac8457b816e553eed915a8e69a0db` |
| 연구 실행 producer tree | `44824e062168d5672875e44f3d54e9a939c8a55c` |
| Review hardening commit/tree | `55ec1a95fafebbbe8bc255fafd9e866854eb866c` / `f3dc794c538179a54d068e156cd86c4553ae2c9e` |
| Base release | `fork-v1.14.0-kronos-rl-d4-algorithm-objective` |
| Research branch | `codex/rl-d5-full-train-cost-v1` |
| Release status | PR·master merge·v1.15 tag 전, governance 8점 보류 |

## 프로그램 100점 평가

| 영역 | 원점수/100 | 가중치 | 가중 점수 | 평가 근거 | 남은 조건 |
|---|---:|---:|---:|---|---|
| Platform | 98 | 30% | 29.4 | 12페이지, D5 fail-closed API, 10-unit custody, evidence UX | broker operation UI는 범위 밖 |
| RL Evidence | 92 | 30% | 27.6 | 실제 DQN 10개, 5-seed shuffle, 23bp, baseline 문맥 | D5 gate·Fresh OOS 미통과 |
| Engineering | 97 | 20% | 19.4 | held input, atomic artifacts, terminal receipt, HMAC, exact inventory | cross-process resume 자동화 |
| Governance | 92 | 10% | 9.2 | prereg 우선, 실패 공개, custody, OOS 봉인 | PR·master·annotated tag 8점 보류 |
| Live readiness | 0 | 10% | 0.0 | Fresh OOS·paper·broker·risk operation 없음 | 별도 D6/D7 이후에만 가능 |
| **전체** |  | **100%** | **85.6 → 86/100** | 연구 플랫폼은 강하지만 실거래 준비는 0점 | D5R→D6→D7 |

## 전체 12페이지 진행표

| 페이지 | 진행률 | D5 반영 상태 | 현재 성과 | 다음 액션 | 예상 시간 |
|---|---:|---|---|---|---:|
| Home | 100% | `D5_NOT_CONFIRMED_VISIBLE` | 공통 NO-GO·OOS 봉인 배너 | D5R 링크 | 30분 |
| Program Scorecard | 100% | `D5_AUDITED_86` | 영역별 100점·가중치 공개 | release 계보 반영 | PR 후 30분 |
| Discovery Lab | 100% | `D5_PRIMARY_10_OF_10` | 10모델·seed·cost·control | D5R 설계 | 2–4시간 |
| Data | 100% | `FULL_TRAIN_573_BOUND` | 573세션·278,097행 hash 동결 | D5R 입력 재사용 | 완료 |
| Experiment | 100% | `D5_PREREG_EXECUTED` | prereg-before-code 준수 | D5R prereg | 2–4시간 |
| Training | 100% | `D5_PRIMARY_10_OF_10` | 실제 DQN 2,000,000 steps | 400k/800k budget 연구 | 6–12시간 |
| Evaluation | 100% | `D5_FULL_TRAIN_COST_NOT_CONFIRMED` | accuracy/reward 실패 분리 | near-optimal regret | 2–4시간 |
| Compare | 100% | `D5_NATIVE_DELTA_0_985` | native/shuffle/no-trade/RULE 문맥 | capacity ablation | 4–8시간 |
| Report | 100% | `D5_PRIMARY_RECEIPT_CUSTODY` | SHA·10 outcomes·NO-GO 문서 | PR/tag handoff | PR 후 30분 |
| Insights | 76% | `OBSERVATION_ONLY` | 관찰 UI 유지 | 정식 입력 경계 강화 | 30–60분 |
| Other Lanes | 73% | `INELIGIBLE_FOR_RL_RANK` | RULE/인트라데이와 D5 점수 분리 | 현 상태 유지 | 30분 |
| Settings | 84% | `LOCAL_ONLY` | 읽기 전용 연구 설정 | 실행 권한 추가 보류 | 15분 |

## 검증 기록

| 검증 | 명령/범위 | 결과 |
|---|---|---|
| Python 핵심 회귀 | D5·dashboard·orderbook·RULE/gate 17개 test module | `124 passed, 2 skipped` |
| D5 hardening 회귀 | storage guard·gate·runner·dashboard | `12 passed, 1 skipped` |
| Frontend 전체 | `npm test` | `392 passed, 0 failed` |
| Svelte 정적 검사 | `npm run check` | `0 errors, 0 warnings` |
| Production build | `npm run build` | 960 modules transformed; served dist 갱신 |
| Python lint/no-excuse | Ruff + programming audit | PASS / 0 violations |
| TypeScript no-excuse | programming audit | 0 violations |

Browser 실사용 QA와 최종 5-lane 재검토는 PR 생성 전 release gate로 다시 수행한다. 빌드 산출물은 `webui/static/v2/dist/`에 source와 함께 갱신한다.

### 감사 한계

- custody JSON은 저장소에 커밋된 SHA·producer 계보를 검증하는 장기 스냅샷이며, 별도 공인 인증기관의 독립 전자서명은 아니다. Primary 실행 당시의 HMAC 비밀키는 보관하지 않았다.
- 승인된 Smoke manifest를 Primary manifest 안에 다시 내장하지 않은 점은 실행 완료 후 소급 변경하지 않는다. D5R부터 승인 receipt와 Smoke manifest SHA를 Primary prereg/receipt에 직접 결속한다.
- 실패 receipt에는 현재 예외 형식 정보가 포함될 수 있다. 로컬 연구 산출물만 대상으로 하며, D5R 실행기에서는 외부 노출용 안정 오류코드와 내부 상세를 분리한다.

## 다음 연구 제안: D5R 용량·목적 분해

D6 재사용 validation은 열지 않는다. D5가 실패했으므로 다음 연구도 TRAIN_ONLY에서 원인을 분해한다.

| 단계 | 연구 질문 | 제안 실험 | 성공 조건 | 목적 |
|---|---|---|---|---|
| D5R-1 | exact accuracy가 낮은 이유가 동률·근접 보상인가 | top-1 대비 선택 행동 regret, 5/10/25bp 이내 near-optimal accuracy 계산 | reward ratio와 exact accuracy 차이를 수치 설명 | gate 설계 진단 |
| D5R-2 | 200k step이 부족한가 | DQN 400k/800k learning curve, Native 3 seed 우선 | 사전등록한 accuracy·reward 동시 향상 | 계산 예산 검증 |
| D5R-3 | 네트워크/탐색 용량이 부족한가 | 512×256, dueling/Double-DQN 계열 또는 QR-DQN 비교 | shuffled control 분리 유지 + Native 안정성 증가 | 알고리즘 용량 검증 |
| D5R-4 | 과적합 가능성 자체를 확인할 수 있는가 | TRAIN_ONLY oracle 행동 모방 pretrain 뒤 DQN fine-tune, `HYBRID_RL`로 명시 | exact accuracy 0.90 이상 3/5 | 표현/최적화 상한 확인 |
| D6 | 재사용 validation으로 넘어가도 되는가 | D5R이 새 prereg gate 통과할 때만 별도 승인 | TRAIN_ONLY 확인 선행 | 데이터 누출 방지 |

D5R-4는 순수 RL로 부르지 않는다. 모방학습으로 초기화한 뒤 RL fine-tune한 하이브리드 연구이며, TRAIN_ONLY 과적합 가능성을 확인하는 진단이다. 실제 alpha나 수익성을 주장하려면 이후 D6와 Fresh OOS가 별도로 필요하다.
