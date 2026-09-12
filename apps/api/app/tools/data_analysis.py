from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.agents import Evidence, Finding


class PandasSalesAnalysisTool:
    """Analyze only staged CSV files beneath the configured data root."""

    def __init__(self, allowed_root: Path) -> None:
        self.allowed_root = allowed_root.resolve()

    def analyze(self, dataset_path: str) -> tuple[list[Finding], list[Evidence], dict[str, Any]]:
        path = Path(dataset_path).resolve()
        if self.allowed_root not in path.parents and path != self.allowed_root:
            raise ValueError("Dataset path is outside the allowed data root")
        if path.suffix.lower() != ".csv":
            raise ValueError("Data analyst accepts CSV files only")

        frame = pd.read_csv(path, parse_dates=["date"])
        required = {
            "date",
            "region",
            "product",
            "units_sold",
            "revenue",
            "cost",
            "profit",
            "inventory_level",
        }
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
        frame["margin"] = frame["profit"] / frame["revenue"]
        source = Evidence(
            source=str(path),
            source_type="dataset",
            locator="sales_data.csv",
            excerpt="Computed from validated transaction rows.",
            metadata={"rows": int(len(frame))},
        )
        findings: list[Finding] = []

        product_summary = frame.groupby("product", as_index=False).agg(
            revenue=("revenue", "sum"), profit=("profit", "sum"), margin=("margin", "mean")
        )
        top_product = product_summary.sort_values("margin", ascending=False).iloc[0]
        findings.append(
            Finding(
                statement=f"{top_product['product']} has the highest average transaction margin in the dataset.",
                category="fact",
                confidence=0.98,
                evidence=[source],
                metrics={"average_margin": round(float(top_product["margin"]), 4)},
            )
        )

        frame["year"] = frame["date"].dt.year
        region_year = frame.groupby(["region", "year"])["revenue"].sum().unstack(fill_value=0)
        if 2024 in region_year and 2025 in region_year:
            region = (region_year[2025] / region_year[2024]).sort_values().index[0]
            change = float(region_year.loc[region, 2025] / region_year.loc[region, 2024] - 1)
            findings.append(
                Finding(
                    statement=f"{region} revenue changed by {change:.1%} from 2024 to 2025.",
                    category="trend",
                    confidence=0.96,
                    evidence=[source],
                    metrics={"revenue_change": round(change, 4)},
                )
            )

        product_year = frame.groupby(["product", "year"])["margin"].mean().unstack(fill_value=0)
        if 2023 in product_year and 2025 in product_year:
            falling = (product_year[2025] - product_year[2023]).sort_values().index[0]
            change = float(product_year.loc[falling, 2025] - product_year.loc[falling, 2023])
            findings.append(
                Finding(
                    statement=f"{falling} average margin changed by {change:.1%} between 2023 and 2025.",
                    category="risk",
                    confidence=0.95,
                    evidence=[source],
                    metrics={"margin_change": round(change, 4)},
                )
            )

        low_inventory = frame[frame["inventory_level"] <= frame["inventory_level"].quantile(0.05)]
        if not low_inventory.empty:
            findings.append(
                Finding(
                    statement="A concentrated set of transactions occurred at the low end of observed inventory levels.",
                    category="anomaly",
                    confidence=0.9,
                    evidence=[source],
                    metrics={"low_inventory_rows": int(len(low_inventory))},
                )
            )

        monthly = frame.groupby(frame["date"].dt.to_period("M"))["units_sold"].sum()
        baseline = float(monthly.median())
        peak_period = monthly.idxmax()
        peak_ratio = float(monthly.max() / baseline) if baseline else 0
        if peak_ratio > 1.5:
            findings.append(
                Finding(
                    statement=f"Units sold peaked in {peak_period} at {peak_ratio:.1f} times the typical month.",
                    category="anomaly",
                    confidence=0.94,
                    evidence=[source],
                    metrics={"peak_to_median_ratio": round(peak_ratio, 3)},
                )
            )

        summary = {
            "rows": int(len(frame)),
            "revenue": round(float(frame["revenue"].sum()), 2),
            "profit": round(float(frame["profit"].sum()), 2),
            "average_margin": round(float(frame["margin"].mean()), 4),
        }
        return findings, [source], summary
