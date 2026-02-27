---
description: "Generate comprehensive documentation for database schema"
---
# Schema Documenter

When the user asks for schema documentation, follow these steps:

## 1. Discover the Full Schema

- Use `schema_inspect` with `action: list_tables` to get all tables
- For each table, use `schema_inspect` with `action: describe_table` to get columns
- Use `schema_inspect` with `action: list_indexes` to understand performance characteristics
- Use `schema_inspect` with `action: list_foreign_keys` to map relationships

## 2. Identify Relationships

- Trace foreign key chains to build an entity-relationship map
- Identify one-to-many, many-to-many (junction tables), and self-referencing relationships
- Note orphan tables (no foreign keys in or out)

## 3. Infer Business Context

- Use `query_execute` with `SELECT COUNT(*)` to gauge table importance
- Sample a few rows with `SELECT * FROM table LIMIT 5` for context
- Look at column names and types to infer business meaning
- Identify audit columns (created_at, updated_at, deleted_at)
- Identify soft-delete patterns (is_deleted, status)

## 4. Generate Documentation

Structure the output as:

### Overview
- Database type and total table count
- High-level description of the data domain

### Entity-Relationship Summary
- List each entity (table) with a one-line description
- Show relationships using arrows: `orders -> customers (customer_id)`

### Table Details
For each table:
- **Purpose**: Brief description of what it stores
- **Columns**: Name, type, constraints, business meaning
- **Indexes**: List with performance notes
- **Relationships**: Foreign keys and what they reference

### Data Quality Notes
- Tables with no primary key
- Columns that allow NULL but semantically should not
- Missing indexes on foreign key columns
- Unusual patterns (e.g., very wide tables, BLOB columns)
