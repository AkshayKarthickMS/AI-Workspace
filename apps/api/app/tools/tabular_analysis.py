"""Generalized tabular analysis tool for the Analyst agent -- works on any
staged CSV with numeric/categorical columns rather than a fixed schema
(ARCHITECTURE.md section 7; supersedes the sales-specific
PandasSalesAnalysisTool)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.agents import Evidence, Finding

_MAX_PROFILED_NUMERIC_COLUMNS = 5
_MAX_PROFILED_CATEGORICAL_COLUMNS = 3


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
        for column in numeric_columns[:_MAX_PROFILED_NUMERIC_COLUMNS]:
            series = frame[column].dropna()
            if series.empty:
                continue
            findings.append(_numeric_summary_finding(column, series, source))
            outlier_finding = _outlier_finding(column, series, source)
            if outlier_finding is not None:
                findings.append(outlier_finding)

        categorical_columns = [
            column
            for column in frame.select_dtypes(include=["object", "category"]).columns
            if not _looks_like_date_column(frame[column])
        ]
        for column in categorical_columns[:_MAX_PROFILED_CATEGORICAL_COLUMNS]:
            categorical_finding = _categorical_summary_finding(column, frame[column], source)
            if categorical_finding is not None:
                findings.append(categorical_finding)

        trend_finding = _trend_finding(frame, numeric_columns, source)
        if trend_finding is not None:
            findings.append(trend_finding)

        summary = {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
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


def _trend_finding(
    frame: pd.DataFrame, numeric_columns: list[str], source: Evidence
) -> Finding | None:
    date_column = next((col for col in frame.columns if _looks_like_date_column(frame[col])), None)
    if date_column is None or not numeric_columns:
        return None
    dates = pd.to_datetime(frame[date_column], errors="coerce", format="mixed")
    if dates.isna().all():
        return None
    metric_column = numeric_columns[0]
    midpoint = dates.dropna().median()
    first_half = frame.loc[dates < midpoint, metric_column].mean()
    second_half = frame.loc[dates >= midpoint, metric_column].mean()
    if pd.isna(first_half) or pd.isna(second_half) or first_half == 0:
        return None
    change = (second_half - first_half) / abs(first_half)
    statement = (
        f"'{metric_column}' changed {change:+.1%} from the first half to the second half "
        "of the observed period."
    )
    return Finding(
        statement=statement,
        category="trend",
        confidence=0.85,
        evidence=[_derived_evidence(source, statement)],
        metrics={"change": round(float(change), 4)},
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
