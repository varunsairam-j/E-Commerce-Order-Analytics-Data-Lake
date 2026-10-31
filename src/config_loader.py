
import json
from pathlib import Path
from datetime import date


# Locate the project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Configuration file location
CONFIG_PATH = PROJECT_ROOT / "config.json"


def load_config():
    """Load and validate the project configuration."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    validate_config(config)

    return config


def validate_config(config):
    """Validate required configuration sections and values."""

    required_sections = [
        "project",
        "dataset",
        "data_quality",
        "partitioning",
        "benchmark"
    ]

    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"Missing configuration section: {section}"
            )

    dataset = config["dataset"]

    required_counts = [
        "customers",
        "products",
        "orders",
        "order_items"
    ]

    for field in required_counts:
        if field not in dataset:
            raise ValueError(
                f"Missing dataset configuration: {field}"
            )

        value = dataset[field]

        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"{field} must be a positive integer."
            )

    if "random_seed" not in dataset:
        raise ValueError("Missing random_seed.")

    if isinstance(dataset["random_seed"], bool) or not isinstance(dataset["random_seed"], int):
        raise ValueError("random_seed must be an integer.")

    try:
        start_date = date.fromisoformat(dataset["start_date"])
        end_date = date.fromisoformat(dataset["end_date"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid dataset date configuration.") from error

    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date.")

    if config["project"].get("timezone") != "UTC":
        raise ValueError("Project timezone must be UTC.")

    if config["project"].get("currency") != "INR":
        raise ValueError("Project currency must be INR.")

    return True


if __name__ == "__main__":
    configuration = load_config()

    print("Configuration loaded successfully!")
    print(f"Project: {configuration['project']['name']}")
    print(f"Customers: {configuration['dataset']['customers']:,}")
    print(f"Products: {configuration['dataset']['products']:,}")
    print(f"Orders: {configuration['dataset']['orders']:,}")
    print(f"Order Items: {configuration['dataset']['order_items']:,}")
