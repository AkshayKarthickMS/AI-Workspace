"""Validate the synthetic AegisOS demo sales dataset with Pandas."""

from pathlib import Path

import pandas as pd


DATA_FILE = Path("data/demo/sales_data.csv")
REQUIRED_COLUMNS = {
    "date",
    "region",
    "country",
    "product",
    "product_category",
    "customer_segment",
    "units_sold",
    "unit_price",
    "revenue",
    "cost",
    "profit",
    "sales_channel",
    "salesperson",
    "inventory_level",
}


def main() -> None:
    frame = pd.read_csv(DATA_FILE, parse_dates=["date"])
    assert len(frame) == 10_000, f"Expected 10,000 rows, found {len(frame):,}."
    assert set(frame.columns) == REQUIRED_COLUMNS, "Dataset columns do not match the contract."
    assert frame["date"].notna().all(), "Dates must parse successfully."
    assert not frame.isna().any().any(), "Synthetic dataset must not contain missing values."
    assert (frame[["units_sold", "inventory_level"]] > 0).all().all(), "Counts must be positive."
    assert (frame["inventory_level"] >= frame["units_sold"]).all(), "Inventory must cover fulfilled units."
    assert (frame["unit_price"] > 0).all(), "Unit prices must be positive."
    assert (frame[["revenue", "cost", "profit"]] >= 0).all().all(), "Financial values must be non-negative."
    assert (frame["revenue"] - frame["units_sold"] * frame["unit_price"]).abs().max() <= 0.01
    assert (frame["profit"] - (frame["revenue"] - frame["cost"])).abs().max() <= 0.01

    frame["year"] = frame["date"].dt.year
    frame["margin"] = frame["profit"] / frame["revenue"]
    europe_revenue = frame.groupby(["region", "year"])["revenue"].sum().unstack()
    assert europe_revenue.loc["Europe", 2025] < europe_revenue.loc["Europe", 2024]

    automate = frame[frame["product"] == "Aegis Automate"]
    assert automate[automate["date"] >= "2025-07-01"]["margin"].mean() > automate[
        automate["date"] < "2025-07-01"
    ]["margin"].mean()

    edge = frame[frame["product"] == "Aegis Edge"]
    assert edge[edge["year"] == 2025]["margin"].mean() < edge[edge["year"] < 2025]["margin"].mean()

    constrained = edge[
        (edge["region"] == "APAC")
        & (edge["date"] >= "2025-09-01")
        & (edge["date"] <= "2025-11-30")
    ]
    assert constrained["inventory_level"].mean() < 40

    print(
        "Validation passed: 10,000 rows, required schema, parsed dates, no missing values, "
        "financial reconciliation, positive fulfillment quantities, and expected aggregate variation."
    )


if __name__ == "__main__":
    main()
