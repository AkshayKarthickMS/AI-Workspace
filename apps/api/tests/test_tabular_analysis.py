"""Unit coverage for the business-analytics findings in
``GenericTabularAnalysisTool`` (segment/driver breakdowns, correlation
drivers, period-over-period growth, and margin) -- these are what makes the
Analyst agent's output actually useful to a business reader, as opposed to
generic per-column profiling."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.tools.tabular_analysis import GenericTabularAnalysisTool


def _write_csv(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def segment_dataset(tmp_path: Path) -> str:
    # revenue = 10 * units exactly (r=1.00, a deterministic top driver);
    # cost tracks revenue loosely but not perfectly, so it can never rank
    # above units regardless of sort-tie behavior. North dominates revenue
    # (420 of 510 = 82.4%); monthly revenue is 120 -> 150 -> 240.
    content = (
        "date,region,units,revenue,cost\n"
        "2024-01-05,North,10,100,58\n"
        "2024-01-15,South,2,20,15\n"
        "2024-02-05,North,12,120,66\n"
        "2024-02-15,South,3,30,20\n"
        "2024-03-05,North,20,200,110\n"
        "2024-03-15,South,4,40,29\n"
    )
    return _write_csv(tmp_path / "segments.csv", content)


@pytest.fixture
def margin_dataset(tmp_path: Path) -> str:
    content = "revenue,profit\n100,40\n200,50\n150,45\n50,15\n"
    return _write_csv(tmp_path / "margin.csv", content)


def test_segment_breakdown_identifies_top_region(segment_dataset: str, tmp_path: Path) -> None:
    tool = GenericTabularAnalysisTool(tmp_path)
    findings, _, summary = tool.analyze(segment_dataset)

    assert summary["primary_metric"] == "revenue"
    driver_statements = [f.statement for f in findings if f.category == "driver"]
    assert any(
        "'North' is the top region by revenue" in statement and "82.4%" in statement
        for statement in driver_statements
    )


def test_correlation_driver_flags_perfectly_correlated_column(
    segment_dataset: str, tmp_path: Path
) -> None:
    tool = GenericTabularAnalysisTool(tmp_path)
    findings, _, _ = tool.analyze(segment_dataset)

    driver_statements = [f.statement for f in findings if f.category == "driver"]
    assert any(
        "'units'" in statement
        and "strongly positively correlated" in statement
        and "r=1.00" in statement
        for statement in driver_statements
    )


def test_growth_findings_report_period_over_period_change(
    segment_dataset: str, tmp_path: Path
) -> None:
    tool = GenericTabularAnalysisTool(tmp_path)
    findings, _, _ = tool.analyze(segment_dataset)

    trend_findings = [f for f in findings if f.category == "trend"]
    overall = next(f for f in trend_findings if "over the observed period" in f.statement)
    assert overall.metrics["change"] == 1.0  # 120 -> 240 total revenue

    month_over_month = next(f for f in trend_findings if "month-over-month" in f.statement)
    assert month_over_month.metrics["change"] == 0.6  # 150 -> 240


def test_margin_finding_computes_overall_margin(margin_dataset: str, tmp_path: Path) -> None:
    tool = GenericTabularAnalysisTool(tmp_path)
    findings, _, _ = tool.analyze(margin_dataset)

    margin_finding = next(f for f in findings if "margin is" in f.statement)
    assert margin_finding.metrics["margin"] == 0.3  # 150 profit / 500 revenue


def test_analyze_rejects_non_csv_files(tmp_path: Path) -> None:
    other = tmp_path / "notes.txt"
    other.write_text("not a csv", encoding="utf-8")
    tool = GenericTabularAnalysisTool(tmp_path)

    with pytest.raises(ValueError, match="CSV files only"):
        tool.analyze(str(other))
