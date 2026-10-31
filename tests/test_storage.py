
import sys
from pathlib import Path
from datetime import date, datetime, timezone
from decimal import Decimal

import pyarrow as pa
import pyarrow.dataset as ds
import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

import storage


@pytest.fixture
def sample_fact_table():
    records = [
        {
            "order_item_id": "ITEM00000001",
            "order_id": "ORD0000001",
            "order_timestamp": datetime(
                2024, 6, 15, 10, 30, tzinfo=timezone.utc
            ),
            "order_date": date(2024, 6, 15),
            "customer_id": "CUST000001",
            "product_id": "PROD00001",
            "product_category": "Electronics",
            "shipping_country": "India",
            "quantity": 2,
            "unit_price": Decimal("1000.00"),
            "gross_amount": Decimal("2000.00"),
            "discount_amount": Decimal("100.00"),
            "net_revenue": Decimal("1900.00"),
            "order_status": "paid",
            "recognized_revenue": Decimal("1900.00"),
            "run_id": "test_run_001",
            "source_file": "order_items.csv",
            "ingested_at": datetime(
                2026, 10, 31, 10, 0, tzinfo=timezone.utc
            )
        }
    ]

    return pa.Table.from_pylist(
        records,
        schema=storage.FACT_SCHEMA
    )



# --------------------------------------------------
# PyArrow Schema Tests
# --------------------------------------------------

def test_fact_schema_contains_18_columns():
    assert len(storage.FACT_SCHEMA) == 18


def test_fact_schema_preserves_financial_decimal_types():
    for column in [
        "unit_price",
        "gross_amount",
        "discount_amount",
        "net_revenue",
        "recognized_revenue"
    ]:
        assert storage.FACT_SCHEMA.field(column).type == (
            pa.decimal128(18, 2)
        )


def test_fact_schema_uses_utc_timestamps():
    for column in ["order_timestamp", "ingested_at"]:
        field_type = storage.FACT_SCHEMA.field(column).type

        assert pa.types.is_timestamp(field_type)
        assert field_type.tz == "UTC"


# --------------------------------------------------
# Partition Column Tests
# --------------------------------------------------

def test_partition_columns_are_added_correctly(
    sample_fact_table
):
    table = storage.add_partition_columns(
        sample_fact_table
    )

    assert table.column("year").to_pylist() == [2024]
    assert table.column("month").to_pylist() == [6]
    assert table.column("day").to_pylist() == [15]


def test_partition_columns_have_correct_data_types(
    sample_fact_table
):
    table = storage.add_partition_columns(
        sample_fact_table
    )

    assert table.schema.field("year").type == pa.int16()
    assert table.schema.field("month").type == pa.int8()
    assert table.schema.field("day").type == pa.int8()


def test_partition_columns_do_not_modify_original_schema(
    sample_fact_table
):
    original_columns = sample_fact_table.column_names

    storage.add_partition_columns(sample_fact_table)

    assert sample_fact_table.column_names == original_columns



# --------------------------------------------------
# Parquet Write And Read Tests
# --------------------------------------------------

def test_partitioned_dataset_is_written_successfully(
    tmp_path,
    sample_fact_table
):
    output_dir = tmp_path / "daily"

    table = storage.add_partition_columns(
        sample_fact_table
    )

    storage.write_partitioned_dataset(
        table,
        output_dir,
        ["year", "month", "day"]
    )

    assert output_dir.exists()

    parquet_files = list(output_dir.rglob("*.parquet"))

    assert len(parquet_files) == 1


def test_parquet_dataset_preserves_record_count(
    tmp_path,
    sample_fact_table
):
    output_dir = tmp_path / "daily"

    table = storage.add_partition_columns(
        sample_fact_table
    )

    storage.write_partitioned_dataset(
        table,
        output_dir,
        ["year", "month", "day"]
    )

    dataset = ds.dataset(
        str(output_dir),
        format="parquet",
        partitioning="hive"
    )

    assert dataset.count_rows() == 1


def test_parquet_dataset_preserves_financial_precision(
    tmp_path,
    sample_fact_table
):
    output_dir = tmp_path / "daily"

    table = storage.add_partition_columns(
        sample_fact_table
    )

    storage.write_partitioned_dataset(
        table,
        output_dir,
        ["year", "month", "day"]
    )

    dataset = ds.dataset(
        str(output_dir),
        format="parquet",
        partitioning="hive"
    )

    result = dataset.to_table()

    assert result.column("gross_amount").to_pylist() == [
        Decimal("2000.00")
    ]

    assert result.column("recognized_revenue").to_pylist() == [
        Decimal("1900.00")
    ]


def test_parquet_dataset_preserves_partition_values(
    tmp_path,
    sample_fact_table
):
    output_dir = tmp_path / "daily"

    table = storage.add_partition_columns(
        sample_fact_table
    )

    storage.write_partitioned_dataset(
        table,
        output_dir,
        ["year", "month", "day"]
    )

    dataset = ds.dataset(
        str(output_dir),
        format="parquet",
        partitioning="hive"
    )

    result = dataset.to_table()

    assert result.column("year").to_pylist() == [2024]
    assert result.column("month").to_pylist() == [6]
    assert result.column("day").to_pylist() == [15]



# --------------------------------------------------
# Publication Recovery Tests
# --------------------------------------------------

def test_recovery_restores_backup_when_output_is_missing(
    tmp_path
):
    output_dir = tmp_path / "daily"

    backup_dir = tmp_path / ".daily.test123.backup"
    backup_dir.mkdir()

    (backup_dir / "recovery_marker.txt").write_text(
        "Previous valid dataset",
        encoding="utf-8"
    )

    storage.recover_publication(output_dir)

    assert output_dir.exists()
    assert (
        output_dir / "recovery_marker.txt"
    ).read_text(encoding="utf-8") == "Previous valid dataset"

    assert not backup_dir.exists()

    
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

    assert output_dir.exists()

    assert (
        output_dir / "previous_data.txt"
    ).read_text(encoding="utf-8") == "Previous valid dataset"

    assert not staging_dir.exists()
    assert not backup_dir.exists()


def test_recovery_restores_most_recent_backup(
    tmp_path
):
    """Verify that recovery selects the newest backup."""

    output_dir = tmp_path / "daily"

    older_backup = tmp_path / ".daily.older.backup"
    newer_backup = tmp_path / ".daily.newer.backup"

    older_backup.mkdir()
    newer_backup.mkdir()

    (older_backup / "marker.txt").write_text(
        "Older backup",
        encoding="utf-8"
    )

    (newer_backup / "marker.txt").write_text(
        "Newer backup",
        encoding="utf-8"
    )

    # Explicitly establish modification-time ordering.
    import os

    os.utime(older_backup, (1000000000, 1000000000))
    os.utime(newer_backup, (1100000000, 1100000000))

    storage.recover_publication(output_dir)

    assert output_dir.exists()

    assert (
        output_dir / "marker.txt"
    ).read_text(encoding="utf-8") == "Newer backup"

    assert not older_backup.exists()
    assert not newer_backup.exists()



def test_recovery_keeps_existing_output_and_removes_stale_backup(
    tmp_path
):
    output_dir = tmp_path / "daily"
    output_dir.mkdir()

    (output_dir / "current.txt").write_text(
        "Current dataset",
        encoding="utf-8"
    )

    backup_dir = tmp_path / ".daily.test123.backup"
    backup_dir.mkdir()

    storage.recover_publication(output_dir)

    assert output_dir.exists()
    assert (output_dir / "current.txt").exists()
    assert not backup_dir.exists()


def test_recovery_does_nothing_when_no_backup_exists(
    tmp_path
):
    output_dir = tmp_path / "daily"

    storage.recover_publication(output_dir)

    assert not output_dir.exists()



def test_failed_publication_restores_previous_dataset(
    tmp_path,
    sample_fact_table,
    monkeypatch
):
    """Verify that failed publication restores the previous dataset."""

    output_dir = tmp_path / "daily"
    output_dir.mkdir()

    marker_file = output_dir / "previous_data.txt"
    marker_file.write_text(
        "Previous valid dataset",
        encoding="utf-8"
    )

    table = storage.add_partition_columns(
        sample_fact_table
    )

    original_rename = storage.rename_with_retry

    def simulate_publication_failure(source, destination, attempts=5):
        # Fail only when staging is being published.
        if source.name.endswith(".staging") and destination == output_dir:
            raise PermissionError("Simulated publication failure")

        return original_rename(source, destination, attempts)

    monkeypatch.setattr(
        storage,
        "rename_with_retry",
        simulate_publication_failure
    )

    with pytest.raises(
        PermissionError,
        match="Simulated publication failure"
    ):
        storage.write_partitioned_dataset(
            table,
            output_dir,
            ["year", "month", "day"]
        )

    # Previous dataset must be restored.
    assert output_dir.exists()

    assert (
        output_dir / "previous_data.txt"
    ).read_text(encoding="utf-8") == "Previous valid dataset"

    # No backup or staging directories should remain.
    assert not list(tmp_path.glob("*.backup"))
    assert not list(tmp_path.glob("*.staging"))


def test_successful_republication_replaces_previous_dataset(
    tmp_path,
    sample_fact_table
):
    """Verify that successful republication replaces the old dataset."""

    output_dir = tmp_path / "daily"
    output_dir.mkdir()

    (output_dir / "old_marker.txt").write_text(
        "Old dataset",
        encoding="utf-8"
    )

    table = storage.add_partition_columns(
        sample_fact_table
    )

    storage.write_partitioned_dataset(
        table,
        output_dir,
        ["year", "month", "day"]
    )

    # New dataset must be published.
    assert output_dir.exists()

    # Previous dataset must no longer exist.
    assert not (output_dir / "old_marker.txt").exists()

    # Published dataset must contain the expected records.
    dataset = ds.dataset(
        str(output_dir),
        format="parquet",
        partitioning="hive"
    )

    assert dataset.count_rows() == 1

    # No leftover backup or staging directories.
    assert not list(tmp_path.glob("*.backup"))
    assert not list(tmp_path.glob("*.staging"))


# --------------------------------------------------
# Empty Dataset Tests
# --------------------------------------------------

def test_empty_fact_table_preserves_schema():
    table = pa.Table.from_pylist(
        [],
        schema=storage.FACT_SCHEMA
    )

    assert table.num_rows == 0
    assert table.schema == storage.FACT_SCHEMA


def test_empty_fact_table_accepts_partition_columns():
    table = pa.Table.from_pylist(
        [],
        schema=storage.FACT_SCHEMA
    )

    result = storage.add_partition_columns(table)

    assert result.num_rows == 0
    assert "year" in result.column_names
    assert "month" in result.column_names
    assert "day" in result.column_names


def test_empty_dataset_can_be_published(tmp_path):
    table = pa.Table.from_pylist(
        [],
        schema=storage.FACT_SCHEMA
    )

    table = storage.add_partition_columns(table)

    output_dir = tmp_path / "empty_dataset"

    storage.write_partitioned_dataset(
        table,
        output_dir,
        ["year", "month", "day"]
    )

    assert output_dir.exists()


def test_empty_parquet_dataset_can_be_reopened(tmp_path):
    table = pa.Table.from_pylist(
        [],
        schema=storage.FACT_SCHEMA
    )

    table = storage.add_partition_columns(table)

    output_dir = tmp_path / "empty_dataset"

    storage.write_partitioned_dataset(
        table,
        output_dir,
        ["year", "month", "day"]
    )

    dataset = ds.dataset(
        str(output_dir),
        format="parquet"
    )

    assert dataset.count_rows() == 0
    assert dataset.schema.names == table.schema.names