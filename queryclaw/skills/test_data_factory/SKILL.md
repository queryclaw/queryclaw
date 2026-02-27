---
description: "Generate semantically realistic test data respecting foreign key constraints"
---
# Test Data Factory

When the user asks to generate test data, follow these steps:

## 1. Analyze the Schema

- Use `schema_inspect` with `action: list_tables` to discover all tables
- Use `schema_inspect` with `action: describe_table` for each table to understand columns and types
- Use `schema_inspect` with `action: list_foreign_keys` to map all foreign key dependencies

## 2. Determine Insertion Order

- Build a dependency graph from foreign keys
- Topologically sort tables: parent tables (referenced) must be populated before child tables (referencing)
- Identify self-referencing tables and handle them with NULLable FK columns first, then update

## 3. Generate Data Strategy

Based on column types and names, generate realistic data:

| Column pattern | Generation strategy |
|---------------|-------------------|
| `email` | Realistic email addresses (e.g. `user42@example.com`) |
| `name`, `first_name`, `last_name` | Plausible human names |
| `phone` | Phone number format |
| `created_at`, `updated_at` | Recent timestamps in chronological order |
| `status` | Sample existing values first with `SELECT DISTINCT status`, then reuse |
| `price`, `amount` | Reasonable numeric ranges based on column type |
| `is_*`, `has_*` | Boolean-like values |
| FK columns | Reference valid IDs from the parent table |

## 4. Execute Insertions

- Use `data_modify` to insert data in dependency order (parent -> child)
- For large batches (>50 rows), use `spawn_subagent` to delegate the work
- Insert in batches of 10-20 rows per statement for efficiency
- Use `transaction` with `action: begin` before the batch, then `commit` at the end

## 5. Verify Results

- After insertion, use `query_execute` to verify row counts match expectations
- Check referential integrity: `SELECT ... LEFT JOIN ... WHERE parent.id IS NULL`
- Report a summary: tables populated, rows inserted, any issues encountered

## User Customization

Users may specify scenarios like:
- "100 users, each with 3-5 orders"
- "Include some orders with NULL shipping_date (pending orders)"
- "Generate anomalous data for testing (duplicates, edge cases)"

Adapt the generation strategy to match the user's scenario description.

## Example Interaction

User: "Generate 50 test users with orders"

Steps:
1. Inspect schema to find `users` and `orders` tables
2. Determine that `orders.user_id` references `users.id`
3. Insert 50 users first with `data_modify`
4. For each user, insert 1-5 orders referencing that user's ID
5. Verify with `query_execute`: `SELECT COUNT(*) FROM users` and `SELECT COUNT(*) FROM orders`
