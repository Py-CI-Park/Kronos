from __future__ import annotations

import hashlib
import os
from pathlib import Path, PureWindowsPath

import pytest

from webui.research_reports import (
    FALSE_LOCKS,
    MAX_REPORT_BYTES,
    ResearchReportCatalog,
    ResearchReportCatalogError,
    SCHEMA_VERSION,
)


EXPECTED_FALSE_LOCKS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _single(catalog: ResearchReportCatalog) -> dict[str, object]:
    reports = catalog.list_reports()
    assert len(reports) == 1
    return reports[0]


def test_list_and_read_report_preserve_utf8_korean_and_v51_no_claim_protocol(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    body = "# 연구 보고서\n\nD일 15:20 종가 대용값은 공식 종가가 아니다. 종목 005930은 문자열로 유지한다.\n"
    report_path = _write(root / "ledger.md", body)
    catalog = ResearchReportCatalog([root])

    item = _single(catalog)
    expected_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert item["schema_version"] == SCHEMA_VERSION
    assert item["relative_path"] == "ledger.md"
    assert item["title"] == "연구 보고서"
    assert item["content_sha256"] == expected_sha
    assert item["sha256"] == expected_sha
    assert item["byte_length"] == report_path.stat().st_size
    assert item["media_type"] == "text/markdown; charset=utf-8"
    assert item["updated_metadata"]["size_bytes"] == report_path.stat().st_size
    assert item["false_locks"] == FALSE_LOCKS == EXPECTED_FALSE_LOCKS
    assert item["no_claims"] == {
        "live_broker_order_claim": False,
        "paper_forward_claim": False,
        "paper_trading_claim": False,
        "profitability_claim": False,
        "official_close_claim": False,
        "production_readiness_claim": False,
    }
    assert item["source_protocol"] == {
        "schema_version": SCHEMA_VERSION,
        "read_only": True,
        "writes_allowed": False,
        "root_policy": "explicit_allowlist_existing_directories_only",
        "allowed_extensions": [".md", ".html"],
        "encoding": "utf-8",
        "html_policy": "escaped_pre_article_no_executable_markup",
        "causal_cutoff_kst": "15:20:00",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "symbol_policy": "preserve_six_digit_strings",
        "cost_identifier_policy": "preserve_internal_bp_identifiers",
        "claim_policy": item["no_claims"],
    }

    payload = catalog.read_report(str(item["report_id"]))
    assert payload["content"] == body
    assert payload["raw_text"] == body
    assert "연구 보고서" in str(payload["safe_html"])
    assert "005930" in str(payload["safe_html"])
    assert payload["content_sha256"] == expected_sha
    assert not hasattr(catalog, "write_report")


def test_html_source_is_served_as_escaped_non_executable_article(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    source = (
        "<html><head><title>위험 보고서</title></head><body>"
        "<h1 onclick='alert(1)'>X</h1>"
        "<script>alert(1)</script>"
        "<iframe src='https://example.invalid'></iframe>"
        "<a href='javascript:alert(1)'>bad</a>"
        "<style>body{display:none}</style>"
        "</body></html>"
    )
    _write(root / "danger.html", source)
    catalog = ResearchReportCatalog([root])

    item = _single(catalog)
    payload = catalog.read_report(str(item["report_id"]))
    safe_html = str(payload["safe_html"])
    lowered = safe_html.casefold()

    assert payload["media_type"] == "text/html; charset=utf-8"
    assert payload["title"] == "위험 보고서"
    assert safe_html.startswith('<article data-kronos-report-html="escaped-pre"><pre>')
    assert "<script" not in lowered
    assert "<iframe" not in lowered
    assert "<style" not in lowered
    assert "<h1" not in lowered
    assert "javascript:" not in lowered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in safe_html


@pytest.mark.parametrize(
    "bad_report_id",
    [
        "../ledger.md",
        "approved/../ledger.md",
        "/approved/ledger.md",
        "approved\\ledger.md",
        "C:\\approved\\ledger.md",
        "//server/share/ledger.md",
        "approved/ledger.md\x00suffix",
        "approved//ledger.md",
        "approved/con.md",
    ],
)
def test_read_report_rejects_traversal_absolute_windows_and_nul_ids(tmp_path: Path, bad_report_id: str) -> None:
    root = tmp_path / "approved"
    _write(root / "ledger.md", "# Safe\n")
    catalog = ResearchReportCatalog([root])

    assert PureWindowsPath(bad_report_id).drive or bad_report_id.startswith(("/", "..", "approved"))
    with pytest.raises(ResearchReportCatalogError) as excinfo:
        catalog.read_report(bad_report_id)
    assert excinfo.value.code == "INVALID_REPORT_ID"


def test_catalog_is_rooted_only_in_supplied_allowlist_and_ignores_spoofed_binary_and_oversize(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    outside = tmp_path / "outside"
    _write(approved / "safe.md", "# Safe\n")
    _write(approved / "safe.md.exe", "# Not a report\n")
    _write(approved / "malware.exe.md", "# Spoofed executable suffix\n")
    (approved / "binary.md").write_bytes(b"\x00\x01not text")
    (approved / "large.md").write_bytes(b"a" * (MAX_REPORT_BYTES + 1))
    _write(outside / "outside.md", "# Outside\n")

    catalog = ResearchReportCatalog([approved])
    reports = catalog.list_reports()

    assert [item["relative_path"] for item in reports] == ["safe.md"]
    assert catalog.read_report(str(reports[0]["report_id"]))["content"] == "# Safe\n"
    with pytest.raises(ResearchReportCatalogError) as excinfo:
        catalog.read_report("outside/outside.md")
    assert excinfo.value.code == "REPORT_NOT_FOUND"


def test_duplicate_roots_are_collapsed_but_windows_case_id_collisions_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    _write(root / "Only.md", "# One\n")
    catalog = ResearchReportCatalog([root, root])
    assert [item["relative_path"] for item in catalog.list_reports()] == ["Only.md"]

    case_root = tmp_path / "case-root"
    upper = _write(case_root / "Report.md", "# Upper\n")
    lower = case_root / "report.MD"
    lower.write_text("# Lower\n", encoding="utf-8")
    same_file = False
    try:
        same_file = os.path.samefile(upper, lower)
    except OSError:
        same_file = False

    if same_file:
        assert [item["relative_path"] for item in ResearchReportCatalog([case_root]).list_reports()] == ["Report.md"]
    else:
        with pytest.raises(ResearchReportCatalogError) as excinfo:
            ResearchReportCatalog([case_root]).list_reports()
        assert excinfo.value.code == "DUPLICATE_REPORT_ID"


def test_symlink_or_reparse_report_escape_is_not_cataloged(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    outside = _write(tmp_path / "outside.md", "# Outside\n")
    link = root / "linked.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    _write(root / "real.md", "# Real\n")

    reports = ResearchReportCatalog([root]).list_reports()

    assert [item["relative_path"] for item in reports] == ["real.md"]
    assert all(item["relative_path"] != "linked.md" for item in reports)


def test_symlink_or_reparse_approved_root_is_rejected(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    link_root = tmp_path / "root-link"
    try:
        link_root.symlink_to(real_root, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlink creation unavailable: {exc}")

    with pytest.raises(ResearchReportCatalogError) as excinfo:
        ResearchReportCatalog([link_root])
    assert excinfo.value.code == "UNSAFE_LINK"
