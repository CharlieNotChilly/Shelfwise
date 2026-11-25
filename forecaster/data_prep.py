"""Build the Phase 1 weekly sales table with python forecaster/data_prep.py."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"
WORKBOOK = DATA_DIR / "raw" / "online_retail_II.xlsx"
WEEKLY_SALES = DATA_DIR / "processed" / "weekly_sales.parquet"
SHEETS = ["Year 2009-2010", "Year 2010-2011"]
SOURCE_COLUMNS = [
    "Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"
]


def weekly_sales(lines: pd.DataFrame) -> pd.DataFrame:
    """Aggregate eligible invoice lines on a shared Monday calendar for all SKUs."""
    invoices = lines["Invoice"].astype("string")
    codes = lines["StockCode"].astype("string")
    descriptions = lines["Description"].astype("string").str.strip()
    keep = (
        ~invoices.str.startswith("C", na=False)
        & lines["Quantity"].gt(0)
        & lines["Price"].gt(0)
        & codes.str.match(r"[0-9]", na=False)
        & descriptions.fillna("").ne("")
    )
    sales = lines.loc[keep, ["Quantity", "InvoiceDate", "Price"]].copy()
    sales["stock_code"] = codes.loc[keep]
    sales["week_start"] = pd.to_datetime(sales["InvoiceDate"]).dt.to_period("W-SUN").dt.start_time

    totals = sales.groupby(["stock_code", "week_start"]).agg(
        units=("Quantity", "sum"),
        avg_price=("Price", "mean"),
    )
    if totals.empty:
        return totals.reset_index()

    weeks = pd.date_range(sales["week_start"].min(), sales["week_start"].max(), freq="W-MON")
    calendar = pd.MultiIndex.from_product(
        [totals.index.unique("stock_code"), weeks], names=totals.index.names
    )
    return totals.reindex(calendar, fill_value=0).reset_index()


def build_weekly_sales(workbook: Path = WORKBOOK, output: Path = WEEKLY_SALES) -> None:
    sheets = pd.read_excel(
        workbook,
        sheet_name=SHEETS,
        usecols=SOURCE_COLUMNS,
        dtype={"Invoice": "string", "StockCode": "string"},
        keep_default_na=False,
        na_values=[""],
        engine="openpyxl",
    )
    # Pair the nth identical line in one sheet with the nth in the other.
    for sheet in sheets.values():
        sheet["occurrence"] = sheet.groupby(SOURCE_COLUMNS, sort=False, dropna=False).cumcount()
    lines = pd.concat(sheets.values(), ignore_index=True).drop_duplicates()
    weekly = weekly_sales(lines)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a finished Parquet file, including on repeated runs.
    with TemporaryDirectory(dir=output.parent) as temporary:
        pending = Path(temporary) / output.name
        weekly.to_parquet(pending, engine="pyarrow", index=False)
        pending.replace(output)


if __name__ == "__main__":
    build_weekly_sales()
