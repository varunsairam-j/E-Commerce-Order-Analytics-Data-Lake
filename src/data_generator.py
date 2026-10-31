
import csv
import random
from datetime import date, timedelta, datetime, time, timezone
from pathlib import Path
from decimal import Decimal


from config_loader import PROJECT_ROOT, load_config


# Load project configuration
CONFIG = load_config()
DATASET_CONFIG = CONFIG["dataset"]

# Initialize a reproducible random generator
RANDOM = random.Random(DATASET_CONFIG["random_seed"])

# Output directory
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


# Sample values used to generate realistic records
FIRST_NAMES = [
    "Aarav", "Aditya", "Ananya", "Diya", "Ishaan",
    "Kavya", "Meera", "Neha", "Rahul", "Rohan",
    "Sanjay", "Sneha", "Varun", "Priya", "Arjun"
]

LAST_NAMES = [
    "Sharma", "Reddy", "Patel", "Kumar", "Rao",
    "Gupta", "Singh", "Verma", "Nair", "Iyer",
    "Joshi", "Das", "Mehta", "Mishra", "Kapoor"
]

COUNTRIES = [
    "India", "United States", "United Kingdom",
    "Australia", "Canada", "Germany", "Singapore"
]

PRODUCT_CATEGORIES = {
    "Electronics": (500, 50000),
    "Clothing": (200, 5000),
    "Home & Kitchen": (150, 15000),
    "Books": (100, 2000),
    "Sports": (250, 10000),
    "Beauty": (100, 5000)
}


def random_date(start_date, end_date):
    """Return a random date within the inclusive date range."""

    days_between = (end_date - start_date).days

    return start_date + timedelta(
        days=RANDOM.randint(0, days_between)
    )


def generate_customers():
    """Generate customer records and save them as CSV."""

    customer_count = DATASET_CONFIG["customers"]

    start_date = date.fromisoformat(DATASET_CONFIG["start_date"])
    end_date = date.fromisoformat(DATASET_CONFIG["end_date"])

    output_path = RAW_DATA_DIR / "customers.csv"

    fieldnames = [
        "customer_id",
        "customer_name",
        "email",
        "signup_date",
        "country"
    ]

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for number in range(1, customer_count + 1):
            first_name = RANDOM.choice(FIRST_NAMES)
            last_name = RANDOM.choice(LAST_NAMES)

            customer_id = f"CUST{number:06d}"

            customer_name = f"{first_name} {last_name}"

            email = (
                f"{first_name.lower()}."
                f"{last_name.lower()}{number:06d}@example.com"
            )

            signup_date = random_date(start_date, end_date)

            country = RANDOM.choice(COUNTRIES)

            writer.writerow({
                "customer_id": customer_id,
                "customer_name": customer_name,
                "email": email,
                "signup_date": signup_date.isoformat(),
                "country": country
            })

    print(f"Generated {customer_count:,} customers.")
    print(f"Saved to: {output_path}")


def generate_products():
    """Generate product records and save them as CSV."""

    product_count = DATASET_CONFIG["products"]

    output_path = RAW_DATA_DIR / "products.csv"

    fieldnames = [
        "product_id",
        "product_name",
        "category",
        "unit_cost",
        "list_price"
    ]

    categories = list(PRODUCT_CATEGORIES.keys())

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for number in range(1, product_count + 1):
            category = RANDOM.choice(categories)

            minimum_price, maximum_price = PRODUCT_CATEGORIES[category]

            list_price = Decimal(
                str(RANDOM.randint(minimum_price, maximum_price))
            ).quantize(Decimal("0.01"))

            # Generate a cost between 40% and 80% of list price
            cost_percentage = Decimal(
                str(RANDOM.randint(40, 80))
            ) / Decimal("100")

            unit_cost = (
                list_price * cost_percentage
            ).quantize(Decimal("0.01"))

            writer.writerow({
                "product_id": f"PROD{number:05d}",
                "product_name": f"{category} Product {number:05d}",
                "category": category,
                "unit_cost": f"{unit_cost:.2f}",
                "list_price": f"{list_price:.2f}"
            })

    print(f"Generated {product_count:,} products.")
    print(f"Saved to: {output_path}")



def read_source_csv(filename):
    """Read an existing source CSV file."""

    file_path = RAW_DATA_DIR / filename

    with file_path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def generate_orders_and_items():
    """Generate orders and order items with valid relationships."""

    customers = read_source_csv("customers.csv")
    products = read_source_csv("products.csv")

    order_count = DATASET_CONFIG["orders"]
    item_count = DATASET_CONFIG["order_items"]

    start_date = date.fromisoformat(DATASET_CONFIG["start_date"])
    end_date = date.fromisoformat(DATASET_CONFIG["end_date"])

    if item_count < order_count:
        raise ValueError(
            "Order items must be at least equal to the number of orders."
        )

    output_orders = RAW_DATA_DIR / "orders.csv"
    output_items = RAW_DATA_DIR / "order_items.csv"

    order_fields = [
        "order_id",
        "customer_id",
        "order_timestamp",
        "order_status",
        "shipping_country"
    ]

    item_fields = [
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "discount_amount"
    ]

    # Allocate at least one item to every order.
    # Distribute the remaining items randomly.
    items_per_order = [1] * order_count

    for _ in range(item_count - order_count):
        selected_order = RANDOM.randrange(order_count)
        items_per_order[selected_order] += 1

    generated_orders = []

    status_values = [
        "pending",
        "paid",
        "shipped",
        "delivered",
        "cancelled"
    ]

    status_weights = [10, 20, 15, 45, 10]

    # Generate orders.
    with output_orders.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(file, fieldnames=order_fields)
        writer.writeheader()

        for number in range(1, order_count + 1):

            customer = RANDOM.choice(customers)

            signup_date = date.fromisoformat(customer["signup_date"])

            order_date = random_date(
                max(start_date, signup_date),
                end_date
            )

            order_time = time(
                hour=RANDOM.randint(0, 23),
                minute=RANDOM.randint(0, 59),
                second=RANDOM.randint(0, 59)
            )

            timestamp = datetime.combine(
                order_date,
                order_time,
                tzinfo=timezone.utc
            )

            status = RANDOM.choices(
                status_values,
                weights=status_weights,
                k=1
            )[0]

            order_id = f"ORD{number:07d}"

            order_record = {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "order_timestamp": timestamp.isoformat(),
                "order_status": status,
                "shipping_country": customer["country"]
            }

            writer.writerow(order_record)

            generated_orders.append({
                "order_id": order_id,
                "item_count": items_per_order[number - 1]
            })

    print(f"Generated {order_count:,} orders.")
    print(f"Saved to: {output_orders}")

    # Generate order items.
    with output_items.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(file, fieldnames=item_fields)
        writer.writeheader()

        item_number = 1

        for order in generated_orders:

            for _ in range(order["item_count"]):

                product = RANDOM.choice(products)

                quantity = RANDOM.randint(1, 5)

                unit_price = Decimal(product["list_price"])

                gross_amount = unit_price * quantity

                discount_percentage = RANDOM.randint(0, 20)

                discount_amount = (
                    gross_amount * Decimal(discount_percentage) /
                    Decimal("100")
                ).quantize(Decimal("0.01"))

                writer.writerow({
                    "order_item_id": f"ITEM{item_number:08d}",
                    "order_id": order["order_id"],
                    "product_id": product["product_id"],
                    "quantity": quantity,
                    "unit_price": f"{unit_price:.2f}",
                    "discount_amount": f"{discount_amount:.2f}"
                })

                item_number += 1

    print(f"Generated {item_count:,} order items.")
    print(f"Saved to: {output_items}")



def main():
    """Generate all four source datasets."""

    generate_customers()
    generate_products()
    generate_orders_and_items()

    print("\nAll source datasets generated successfully.")


if __name__ == "__main__":
    main()