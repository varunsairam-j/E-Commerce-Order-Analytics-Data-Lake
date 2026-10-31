from pathlib import Path

from pandas.plotting import table
import pyarrow as pa
import pyarrow.dataset as ds

from config_loader import PROJECT_ROOT, load_config

import csv

import gc

import time

from datetime import date, datetime, timezone
from decimal import Decimal

import shutil
from uuid import uuid4

import pyarrow.parquet as pq

import storage

CONFIG = load_config()

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LAKE_DIR = PROJECT_ROOT / "data" / "lake"

DAILY_DIR = LAKE_DIR / "daily"
MONTHLY_DIR = LAKE_DIR / "monthly"
YEARLY_COMPACTED_DIR = LAKE_DIR / "yearly_compacted"



FACT_SCHEMA = pa.schema([
    ("order_item_id", pa.string()),
    ("order_id", pa.string()),
    ("order_timestamp", pa.timestamp("us", tz="UTC")),
    ("order_date", pa.date32()),
    ("customer_id", pa.string()),
    ("product_id", pa.string()),
    ("product_category", pa.string()),
    ("shipping_country", pa.string()),
    ("quantity", pa.int32()),
    ("unit_price", pa.decimal128(18, 2)),
    ("gross_amount", pa.decimal128(18, 2)),
    ("discount_amount", pa.decimal128(18, 2)),
    ("net_revenue", pa.decimal128(18, 2)),
    ("order_status", pa.string()),
    ("recognized_revenue", pa.decimal128(18, 2)),
    ("run_id", pa.string()),
    ("source_file", pa.string()),
    ("ingested_at", pa.timestamp("us", tz="UTC"))
])


def parse_utc_timestamp(value, field_name):
    """Parse a timestamp and require an explicit timezone."""

    try:
        timestamp = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            f"Invalid {field_name}: {value}"
        ) from exc

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(
            f"{field_name} must include a timezone: {value}"
        )

    return timestamp.astimezone(timezone.utc)


def load_fact_table():
    """Load the transformed CSV into a validated typed PyArrow table."""

    csv_path = PROCESSED_DIR / "fact_order_items.csv"

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Fact table not found: {csv_path}"
        )

    records = []

    with csv_path.open(
        "r", newline="", encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file, strict=True)

        # Validate exact column names and order.
        if reader.fieldnames != FACT_SCHEMA.names:
            raise ValueError(
                "Fact table schema mismatch. "
                f"Expected {FACT_SCHEMA.names}, "
                f"received {reader.fieldnames}"
            )

        for row_number, row in enumerate(reader, start=2):

            # Detect unexpected extra fields.
            if None in row:
                raise ValueError(
                    f"Extra fields detected in fact CSV "
                    f"at line {row_number}"
                )

            # Detect missing fields.
            if any(value is None for value in row.values()):
                raise ValueError(
                    f"Missing fields detected in fact CSV "
                    f"at line {row_number}"
                )

            record = {
                "order_item_id": row["order_item_id"],
                "order_id": row["order_id"],
                "order_timestamp": parse_utc_timestamp(
                    row["order_timestamp"],
                    "order_timestamp"
               ),
                "order_date": date.fromisoformat(
                    row["order_date"]
                ),
                "customer_id": row["customer_id"],
                "product_id": row["product_id"],
                "product_category": row["product_category"],
                "shipping_country": row["shipping_country"],
                "quantity": int(row["quantity"]),
                "unit_price": Decimal(row["unit_price"]),
                "gross_amount": Decimal(row["gross_amount"]),
                "discount_amount": Decimal(row["discount_amount"]),
                "net_revenue": Decimal(row["net_revenue"]),
                "order_status": row["order_status"],
                "recognized_revenue": Decimal(
                    row["recognized_revenue"]
                ),
                "run_id": row["run_id"],
                "source_file": row["source_file"],
                "ingested_at": parse_utc_timestamp(
                    row["ingested_at"],
                    "ingested_at"
                )
            }

            records.append(record)

    return pa.Table.from_pylist(
        records,
        schema=FACT_SCHEMA
    )


def add_partition_columns(table):
    """Derive year, month and day columns from order_date."""

    order_dates = table.column("order_date").to_pylist()

    years = [value.year for value in order_dates]
    months = [value.month for value in order_dates]
    days = [value.day for value in order_dates]

    table = table.append_column(
        "year", pa.array(years, type=pa.int16())
    )

    table = table.append_column(
        "month", pa.array(months, type=pa.int8())
    )

    table = table.append_column(
        "day", pa.array(days, type=pa.int8())
    )

    return table


def rename_with_retry(source, destination, attempts=5):
    """Retry directory renames when Windows temporarily locks a path."""

    for attempt in range(attempts):
        try:
            source.rename(destination)
            return

        except PermissionError:
            if attempt == attempts - 1:
                raise

            wait_seconds = 0.5 * (2 ** attempt)

            print(
                f"Directory rename temporarily blocked. "
                f"Retrying in {wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)


def write_partitioned_dataset(
    table,
    output_dir,
    partition_columns,
    max_rows_per_file=None
):
    """Safely write and publish a partitioned Parquet dataset."""

    recover_publication(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)


    staging_dir = output_dir.with_name(
        f".{output_dir.name}.{uuid4().hex}.staging"
    )

    backup_dir = output_dir.with_name(
        f".{output_dir.name}.{uuid4().hex}.backup"
    )

    partition_schema = pa.schema([
        table.schema.field(column)
        for column in partition_columns
    ])

    partitioning = ds.partitioning(
        partition_schema,
        flavor="hive"
    )

    try:
        ds.write_dataset(
            table,
            base_dir=str(staging_dir),
            format="parquet",
            partitioning=partitioning,
            basename_template="part-{i}.parquet",
            existing_data_behavior="error",
            max_rows_per_file=max_rows_per_file or 0,
            max_rows_per_group=max_rows_per_file or 1024 * 1024,
            file_options=ds.ParquetFileFormat().make_write_options(
                compression="snappy"
            )
        )

        
        
        
        # Verify the staged dataset before publishing.
        if table.num_rows == 0:

            # PyArrow may not create a directory for an empty dataset.
            staging_dir.mkdir(parents=True, exist_ok=True)

            # Create an empty Parquet file carrying the complete schema.
            pq.write_table(
                table,
                staging_dir / "part-0.parquet",
                compression="snappy"
            )

            staged_count = 0

        staged_dataset = ds.dataset(
            str(staging_dir),
            format="parquet",
            partitioning="hive"
        )

        staged_count = staged_dataset.count_rows()

        # Release PyArrow resources before renaming directories on Windows.
        del staged_dataset
        gc.collect()

        if staged_count != table.num_rows:
            raise ValueError(
                f"Record count mismatch: expected {table.num_rows}, "
                f"found {staged_count}"
            )

        # Preserve the existing dataset until the replacement is ready.
        if output_dir.exists():
            rename_with_retry(output_dir, backup_dir)

        try:
            rename_with_retry(staging_dir, output_dir)

        except Exception:
            # Restore the previous dataset if publication fails.
            if backup_dir.exists():
                rename_with_retry(backup_dir, output_dir)

            raise

        # Remove the backup only after successful publication.
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        print(f"Dataset published: {output_dir}")
        print(f"Verified records: {staged_count:,}")

    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)




def recover_publication(output_dir):
    """Recover an interrupted dataset publication if necessary."""

    parent_dir = output_dir.parent

    backup_pattern = f".{output_dir.name}.*.backup"
    staging_pattern = f".{output_dir.name}.*.staging"

    backup_dirs = sorted(
        [
            path for path in parent_dir.glob(backup_pattern)
            if path.is_dir()
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    # Restore the most recent backup if the published dataset is missing.
    if not output_dir.exists() and backup_dirs:
        backup_dir = backup_dirs.pop(0)

        rename_with_retry(backup_dir, output_dir)

        print(
            f"Recovered previous dataset from: {backup_dir.name}"
        )

    # Remove stale backups only when a valid output exists.
    if output_dir.exists():
        for backup_dir in backup_dirs:
            shutil.rmtree(backup_dir)

            print(
                f"Removed stale backup: {backup_dir.name}"
            )

    # Remove abandoned staging directories.
    staging_dirs = list(
        parent_dir.glob(staging_pattern)
    )

    for staging_dir in staging_dirs:
        if staging_dir.is_dir():
            shutil.rmtree(staging_dir)

            print(
                f"Removed abandoned staging directory: "
                f"{staging_dir.name}"
            )


def test_recovery_restores_backup_and_removes_abandoned_staging(
    tmp_path
):
    """Verify recovery after an interrupted dataset publication."""

    output_dir = tmp_path / "daily"

    # Simulate the previous valid dataset moved to backup.
    backup_dir = tmp_path / ".daily.crash123.backup"
    backup_dir.mkdir()

    (backup_dir / "previous_data.txt").write_text(
        "Previous valid dataset",
        encoding="utf-8"
    )

    # Simulate an incomplete replacement left behind after a crash.
    staging_dir = tmp_path / ".daily.crash123.staging"
    staging_dir.mkdir()

    (staging_dir / "incomplete.txt").write_text(
        "Incomplete replacement",
        encoding="utf-8"
    )

    storage.recover_publication(output_dir)

    # Previous dataset must be restored.
    assert output_dir.exists()

    assert (
        output_dir / "previous_data.txt"
    ).read_text(encoding="utf-8") == "Previous valid dataset"

    # Abandoned staging directory must be removed.
    assert not staging_dir.exists()

    # Restored backup must no longer exist at its old location.
    assert not backup_dir.exists()


def main():
    print("Loading analytical fact table...")

    table = load_fact_table()
    table = add_partition_columns(table)

    print(f"Records loaded: {table.num_rows:,}")

    print("\nWriting daily partitioned dataset...")

    write_partitioned_dataset(
        table,
        DAILY_DIR,
        ["year", "month", "day"]
    )

    print("\nWriting monthly partitioned dataset...")

    write_partitioned_dataset(
        table,
        MONTHLY_DIR,
        ["year", "month"]
    )

    compaction_config = CONFIG["partitioning"]["compaction"]

    max_rows = compaction_config["max_rows_per_file"]

    print("\nWriting yearly compacted dataset...")
    print(f"Maximum rows per file: {max_rows:,}")

    write_partitioned_dataset(
        table,
        YEARLY_COMPACTED_DIR,
        ["year"],
        max_rows_per_file=max_rows
    )

    print("\nAll Parquet datasets published successfully.")


    return {
        "records_published": table.num_rows,
        "datasets": {
            "daily": "published",
            "monthly": "published",
            "yearly_compacted": "published"
        }
    }
    


if __name__ == "__main__":
    main()

