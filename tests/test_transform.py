
import sys
from pathlib import Path
from decimal import Decimal

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

import transform


@pytest.fixture
def sample_datasets(monkeypatch):
    orders = [
        {
            "order_id": "ORD0000001",
            "customer_id": "CUST000001",
            "order_timestamp": "2024-06-15T10:30:00+00:00",
            "order_status": "paid",
            "shipping_country": "India"
        }
    ]

    products = [
        {
            "product_id": "PROD00001",
            "category": "Electronics"
        }
    ]

    order_items = [
        {
            "order_item_id": "ITEM00000001",
            "order_id": "ORD0000001",
            "product_id": "PROD00001",
            "quantity": "2",
            "unit_price": "1000.00",
            "discount_amount": "100.00"
        }
    ]

    monkeypatch.setattr(
        transform,
        "load_datasets",
        lambda: (
            order_items,
            {row["order_id"]: row for row in orders},
            {row["product_id"]: row for row in products}
        )
    )

    return orders, products, order_items


@pytest.fixture
def fixed_run_metadata():
    return {
        "run_id": "test_run_001",
        "ingested_at": "2026-10-31T10:00:00+00:00"
    }



# --------------------------------------------------
# Financial Calculation Tests
# --------------------------------------------------

def test_gross_amount_calculation(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert Decimal(rows[0]["gross_amount"]) == Decimal("2000.00")


def test_net_revenue_calculation(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert Decimal(rows[0]["net_revenue"]) == Decimal("1900.00")


def test_recognized_revenue_for_paid_order(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert Decimal(rows[0]["recognized_revenue"]) == Decimal("1900.00")


def test_recognized_revenue_for_cancelled_order(
    sample_datasets,
    fixed_run_metadata
):
    sample_datasets[0][0]["order_status"] = "cancelled"

    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert Decimal(rows[0]["recognized_revenue"]) == Decimal("0.00")


def test_recognized_revenue_for_pending_order(
    sample_datasets,
    fixed_run_metadata
):
    sample_datasets[0][0]["order_status"] = "pending"

    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert Decimal(rows[0]["recognized_revenue"]) == Decimal("0.00")


def test_recognized_revenue_for_shipped_order(
    sample_datasets,
    fixed_run_metadata
):
    sample_datasets[0][0]["order_status"] = "shipped"

    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert Decimal(rows[0]["recognized_revenue"]) == Decimal("1900.00")


def test_recognized_revenue_for_delivered_order(
    sample_datasets,
    fixed_run_metadata
):
    sample_datasets[0][0]["order_status"] = "delivered"

    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert Decimal(rows[0]["recognized_revenue"]) == Decimal("1900.00")


# --------------------------------------------------
# Join And Data Integrity Tests
# --------------------------------------------------

def test_order_customer_and_shipping_details_are_joined(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert rows[0]["order_id"] == "ORD0000001"
    assert rows[0]["customer_id"] == "CUST000001"
    assert rows[0]["shipping_country"] == "India"


def test_product_category_is_joined(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert rows[0]["product_id"] == "PROD00001"
    assert rows[0]["product_category"] == "Electronics"


def test_order_timestamp_and_date_are_transformed(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert rows[0]["order_timestamp"] == "2024-06-15T10:30:00+00:00"
    assert rows[0]["order_date"] == "2024-06-15"


# --------------------------------------------------
# Foreign-Key Integrity Tests
# --------------------------------------------------

def test_missing_order_reference_raises_error(
    sample_datasets,
    fixed_run_metadata
):
    sample_datasets[2][0]["order_id"] = "ORD9999999"

    with pytest.raises(
        ValueError,
        match="Missing order reference"
    ):
        transform.build_fact_order_items(
            fixed_run_metadata
        )


def test_missing_product_reference_raises_error(
    sample_datasets,
    fixed_run_metadata
):
    sample_datasets[2][0]["product_id"] = "PROD99999"

    with pytest.raises(
        ValueError,
        match="Missing product reference"
    ):
        transform.build_fact_order_items(
            fixed_run_metadata
        )


# --------------------------------------------------
# Run Metadata Tests
# --------------------------------------------------

def test_run_id_is_consistent_across_all_records(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert all(
        row["run_id"] == "test_run_001"
        for row in rows
    )


def test_ingestion_timestamp_is_consistent_across_all_records(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert all(
        row["ingested_at"] == "2026-10-31T10:00:00+00:00"
        for row in rows
    )


def test_source_file_is_recorded_correctly(
    sample_datasets,
    fixed_run_metadata
):
    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    assert all(
        row["source_file"] == "order_items.csv"
        for row in rows
    )


# --------------------------------------------------
# Output Schema And Empty Dataset Tests
# --------------------------------------------------

def test_fact_columns_contains_exactly_18_columns():
    assert len(transform.FACT_COLUMNS) == 18

    assert transform.FACT_COLUMNS == [
        "order_item_id",
        "order_id",
        "order_timestamp",
        "order_date",
        "customer_id",
        "product_id",
        "product_category",
        "shipping_country",
        "quantity",
        "unit_price",
        "gross_amount",
        "discount_amount",
        "net_revenue",
        "order_status",
        "recognized_revenue",
        "run_id",
        "source_file",
        "ingested_at"
    ]


def test_empty_fact_dataset_is_written_with_header(
    tmp_path,
    monkeypatch
):
    monkeypatch.setattr(transform, "OUTPUT_DIR", tmp_path)

    transform.write_fact_csv([])

    output_path = tmp_path / "fact_order_items.csv"

    assert output_path.exists()

    import csv

    with output_path.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        reader = csv.reader(file)
        header = next(reader)

    assert header == transform.FACT_COLUMNS


def test_fact_writer_preserves_column_order(
    tmp_path,
    monkeypatch,
    sample_datasets,
    fixed_run_metadata
):
    monkeypatch.setattr(transform, "OUTPUT_DIR", tmp_path)

    rows = transform.build_fact_order_items(
        fixed_run_metadata
    )

    transform.write_fact_csv(rows)

    output_path = tmp_path / "fact_order_items.csv"

    import csv

    with output_path.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        reader = csv.reader(file)
        header = next(reader)

    assert header == transform.FACT_COLUMNS