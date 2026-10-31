# Partitioning and File-Sizing Strategy Analysis

## 1. Objective

Evaluate three time-based Parquet storage strategies for the E-Commerce Order Analytics Data Lake:

1. Daily partitioning
2. Monthly partitioning
3. Yearly partitioning with file compaction

The objective is to understand the trade-offs between partition pruning, file count, storage consumption, query performance, and the small-file problem.

All three datasets contain the same 118,707 analytical order-item records.

## 2. Technical Environment

| Component | Technology |
|---|---|
| Programming language | Python 3.12 |
| Storage format | Apache Parquet |
| Compression | Snappy |
| Query engine | DuckDB |
| Parquet processing | PyArrow |
| Benchmark repetitions | 7 per strategy and date |
| Partition column | order_date |

## 3. Partitioning Strategies

### 3.1 Daily Partitioning

- Partition columns: year, month, day
- Total Parquet files: 717
- Total storage: 18,455,875 bytes (18.46 MB)
- Average file size: approximately 25.1 KB
- Minimum file size: 5,720 bytes
- Maximum file size: 78,512 bytes

Daily partitioning provides the finest date-level partition pruning but produces a large number of small files.

### 3.2 Monthly Partitioning

- Partition columns: year, month
- Total Parquet files: 24
- Total storage: 6,624,755 bytes (6.62 MB)
- Average file size: approximately 269.6 KB
- Minimum file size: 24,361 bytes
- Maximum file size: 1,015,813 bytes

Monthly partitioning substantially reduces file count while retaining useful date-based partition pruning.

### 3.3 Yearly Partitioning with Compaction

- Partition column: year
- Maximum rows per file: 50,000
- Total Parquet files: 3
- Total storage: 5,489,743 bytes (5.49 MB)
- Average file size: approximately 1.83 MB
- Minimum file size: 972,565 bytes
- Maximum file size: 2,270,166 bytes

Yearly partitioning with compaction produces the fewest files and the lowest storage consumption among the tested strategies.

The configured target file size is 128 MB. This target was not reached because the generated dataset is relatively small. The implementation currently applies a maximum row count per file rather than guaranteeing a target file size in bytes.

## 4. Storage Comparison

| Metric | Daily | Monthly | Yearly Compacted |
|---|---:|---:|---:|
| Parquet files | 717 | 24 | 3 |
| Total size (MB) | 18.46 | 6.62 | 5.49 |
| Average file size (KB) | 25.1 | 269.6 | 1,787.0 |
| Records | 118,707 | 118,707 | 118,707 |

Compared with daily partitioning:

- Monthly partitioning produces approximately 96.65% fewer files and uses approximately 64.1% less storage.
- Yearly compacted partitioning produces approximately 99.58% fewer files and uses approximately 70.3% less storage.

These results demonstrate the reduction in small-file overhead achieved through coarser partitioning and compaction.

## 5. Data Integrity and Reconciliation

Before performance comparisons, all three Parquet datasets were independently verified using DuckDB.

| Integrity Metric | Daily | Monthly | Yearly Compacted |
|---|---:|---:|---:|
| Total records | 118,707 | 118,707 | 118,707 |
| Distinct order-item IDs | 118,707 | 118,707 | 118,707 |
| Total quantity | 356,620 | 356,620 | 356,620 |
| Recognized revenue (INR) | 1,872,484,005.17 | 1,872,484,005.17 | 1,872,484,005.17 |
| Critical null records | 0 | 0 | 0 |

All three layouts passed reconciliation.

This confirms that the physical storage strategy changes did not alter the underlying analytical business data.

Verification evidence: `benchmarks/dataset_verification.json`

## 6. Partition Pruning Evidence

DuckDB query-plan inspection was performed using the date 2025-11-10.

| Metric | Daily | Monthly | Yearly Compacted |
|---|---:|---:|---:|
| Total files | 717 | 24 | 3 |
| Files scanned | 1 | 1 | 2 |
| Files skipped | 716 | 23 | 1 |
| Partition filters | Year, Month, Day | Year, Month | Year |

All three strategies successfully demonstrated partition pruning.

### Interpretation

**Daily:** DuckDB scans only the requested day's file, providing the finest-grained pruning.

**Monthly:** DuckDB scans only the requested month's file, providing effective pruning with fewer files overall.

**Yearly Compacted:** DuckDB filters by year and scans both files belonging to 2025. It excludes the 2024 file, but cannot eliminate one of the two files within the 2025 partition.

This demonstrates the trade-off between partition granularity and file compaction.

## 7. Query Performance Benchmark

The same single-day analytical query was executed against all three layouts.

The query calculates:
- Number of order items
- Total quantity
- Total recognized revenue

The benchmark used three dates and seven repetitions per strategy and date. Execution order was rotated to reduce systematic order bias, and the median execution time was used for comparison.

| Date | Daily | Monthly | Yearly Compacted |
|---|---:|---:|---:|
| 2024-03-15 | 301.754 ms | 14.802 ms | 5.657 ms |
| 2025-06-15 | 244.777 ms | 11.641 ms | 9.330 ms |
| 2025-11-10 | 253.713 ms | 11.955 ms | 7.924 ms |

### Performance Findings

- Yearly compacted partitioning was fastest in all three tested queries.
- Monthly partitioning was consistently faster than daily partitioning.
- Daily partitioning was the slowest in all three tests despite scanning only one file.

The observed performance differences may reflect file discovery, metadata handling, caching, and execution overhead. The results do not establish that partition granularity alone caused the differences.

Benchmark evidence: `benchmarks/multi_date_benchmark.json`

## 8. Trade-Off Analysis

| Consideration | Daily | Monthly | Yearly Compacted |
|---|---|---|---|
| Partition pruning | Excellent | Good | Coarse |
| File count | Very high | Low | Very low |
| Small-file risk | High | Lower | Lowest in this test |
| Single-day query performance | Slowest in this test | Intermediate | Fastest in this test |
| Date-level data isolation | Excellent | Good | Limited |
| Storage consumption | Highest | Lower | Lowest |

No partitioning strategy is universally optimal. The appropriate design depends on the expected query workload, data volume, ingestion frequency, maintenance requirements, and file-size targets.

## 9. Final Recommendation

**Recommended strategy: Monthly partitioning.**

Although yearly compacted partitioning achieved the lowest execution times in the three tested queries, monthly partitioning offers a better balance for the intended time-based analytics workload.

Reasons:

1. Reduces the file count from 717 to 24.
2. Reduces storage consumption by approximately 64.1% compared with daily partitioning.
3. Scans only one file for the tested single-day query.
4. Provides more granular date-level partition pruning than yearly partitioning.
5. Avoids the excessive small-file creation observed with daily partitioning.

Yearly compaction remains useful as a file-management strategy for larger datasets, archival storage, and workloads where coarser time-based access is acceptable.

Daily partitioning may be appropriate when fine-grained date isolation, daily replacement, or date-specific ingestion is a major requirement.

## 10. Limitations and Future Improvements

1. The benchmark uses a dataset of 118,707 records. Larger datasets may produce different results.
2. Only three single-day query dates were tested. Date-range, monthly aggregation, and multi-year analytical workloads should also be benchmarked.
3. Execution times are specific to the local machine, DuckDB version, operating environment, and benchmark methodology.
4. The 128 MB target file size was not achieved. Actual file sizes were below this target because of the dataset's limited volume.
5. Future testing should evaluate larger datasets, byte-based file-size targets, and periodic compaction.
6. Additional repeated benchmark sessions on larger datasets would improve confidence in the performance conclusions.

## 11. Conclusion

The experiment demonstrates that partitioning and file sizing must be designed together.

Daily partitioning provides excellent partition pruning but creates excessive small files. Yearly compaction minimizes file count and storage consumption but provides coarser pruning. Monthly partitioning offers a practical balance between these competing requirements for the tested E-Commerce Order Analytics workload.