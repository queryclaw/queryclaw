---
description: "Analyze data patterns, summarize tables, generate insights"
---
# Data Analysis

When the user asks for data analysis, follow these steps:

## 1. Understand the Data

- Use `schema_inspect` with `action: list_tables` to see what tables are available
- Use `schema_inspect` with `action: describe_table` to understand the columns and types

## 2. Explore the Data

> **CRITICAL**: Every SQL you write must use **only** the column names returned
> by `describe_table`. Do not assume column names based on business context
> (e.g. do not guess `score`, `battery_level`, `department_id`, etc.).
> When joining tables, verify the exact FK column names via `describe_table`
> or `list_foreign_keys` before writing the JOIN condition.

- Use `query_execute` with SELECT queries to explore the data
- Start with `SELECT COUNT(*)` to understand table sizes
- Use `SELECT DISTINCT` to understand cardinality of key columns
- Check for NULL values in important columns

## 3. Analyze Patterns

- Look for trends over time (if date/timestamp columns exist)
- Calculate aggregates: COUNT, SUM, AVG, MIN, MAX
- Group by relevant dimensions
- Look for outliers or anomalies

## 4. Present Findings

- Summarize findings in clear, concise language
- Include key numbers and statistics
- Highlight any anomalies or interesting patterns
- Suggest follow-up questions the user might want to explore
