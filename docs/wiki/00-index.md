# Kronos Wiki Index

This wiki is the current operator-facing documentation for Kronos. It is served
inside **Kronos 대시보드** from the Docs tab and loaded from `docs/wiki/` through
read-only `/api/docs/*` endpoints.

## Categories

### Basics
- [00-index](00-index.md) - this index
- [01-overview](01-overview) - project overview and route map
- [02-architecture](02-architecture) - system architecture

### STOM data
- [03-stom-1tick](03-stom-1tick) - 1-tick data usage
- [04-stom-1min](04-stom-1min) - 1-minute data usage
- [05-stom-1day](05-stom-1day) - daily data usage

### Operations
- [06-know-how](06-know-how) - operating notes
- [07-trial-and-error](07-trial-and-error) - trial/error log
- [08-setup](08-setup) - setup and run guide

### Interface
- [09-api-reference](09-api-reference) - read-only API catalog
- [10-dashboard-guide](10-dashboard-guide) - official dashboard usage guide

### Research governance
- [11-reinforcement-learning](11-reinforcement-learning) - reinforcement-learning study guide
- [12-portfolio-rl-roadmap](12-portfolio-rl-roadmap) - portfolio RL roadmap
- [13-research-ledger](13-research-ledger) - current research status and evidence index
- [14-document-standard](14-document-standard) - document taxonomy and report templates
- [15-type2-d0-primary](15-type2-d0-primary) - Type2-D0 Primary reviewed evidence summary
- [16-type2-d1-action-reward](16-type2-d1-action-reward) - Type2-D1 action/reward reviewed evidence summary

### Latest Type2-D0 evidence

- [Type2-D0 reviewed summary](15-type2-d0-primary) - 12/12 units, `PRIMARY_COMPLETE`, hypothesis `NO-GO`, custody limitations, and source paths

### Latest Type2-D1 evidence

- [Type2-D1 reviewed summary](16-type2-d1-action-reward) - 9/9 units, `D1_ACTION_REWARD_CONFIRMED` for synthetic train-only mechanics; Fresh OOS and live claims remain blocked

## 최신 구현 결과

- `docs/kronos_dashboard_v51_implementation_result_2026-07-18.md` — Kronos Dashboard V5.1 구현·릴리스 결과. `IMPLEMENTED_RESEARCH_FOUNDATION`; RL/live 결과는 `NOT_RUN / NO-GO` 유지; branch `feature/dashboard-v5-learning-evidence`; commits `9d8e2ad` through `c1e4b37`; 다음 연구 단계는 coverage/custody 확인 후 새 사전등록 기반 15:20 H1 smoke와 H3/H5 validation variant다.

## Quick start

```powershell
cd D:\Chanil_Park\Project\Programming\Kronos
$env:KRONOS_WEBUI_PORT = "8122"
$env:KRONOS_WEBUI_HOST = "127.0.0.1"
$env:KRONOS_WEBUI_OPEN_BROWSER = "0"
C:\Python\64\Python3119\python.exe webui\run.py
```

Open `http://127.0.0.1:8122/` for the official dashboard,
`http://127.0.0.1:8122/?tab=rl&ui=v5` for V5.1 RL evidence, and
`http://127.0.0.1:8122/?tab=docs&ui=v5` for Research Reports & Wiki.

Legacy `/v2*` and `/rl-lab` URLs are compatibility redirects only.

## Editing guide

- Use `NN-slug.md` filenames.
- Keep the first line as `# Title`.
- Prefer Korean operator-facing copy, with English terms where they are already
  dashboard labels.
- Do not claim live-trading readiness or profitability from dashboard evidence.
- Keep prior evidence documents immutable; add new dated results and connect them through the research ledger.
- Show user-facing transaction costs as percentages while preserving legacy API/artifact identifiers when compatibility requires them.
