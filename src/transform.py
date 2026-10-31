import csv
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from config_loader import PROJECT_ROOT, load_config


CONFIG = load_config()

ACCEPTED_DIR = PROJECT_ROOT / "data" / "accepted"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_FILE = "order_items.csv"

FACT_COLUMNS = [
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

def generate_run_metadata():
    """Generate metadata shared by all records in one execution."""

    return {
        "run_id": uuid4().hex,
        "ingested_at": datetime.now(timezone.utc).isoformat()
    }


def read_csv(filename):
    """Read a validated CSV dataset."""

    file_path = ACCEPTED_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Accepted dataset not found: {file_path}"
        )

    with file_path.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def load_datasets():
    """Load accepted datasets required for transformation."""

    orders = read_csv("orders.csv")
    products = read_csv("products.csv")
    order_items = read_csv("order_items.csv")

    orders_by_id = {
        row["order_id"]: row
        for row in orders
    }

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    return order_items, orders_by_id, products_by_id    


def build_fact_order_items(run_metadata=None):
    """Join accepted datasets and build the analytical fact table."""

    order_items, orders_by_id, products_by_id = load_datasets()

    fact_rows = []

    if run_metadata is None:
        run_metadata = generate_run_metadata()

    for item in order_items:

        order = orders_by_id.get(item["order_id"])
        product = products_by_id.get(item["product_id"])

        if order is None:
            raise ValueError(
                f"Missing order reference: {item['order_id']}"
            )

        if product is None:
            raise ValueError(
                f"Missing product reference: {item['product_id']}"
            )

        quantity = int(item["quantity"])
        unit_price = Decimal(item["unit_price"])
        discount_amount = Decimal(item["discount_amount"])

        gross_amount = Decimal(quantity) * unit_price
        net_revenue = gross_amount - discount_amount

        order_timestamp = datetime.fromisoformat(
            order["order_timestamp"].replace("Z", "+00:00")
        )

        recognized_revenue = (
            net_revenue
            if order["order_status"] in {
                "paid", "shipped", "delivered"
            }
            else Decimal("0.00")
        )

        fact_row = {
            "order_item_id": item["order_item_id"],
            "order_id": item["order_id"],
            "order_timestamp": order_timestamp.isoformat(),
            "order_date": order_timestamp.date().isoformat(),
            "customer_id": order["customer_id"],
            "product_id": item["product_id"],
            "product_category": product["category"],
            "shipping_country": order["shipping_country"],
            "quantity": quantity,
            "unit_price": str(unit_price),
            "gross_amount": str(gross_amount),
            "discount_amount": str(discount_amount),
            "net_revenue": str(net_revenue),
            "order_status": order["order_status"],
            "recognized_revenue": str(recognized_revenue),
            "run_id": run_metadata["run_id"],
            "source_file": SOURCE_FILE,
            "ingested_at": run_metadata["ingested_at"]
        }

        fact_rows.append(fact_row)

    return fact_rows


def write_fact_csv(rows):
    """Write the transformed fact table to CSV."""

    output_path = OUTPUT_DIR / "fact_order_items.csv"

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FACT_COLUMNS,
            extrasaction="raise"
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Fact table saved: {output_path}")


def main(run_metadata=None):
    print("Starting fact table transformation...")

    fact_rows = build_fact_order_items(run_metadata)

    write_fact_csv(fact_rows)

    print("\nTransformation completed successfully.")
    print(f"Total fact records: {len(fact_rows):,}")

    return {
        "fact_records": len(fact_rows),
        "run_id": (
            fact_rows[0]["run_id"]
            if fact_rows
            else run_metadata["run_id"]
        )
    }

if __name__ == "__main__":
    main()
