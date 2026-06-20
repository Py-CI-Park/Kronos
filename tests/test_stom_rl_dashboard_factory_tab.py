from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SRC = REPO_ROOT / "webui" / "v2_src" / "src"
RL_COMPONENT_DIR = DASHBOARD_SRC / "tabs" / "rlTrading"
RL_API = DASHBOARD_SRC / "lib" / "rlApi.ts"

FACTORY_CARD_FILES = [
    "FactoryStatusCard.svelte",
    "CalibrationCard.svelte",
    "EdgeLedgerCard.svelte",
    "SessionReplayCard.svelte",
]


def _card_text(name: str) -> str:
    return (RL_COMPONENT_DIR / name).read_text(encoding="utf-8")


def _factory_source_text() -> str:
    files = [RL_API]
    files.extend(RL_COMPONENT_DIR / name for name in FACTORY_CARD_FILES)
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_rl_api_exposes_read_only_factory_endpoints():
    api = RL_API.read_text(encoding="utf-8")

    for marker in [
        "/api/rl/factory/queue",
        "/api/rl/factory/lane-runs",
        "/api/rl/factory/lane/",
        "/calibration",
        "/edge-ledger",
        "factoryQueue",
        "factoryLaneRuns",
        "factoryLaneCalibration",
        "factoryLaneEdgeLedger",
        "RlFactoryQueueResponse",
        "RlFactoryCalibrationResponse",
        "RlFactoryEdgeLedgerResponse",
    ]:
        assert marker in api


def test_factory_status_card_shows_guardrail_and_verdict_evidence_copy():
    source = _card_text("FactoryStatusCard.svelte")

    assert "data-rl-factory-status-card" in source
    assert "guardrail" in source
    assert "Verdict labels are evidence, not profitability." in source
    assert "registry not found" in source.lower()
    assert "NO-GO" in source
    assert "INCONCLUSIVE" in source
    assert "GO_CANDIDATE" in source


def test_calibration_card_labels_supervised_gate_not_rl():
    source = _card_text("CalibrationCard.svelte")

    assert "data-rl-calibration-card" in source
    assert "supervised gate" in source
    assert "NOT RL" in source
    assert "lower is better" in source
    assert "skill exists only when Brier" in source
    assert "brier_constant" in source
    assert "reliability_bins" in source
    assert "ts_imb" in source


def test_edge_ledger_card_states_23bp_cost_and_no_profit_claim():
    source = _card_text("EdgeLedgerCard.svelte")

    assert "data-rl-edge-ledger-card" in source
    assert "not a profit claim" in source
    assert "23bp" in source
    assert "TAKE" in source
    assert "SKIP" in source
    assert "net_pct_23bp" in source


def test_session_replay_card_is_observation_only():
    source = _card_text("SessionReplayCard.svelte")

    assert "data-rl-session-replay-card" in source
    assert "not evidence of profitability" in source
    assert "read-only" in source
    assert "23bp" in source
    assert "session" in source
    assert "setInterval" not in source
    assert "setTimeout" not in source


def test_rl_trading_tab_mounts_all_factory_cards():
    tab = (DASHBOARD_SRC / "tabs" / "RLTradingTab.svelte").read_text(encoding="utf-8")

    for marker in [
        "import FactoryStatusCard from './rlTrading/FactoryStatusCard.svelte'",
        "import CalibrationCard from './rlTrading/CalibrationCard.svelte'",
        "import EdgeLedgerCard from './rlTrading/EdgeLedgerCard.svelte'",
        "import SessionReplayCard from './rlTrading/SessionReplayCard.svelte'",
        "<FactoryStatusCard />",
        "<CalibrationCard />",
        "<EdgeLedgerCard />",
        "<SessionReplayCard />",
    ]:
        assert marker in tab


def test_factory_sources_avoid_forbidden_chart_and_copy_patterns():
    source = _factory_source_text()

    assert "Cumulative profit curve" not in source
    assert "].filter(Boolean).join('<br/>')" not in source
    assert "RL Lab" not in source


def test_factory_cards_consume_read_only_get_apis_only():
    for name in FACTORY_CARD_FILES:
        source = _card_text(name)
        assert "rlApi." in source
        assert "POST" not in source
        assert "method:" not in source
        assert "fetch(" not in source
