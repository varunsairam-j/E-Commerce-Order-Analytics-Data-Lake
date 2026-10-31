
import json
import sys
from pathlib import Path

import pytest

# Make the src directory available for imports.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import run_pipeline


def test_validation_failure_is_recorded_in_manifest(
    tmp_path, monkeypatch
):
    """Verify that a validation failure produces a failure manifest."""

    # Store test manifests in a temporary directory.
    monkeypatch.setattr(
        run_pipeline,
        "MANIFEST_DIR",
        tmp_path
    )

    # Simulate a missing input file during validation.
    def simulate_validation_failure():
        raise FileNotFoundError("Simulated missing input file")

    monkeypatch.setattr(
        run_pipeline,
        "run_validation",
        simulate_validation_failure
    )

    # The orchestrator should record the failure and re-raise it.
    with pytest.raises(
        FileNotFoundError,
        match="Simulated missing input file"
    ):
        run_pipeline.main()

    # Find the generated failure manifest.
    manifest_files = list(tmp_path.glob("run_*.json"))

    assert len(manifest_files) == 1

    with manifest_files[0].open(
        "r", encoding="utf-8"
    ) as file:
        manifest = json.load(file)

    # Verify failure information.
    assert manifest["status"] == "FAILED"
    assert manifest["failure"]["stage"] == "validation"
    assert manifest["failure"]["error_type"] == "FileNotFoundError"
    assert manifest["failure"]["error_message"] == (
        "Simulated missing input file"
    )

    # Verify execution timestamps.
    assert manifest["started_at"] is not None
    assert manifest["completed_at"] is not None

    # Transformation and storage should not have run.
    assert manifest["transformation"] == {}
    assert manifest["storage"] == {}

    # Verify stage statuses.
    assert manifest["stage_status"]["validation"] == "FAILED"
    assert manifest["stage_status"]["transformation"] == "PENDING"
    assert manifest["stage_status"]["storage"] == "PENDING"


def test_transformation_failure_is_recorded_in_manifest(
    tmp_path, monkeypatch
):
    """Verify that transformation failures are recorded."""

    monkeypatch.setattr(
        run_pipeline,
        "MANIFEST_DIR",
        tmp_path
    )

    validation_metrics = {
        "source_records": {},
        "accepted_records": {},
        "rejected_records": {}
    }

    monkeypatch.setattr(
        run_pipeline,
        "run_validation",
        lambda: validation_metrics
    )

    def simulate_transformation_failure(run_metadata):
        raise ValueError("Simulated transformation failure")

    monkeypatch.setattr(
        run_pipeline,
        "run_transformation",
        simulate_transformation_failure
    )

    storage_called = False

    def simulate_storage():
        nonlocal storage_called
        storage_called = True
        return {}

    monkeypatch.setattr(
        run_pipeline,
        "run_storage",
        simulate_storage
    )

    with pytest.raises(
        ValueError,
        match="Simulated transformation failure"
    ):
        run_pipeline.main()

    manifest_files = list(tmp_path.glob("run_*.json"))

    assert len(manifest_files) == 1

    manifest = json.loads(
        manifest_files[0].read_text(encoding="utf-8")
    )

    assert manifest["status"] == "FAILED"
    assert manifest["failure"]["stage"] == "transformation"
    assert manifest["failure"]["error_type"] == "ValueError"
    assert manifest["failure"]["error_message"] == (
        "Simulated transformation failure"
    )

    assert manifest["source_records"] == {}
    assert manifest["transformation"] == {}
    assert manifest["storage"] == {}

    assert storage_called is False

    # Verify stage statuses.
    assert manifest["stage_status"]["validation"] == "SUCCESS"
    assert manifest["stage_status"]["transformation"] == "FAILED"
    assert manifest["stage_status"]["storage"] == "PENDING"


def test_storage_failure_is_recorded_in_manifest(
    tmp_path, monkeypatch
):
    """Verify that storage failures are recorded."""

    monkeypatch.setattr(
        run_pipeline,
        "MANIFEST_DIR",
        tmp_path
    )

    validation_metrics = {
        "source_records": {
            "customers": 10,
            "order_items": 120
        },
        "accepted_records": {
            "customers": 9,
            "order_items": 100
        },
        "rejected_records": {
            "customers": 1,
            "order_items": 20
        }
    }
    
    transformation_metrics = {
        "fact_records": 100,
        "run_id": "test-run-id"
    }

    monkeypatch.setattr(
        run_pipeline,
        "run_validation",
        lambda: validation_metrics
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_transformation",
        lambda run_metadata: transformation_metrics
    )

    def simulate_storage_failure():
        raise OSError("Simulated storage publication failure")

    monkeypatch.setattr(
        run_pipeline,
        "run_storage",
        simulate_storage_failure
    )

    with pytest.raises(
        OSError,
        match="Simulated storage publication failure"
    ):
        run_pipeline.main()

    manifest_files = list(tmp_path.glob("run_*.json"))

    assert len(manifest_files) == 1

    manifest = json.loads(
        manifest_files[0].read_text(encoding="utf-8")
    )

    assert manifest["status"] == "FAILED"
    assert manifest["failure"]["stage"] == "storage"
    assert manifest["failure"]["error_type"] == "OSError"
    assert manifest["failure"]["error_message"] == (
        "Simulated storage publication failure"
    )

    assert manifest["source_records"] == {
    "customers": 10,
    "order_items": 120
    }
    assert manifest["transformation"]["fact_records"] == 100
    assert manifest["storage"] == {}
    assert manifest["reconciliation"]["accepted_items_match_fact_records"] is True

    assert manifest["stage_status"]["validation"] == "SUCCESS"
    assert manifest["stage_status"]["transformation"] == "SUCCESS"
    assert manifest["stage_status"]["storage"] == "FAILED"



def test_source_reconciliation_failure_is_recorded(
    tmp_path, monkeypatch
):
    """Verify that source count mismatches fail reconciliation."""

    monkeypatch.setattr(
        run_pipeline,
        "MANIFEST_DIR",
        tmp_path
    )

    validation_metrics = {
        "source_records": {
            "customers": 10
        },
        "accepted_records": {
            "customers": 9
        },
        "rejected_records": {
            "customers": 2
        }
    }

    monkeypatch.setattr(
        run_pipeline,
        "run_validation",
        lambda: validation_metrics
    )

    transformation_called = False

    def simulate_transformation(run_metadata):
        nonlocal transformation_called
        transformation_called = True
        return {"fact_records": 9, "run_id": "test-run-id"}

    monkeypatch.setattr(
        run_pipeline,
        "run_transformation",
        simulate_transformation
    )

    with pytest.raises(
        ValueError,
        match="Source record reconciliation failed"
    ):
        run_pipeline.main()

    manifest_files = list(tmp_path.glob("run_*.json"))
    assert len(manifest_files) == 1

    manifest = json.loads(
        manifest_files[0].read_text(encoding="utf-8")
    )

    assert manifest["status"] == "FAILED"
    assert manifest["failure"]["stage"] == "reconciliation"
    assert manifest["failure"]["error_type"] == "ValueError"

    assert (
        manifest["reconciliation"]["entity_counts"]["customers"]["matches"]
        is False
    )

    assert manifest["stage_status"]["validation"] == "SUCCESS"
    assert manifest["stage_status"]["reconciliation"] == "FAILED"
    assert manifest["stage_status"]["transformation"] == "PENDING"

    assert transformation_called is False



def test_transformation_reconciliation_failure_is_recorded(
    tmp_path, monkeypatch
):
    """Verify that fact record count mismatches fail reconciliation."""

    monkeypatch.setattr(
        run_pipeline,
        "MANIFEST_DIR",
        tmp_path
    )

    validation_metrics = {
        "source_records": {
            "order_items": 120
        },
        "accepted_records": {
            "order_items": 100
        },
        "rejected_records": {
            "order_items": 20
        }
    }

    transformation_metrics = {
        "fact_records": 95,
        "run_id": "test-run-id"
    }

    monkeypatch.setattr(
        run_pipeline,
        "run_validation",
        lambda: validation_metrics
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_transformation",
        lambda run_metadata: transformation_metrics
    )

    storage_called = False

    def simulate_storage():
        nonlocal storage_called
        storage_called = True
        return {}

    monkeypatch.setattr(
        run_pipeline,
        "run_storage",
        simulate_storage
    )

    with pytest.raises(
        ValueError,
        match="Transformation record reconciliation failed"
    ):
        run_pipeline.main()

    manifest_files = list(tmp_path.glob("run_*.json"))
    assert len(manifest_files) == 1

    manifest = json.loads(
        manifest_files[0].read_text(encoding="utf-8")
    )

    assert manifest["status"] == "FAILED"
    assert manifest["failure"]["stage"] == "reconciliation"
    assert manifest["failure"]["error_type"] == "ValueError"

    assert (
        manifest["reconciliation"]["accepted_items_match_fact_records"]
        is False
    )

    assert manifest["stage_status"]["validation"] == "SUCCESS"
    assert manifest["stage_status"]["reconciliation"] == "FAILED"
    assert manifest["stage_status"]["transformation"] == "SUCCESS"
    assert manifest["stage_status"]["storage"] == "PENDING"

    assert storage_called is False



def test_publication_reconciliation_failure_is_recorded(
    tmp_path, monkeypatch
):
    """Verify that published record count mismatches fail reconciliation."""

    monkeypatch.setattr(
        run_pipeline,
        "MANIFEST_DIR",
        tmp_path
    )

    validation_metrics = {
        "source_records": {
            "order_items": 120
        },
        "accepted_records": {
            "order_items": 100
        },
        "rejected_records": {
            "order_items": 20
        }
    }

    transformation_metrics = {
        "fact_records": 100,
        "run_id": "test-run-id"
    }

    storage_metrics = {
        "records_published": 95,
        "datasets": {
            "daily": "published",
            "monthly": "published",
            "yearly_compacted": "published"
        }
    }

    monkeypatch.setattr(
        run_pipeline,
        "run_validation",
        lambda: validation_metrics
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_transformation",
        lambda run_metadata: transformation_metrics
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_storage",
        lambda: storage_metrics
    )

    with pytest.raises(
        ValueError,
        match="Publication record reconciliation failed"
    ):
        run_pipeline.main()

    manifest_files = list(tmp_path.glob("run_*.json"))
    assert len(manifest_files) == 1

    manifest = json.loads(
        manifest_files[0].read_text(encoding="utf-8")
    )

    assert manifest["status"] == "FAILED"
    assert manifest["failure"]["stage"] == "reconciliation"
    assert manifest["failure"]["error_type"] == "ValueError"

    assert (
        manifest["reconciliation"]["fact_records_match_published_records"]
        is False
    )

    assert manifest["stage_status"]["validation"] == "SUCCESS"
    assert manifest["stage_status"]["transformation"] == "SUCCESS"
    assert manifest["stage_status"]["storage"] == "SUCCESS"
    assert manifest["stage_status"]["reconciliation"] == "FAILED"



def test_successful_reconciliation_is_recorded(
    tmp_path, monkeypatch
):
    """Verify that all reconciliation checks pass."""

    monkeypatch.setattr(
        run_pipeline,
        "MANIFEST_DIR",
        tmp_path
    )

    validation_metrics = {
        "source_records": {
            "customers": 10,
            "order_items": 120
        },
        "accepted_records": {
            "customers": 9,
            "order_items": 100
        },
        "rejected_records": {
            "customers": 1,
            "order_items": 20
        }
    }

    transformation_metrics = {
        "fact_records": 100,
        "run_id": "test-run-id"
    }

    storage_metrics = {
        "records_published": 100,
        "datasets": {
            "daily": "published",
            "monthly": "published",
            "yearly_compacted": "published"
        }
    }

    monkeypatch.setattr(
        run_pipeline,
        "run_validation",
        lambda: validation_metrics
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_transformation",
        lambda run_metadata: transformation_metrics
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_storage",
        lambda: storage_metrics
    )

    result = run_pipeline.main()

    manifest_files = list(tmp_path.glob("run_*.json"))
    assert len(manifest_files) == 1

    manifest = json.loads(
        manifest_files[0].read_text(encoding="utf-8")
    )

    # Verify Schema Version Metadata
    assert manifest["schema_versions"]["customers"]["source_supported"] == [
    "v1", "v2"
]

    assert manifest["schema_versions"]["customers"]["target"] == "v2"

    assert result["status"] == "SUCCESS"
    assert manifest["status"] == "SUCCESS"

    assert manifest["reconciliation"]["passed"] is True

    assert all(
        entity["matches"]
        for entity in manifest["reconciliation"]["entity_counts"].values()
    )

    assert (
        manifest["reconciliation"]["accepted_items_match_fact_records"]
        is True
    )

    assert (
        manifest["reconciliation"]["fact_records_match_published_records"]
        is True
    )

    assert manifest["stage_status"]["validation"] == "SUCCESS"
    assert manifest["stage_status"]["reconciliation"] == "SUCCESS"
    assert manifest["stage_status"]["transformation"] == "SUCCESS"
    assert manifest["stage_status"]["storage"] == "SUCCESS"

    assert manifest["failure"] is None


