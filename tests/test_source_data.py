
import csv
from decimal import Decimal
from pathlib import Path

from datetime import date, datetime, timezone
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def read_csv(filename):
    with (RAW_DIR / filename).open(
        "r", newline="", encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def test_customer_data():
    customers = read_csv("customers.csv")

    assert len(customers) == 10000

    customer_ids = [row["customer_id"] for row in customers]
    emails = [row["email"] for row in customers]

    assert len(customer_ids) == len(set(customer_ids))
    assert len(emails) == len(set(emails))

    for row in customers:
        assert all(row[field].strip() for field in [
            "customer_id",
            "customer_name",
            "email",
            "signup_date",
            "country"
        ])

        assert row["email"].endswith("@example.com")


def test_product_data():
    products = read_csv("products.csv")

    assert len(products) == 2000

    product_ids = [row["product_id"] for row in products]

    assert len(product_ids) == len(set(product_ids))

    allowed_categories = {
        "Electronics",
        "Clothing",
        "Home & Kitchen",
        "Books",
        "Sports",
        "Beauty"
    }

    for row in products:
        assert row["category"] in allowed_categories

        unit_cost = Decimal(row["unit_cost"])
        list_price = Decimal(row["list_price"])

        assert unit_cost > 0
        assert list_price > 0
        assert unit_cost <= list_price


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))



def test_order_data():
    customers = read_csv("customers.csv")
    orders = read_csv("orders.csv")

    assert len(orders) == 40000

    customer_ids = {row["customer_id"] for row in customers}
    order_ids = [row["order_id"] for row in orders]

    # Every order must have a unique ID.
    assert len(order_ids) == len(set(order_ids))

    allowed_statuses = {
        "pending", "paid", "shipped", "delivered", "cancelled"
    }

    customer_signup_dates = {
        row["customer_id"]: date.fromisoformat(row["signup_date"])
        for row in customers
    }

    for row in orders:
        # Every order must reference an existing customer.
        assert row["customer_id"] in customer_ids

        # Every order must have an allowed status.
        assert row["order_status"] in allowed_statuses

        # Timestamp must be valid and timezone-aware UTC.
        timestamp = datetime.fromisoformat(row["order_timestamp"])

        assert timestamp.tzinfo is not None
        assert timestamp.utcoffset() == timezone.utc.utcoffset(timestamp)

        # Customers cannot order before signing up.
        assert timestamp.date() >= customer_signup_dates[row["customer_id"]]


def test_order_item_data():
    orders = read_csv("orders.csv")
    products = read_csv("products.csv")
    items = read_csv("order_items.csv")

    assert len(items) == 120000

    order_ids = {row["order_id"] for row in orders}
    product_ids = {row["product_id"] for row in products}

    item_ids = [row["order_item_id"] for row in items]

    # Every order item must have a unique ID.
    assert len(item_ids) == len(set(item_ids))

    # Count how many items belong to each order.
    items_per_order = Counter()

    for row in items:
        assert row["order_id"] in order_ids
        assert row["product_id"] in product_ids

        quantity = int(row["quantity"])
        unit_price = Decimal(row["unit_price"])
        discount = Decimal(row["discount_amount"])

        assert quantity > 0
        assert unit_price > 0

        gross_amount = quantity * unit_price

        assert discount >= 0
        assert discount <= gross_amount

        items_per_order[row["order_id"]] += 1

    # Every order must contain at least one item.
    assert set(items_per_order) == order_ids
    assert all(count >= 1 for count in items_per_order.values())
