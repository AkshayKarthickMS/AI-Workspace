"""Generalized tabular analysis tool for the Analyst agent -- works on any
staged CSV with numeric/categorical columns rather than a fixed schema
(ARCHITECTURE.md section 7; supersedes the sales-specific
PandasSalesAnalysisTool).

Beyond basic column profiling, this computes the analytics an actual
business analyst would reach for first: which segment (region, product,
channel, ...) drives the primary metric, which other numeric columns move
with it (candidate drivers), how the metric is trending period over period,
and overall margin -- all driven by column-name heuristics and dtypes so it
stays dataset-agnostic rather than hardcoding a sales schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.agents import Evidence, Finding

_MAX_PROFILED_NUMERIC_COLUMNS = 5
_MAX_PROFILED_CATEGORICAL_COLUMNS = 3
_MAX_SEGMENT_DIMENSIONS = 3
_MAX_DRIVER_CORRELATIONS = 2
_MIN_CORRELATION_TO_REPORT = 0.3
_CONCENTRATION_MIN_CATEGORIES = 5
_METRIC_KEYWORDS = (
    "revenue",
    "sales",
    "profit",
    "income",
    "amount",
    "total",
    "gmv",
    "gross",
    "value",
)
_PROFIT_KEYWORDS = ("profit", "margin", "net income")
_REVENUE_KEYWORDS = ("revenue", "sales", "income", "gmv")


class GenericTabularAnalysisTool:
    """Analyze only staged CSV files beneath the configured data root."""

    def __init__(self, allowed_root: Path) -> None:
        self.allowed_root = allowed_root.resolve()

    def analyze(self, dataset_path: str) -> tuple[list[Finding], list[Evidence], dict[str, Any]]:
        path = Path(dataset_path).resolve()
        if self.allowed_root not in path.parents and path != self.allowed_root:
            raise ValueError("Dataset path is outside the allowed data root")
        if path.suffix.lower() != ".csv":
            raise ValueError("Analyst agent accepts CSV files only")

        frame = pd.read_csv(path)
        if frame.empty:
            raise ValueError("Dataset has no rows to analyze")

        source = Evidence(
            source=str(path),
            source_type="dataset",
            locator=path.name,
            excerpt="Computed from staged tabular data.",
            metadata={"rows": int(len(frame)), "columns": int(len(frame.columns))},
        )

        row_count_statement = (
            f"The dataset contains {len(frame):,} rows across {len(frame.columns)} columns."
        )
        findings: list[Finding] = [
            Finding(
                statement=row_count_statement,
                category="fact",
                confidence=1.0,
                evidence=[_derived_evidence(source, row_count_statement)],
                metrics={"rows": int(len(frame)), "columns": int(len(frame.columns))},
            )
        ]

        numeric_columns = list(frame.select_dtypes(include="number").columns)
        categorical_columns = [
            column
            for column in frame.select_dtypes(include=["object", "category"]).columns
            if not _looks_like_date_column(frame[column])
        ]
        metric_column = _primary_metric_column(frame, numeric_columns)

        # Business-insight findings first (highest value; also what the
        # frontend's slide deck shows first) -- which segment drives the
        # primary metric, what correlates with it, how it's trending, and
        # overall margin -- before the generic per-column profiling below.
        if metric_column is not None:
            metric_series = frame[metric_column].dropna()
            if not metric_series.empty:
                findings.append(_numeric_summary_finding(metric_column, metric_series, source))

        findings.extend(
            _segment_breakdown_findings(frame, categorical_columns, metric_column, source)
        )
        findings.extend(_correlation_driver_findings(frame, numeric_columns, metric_column, source))
        findings.extend(_growth_findings(frame, metric_column, source))
        margin_finding = _margin_finding(frame, numeric_columns, metric_column, source)
        if margin_finding is not None:
            findings.append(margin_finding)

        for column in numeric_columns[:_MAX_PROFILED_NUMERIC_COLUMNS]:
            series = frame[column].dropna()
            if series.empty:
                continue
            if column != metric_column:
                findings.append(_numeric_summary_finding(column, series, source))
            outlier_finding = _outlier_finding(column, series, source)
            if outlier_finding is not None:
                findings.append(outlier_finding)

        for column in categorical_columns[:_MAX_PROFILED_CATEGORICAL_COLUMNS]:
            categorical_finding = _categorical_summary_finding(column, frame[column], source)
            if categorical_finding is not None:
                findings.append(categorical_finding)

        summary = {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "primary_metric": metric_column,
        }
        return findings, [source], summary


def _derived_evidence(source: Evidence, excerpt: str) -> Evidence:
    """An Evidence pointing at the same dataset, restating the specific
    computed value a derived finding is based on.

    Reusing one generic excerpt ("computed from staged data") across every
    finding would give a QA groundedness check nothing to actually compare —
    for a derived/computed fact, the evidence *is* the computation, so the
    excerpt should restate it rather than just cite its source.
    """

    return source.model_copy(update={"excerpt": excerpt})


def _primary_metric_column(frame: pd.DataFrame, numeric_columns: list[str]) -> str | None:
    """Picks the numeric column a business user would care about most:
    first, a name match against common monetary/volume keywords; otherwise
    the numeric column with the largest total magnitude, on the heuristic
    that a big monetary total outranks a small count/id/rate column."""

    if not numeric_columns:
        return None
    for column in numeric_columns:
        lowered = column.lower()
        if any(keyword in lowered for keyword in _METRIC_KEYWORDS):
            return column
    return max(numeric_columns, key=lambda column: float(frame[column].abs().sum()))


def _numeric_summary_finding(column: str, series: pd.Series, source: Evidence) -> Finding:
    statement = (
        f"'{column}' averages {series.mean():.2f} (range {series.min():.2f} to "
        f"{series.max():.2f})."
    )
    return Finding(
        statement=statement,
        category="fact",
        confidence=0.97,
        evidence=[_derived_evidence(source, statement)],
        metrics={
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "std": round(float(series.std() or 0.0), 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
        },
    )


def _outlier_finding(column: str, series: pd.Series, source: Evidence) -> Finding | None:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr <= 0:
        return None
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = series[(series < lower) | (series > upper)]
    if outliers.empty:
        return None
    statement = (
        f"{len(outliers)} row(s) fall outside the typical range of '{column}' (beyond "
        "1.5x the interquartile range)."
    )
    return Finding(
        statement=statement,
        category="anomaly",
        confidence=0.9,
        evidence=[_derived_evidence(source, statement)],
        metrics={
            "outlier_count": int(len(outliers)),
            "outlier_share": round(len(outliers) / len(series), 4),
        },
    )


def _categorical_summary_finding(
    column: str, series: pd.Series, source: Evidence
) -> Finding | None:
    counts = series.value_counts(dropna=True)
    if counts.empty:
        return None
    top_value = counts.index[0]
    share = counts.iloc[0] / len(series)
    statement = f"'{top_value}' is the most common value in '{column}', at {share:.1%} of rows."
    return Finding(
        statement=statement,
        category="fact",
        confidence=0.95,
        evidence=[_derived_evidence(source, statement)],
        metrics={"share": round(float(share), 4), "distinct_values": int(counts.shape[0])},
    )


def _segment_breakdown_findings(
    frame: pd.DataFrame,
    categorical_columns: list[str],
    metric_column: str | None,
    source: Evidence,
) -> list[Finding]:
    """For each of the first few categorical dimensions, which value drives
    the primary metric most -- and, when there are enough distinct values to
    make it meaningful, a Pareto-style concentration insight (what share of
    the metric the top-fifth of values account for)."""

    if metric_column is None:
        return []
    total = frame[metric_column].sum()
    if not total:
        return []

    findings: list[Finding] = []
    for column in categorical_columns[:_MAX_SEGMENT_DIMENSIONS]:
        grouped = frame.groupby(column)[metric_column].sum().sort_values(ascending=False)
        if len(grouped) < 2:
            continue

        top_name, top_value = grouped.index[0], float(grouped.iloc[0])
        top_share = top_value / total
        statement = (
            f"'{top_name}' is the top {column} by {metric_column}, contributing "
            f"{top_value:,.2f} ({top_share:.1%} of total {metric_column} across "
            f"{len(grouped)} distinct {column} values)."
        )
        findings.append(
            Finding(
                statement=statement,
                category="driver",
                confidence=0.95,
                evidence=[_derived_evidence(source, statement)],
                metrics={
                    "top_value": str(top_name),
                    "share": round(float(top_share), 4),
                    "total_segments": int(len(grouped)),
                },
            )
        )

        if len(grouped) >= _CONCENTRATION_MIN_CATEGORIES:
            top_n = max(1, round(len(grouped) * 0.2))
            top_n_share = float(grouped.iloc[:top_n].sum()) / total
            concentration_statement = (
                f"The top {top_n} of {len(grouped)} {column} values "
                f"({top_n / len(grouped):.0%} of them) account for {top_n_share:.1%} of "
                f"total {metric_column}."
            )
            findings.append(
                Finding(
                    statement=concentration_statement,
                    category="driver",
                    confidence=0.9,
                    evidence=[_derived_evidence(source, concentration_statement)],
                    metrics={
                        "top_n": int(top_n),
                        "concentration_share": round(float(top_n_share), 4),
                    },
                )
            )
    return findings


def _correlation_driver_findings(
    frame: pd.DataFrame,
    numeric_columns: list[str],
    metric_column: str | None,
    source: Evidence,
) -> list[Finding]:
    """Which other numeric columns move with the primary metric -- a cheap,
    honest stand-in for "what drives this number" that doesn't require a
    causal model, reported with its correlation strength so it reads as a
    lead worth investigating rather than a proven cause."""

    if metric_column is None:
        return []
    other_columns = [column for column in numeric_columns if column != metric_column]
    if not other_columns:
        return []

    correlations = frame[other_columns].corrwith(frame[metric_column]).dropna()
    if correlations.empty:
        return []
    ranked = correlations.reindex(correlations.abs().sort_values(ascending=False).index)

    findings: list[Finding] = []
    for column, corr in ranked.head(_MAX_DRIVER_CORRELATIONS).items():
        if abs(corr) < _MIN_CORRELATION_TO_REPORT:
            continue
        direction = "positively" if corr > 0 else "negatively"
        strength = "strongly" if abs(corr) >= 0.7 else "moderately"
        statement = (
            f"'{column}' is {strength} {direction} correlated with '{metric_column}' "
            f"(r={corr:.2f}), making it a likely driver worth investigating."
        )
        findings.append(
            Finding(
                statement=statement,
                category="driver",
                confidence=round(min(0.95, 0.5 + abs(corr) / 2), 4),
                evidence=[_derived_evidence(source, statement)],
                metrics={"correlation": round(float(corr), 4)},
            )
        )
    return findings


def _growth_findings(
    frame: pd.DataFrame, metric_column: str | None, source: Evidence
) -> list[Finding]:
    """Real period-over-period growth on the primary metric: overall change
    across the observed date range, and the latest month-over-month move --
    replaces a naive first-half/second-half split with actual monthly
    aggregation, which is what "trend" means to a business reader."""

    if metric_column is None:
        return []
    date_column = next((col for col in frame.columns if _looks_like_date_column(frame[col])), None)
    if date_column is None:
        return []

    dates = pd.to_datetime(frame[date_column], errors="coerce", format="mixed")
    valid = dates.notna()
    if valid.sum() < 2:
        return []

    periods = dates[valid].dt.to_period("M")
    monthly = frame.loc[valid, metric_column].groupby(periods).sum().sort_index()
    if len(monthly) < 2:
        return []

    findings: list[Finding] = []
    first_period, last_period = monthly.index[0], monthly.index[-1]
    first_value, last_value = float(monthly.iloc[0]), float(monthly.iloc[-1])
    if first_value:
        overall_change = (last_value - first_value) / abs(first_value)
        statement = (
            f"'{metric_column}' moved from {first_value:,.2f} in {first_period} to "
            f"{last_value:,.2f} in {last_period}, a change of {overall_change:+.1%} over "
            "the observed period."
        )
        findings.append(
            Finding(
                statement=statement,
                category="trend",
                confidence=0.85,
                evidence=[_derived_evidence(source, statement)],
                metrics={"change": round(float(overall_change), 4)},
            )
        )

    prev_value, latest_value = float(monthly.iloc[-2]), float(monthly.iloc[-1])
    if prev_value:
        latest_change = (latest_value - prev_value) / abs(prev_value)
        statement = (
            f"'{metric_column}' changed {latest_change:+.1%} month-over-month, from "
            f"{prev_value:,.2f} in {monthly.index[-2]} to {latest_value:,.2f} in "
            f"{monthly.index[-1]}."
        )
        findings.append(
            Finding(
                statement=statement,
                category="trend",
                confidence=0.8,
                evidence=[_derived_evidence(source, statement)],
                metrics={"change": round(float(latest_change), 4)},
            )
        )
    return findings


def _margin_finding(
    frame: pd.DataFrame,
    numeric_columns: list[str],
    metric_column: str | None,
    source: Evidence,
) -> Finding | None:
    """Overall margin when both a profit-like and a revenue-like numeric
    column are present -- common enough across business datasets (not just
    sales) to be worth a name-heuristic check, without assuming a fixed
    schema."""

    profit_column = next(
        (
            column
            for column in numeric_columns
            if any(keyword in column.lower() for keyword in _PROFIT_KEYWORDS)
        ),
        None,
    )
    revenue_column = (
        metric_column
        if metric_column and any(keyword in metric_column.lower() for keyword in _REVENUE_KEYWORDS)
        else next(
            (
                column
                for column in numeric_columns
                if any(keyword in column.lower() for keyword in _REVENUE_KEYWORDS)
            ),
            None,
        )
    )
    if profit_column is None or revenue_column is None or profit_column == revenue_column:
        return None

    total_revenue = float(frame[revenue_column].sum())
    total_profit = float(frame[profit_column].sum())
    if not total_revenue:
        return None

    margin = total_profit / total_revenue
    statement = (
        f"Overall {profit_column} margin is {margin:.1%} ({profit_column} of "
        f"{total_profit:,.2f} on {revenue_column} of {total_revenue:,.2f})."
    )
    return Finding(
        statement=statement,
        category="fact",
        confidence=0.95,
        evidence=[_derived_evidence(source, statement)],
        metrics={"margin": round(float(margin), 4)},
    )


def _looks_like_date_column(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if series.dtype != object:
        return False
    sample = series.dropna().head(20)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return bool(parsed.notna().mean() > 0.8)
