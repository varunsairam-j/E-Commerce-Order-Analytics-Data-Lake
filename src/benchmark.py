import duckdb
import time
import json

from pathlib import Path

from config_loader import PROJECT_ROOT

from decimal import Decimal

LAKE_DIR = PROJECT_ROOT / "data" / "lake"
BENCHMARK_DIR = PROJECT_ROOT / "benchmarks"

BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

DAILY_PATH = LAKE_DIR / "daily" / "**" / "*.parquet"
MONTHLY_PATH = LAKE_DIR / "monthly" / "**" / "*.parquet"
YEARLY_PATH = LAKE_DIR / "yearly_compacted" / "**" / "*.parquet"

CONNECTION = duckdb.connect()


def run_daily_query(strategy, target_date):
    """Run an equivalent single-day revenue query."""

    year, month, day = map(
        int, target_date.split("-")
    )

    dataset_paths = {
        "daily": DAILY_PATH,
        "monthly": MONTHLY_PATH,
        "yearly_compacted": YEARLY_PATH
    }

    if strategy not in dataset_paths:
        raise ValueError("Unknown partitioning strategy")

    parquet_path = dataset_paths[strategy]

    if strategy == "daily":
        partition_filter = (
            f"year = {year} "
            f"AND month = {month} "
            f"AND day = {day}"
        )

    elif strategy == "monthly":
        partition_filter = (
            f"year = {year} "
            f"AND month = {month}"
        )

    else:
        partition_filter = f"year = {year}"

    query = f"""
        SELECT
            COUNT(*) AS total_items,
            SUM(quantity) AS total_quantity,
            SUM(recognized_revenue) AS total_revenue
        FROM read_parquet(
            '{parquet_path.as_posix()}',
            hive_partitioning = true
        )
        WHERE {partition_filter}
          AND order_date = DATE '{target_date}'
    """

    return CONNECTION.execute(query).fetchone()


def benchmark_strategy(strategy, target_date, repetitions=7):
    """Measure query execution time across repeated runs."""

    # Warm-up execution (not included in measurements).
    run_daily_query(strategy, target_date)

    execution_times = []
    query_result = None

    for _ in range(repetitions):
        start_time = time.perf_counter()

        query_result = run_daily_query(
            strategy, target_date
        )

        end_time = time.perf_counter()

        execution_times.append(
            (end_time - start_time) * 1000
        )

    sorted_times = sorted(execution_times)

    median_time = sorted_times[len(sorted_times) // 2]

    return {
        "strategy": strategy,
        "target_date": target_date,
        "repetitions": repetitions,
        "execution_times_ms": execution_times,
        "median_time_ms": median_time,
        "result": {
            "total_items": query_result[0],
            "total_quantity": query_result[1],
            "total_revenue": str(query_result[2])
        }
    }

def benchmark_comparison(target_date, repetitions=7):
    """Compare all three partitioning strategies fairly."""

    strategies = [
        "daily",
        "monthly",
        "yearly_compacted"
    ]

    # Warm up all strategies.
    for strategy in strategies:
        run_daily_query(strategy, target_date)

    timings = {
        strategy: []
        for strategy in strategies
    }

    results = {}

    for repetition in range(repetitions):

        # Rotate execution order to reduce order bias.
        rotation = repetition % len(strategies)

        execution_order = (
            strategies[rotation:]
            + strategies[:rotation]
        )

        for strategy in execution_order:
            start_time = time.perf_counter()

            result = run_daily_query(
                strategy,
                target_date
            )

            elapsed_ms = (
                time.perf_counter() - start_time
            ) * 1000

            timings[strategy].append(elapsed_ms)
            results[strategy] = result

    comparison = {}

    for strategy in strategies:
        sorted_times = sorted(timings[strategy])

        median_time = sorted_times[len(sorted_times) // 2]

        comparison[strategy] = {
            "execution_times_ms": timings[strategy],
            "median_time_ms": median_time,
            "result": {
                "total_items": results[strategy][0],
                "total_quantity": results[strategy][1],
                "total_revenue": str(results[strategy][2])
            }
        }

    # Reconcile the business results.
    reference = comparison["daily"]["result"]

    for strategy in strategies[1:]:
        if comparison[strategy]["result"] != reference:
            raise ValueError(
                f"Reconciliation failed for {strategy} "
                f"on {target_date}"
            )

    return comparison


def inspect_query_plan(strategy, target_date):
    """Display DuckDB's physical query plan."""

    year, month, day = map(
        int, target_date.split("-")
    )

    dataset_paths = {
        "daily": DAILY_PATH,
        "monthly": MONTHLY_PATH,
        "yearly_compacted": YEARLY_PATH
    }

    if strategy not in dataset_paths:
        raise ValueError("Unknown partitioning strategy")

    parquet_path = dataset_paths[strategy]

    if strategy == "daily":
        partition_filter = (
            f"year = {year} "
            f"AND month = {month} "
            f"AND day = {day}"
        )

    elif strategy == "monthly":
        partition_filter = (
            f"year = {year} "
            f"AND month = {month}"
        )

    else:
        partition_filter = f"year = {year}"

    query = f"""
        EXPLAIN
        SELECT
            COUNT(*),
            SUM(recognized_revenue)
        FROM read_parquet(
            '{parquet_path.as_posix()}',
            hive_partitioning = true
        )
        WHERE {partition_filter}
          AND order_date = DATE '{target_date}'
    """

    return CONNECTION.execute(query).fetchall()


def verify_dataset(strategy):
    """Verify record counts, uniqueness, quantities, revenue and nulls."""

    dataset_paths = {
        "daily": DAILY_PATH,
        "monthly": MONTHLY_PATH,
        "yearly_compacted": YEARLY_PATH
    }

    if strategy not in dataset_paths:
        raise ValueError(f"Unknown dataset strategy: {strategy}")

    parquet_path = dataset_paths[strategy]

    query = f"""
        SELECT
            COUNT(*) AS total_records,
            COUNT(DISTINCT order_item_id) AS distinct_order_items,
            SUM(quantity) AS total_quantity,
            SUM(recognized_revenue) AS total_revenue,
            COUNT(*) FILTER (
                WHERE order_item_id IS NULL
                   OR order_id IS NULL
                   OR order_date IS NULL
                   OR quantity IS NULL
                   OR recognized_revenue IS NULL
            ) AS null_records
        FROM read_parquet(
            '{parquet_path.as_posix()}',
            hive_partitioning = true
        )
    """

    result = CONNECTION.execute(query).fetchone()

    return {
        "strategy": strategy,
        "total_records": result[0],
        "distinct_order_items": result[1],
        "total_quantity": result[2],
        "total_revenue": str(result[3]),
        "null_records": result[4]
    }


def verify_all_datasets():
    """Verify and reconcile all three Parquet layouts."""

    strategies = [
        "daily",
        "monthly",
        "yearly_compacted"
    ]

    all_results = []

    print("\nDATASET INTEGRITY VERIFICATION")
    print("=" * 65)

    for strategy in strategies:
        result = verify_dataset(strategy)
        all_results.append(result)

        print(f"\nStrategy: {strategy.upper()}")
        print(f"Total Records: {result['total_records']:,}")
        print(f"Distinct Order Items: {result['distinct_order_items']:,}")
        print(f"Total Quantity: {result['total_quantity']:,}")
        print(f"Total Revenue: ₹{result['total_revenue']}")
        print(f"Records With Critical Nulls: {result['null_records']:,}")

    # Compare business metrics across all three layouts.
    reference = {
        key: all_results[0][key]
        for key in [
            "total_records",
            "distinct_order_items",
            "total_quantity",
            "total_revenue",
            "null_records"
        ]
    }

    for result in all_results[1:]:
        current = {
            key: result[key]
            for key in reference
        }

        if current != reference:
            raise ValueError(
                "Dataset reconciliation failed. "
                f"Mismatch found in {result['strategy']}."
            )

    if reference["total_records"] != reference["distinct_order_items"]:
        raise ValueError("Duplicate order_item_id values detected.")

    if reference["null_records"] != 0:
        raise ValueError("Critical null values detected.")

    output_path = BENCHMARK_DIR / "dataset_verification.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(all_results, file, indent=4)

    print("\n" + "=" * 65)
    print("SUCCESS: All three datasets passed reconciliation.")
    print(f"Verification report saved to: {output_path}")


def main_query_plan():
    target_date = "2025-11-10"

    for strategy in [
    "daily",
    "monthly",
    "yearly_compacted"
]:
        print(f"\n{'=' * 60}")
        print(f"{strategy.upper()} PARTITIONING")
        print(f"{'=' * 60}")

        plan = inspect_query_plan(
            strategy,
            target_date
        )

        for row in plan:
            print(row[1])



def main():
    target_dates = [
        "2024-03-15",
        "2025-06-15",
        "2025-11-10"
    ]

    all_results = []

    print("Starting multi-date partitioning benchmark...")

    for target_date in target_dates:
        print(f"\nBenchmarking date: {target_date}")

        comparison = benchmark_comparison(
            target_date,
            repetitions=7
        )

        for strategy in [
            "daily",
            "monthly",
            "yearly_compacted"
        ]:
            result = comparison[strategy]

            print(
                f"{strategy.upper():8} "
                f"Median: {result['median_time_ms']:.3f} ms"
            )

            print(
                f"         Records: "
                f"{result['result']['total_items']:,}"
            )

        all_results.append({
            "target_date": target_date,
            "comparison": comparison
        })

    output_path = BENCHMARK_DIR / "multi_date_benchmark.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(all_results, file, indent=4)

    print("\nMulti-date benchmark completed successfully.")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()


