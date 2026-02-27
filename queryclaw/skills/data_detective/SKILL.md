---
description: "Detect data quality issues, anomalies, and inconsistencies"
---
# Data Detective

When the user asks for data quality analysis or anomaly detection, follow these steps:

## 1. Profile the Table

- Use `schema_inspect` with `action: describe_table` to understand the schema
- Run basic profiling queries:

```sql
SELECT COUNT(*) AS total_rows FROM table_name;

SELECT
  COUNT(*) AS total,
  COUNT(DISTINCT column_name) AS distinct_count,
  COUNT(*) - COUNT(column_name) AS null_count
FROM table_name;
```

- For numeric columns, compute min, max, avg, stddev
- For string columns, check min/max length and distinct count

## 2. Detect Common Issues

### Null Analysis
- Find columns with unexpected NULLs (especially NOT NULL business-critical fields)
- Calculate NULL percentage per column

### Duplicate Detection
- Check for duplicate rows on primary key or unique constraints
- Find near-duplicates on business keys:

```sql
SELECT column1, column2, COUNT(*)
FROM table_name
GROUP BY column1, column2
HAVING COUNT(*) > 1;
```

### Referential Integrity
- Use `schema_inspect` with `action: list_foreign_keys` to find relationships
- Check for orphan records:

```sql
SELECT child.id FROM child_table child
LEFT JOIN parent_table parent ON child.parent_id = parent.id
WHERE parent.id IS NULL;
```

### Value Distribution
- Find columns with extreme skew (one value dominates)
- Detect outliers in numeric columns using IQR or stddev thresholds

## 3. Temporal Analysis (if date columns exist)

- Check for gaps in time series data
- Find records with future dates or impossibly old dates
- Detect sudden spikes or drops in record creation rate:

```sql
SELECT DATE(created_at) AS day, COUNT(*) AS cnt
FROM table_name
GROUP BY DATE(created_at)
ORDER BY day;
```

## 4. Cross-Table Consistency

- Verify that status columns have consistent values
- Check that totals match (e.g., order total vs sum of line items)
- Look for logical contradictions (e.g., end_date < start_date)

## 5. Report Findings

Structure the report as:

### Summary
- Total rows analyzed
- Overall data quality score (percentage of rows without issues)

### Critical Issues
- Issues that indicate data corruption or application bugs
- Include example rows and counts

### Warnings
- Issues that may be intentional but worth reviewing
- Include distribution statistics

### Recommendations
- Suggested fixes or constraints to add
- Monitoring queries to run periodically
