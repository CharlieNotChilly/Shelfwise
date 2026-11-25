import pandas as pd
import pytest

from data_prep import build_weekly_sales, weekly_sales


@pytest.fixture
def sale():
    return {
        "Invoice": 10001,
        "StockCode": "00123A",
        "Description": "Mug",
        "Quantity": 2,
        "InvoiceDate": pd.Timestamp("2010-01-04 10:00"),
        "Price": 3.0,
        "Customer ID": None,
        "Country": "United Kingdom",
    }


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("Invoice", "C10002"),
        ("Quantity", 0),
        ("Quantity", -1),
        ("Price", 0),
        ("Price", -1.5),
        ("StockCode", "POST"),
        ("StockCode", "C2"),
        ("StockCode", None),
        ("Description", None),
        ("Description", ""),
        ("Description", "  "),
    ],
)
def test_s21_excludes_ineligible_line(sale, column, value):
    lines = pd.DataFrame([sale, {**sale, column: value}])
    assert weekly_sales(lines).to_dict("records") == [
        {"stock_code": "00123A", "week_start": pd.Timestamp("2010-01-04"),
         "units": 2, "avg_price": 3.0}
    ]


def test_s21_monday_boundary_and_zero_filled_calendar(sale):
    lines = pd.DataFrame([
        sale,
        {**sale, "InvoiceDate": pd.Timestamp("2010-01-10 23:59"), "Quantity": 6, "Price": 5.0},
        {**sale, "InvoiceDate": pd.Timestamp("2010-01-11 00:00"), "StockCode": 234},
        {**sale, "InvoiceDate": pd.Timestamp("2010-01-25 13:00")},
    ])
    weekly = weekly_sales(lines).set_index(["stock_code", "week_start"])
    mondays = pd.date_range("2010-01-04", periods=4, freq="W-MON")
    for code, units, prices in [
        ("00123A", [8, 0, 0, 2], [4.0, 0, 0, 3.0]),
        ("234", [0, 2, 0, 0], [0, 3.0, 0, 0]),
    ]:
        product = weekly.loc[code]
        assert product.index.tolist() == mondays.tolist()
        assert product["units"].tolist() == units
        assert product["avg_price"].tolist() == prices


def test_s21_combines_both_sheets_and_writes_parquet(sale, tmp_path):
    workbook = tmp_path / "online_retail_II.xlsx"
    output = tmp_path / "processed" / "weekly_sales.parquet"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame([sale]).to_excel(writer, sheet_name="Year 2009-2010", index=False)
        second = {**sale, "Invoice": 10002, "Description": "NA", "Quantity": 4, "Price": 7.0}
        pd.DataFrame([second]).to_excel(writer, sheet_name="Year 2010-2011", index=False)

    build_weekly_sales(workbook, output)
    weekly = pd.read_parquet(output)
    assert weekly.columns.tolist() == ["stock_code", "week_start", "units", "avg_price"]
    assert list(weekly.itertuples(index=False, name=None)) == [
        ("00123A", pd.Timestamp("2010-01-04"), 6, 5.0)
    ]


def test_s21_overlap_preserves_within_sheet_multiplicity_and_distinct_lines(sale, tmp_path):
    workbook = tmp_path / "overlap.xlsx"
    output = tmp_path / "weekly.parquet"
    other = {**sale, "Country": "France"}
    distinct_customer = {**sale, "Customer ID": 42}
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame([sale, sale, other]).to_excel(writer, sheet_name="Year 2009-2010", index=False)
        pd.DataFrame([sale, other, other, distinct_customer]).to_excel(
            writer, sheet_name="Year 2010-2011", index=False
        )
    build_weekly_sales(workbook, output)
    assert pd.read_parquet(output)["units"].tolist() == [10]
