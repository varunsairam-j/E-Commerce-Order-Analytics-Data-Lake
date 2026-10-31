
import csv
import json

from pathlib import Path
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from collections import defaultdict

from config_loader import PROJECT_ROOT, load_config


# Load configuration
CONFIG = load_config()

INCOMING_DIR = PROJECT_ROOT / "data" / "incoming"
ACCEPTED_DIR = PROJECT_ROOT / "data" / "accepted"
QUARANTINE_DIR = PROJECT_ROOT / "outputs" / "quarantine"

ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)


# Expected source schemas
SCHEMAS = {
    "customers": [
        "customer_id",
        "customer_name",
        "email",
        "signup_date",
        "country"
    ],
    "products": [
        "product_id",
        "product_name",
        "category",
        "unit_cost",
        "list_price"
    ],
    "orders": [
        "order_id",
        "customer_id",
        "order_timestamp",
        "order_status",
        "shipping_country"
    ],
    "order_items": [
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "discount_amount"
    ]
}

# Supported Customer Schema Versions
CUSTOMER_SCHEMA_VERSIONS = {
    "v1": SCHEMAS["customers"],
    "v2": SCHEMAS["customers"] + ["phone_number"]
}

# Optional Columns By Schema Version
OPTIONAL_CUSTOMER_COLUMNS = {
    "v1": [],
    "v2": ["phone_number"]
}

# Current Customer Schema Version
CURRENT_CUSTOMER_SCHEMA_VERSION = "v2"



def read_csv(filename):
    """Read incoming CSV records after validating their structure."""

    file_path = INCOMING_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Incoming file not found: {file_path}"
        )

    # Determine the expected schema from the filename.
    schema_name = Path(filename).stem

    if schema_name not in SCHEMAS:
        raise ValueError(
            f"No schema defined for incoming file: {filename}"
        )

    expected_columns = SCHEMAS[schema_name]

    # Validate the header and every row before reading records.
    validate_schema(filename, expected_columns)

    with file_path.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        reader = csv.DictReader(file)
        records = list(reader)

    # Apply backward-compatible customer schema evolution.
    if schema_name == "customers":
        optional_columns = OPTIONAL_CUSTOMER_COLUMNS[
            CURRENT_CUSTOMER_SCHEMA_VERSION
        ]

        for row in records:
            for column in optional_columns:
                row.setdefault(column, "")
    return records

def validate_schema(filename, expected_columns):
    """Validate CSV headers and ensure every row has the correct width."""

    file_path = INCOMING_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Incoming file not found: {file_path}"
        )

    with file_path.open(
        "r", newline="", encoding="utf-8"
    ) as file:
        reader = csv.reader(file, strict=True)

        actual_columns = next(reader, [])

        if Path(filename).stem == "customers":
            supported_schemas = list(
                CUSTOMER_SCHEMA_VERSIONS.values()
            )

            if actual_columns not in supported_schemas:
                raise ValueError(
                    f"Schema mismatch in {filename}. "
                    f"Supported customer schemas: {supported_schemas}. "
                    f"Received: {actual_columns}"
            )

        elif actual_columns != expected_columns:
            raise ValueError(
                f"Schema mismatch in {filename}. "
                f"Expected {expected_columns}, received {actual_columns}"
            )
        
        for row_number, row in enumerate(reader, start=2):

            # Ignore completely blank lines.
            if not row:
                continue

            if len(row) != len(actual_columns):
                raise ValueError(
                    f"Malformed row in {filename} at line {row_number}. "
                    f"Expected {len(actual_columns)} fields, "
                    f"received {len(row)}"
                )

    return True


def quarantine_record(collection, record, reason):
    """Store a rejected record with its reason."""

    collection.append({
        "record": record,
        "rejection_reason": reason
    })

def get_clean_value(row, field):
    """Safely retrieve and normalize a string field."""

    value = row.get(field)

    if value is None:
        return ""

    return str(value).strip()

def write_csv(filename, rows, fieldnames):
    """Write accepted records, including empty datasets."""

    output_path = ACCEPTED_DIR / filename

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)


def write_quarantine(filename, records):
    """Write rejected records and their reasons."""

    output_path = QUARANTINE_DIR / filename

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["record", "rejection_reason"]
        )

        writer.writeheader()

        for entry in records:
            writer.writerow({
                "record": json.dumps(
                    entry["record"],
                    ensure_ascii=False
                ),
                "rejection_reason": entry["rejection_reason"]
            })


def validate_customers(customers):
    """Validate customer records."""

    accepted = []
    rejected = []
    seen_ids = set()
    seen_emails = set()

    for row in customers:

        customer_id = get_clean_value(row, "customer_id")
        email = get_clean_value(row, "email")
        customer_name = get_clean_value(row, "customer_name")
        signup_date_value = get_clean_value(row, "signup_date")

        if not customer_id:
            quarantine_record(
                rejected, row, "Missing customer_id"
            )
            continue

        if customer_id in seen_ids:
            quarantine_record(
                rejected, row, "Duplicate customer_id"
            )
            continue

        if not customer_name:
            quarantine_record(
                rejected, row, "Missing customer_name"
            )
            continue

        if not email or "@" not in email:
            quarantine_record(
                rejected, row, "Missing or invalid email"
            )
            continue

        if email in seen_emails:
            quarantine_record(
                rejected, row, "Duplicate email"
            )
            continue

        try:
            signup_date = date.fromisoformat(signup_date_value)
        except ValueError:
            quarantine_record(
                rejected, row, "Invalid signup_date"
            )
            continue

        if signup_date > date.fromisoformat(
            CONFIG["dataset"]["end_date"]
        ):
            quarantine_record(
                rejected, row, "Signup date outside configured range"
            )
            continue

        seen_ids.add(customer_id)
        seen_emails.add(email)

        accepted.append(row)

    return accepted, rejected


def validate_products(products):
    """Validate product records."""

    accepted = []
    rejected = []
    seen_ids = set()

    allowed_categories = {
        "Electronics",
        "Clothing",
        "Home & Kitchen",
        "Books",
        "Sports",
        "Beauty"
    }

    for row in products:

        product_id = get_clean_value(row, "product_id")
        product_name = get_clean_value(row, "product_name")
        category = get_clean_value(row, "category")
        unit_cost_value = get_clean_value(row, "unit_cost")
        list_price_value = get_clean_value(row, "list_price")

        if not product_id:
            quarantine_record(
                rejected, row, "Missing product_id"
            )
            continue

        if product_id in seen_ids:
            quarantine_record(
                rejected, row, "Duplicate product_id"
            )
            continue

        if not product_name:
            quarantine_record(
                rejected, row, "Missing product_name"
            )
            continue

        if category not in allowed_categories:
            quarantine_record(
                rejected, row, "Invalid product category"
            )
            continue

        try:
            unit_cost = Decimal(unit_cost_value)
            list_price = Decimal(list_price_value)
        except InvalidOperation:
            quarantine_record(
                rejected, row, "Invalid product price"
            )
            continue

        if not unit_cost.is_finite() or not list_price.is_finite():
            quarantine_record(
                rejected, row, "Non-finite product price"
            )
            continue

        if unit_cost < 0 or list_price <= 0:
            quarantine_record(
                rejected, row, "Negative cost or non-positive list price"
            )
            continue

        if unit_cost > list_price:
            quarantine_record(
                rejected, row, "Unit cost exceeds list price"
            )
            continue

        seen_ids.add(product_id)
        accepted.append(row)

    return accepted, rejected

def validate_orders(orders, accepted_customer_ids):
    accepted = []
    rejected = []

    seen_ids = set()

    allowed_statuses = {
        "pending",
        "paid",
        "shipped",
        "delivered",
        "cancelled"
    }

    start_date = date.fromisoformat(CONFIG["dataset"]["start_date"])
    end_date = date.fromisoformat(CONFIG["dataset"]["end_date"])

    for row in orders:
        order_id = get_clean_value(row, "order_id")
        customer_id = get_clean_value(row, "customer_id")
        status = get_clean_value(row, "order_status").lower()
        shipping_country = get_clean_value(row, "shipping_country")
        timestamp_value = get_clean_value(row, "order_timestamp")

        if not order_id:
            quarantine_record(rejected, row, "Missing order_id")
            continue

        if order_id in seen_ids:
            quarantine_record(rejected, row, "Duplicate order_id")
            continue


        if not customer_id or customer_id not in accepted_customer_ids:
            quarantine_record(
                rejected, row, "Customer does not exist in accepted customers"
            )
            continue

        if not shipping_country:
            quarantine_record(rejected, row, "Missing shipping_country")
            continue

        if status not in allowed_statuses:
            quarantine_record(rejected, row, "Invalid order_status")
            continue

        try:
            timestamp = datetime.fromisoformat(
                timestamp_value.replace("Z", "+00:00")
            )

            if timestamp.tzinfo is None:
                raise ValueError("Timestamp must include timezone")

            if timestamp.date() < start_date or timestamp.date() > end_date:
                raise ValueError("Timestamp outside configured date range")

        except ValueError:
            quarantine_record(rejected, row, "Invalid order_timestamp")
            continue

        seen_ids.add(order_id)

        row["order_status"] = status
        accepted.append(row)

    return accepted, rejected

def validate_order_items(order_items, accepted_order_ids, accepted_product_ids):
    accepted = []
    rejected = []

    # Step 1: Group all records by order_item_id.
    grouped_items = defaultdict(list)

    for row in order_items:
        item_id = get_clean_value(row, "order_item_id")

        if not item_id:
            quarantine_record(rejected, row, "Missing order_item_id")
            continue

        grouped_items[item_id].append(row)

    # Step 2: Identify conflicting duplicate IDs.
    conflicting_ids = set()

    for item_id, rows in grouped_items.items():
        unique_versions = {
            tuple(sorted(row.items()))
            for row in rows
        }

        if len(unique_versions) > 1:
            conflicting_ids.add(item_id)

    # Step 3: Validate each remaining record.
    for item_id, rows in grouped_items.items():

        if item_id in conflicting_ids:
            for row in rows:
                quarantine_record(
                    rejected, row, "Conflicting duplicate order_item_id"
                )
            continue

        # Exact duplicates: keep only one copy.
        row = rows[0]

        if len(rows) > 1:
            for duplicate in rows[1:]:
                quarantine_record(
                    rejected, duplicate, "Exact duplicate record"
                )

        order_id = get_clean_value(row, "order_id")
        product_id = get_clean_value(row, "product_id")

        try:
            quantity_value = get_clean_value(row, "quantity")
            unit_price_value = get_clean_value(row, "unit_price")
            discount_value = get_clean_value(row, "discount_amount")

            quantity = int(quantity_value)
            unit_price = Decimal(unit_price_value)
            discount_amount = Decimal(discount_value)

            if not unit_price.is_finite() or not discount_amount.is_finite():
                raise ValueError("Non-finite numeric value")

        except (ValueError, InvalidOperation):
            quarantine_record(rejected, row, "Invalid numeric value")
            continue

        if order_id not in accepted_order_ids:
            quarantine_record(
                rejected, row, "Order does not exist in accepted orders"
            )
            continue

        if product_id not in accepted_product_ids:
            quarantine_record(
                rejected, row, "Product does not exist in accepted products"
            )
            continue

        if quantity <= 0:
            quarantine_record(rejected, row, "Quantity must be positive")
            continue

        if unit_price < 0:
            quarantine_record(rejected, row, "Unit price cannot be negative")
            continue

        gross_amount = Decimal(quantity) * unit_price

        if discount_amount < 0:
            quarantine_record(rejected, row, "Discount cannot be negative")
            continue

        if discount_amount > gross_amount:
            quarantine_record(
                rejected, row, "Discount exceeds gross amount"
            )
            continue

        # Normalize validated numeric values.
        row["quantity"] = str(quantity)
        row["unit_price"] = str(unit_price)
        row["discount_amount"] = str(discount_amount)

        accepted.append(row)

    return accepted, rejected

def main():
    for entity, columns in SCHEMAS.items():
        validate_schema(f"{entity}.csv", columns)

    customers = read_csv("customers.csv")
    products = read_csv("products.csv")
    orders = read_csv("orders.csv")

    accepted_customers, rejected_customers = validate_customers(customers)
    accepted_products, rejected_products = validate_products(products)

    accepted_customer_ids = {
        row["customer_id"] for row in accepted_customers
    }

    accepted_orders, rejected_orders = validate_orders(
        orders, accepted_customer_ids
    )

    order_items = read_csv("order_items.csv")

    accepted_order_ids = {
    row["order_id"] for row in accepted_orders
    }

    accepted_product_ids = {
    row["product_id"] for row in accepted_products
    }

    accepted_order_items, rejected_order_items = validate_order_items(
    order_items,
    accepted_order_ids,
    accepted_product_ids
)

    write_csv(
        "customers.csv",
        accepted_customers,
        CUSTOMER_SCHEMA_VERSIONS[CURRENT_CUSTOMER_SCHEMA_VERSION]
    )
    write_csv("products.csv", accepted_products, SCHEMAS["products"])
    write_csv("orders.csv", accepted_orders, SCHEMAS["orders"])
    write_csv("order_items.csv", accepted_order_items, SCHEMAS["order_items"])

    write_quarantine("customers_rejected.csv", rejected_customers)
    write_quarantine("products_rejected.csv", rejected_products)
    write_quarantine("orders_rejected.csv", rejected_orders)
    write_quarantine("order_items_rejected.csv", rejected_order_items)

    print("Initial validation completed.")
    print(f"Accepted customers: {len(accepted_customers):,}")
    print(f"Rejected customers: {len(rejected_customers):,}")
    print(f"Accepted products: {len(accepted_products):,}")
    print(f"Rejected products: {len(rejected_products):,}")
    print(f"Accepted orders: {len(accepted_orders):,}")
    print(f"Rejected orders: {len(rejected_orders):,}")
    print(f"Accepted order items: {len(accepted_order_items):,}")
    print(f"Rejected order items: {len(rejected_order_items):,}")
    return {
        "source_records": {
            "customers": len(customers),
            "products": len(products),
            "orders": len(orders),
            "order_items": len(order_items)
        },
        "accepted_records": {
            "customers": len(accepted_customers),
            "products": len(accepted_products),
            "orders": len(accepted_orders),
            "order_items": len(accepted_order_items)
        },
        "rejected_records": {
            "customers": len(rejected_customers),
            "products": len(rejected_products),
            "orders": len(rejected_orders),
            "order_items": len(rejected_order_items)
        }
    }


if __name__ == "__main__":
    main()