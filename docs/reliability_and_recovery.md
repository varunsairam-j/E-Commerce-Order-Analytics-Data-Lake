# Reliability and Recovery

## 1. Overview

The E-Commerce Order Analytics Data Lake pipeline implements reliability mechanisms to support repeated execution, safe dataset publication, failure recovery, and execution consistency.

The storage layer uses a staging-and-backup publication strategy to prevent an incomplete replacement dataset from directly overwriting the previously published dataset.

The pipeline also implements retry handling for temporary Windows directory-locking issues and recovery logic for interrupted publication operations.

### Key Reliability Features

- Safe publication using temporary staging directories.
- Backup preservation during dataset replacement.
- Exponential-backoff retries for directory rename operations.
- Rollback when replacement publication fails.
- Recovery of interrupted publication operations.
- Cleanup of abandoned staging directories.
- Record-count verification before publication.
- Execution manifests and reconciliation checks.

## 2. Dataset Publication Lifecycle

The storage module uses a staging-and-backup strategy when publishing Parquet datasets.

Each publication follows these steps:

1. **Recovery Check:** Check for interrupted publications and recover a previous dataset if necessary.
2. **Staging Creation:** Write the new Parquet dataset into a uniquely named temporary staging directory.
3. **Record Verification:** Reopen the staged dataset and verify that its record count matches the expected input record count.
4. **Resource Release:** Release PyArrow dataset references and trigger garbage collection before directory operations.
5. **Backup Creation:** If an existing published dataset is present, rename it to a uniquely named backup directory.
6. **Dataset Publication:** Rename the staging directory to the final published dataset location.
7. **Rollback:** If publication fails, attempt to restore the previous dataset from its backup.
8. **Backup Cleanup:** After successful publication, remove the previous backup.
9. **Staging Cleanup:** Remove any remaining staging directory during final cleanup.

### Directory Naming Convention

Temporary directories use unique identifiers to avoid naming conflicts.

| Directory Type | Naming Pattern |
|---|---|
| Published dataset | `daily/` |
| Staging directory | `.daily.<unique_id>.staging/` |
| Backup directory | `.daily.<unique_id>.backup/` |

The same naming convention applies to the monthly and yearly-compacted datasets.

### Publication Strategy

The previous published dataset is preserved until the replacement staging dataset has been written and verified.

The implementation uses directory renames rather than writing directly into the published dataset.

This reduces the risk of exposing partially written replacement data.

## 3. Retry Handling

Directory rename operations can occasionally fail on Windows because files or directories may be temporarily locked by the operating system or another process.

To handle temporary permission errors, the storage module implements a retry mechanism.

### Retry Configuration

- Maximum attempts: 5
- Initial delay: 0.5 seconds
- Backoff strategy: Exponential
- Retried exception: `PermissionError`

### Retry Schedule

| Attempt | Wait Before Retry |
|---|---:|
| 1 | 0.5 seconds |
| 2 | 1 second |
| 3 | 2 seconds |
| 4 | 4 seconds |
| 5 | Raise the exception if unsuccessful |

The retry mechanism is used for:
- Moving an existing published dataset to its backup directory.
- Publishing the staging directory.
- Restoring a backup after publication failure.
- Restoring backups during recovery.

If all attempts fail, the exception is propagated to the calling pipeline.

### Observed Behaviour

During actual pipeline execution on Windows, a temporary directory rename failure occurred.

The retry mechanism waited 0.5 seconds and successfully completed the rename operation on the next attempt.

This demonstrated that retry handling can resolve at least some temporary directory-locking issues in the project environment.

## 4. Rollback and Crash Recovery

The storage module implements recovery mechanisms to preserve previously published datasets when replacement operations are interrupted or unsuccessful.

### 4.1 Publication Rollback

If staging publication fails after the existing dataset has been moved to backup:

1. The publication exception is caught.
2. The backup directory is identified.
3. The previous dataset is restored to its original location using the retry mechanism.
4. The original publication exception is propagated.

The backup is removed only after successful publication of the replacement dataset.

A failed-publication test verifies that the previous dataset remains available and its contents are preserved.

### 4.2 Interrupted Publication Recovery

An application interruption may leave a backup directory without a published output directory.

During the next publication attempt, the recovery function:

1. Searches for backup directories matching the dataset naming convention.
2. Sorts available backups by modification time.
3. Restores the most recently modified backup if the published output is missing.
4. Removes other stale backups when a published output exists.
5. Removes abandoned staging directories.

### 4.3 Multiple Backup Handling

If multiple backup directories exist and the published output is missing, the recovery mechanism selects the most recently modified backup.

Automated tests verify that the newest backup is restored.

### 4.4 Recovery Limitations

The recovery mechanism uses directory existence and modification timestamps to make recovery decisions.

It does not independently validate the contents or completeness of an existing published dataset before treating it as available.

Recovery is performed separately for each partitioned dataset layout. The three layouts are not published as one atomic transaction.

## 5. Reliability Testing and Verification

Reliability mechanisms are verified through automated tests and actual pipeline executions.

### 5.1 Automated Test Coverage

The storage test suite covers:

- Initial Parquet dataset publication.
- Published record-count verification.
- Successful replacement of an existing dataset.
- Rollback after simulated publication failure.
- Restoration of a backup when the published output is missing.
- Removal of abandoned staging directories.
- Selection of the most recently modified backup.
- Empty dataset publication and reopening.
- Parquet schema and financial precision preservation.

### 5.2 Test Results

The complete project test suite passed:

| Test Category | Result |
|---|---:|
| Complete project test suite | 105 passed |
| Storage test suite | 21 passed |

### 5.3 End-to-End Verification

The pipeline was executed repeatedly against existing published datasets.

Observed results:

- Multiple consecutive executions completed successfully after retry handling was implemented.
- All three Parquet layouts were successfully republished.
- Each published layout contained 118,707 records.
- A temporary Windows directory-locking issue was successfully handled through retry.
- Execution manifests recorded successful pipeline stages and reconciliation results.

### 5.4 Failure Simulation

Controlled automated tests verified:

- Restoration of the previous dataset after simulated publication failure.
- Recovery after an interrupted publication.
- Cleanup of abandoned staging directories.
- Selection and restoration of the newest available backup.

These scenarios were tested using temporary directories and did not modify production datasets.

### 5.5 Latest Verified Execution

| Metric | Result |
|---|---|
| Run ID | `2bdc3e73c7fd4c398eb456cde8121904` |
| Pipeline Status | SUCCESS |
| Execution Duration | 11.641 seconds |
| Fact Records | 118,707 |
| Published Records | 118,707 |
| Reconciliation | Passed |
| Failure | None |

The latest execution manifest is stored under:

`outputs/run_manifests/run_2bdc3e73c7fd4c398eb456cde8121904.json`

### 5.6 Known Limitations

- Publication is atomic only at the individual dataset-directory replacement level, not across all three layouts as one transaction.
- Recovery does not independently validate an existing published dataset before considering it available.
- Retry handling addresses temporary `PermissionError` conditions but cannot guarantee recovery from persistent permission failures.
- Crash recovery has been verified through controlled simulations rather than an actual forced process termination.