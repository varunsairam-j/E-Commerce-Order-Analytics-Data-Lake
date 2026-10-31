
# Synthetic Dataset Design

## 1. Project
E-Commerce Order Analytics Data Lake

## 2. Dataset Scale

| Entity | Target Records |
|---|---:|
| Customers | 10,000 |
| Products | 2,000 |
| Orders | 40,000 |
| Order Items | 100,000+ |

The generator must support configurable record volumes.

## 3. Date Range

Start Date: 2024-01-01

End Date: 2025-12-31

All order timestamps must use UTC.

## 4. Business Characteristics

- Multiple product categories.
- Customers from different countries.
- Multiple products per order.
- Realistic order status distribution.
- Varied quantities, prices and discounts.
- Orders distributed across the date range.
- Seasonal variation in order volume.

## 5. Data Quality Scenarios

The generated raw data will include controlled examples of:

1. Missing required values.
2. Exact duplicate records.
3. Conflicting duplicate primary keys.
4. Invalid quantities and prices.
5. Invalid foreign-key references.
6. Malformed timestamps.
7. Discounts exceeding gross amounts.
8. Invalid order statuses.

The generator must record the expected number and type of injected defects.

## 6. Reproducibility

- Use a configurable random seed.
- Use deterministic identifiers.
- Identical configurations must produce identical logical records.
- Separate clean baseline data generation from controlled defect injection.

## 7. Benchmarking

- Generate at least 100,000 order-item records.
- Compare daily and monthly partition layouts.
- Compare small-file output with compacted output.
- Use equivalent data and query workloads.
- Record actual file counts, file sizes and execution times.
- Do not assume performance improvements without measurements.

## 8. Validation Expectations

- Reconcile source, accepted and rejected records.
- Verify primary-key uniqueness.
- Verify foreign-key integrity.
- Verify monetary calculations.
- Verify partition completeness.
- Verify idempotent reruns.
