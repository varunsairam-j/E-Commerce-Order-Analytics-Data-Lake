
import csv
import json
import random

from copy import deepcopy
from decimal import Decimal

from config_loader import PROJECT_ROOT, load_config


# Load project configuration
CONFIG = load_config()
DATASET_CONFIG = CONFIG["dataset"]
QUALITY_CONFIG = CONFIG["data_quality"]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
INCOMING_DIR = PROJECT_ROOT / "data" / "incoming"

INCOMING_DIR.mkdir(parents=True, exist_ok=True)

RNG = random.Random(DATASET_CONFIG["random_seed"] + 1)

DEFECT_COUNT = QUALITY_CONFIG["defect_count_per_scenario"]


def read_csv(filename):
    """Read baseline CSV records."""

    file_path = RAW_DIR / filename

    with file_path.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def write_csv(filename, rows):
    """Write incoming CSV records."""

    if not rows:
        raise ValueError(f"No records supplied for {filename}")

    output_path = INCOMING_DIR / filename

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)


def select_distinct_indices(total_rows, count, used_indices):
    """Select unique row indexes without overlapping scenarios."""

    available = [
        index for index in range(total_rows)
        if index not in used_indices
    ]

    if len(available) < count:
        raise ValueError(
            "Not enough distinct records for defect injection."
        )

    selected = RNG.sample(available, count)
    used_indices.update(selected)

    return selected


def inject_customer_defects(customers):
    """Inject missing required customer values."""

    rows = deepcopy(customers)
    used = set()

    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    for index in indexes:
        rows[index]["email"] = ""

    return rows


def inject_order_defects(orders):
    """Inject invalid customer references, timestamps and statuses."""

    rows = deepcopy(orders)
    used = set()

    # Invalid foreign keys
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    for index in indexes:
        rows[index]["customer_id"] = "CUST99999999"

    # Malformed timestamps
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    for index in indexes:
        rows[index]["order_timestamp"] = "2025-25-80 INVALID"

    # Invalid order statuses
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    for index in indexes:
        rows[index]["order_status"] = "processing_unknown"

    return rows


def inject_order_item_defects(items):
    """Inject duplicate and invalid order-item records."""

    rows = deepcopy(items)
    used = set()

    # Exact duplicate records
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    exact_duplicates = [
        deepcopy(rows[index]) for index in indexes
    ]

    # Conflicting duplicate primary keys
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    conflicting_duplicates = []

    for index in indexes:
        duplicate = deepcopy(rows[index])
        duplicate["quantity"] = str(
            int(duplicate["quantity"]) + 1
        )
        conflicting_duplicates.append(duplicate)

    # Invalid product references
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    for index in indexes:
        rows[index]["product_id"] = "PROD99999999"

    # Invalid quantities
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    for index in indexes:
        rows[index]["quantity"] = "-5"

    # Excessive discounts
    indexes = select_distinct_indices(
        len(rows), DEFECT_COUNT, used
    )

    for index in indexes:
        gross_amount = (
            Decimal(rows[index]["quantity"])
            * Decimal(rows[index]["unit_price"])
        )

        rows[index]["discount_amount"] = str(
            gross_amount + Decimal("1.00")
        )

    # Append duplicate records
    rows.extend(exact_duplicates)
    rows.extend(conflicting_duplicates)

    return rows


def main():
    if not QUALITY_CONFIG["inject_defects"]:
        print("Defect injection is disabled in config.json.")
        return

    customers = read_csv("customers.csv")
    products = read_csv("products.csv")
    orders = read_csv("orders.csv")
    items = read_csv("order_items.csv")

    incoming_customers = inject_customer_defects(customers)
    incoming_orders = inject_order_defects(orders)
    incoming_items = inject_order_item_defects(items)

    # Products are copied without defects.
    write_csv("customers.csv", incoming_customers)
    write_csv("products.csv", products)
    write_csv("orders.csv", incoming_orders)
    write_csv("order_items.csv", incoming_items)

    manifest = {
        "random_seed": DATASET_CONFIG["random_seed"] + 1,
        "defects_per_scenario": DEFECT_COUNT,
        "injected_defects": {
            "missing_customer_email": DEFECT_COUNT,
            "invalid_customer_reference": DEFECT_COUNT,
            "malformed_order_timestamp": DEFECT_COUNT,
            "invalid_order_status": DEFECT_COUNT,
            "exact_duplicate_order_items": DEFECT_COUNT,
            "conflicting_duplicate_order_item_ids": DEFECT_COUNT,
            "invalid_product_reference": DEFECT_COUNT,
            "invalid_order_item_quantity": DEFECT_COUNT,
            "excessive_order_item_discount": DEFECT_COUNT
        },
        "incoming_record_counts": {
            "customers": len(incoming_customers),
            "products": len(products),
            "orders": len(incoming_orders),
            "order_items": len(incoming_items)
        }
    }

    manifest_path = INCOMING_DIR / "defect_manifest.json"

    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=4)

    print("Controlled data-quality defects injected successfully.")
    print(f"Defects per scenario: {DEFECT_COUNT}")
    print(f"Incoming customers: {len(incoming_customers):,}")
    print(f"Incoming products: {len(products):,}")
    print(f"Incoming orders: {len(incoming_orders):,}")
    print(f"Incoming order items: {len(incoming_items):,}")
    print(f"Manifest saved to: {manifest_path}")


if __name__ == "__main__":
    main()
