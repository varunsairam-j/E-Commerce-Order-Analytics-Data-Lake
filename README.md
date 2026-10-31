# E-Commerce Order Analytics Data Lake

## Project Overview

This project implements an end-to-end E-Commerce Order Analytics Data Lake using Python, PyArrow, and DuckDB.

It simulates a realistic e-commerce data environment, generates source datasets, introduces controlled data-quality defects, validates and processes incoming records, and publishes reliable analytical datasets in Apache Parquet format.

The pipeline is designed with a focus on data quality, data integrity, schema evolution, reproducibility, fault tolerance, and efficient analytical storage.


## Pipeline Architecture

The data lake follows a multi-stage processing workflow:

1. **Configuration:** Loads project settings, dataset parameters, and storage configurations.
2. **Data Generation:** Generates deterministic synthetic datasets for customers, products, orders, and order items.
3. **Defect Injection:** Introduces controlled data-quality issues into incoming datasets to simulate real-world scenarios.
4. **Validation:** Validates schemas, business rules, and referential integrity. Invalid records are rejected and quarantined.
5. **Reconciliation:** Verifies source, accepted, rejected, transformed, and published record counts to detect data loss.
6. **Transformation:** Joins validated datasets, calculates financial metrics, and creates the analytical fact table.
7. **Storage:** Publishes the processed data into partitioned Apache Parquet datasets.
8. **Benchmarking:** Evaluates partitioning strategies and query performance using DuckDB.

Each processing run is tracked through a unique run ID and a JSON manifest containing execution status, record counts, reconciliation results, and timing information.


## Dataset Overview

The project uses deterministic synthetic e-commerce data generated with a fixed random seed.

| Entity | Generated Records |
|---|---:|
| Customers | 10,000 |
| Products | 2,000 |
| Orders | 40,000 |
| Order Items | 120,000 |

**Fact Table Grain:** One record per order item within an order.
**Dataset Period:** January 1, 2024 – December 31, 2025

**Currency:** INR (Indian Rupees)

**Timezone:** UTC


### Data Quality Scenarios

Controlled defects are injected into incoming datasets to test the pipeline's validation and rejection mechanisms.

Scenarios include:

- Missing customer email addresses
- Invalid customer references
- Malformed order timestamps
- Invalid order statuses
- Exact duplicate order item records
- Conflicting duplicate order item IDs
- Invalid product references
- Invalid order quantities
- Discounts exceeding gross order-item amounts

Invalid records are rejected rather than silently included in the analytical dataset.


## Data Quality Results

The validation pipeline validates incoming records and separates accepted records from rejected records.

### Validation Summary

| Entity | Source Records | Accepted Records | Rejected Records |
|---|---:|---:|---:|
| Customers | 10,000 | 9,950 | 50 |
| Products | 2,000 | 2,000 | 0 |
| Orders | 40,000 | 39,640 | 360 |
| Order Items | 120,100 | 118,707 | 1,393 |
| **Total** | **172,100** | **170,297** | **1,803** |

The incoming order-items dataset contains 100 additional records introduced through defect injection.


### Reconciliation

The pipeline verifies the following condition for every entity:

`Source Records = Accepted Records + Rejected Records`

It also verifies that:

- Accepted order items match the number of transformed fact records.
- Transformed fact records match the number of published records.
- All three Parquet storage layouts contain the same number of published fact records.

These checks help prevent silent record loss during processing and publication.


## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Core pipeline development and orchestration |
| Pandas | Tabular data handling |
| PyArrow | Columnar data processing and Parquet storage |
| DuckDB | Analytical SQL queries and performance benchmarking |
| Pytest | Automated testing |
| Git & GitHub | Version control and project hosting |
| VS Code | Development environment |


### Key Capabilities

- Deterministic synthetic data generation
- CSV ingestion and schema validation
- Data-quality checks and record quarantine
- Customer schema evolution (V1 to V2)
- Relational joins and financial transformations
- Decimal-based financial calculations
- Partitioned Parquet storage
- Publication recovery and retry handling
- Run-level execution tracking and JSON manifests
- Automated testing and record reconciliation


## Analytical Data Model

The pipeline produces an analytical fact table named `fact_order_items`.


### Fact Table Grain

Each row represents **one order item within an order**.

The fact table combines validated information from:

- Order Items
- Orders
- Products


### Financial Calculations

| Metric | Calculation |
|---|---|
| Gross Amount | Quantity × Unit Price |
| Net Revenue | Gross Amount − Discount Amount |
| Recognized Revenue | Net Revenue when order status is Paid, Shipped, or Delivered; otherwise zero |

Revenue is recognized only for orders with the following statuses:

- Paid
- Shipped
- Delivered

Pending and cancelled orders contribute zero recognized revenue.


### Data Integrity

- Financial calculations use Python's `Decimal` type to avoid floating-point precision errors.
- Financial values are stored in Parquet using `DECIMAL(18,2)`.
- Timestamps are normalized to UTC.
- Each fact record contains run-level metadata, including `run_id`, `source_file`, and `ingested_at`.


## Parquet Storage and Partitioning Strategy

The project evaluates three storage layouts to understand the impact of partitioning and file sizing on analytical query performance.

| Storage Layout | Number of Files | Average File Size |
|---|---:|---:|
| Daily Partitioning | 717 | ~25.1 KiB |
| Monthly Partitioning | 24 | ~269.6 KiB |
| Yearly Compacted | 3 | ~1.83 MiB |

All three layouts contain the same 118,707 analytical records.


### Partitioning Comparison

- **Daily:** Provides fine-grained date filtering but generates many small files.
- **Monthly:** Reduces file count while retaining useful date-based partition pruning.
- **Yearly Compacted:** Produces fewer, larger files and reduces small-file overhead, but offers less granular partition pruning.


### Benchmark Results

Query performance was measured using DuckDB across seven repetitions, with median execution times recorded.

| Query Date | Daily | Monthly | Yearly Compacted |
|---|---:|---:|---:|
| 2024-03-15 | 301.754 ms | 14.802 ms | 5.657 ms |
| 2025-06-15 | 244.777 ms | 11.641 ms | 9.330 ms |
| 2025-11-10 | 253.713 ms | 11.955 ms | 7.924 ms |


### Conclusion

Monthly partitioning is recommended as a practical balance between partition pruning and file management for this dataset.

**Benchmark limitation:** These measurements reflect a relatively small dataset and a specific execution environment. They should not be treated as universal performance results. Cache effects, metadata overhead, and file discovery can also influence query timings.


## Reliability and Recovery

The storage publication process includes safeguards to reduce the risk of incomplete or interrupted dataset updates.


### Publication Safety

- Data is first written to a staging directory.
- The staged dataset is verified against the expected record count.
- Existing published data is moved to a backup before replacement.
- If publication fails, the previous dataset is restored.
- Temporary staging directories are cleaned up after publication.


### Retry Handling

File and directory rename operations use retry handling for transient Windows `PermissionError` exceptions.

The retry mechanism uses up to five attempts with increasing delays.


### Crash Recovery

The pipeline checks for interrupted publications before starting a new publication.

If the output directory is missing but a backup exists, the most recent backup is restored. Abandoned staging directories and stale backups are also cleaned up when appropriate.

Recovery is performed independently for each storage layout. Publication across all three layouts is not a single atomic transaction.


### Execution Tracking

Each pipeline execution generates a unique run ID and a JSON manifest containing:

- Execution status and timestamps
- Stage-level status
- Source, accepted, and rejected record counts
- Schema version information
- Transformation and publication metrics
- Reconciliation results
- Failure details, when applicable

These mechanisms improve traceability and recovery from transient publication failures.


## Testing and Verification

The project uses Pytest to validate individual components and end-to-end pipeline behavior.


### Test Coverage

Automated tests cover:

- Configuration loading and validation
- Synthetic source data generation
- Schema validation and schema evolution
- Missing values and malformed records
- Referential integrity
- Duplicate and conflicting records
- Business-rule validation
- Financial calculations and transformations
- Empty datasets and invalid input structures
- Parquet schema and record integrity
- Publication failure and rollback
- Backup recovery and abandoned staging cleanup
- Pipeline reconciliation and execution manifests


### Test Results

**Latest recorded test execution:**

- Total tests passed: 105
- Failed tests: 0

Run the complete test suite using:

```bash
pytest -v

## Project Structure

```text
E-Commerce-Order-Analytics-Data-Lake/
│
├── data/
│   ├── raw/
│   ├── incoming/
│   ├── accepted/
│   ├── processed/
│   ├── quarantine/
│   └── lake/
│       ├── daily/
│       ├── monthly/
│       └── yearly_compacted/
│
├── src/
│   ├── config_loader.py
│   ├── data_generator.py
│   ├── defect_injector.py
│   ├── pipeline.py
│   ├── transform.py
│   ├── storage.py
│   ├── run_pipeline.py
│   └── benchmark.py
│
├── tests/
│   ├── test_source_data.py
│   ├── test_pipeline.py
│   ├── test_transform.py
│   ├── test_storage.py
│   └── test_run_pipeline.py├── docs/
├── outputs/
│   ├── quarantine/
│   └── run_manifests/
│
├── config.json
├── requirements.txt
└── README.md


## Installation and Setup

### Prerequisites

- Python 3.12
- Anaconda or Miniconda
- Git


### 1. Clone the Repository and Navigate to the Project

```bash
git clone https://github.com/varunsairam-j/E-Commerce-Order-Analytics-Data-Lake.git
cd E-Commerce-Order-Analytics-Data-Lake
```
Replace `<YOUR_GITHUB_REPOSITORY_URL>` with the actual URL of the published GitHub repository.


### 2. Create and Activate the Conda Environment

```bash
conda create -n yottaflex python=3.12 -y
conda activate yottaflex
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify Configuration

```bash
python src/config_loader.py
```


## Running the Pipeline

Execute these commands from the project root directory.

### 1. Generate Synthetic Source Data

```bash
python src/data_generator.py
```

### 2. Inject Data Quality Defects

```bash
python src/defect_injector.py
```

### 3. Run the Complete Data Lake Pipeline

```bash
python src/run_pipeline.py
```
The pipeline generates a unique run ID and records execution details in a JSON manifest.


The orchestration process executes:

- Data validation
- Record reconciliation
- Data transformation
- Parquet dataset publication

### 4. Execute Automated Tests

```bash
pytest -v
```


## Additional Documentation

Detailed technical documentation is available in the `docs/` directory:

| Document | Description |
|---|---|
| [Data Dictionary](docs/data_dictionary.md) | Entity schemas, column definitions, data types, metadata, and business rules |
| [Dataset Design](docs/dataset_design.md) | Dataset generation strategy, entities, record counts, and design decisions |
| [Partitioning Analysis](docs/partitioning_analysis.md) | Storage layouts, file sizes, partition pruning, and benchmark results |
| [Reliability and Recovery](docs/reliability_and_recovery.md) | Publication safety, retry handling, rollback, and recovery mechanisms |


## AI Usage Disclosure

AI-assisted tools were used selectively as supplementary resources during project development.

They helped with understanding technical concepts, exploring implementation approaches, debugging issues, identifying edge cases, reviewing test scenarios, and improving documentation.

The project involved hands-on implementation, integration, execution, and verification. The developer independently worked through implementation issues, evaluated suggested approaches, validated pipeline outputs, executed automated tests, and made technical decisions throughout development.

All final implementation decisions and submitted results were reviewed and verified against the actual project.

The developer takes responsibility for the submitted code, its functionality, and the ability to explain the project's design and implementation.

