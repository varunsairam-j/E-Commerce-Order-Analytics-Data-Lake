import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from pipeline import (
    validate_customers,
    validate_products,
    validate_orders,
    validate_order_items,
    SCHEMAS
)


def make_customer(**overrides):
    record = {
        "customer_id": "CUST000001",
        "customer_name": "Test Customer",
        "email": "test@example.com",
        "signup_date": "2024-01-01",
        "country": "India"
    }

    record.update(overrides)
    return record


def make_product(**overrides):
    record = {
        "product_id": "PROD00001",
        "product_name": "Test Product",
        "category": "Electronics",
        "unit_cost": "500.00",
        "list_price": "1000.00"
    }

    record.update(overrides)
    return record


def make_order(**overrides):
    record = {
        "order_id": "ORD0000001",
        "customer_id": "CUST000001",
        "order_timestamp": "2024-06-15T10:30:00+00:00",
        "order_status": "paid",
        "shipping_country": "India"
    }

    record.update(overrides)
    return record


def make_order_item(**overrides):
    record = {
        "order_item_id": "ITEM00000001",
        "order_id": "ORD0000001",
        "product_id": "PROD00001",
        "quantity": "2",
        "unit_price": "1000.00",
        "discount_amount": "100.00"
    }

    record.update(overrides)
    return record


# --------------------------------------------------
# Customer Validation Tests
# --------------------------------------------------

def test_valid_customer_is_accepted():
    accepted, rejected = validate_customers([
        make_customer()
    ])

    assert len(accepted) == 1
    assert len(rejected) == 0


def test_customer_with_missing_id_is_rejected():
    accepted, rejected = validate_customers([
        make_customer(customer_id="")
    ])

    assert len(accepted) == 0
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "Missing customer_id"


def test_customer_with_missing_name_is_rejected():
    accepted, rejected = validate_customers([
        make_customer(customer_name="")
    ])

    assert len(accepted) == 0
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "Missing customer_name"


def test_customer_with_missing_email_is_rejected():
    accepted, rejected = validate_customers([
        make_customer(email="")
    ])

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_customer_with_malformed_signup_date_is_rejected():
    accepted, rejected = validate_customers([
        make_customer(signup_date="not-a-date")
    ])

    assert len(accepted) == 0
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "Invalid signup_date"


def test_duplicate_customer_id_is_rejected():
    accepted, rejected = validate_customers([
        make_customer(),
        make_customer(email="another@example.com")
    ])

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "Duplicate customer_id"


def test_duplicate_customer_email_is_rejected():
    accepted, rejected = validate_customers([
        make_customer(),
        make_customer(customer_id="CUST000002")
    ])

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "Duplicate email"


def test_empty_customer_input_returns_empty_results():
    accepted, rejected = validate_customers([])

    assert accepted == []
    assert rejected == []


# --------------------------------------------------
# Product Validation Tests
# --------------------------------------------------

def test_valid_product_is_accepted():
    accepted, rejected = validate_products([
        make_product()
    ])

    assert len(accepted) == 1
    assert len(rejected) == 0


def test_product_with_missing_id_is_rejected():
    accepted, rejected = validate_products([
        make_product(product_id="")
    ])

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Missing product_id"


def test_product_with_missing_name_is_rejected():
    accepted, rejected = validate_products([
        make_product(product_name="")
    ])

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Missing product_name"


def test_product_with_invalid_category_is_rejected():
    accepted, rejected = validate_products([
        make_product(category="Unknown Category")
    ])

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Invalid product category"


def test_product_with_invalid_price_is_rejected():
    accepted, rejected = validate_products([
        make_product(unit_cost="invalid")
    ])

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Invalid product price"


def test_product_with_negative_cost_is_rejected():
    accepted, rejected = validate_products([
        make_product(unit_cost="-10.00")
    ])

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Negative cost or non-positive list price"


def test_product_with_zero_list_price_is_rejected():
    accepted, rejected = validate_products([
        make_product(list_price="0.00")
    ])

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Negative cost or non-positive list price"


def test_product_cost_exceeding_list_price_is_rejected():
    accepted, rejected = validate_products([
        make_product(
            unit_cost="1200.00",
            list_price="1000.00"
        )
    ])

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Unit cost exceeds list price"


def test_duplicate_product_id_is_rejected():
    accepted, rejected = validate_products([
        make_product(),
        make_product(product_name="Another Product")
    ])

    assert len(accepted) == 1
    assert rejected[0]["rejection_reason"] == "Duplicate product_id"


def test_empty_product_input_returns_empty_results():
    accepted, rejected = validate_products([])

    assert accepted == []
    assert rejected == []


# --------------------------------------------------
# Order Validation Tests
# --------------------------------------------------

def test_valid_order_is_accepted():
    accepted, rejected = validate_orders(
        [make_order()],
        {"CUST000001"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 0


def test_order_with_missing_id_is_rejected():
    accepted, rejected = validate_orders(
        [make_order(order_id="")],
        {"CUST000001"}
    )

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Missing order_id"


def test_order_with_invalid_customer_reference_is_rejected():
    accepted, rejected = validate_orders(
        [make_order(customer_id="CUST999999")],
        {"CUST000001"}
    )

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Customer does not exist in accepted customers"


def test_order_with_invalid_status_is_rejected():
    accepted, rejected = validate_orders(
        [make_order(order_status="unknown")],
        {"CUST000001"}
    )

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Invalid order_status"


def test_order_with_malformed_timestamp_is_rejected():
    accepted, rejected = validate_orders(
        [make_order(order_timestamp="not-a-timestamp")],
        {"CUST000001"}
    )

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Invalid order_timestamp"


def test_order_without_timezone_is_rejected():
    accepted, rejected = validate_orders(
        [make_order(order_timestamp="2024-06-15T10:30:00")],
        {"CUST000001"}
    )

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Invalid order_timestamp"


def test_order_outside_configured_date_range_is_rejected():
    accepted, rejected = validate_orders(
        [make_order(order_timestamp="2026-01-01T10:30:00+00:00")],
        {"CUST000001"}
    )

    assert len(accepted) == 0
    assert rejected[0]["rejection_reason"] == "Invalid order_timestamp"


def test_duplicate_order_id_is_rejected():
    accepted, rejected = validate_orders(
        [
            make_order(),
            make_order(customer_id="CUST000002")
        ],
        {"CUST000001", "CUST000002"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "Duplicate order_id"


def test_invalid_first_order_does_not_block_valid_duplicate():
    accepted, rejected = validate_orders(
        [
            make_order(customer_id="CUST999999"),
            make_order()
        ],
        {"CUST000001"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "Customer does not exist in accepted customers"


def test_empty_order_input_returns_empty_results():
    accepted, rejected = validate_orders(
        [],
        {"CUST000001"}
    )

    assert accepted == []
    assert rejected == []


# --------------------------------------------------
# Order Item Validation Tests
# --------------------------------------------------

def test_valid_order_item_is_accepted():
    accepted, rejected = validate_order_items(
        [make_order_item()],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 0


def test_order_item_with_missing_id_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(order_item_id="")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_invalid_order_reference_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(order_id="ORD9999999")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_invalid_product_reference_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(product_id="PROD99999")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_non_integer_quantity_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(quantity="two")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_zero_quantity_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(quantity="0")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_negative_quantity_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(quantity="-2")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_negative_price_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(unit_price="-100.00")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_discount_exceeding_gross_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(discount_amount="2000.01")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_exact_duplicate_order_item_is_detected():
    record = make_order_item()

    accepted, rejected = validate_order_items(
        [record.copy(), record.copy()],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 1


def test_conflicting_duplicate_order_item_ids_are_rejected():
    first = make_order_item()
    second = make_order_item(quantity="3")

    accepted, rejected = validate_order_items(
        [first, second],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 2


def test_empty_order_item_input_returns_empty_results():
    accepted, rejected = validate_order_items(
        [],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert accepted == []
    assert rejected == []

# --------------------------------------------------
# Explicit Null Value Tests
# --------------------------------------------------

def test_customer_with_null_email_is_rejected():
    accepted, rejected = validate_customers([
        make_customer(email=None)
    ])

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_product_with_null_name_is_rejected():
    accepted, rejected = validate_products([
        make_product(product_name=None)
    ])

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_with_null_timestamp_is_rejected():
    accepted, rejected = validate_orders(
        [make_order(order_timestamp=None)],
        {"CUST000001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


def test_order_item_with_null_quantity_is_rejected():
    accepted, rejected = validate_order_items(
        [make_order_item(quantity=None)],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 0
    assert len(rejected) == 1


# --------------------------------------------------
# Financial Boundary Tests
# --------------------------------------------------

def test_order_item_with_zero_discount_is_accepted():
    accepted, rejected = validate_order_items(
        [make_order_item(discount_amount="0.00")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 0


def test_order_item_with_discount_equal_to_gross_is_accepted():
    accepted, rejected = validate_order_items(
        [make_order_item(
            quantity="2",
            unit_price="1000.00",
            discount_amount="2000.00"
        )],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 0


def test_order_item_with_smallest_positive_quantity_is_accepted():
    accepted, rejected = validate_order_items(
        [make_order_item(quantity="1")],
        {"ORD0000001"},
        {"PROD00001"}
    )

    assert len(accepted) == 1
    assert len(rejected) == 0


import csv
import pipeline



# --------------------------------------------------
# CSV Schema And Structure Tests
# --------------------------------------------------

def test_valid_csv_schema_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "INCOMING_DIR", tmp_path)

    file_path = tmp_path / "customers.csv"

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SCHEMAS["customers"])
        writer.writerow([
            "CUST000001",
            "Test Customer",
            "test@example.com",
            "2024-01-01",
            "India"
        ])

    assert pipeline.validate_schema(
        "customers.csv",
        SCHEMAS["customers"]
    ) is True


def test_csv_with_missing_column_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "INCOMING_DIR", tmp_path)

    file_path = tmp_path / "customers.csv"

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SCHEMAS["customers"][:-1])

    with pytest.raises(ValueError, match="Schema mismatch"):
        pipeline.validate_schema(
            "customers.csv",
            SCHEMAS["customers"]
        )


def test_csv_with_missing_row_field_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "INCOMING_DIR", tmp_path)

    file_path = tmp_path / "customers.csv"

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SCHEMAS["customers"])
        writer.writerow(["CUST000001", "Test Customer"])

    with pytest.raises(ValueError, match="Malformed row"):
        pipeline.validate_schema(
            "customers.csv",
            SCHEMAS["customers"]
        )


def test_csv_with_extra_row_field_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "INCOMING_DIR", tmp_path)

    file_path = tmp_path / "customers.csv"

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SCHEMAS["customers"])
        writer.writerow([
            "CUST000001",
            "Test Customer",
            "test@example.com",
            "2024-01-01",
            "India",
            "Unexpected"
        ])

    with pytest.raises(ValueError, match="Malformed row"):
        pipeline.validate_schema(
            "customers.csv",
            SCHEMAS["customers"]
        )


def test_header_only_csv_returns_empty_records(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "INCOMING_DIR", tmp_path)

    file_path = tmp_path / "customers.csv"

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SCHEMAS["customers"])

    records = pipeline.read_csv("customers.csv")

    assert records == []


def test_read_csv_rejects_unknown_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "INCOMING_DIR", tmp_path)

    file_path = tmp_path / "unknown.csv"
    file_path.write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="No schema defined"):
        pipeline.read_csv("unknown.csv")


def test_customer_v1_schema_is_accepted(tmp_path, monkeypatch):
    incoming_dir = tmp_path / "incoming"
    incoming_dir.mkdir()

    monkeypatch.setattr(pipeline, "INCOMING_DIR", incoming_dir)

    file_path = incoming_dir / "customers.csv"

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(pipeline.CUSTOMER_SCHEMA_VERSIONS["v1"])
        writer.writerow([
            "CUST000001",
            "Test Customer",
            "test@example.com",
            "2024-01-01",
            "India"
        ])

    records = pipeline.read_csv("customers.csv")

    assert len(records) == 1
    assert records[0]["phone_number"] == ""


def test_customer_v2_schema_preserves_phone_number(tmp_path, monkeypatch):
    incoming_dir = tmp_path / "incoming"
    incoming_dir.mkdir()

    monkeypatch.setattr(pipeline, "INCOMING_DIR", incoming_dir)

    file_path = incoming_dir / "customers.csv"

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(pipeline.CUSTOMER_SCHEMA_VERSIONS["v2"])
        writer.writerow([
            "CUST000001",
            "Test Customer",
            "test@example.com",
            "2024-01-01",
            "India",
            "9876543210"
        ])

    records = pipeline.read_csv("customers.csv")

    assert len(records) == 1
    assert records[0]["phone_number"] == "9876543210"   