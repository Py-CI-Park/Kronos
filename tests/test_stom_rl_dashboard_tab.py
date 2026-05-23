from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
V2_SRC = REPO_ROOT / "webui" / "v2_src" / "src"


def test_v2_sources_register_stom_rl_lab_tab():
    """강화학습 실험실 탭이 v2 shell/사이드바/헤더에 등록되어야 한다."""

    app = (V2_SRC / "App.svelte").read_text(encoding="utf-8")
    sidebar = (V2_SRC / "layout" / "Sidebar.svelte").read_text(encoding="utf-8")
    header = (V2_SRC / "layout" / "Header.svelte").read_text(encoding="utf-8")
    tab = (V2_SRC / "tabs" / "RLLabTab.svelte").read_text(encoding="utf-8")

    assert "RLLabTab" in app
    assert "tab === 'rl-lab'" in app
    assert "rl-lab" in sidebar
    assert "강화학습 실험실" in sidebar
    assert "'rl-lab': '강화학습 실험실'" in header
    assert "data-rl-lab-tab" in tab


def test_rl_lab_tab_uses_read_only_rl_api_contracts():
    """프론트 탭은 Page 7의 /api/rl/* read-only 산출물 API를 사용해야 한다."""

    api = (V2_SRC / "lib" / "api.ts").read_text(encoding="utf-8")
    tab = (V2_SRC / "tabs" / "RLLabTab.svelte").read_text(encoding="utf-8")

    for marker in [
        "/api/rl/runs",
        "rlRuns",
        "rlRun",
        "rlTrades",
        "rlEquity",
        "rlEpisodes",
        "rlTable",
        "rlCostGate",
    ]:
        assert marker in api

    for marker in [
        "leaderboardChartOption",
        "costGateChartOption",
        "equityChartOption",
        "tradeChartOption",
        "data-rl-leaderboard-table",
        "data-rl-leaderboard-chart",
        "data-rl-cost-gate-table",
        "data-rl-trade-table",
        "Kronos 비의존",
        "성과 리더보드",
        "sb3_smoke",
        "DQN/PPO",
        "25bp cost gate",
    ]:
        assert marker in tab


def test_v2_dist_contains_rl_lab_bundle_marker_when_built():
    """빌드된 dist가 있으면 강화학습 탭 문자열/API 마커도 포함되어야 한다."""

    dist = REPO_ROOT / "webui" / "static" / "v2" / "dist"
    if not dist.is_dir():
        return

    bundle_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (dist / "assets").glob("index-*.js")
    )
    assert "강화학습 실험실" in bundle_text
    assert "data-rl-lab-tab" in bundle_text
    assert "/api/rl/runs" in bundle_text
