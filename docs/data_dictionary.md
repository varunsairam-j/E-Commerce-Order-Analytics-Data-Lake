
# Data Dictionary and Data Contract

## Project
E-Commerce Order Analytics Data Lake

## 1. Source Entities

### customers.csv

Grain: One row per customer.

Supported Schema Versions:

**V1 — Original Schema**

| Column | Type | Key |
|---|---|---|
| customer_id | VARCHAR | Primary Key |
| customer_name | VARCHAR | |
| email | VARCHAR | |
| signup_date | DATE | |
| country | VARCHAR | |

**V2 — Evolved Schema**

V2 introduces an additional optional column.

| Column | Type | Key |
|---|---|---|
| customer_id | VARCHAR | Primary Key |
| customer_name | VARCHAR | |
| email | VARCHAR | |
| signup_date | DATE | |
| country | VARCHAR | |
| phone_number | VARCHAR | Optional |

V2 is the current target schema.

### products.csv
Grain: One row per product.

| Column | Type | Key |
|---|---|---|
| product_id | VARCHAR | Primary Key |
| product_name | VARCHAR | |
| category | VARCHAR | |
| unit_cost | DECIMAL(12,2) | |
| list_price | DECIMAL(12,2) | |

### orders.csv
Grain: One row per order.

| Column | Type | Key |
|---|---|---|
| order_id | VARCHAR | Primary Key |
| customer_id | VARCHAR | Foreign Key |
| order_timestamp | TIMESTAMP UTC | |
| order_status | VARCHAR | |
| shipping_country | VARCHAR | |

Allowed order statuses:
- pending
- paid
- shipped
- delivered
- cancelled

### order_items.csv
Grain: One row per product line within an order.

| Column | Type | Key |
|---|---|---|
| order_item_id | VARCHAR | Primary Key |
| order_id | VARCHAR | Foreign Key |
| product_id | VARCHAR | Foreign Key |
| quantity | INTEGER | |
| unit_price | DECIMAL(12,2) | |
| discount_amount | DECIMAL(12,2) | |

## 2. Relationships

- One customer can have many orders.
- One order can have many order items.
- One product can appear in many order items.
- Every order must reference an existing customer.
- Every order item must reference an existing order and product.

## 3. Business Rules

- Primary keys must not be null or duplicated.
- Customer email must be present and valid in format.
- Product cost and list price must not be negative.
- Order timestamps must be valid.
- Order status must belong to the approved status list.
- Order-item quantity must be a positive integer.
- Unit price and discount must not be negative.
- Discount must not exceed quantity multiplied by unit price.
- Invalid foreign-key references must be rejected.
- Conflicting duplicate identifiers must be flagged, not silently overwritten.

## 4. Analytical Dataset

Name: fact_order_items

Grain: Exactly one row per unique order_item_id.

Columns:
- order_item_id
- order_id
- order_timestamp
- order_date
- customer_id
- product_id
- product_category
- shipping_country
- quantity
- unit_price
- gross_amount
- discount_amount
- net_revenue
- order_status
- recognized_revenue
- run_id
- source_file
- ingested_at

## 5. Financial Calculations

gross_amount = quantity * unit_price

net_amount = gross_amount - discount_amount

Recognized revenue:
- paid: recognized
- shipped: recognized
- delivered: recognized
- pending: zero
- cancelled: zero

Currency: INR.

Financial calculations must use decimal arithmetic.

## 6. Storage and Partitioning

Source format: CSV

Analytical format: Parquet

Partition column: order_date

Layouts to compare:
1. Daily: year/month/day
2. Monthly: year/month

Both layouts must contain equivalent logical records and be evaluated using equivalent query workloads.

## 7. Technical Conventions

- Timestamps use UTC.
- Identifiers are deterministic.
- Dataset generation is reproducible using a fixed random seed.
- Rejected records retain source information and rejection reasons.
- Every pipeline execution has a unique run_id.
- File sizes and benchmark results must be measured, not assumed.

## 8. Customer Schema Evolution

The pipeline supports additive schema evolution for customer records.

### Supported Versions

| Version | Description |
|---|---|
| V1 | Original customer schema containing five columns |
| V2 | Adds the optional phone_number column |

### Compatibility Strategy

- Both V1 and V2 customer input schemas are supported.
- V1 records are accepted without requiring phone_number.
- When phone_number is absent, the pipeline assigns an empty string.
- V2 phone_number values are preserved during ingestion.
- Accepted customer records are standardized to V2.
- Unsupported schemas and missing required columns are rejected.

### Schema Version Tracking

Every pipeline execution records customer schema version metadata in its run manifest.

The metadata includes:
- Supported source schema versions.
- Target customer schema version.

Current configuration:
- Supported source versions: V1, V2.
- Target schema version: V2.
