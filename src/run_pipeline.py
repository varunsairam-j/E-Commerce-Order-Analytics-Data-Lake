
import json

from datetime import datetime, timezone
from time import perf_counter

from pathlib import Path
from uuid import uuid4

from config_loader import PROJECT_ROOT

from pipeline import (
    main as run_validation,
    CUSTOMER_SCHEMA_VERSIONS,
    CURRENT_CUSTOMER_SCHEMA_VERSION
)
from transform import main as run_transformation
from storage import main as run_storage


MANIFEST_DIR = PROJECT_ROOT / "outputs" / "run_manifests"


def save_run_manifest(manifest):
    """Save execution metadata as a JSON file."""

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    run_id = manifest["run_id"]
    output_path = MANIFEST_DIR / f"run_{run_id}.json"

    with output_path.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(
            manifest,
            file,
            indent=4
        )

    print(f"\nRun manifest saved: {output_path}")


def main():
    """Orchestrate validation, transformation and storage."""

    run_id = uuid4().hex
    start_time = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()

    run_metadata = {
        "run_id": run_id,
        "ingested_at": started_at
    }

    manifest = {
    "run_id": run_id,
    "schema_versions": {
        "customers": {
            "source_supported": list(CUSTOMER_SCHEMA_VERSIONS.keys()),
            "target": CURRENT_CUSTOMER_SCHEMA_VERSION
        }
    },
    "status": "RUNNING",
        "stage_status": {
            "validation": "PENDING",
            "reconciliation": "PENDING",
            "transformation": "PENDING",
            "storage": "PENDING"
        },        
        "started_at": started_at,
        "completed_at": None,
        "duration_seconds": None,
        "source_records": {},
        "accepted_records": {},
        "rejected_records": {},
        "transformation": {},
        "storage": {},
        "reconciliation": {},
        "failure": None    }

    current_stage = "initialization"

    print("=" * 60)
    print("E-COMMERCE DATA LAKE PIPELINE")
    print("=" * 60)
    print(f"Run ID: {run_id}")

    try:
        # Stage 1: Data validation
        current_stage = "validation"

        print("\nStarting validation stage...")

        validation_metrics = run_validation()

        manifest["source_records"] = (
            validation_metrics["source_records"]
        )

        manifest["accepted_records"] = (
            validation_metrics["accepted_records"]
        )

        manifest["rejected_records"] = (
            validation_metrics["rejected_records"]
        )

        manifest["stage_status"]["validation"] = "SUCCESS"
        current_stage = "reconciliation"

        # Reconciliation 1: Source = Accepted + Rejected
        entity_reconciliation = {}

        for entity, source_count in manifest["source_records"].items():
            accepted_count = manifest["accepted_records"][entity]
            rejected_count = manifest["rejected_records"][entity]

            matches = source_count == accepted_count + rejected_count

            entity_reconciliation[entity] = {
                "source_records": source_count,
                "accepted_records": accepted_count,
                "rejected_records": rejected_count,
                "matches": matches
            }

        manifest["reconciliation"]["entity_counts"] = (
            entity_reconciliation
        )

        if not all(
            result["matches"]
            for result in entity_reconciliation.values()
        ):
            raise ValueError("Source record reconciliation failed")
        
        # Stage 2: Data transformation
        current_stage = "transformation"

        print("\nStarting transformation stage...")

        transformation_metrics = run_transformation(
            run_metadata
        )

        manifest["transformation"] = transformation_metrics

        manifest["stage_status"]["transformation"] = "SUCCESS"

                # Reconciliation 2: Accepted Items = Transformed Facts
        accepted_items = manifest["accepted_records"]["order_items"]
        fact_records = manifest["transformation"]["fact_records"]

        accepted_items_match_facts = (
            accepted_items == fact_records
        )

        manifest["reconciliation"]["accepted_items_match_fact_records"] = (
            accepted_items_match_facts
        )

        if not accepted_items_match_facts:
            current_stage = "reconciliation"
            manifest["stage_status"]["reconciliation"] = "FAILED"
            raise ValueError(
                "Transformation record reconciliation failed"
            )

        # Stage 3: Parquet publication
        current_stage = "storage"

        print("\nStarting storage stage...")

        storage_metrics = run_storage()

        manifest["storage"] = storage_metrics

        manifest["stage_status"]["storage"] = "SUCCESS"

                # Reconciliation 3: Transformed Facts = Published Records
        fact_records = manifest["transformation"]["fact_records"]
        published_records = manifest["storage"]["records_published"]

        fact_records_match_published = (
            fact_records == published_records
        )

        manifest["reconciliation"]["fact_records_match_published_records"] = (
            fact_records_match_published
        )

        if not fact_records_match_published:
            current_stage = "reconciliation"
            manifest["stage_status"]["reconciliation"] = "FAILED"
            raise ValueError(
                "Publication record reconciliation failed"
            )

        manifest["reconciliation"]["passed"] = True
        manifest["stage_status"]["reconciliation"] = "SUCCESS"

        manifest["status"] = "SUCCESS"

        print("\nAll pipeline stages completed successfully.")

    except Exception as exc:
        manifest["status"] = "FAILED"
        manifest["stage_status"][current_stage] = "FAILED"

        manifest["failure"] = {
            "stage": current_stage,
            "error_type": type(exc).__name__,
            "error_message": str(exc)
        }

        print(f"\nPipeline failed during: {current_stage}")
        print(f"Error: {exc}")

        raise

    finally:
        manifest["completed_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

        manifest["duration_seconds"] = round(
            perf_counter() - start_time,
            3
        )

        save_run_manifest(manifest)

    return manifest


if __name__ == "__main__":
    main()
