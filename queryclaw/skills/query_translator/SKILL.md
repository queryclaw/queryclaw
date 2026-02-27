---
description: "Translate SQL queries between different database dialects"
---
# Query Translator

When the user asks to translate a SQL query between dialects, follow these steps:

## 1. Identify Source and Target

- Determine the source dialect (MySQL, SQLite, PostgreSQL, SQL Server, Oracle, etc.)
- Determine the target dialect
- If the source is not specified, use `schema_inspect` with `action: list_tables` to detect the current database type

## 2. Analyze the Source Query

- Parse the query to understand its intent
- Identify dialect-specific features used:
  - String functions: `CONCAT` vs `||`, `SUBSTRING` vs `SUBSTR`
  - Date functions: `DATE_FORMAT` vs `strftime` vs `TO_CHAR`
  - Limit syntax: `LIMIT` vs `TOP` vs `FETCH FIRST`
  - Auto-increment: `AUTO_INCREMENT` vs `AUTOINCREMENT` vs `SERIAL`/`IDENTITY`
  - Data types: `INT` vs `INTEGER`, `VARCHAR` vs `TEXT`, `DATETIME` vs `TIMESTAMP`
  - Quoting: backticks vs double-quotes vs square brackets
  - Boolean: `TINYINT(1)` vs `BOOLEAN`
  - JSON functions: `JSON_EXTRACT` vs `->>`
  - Upsert: `ON DUPLICATE KEY UPDATE` vs `ON CONFLICT DO UPDATE`
  - Full-text search syntax

## 3. Translate with Verification

- Rewrite the query in the target dialect
- Use `explain_plan` on both versions (if both databases are available) to confirm semantic equivalence
- If only the current database is available, run `explain_plan` on the translated query to verify it parses correctly

## 4. Present the Result

- Show the original and translated queries side by side
- Highlight key differences with brief explanations
- Note any features that have no direct equivalent and explain the workaround used
- Warn about potential behavioral differences (e.g., collation, NULL handling, implicit type coercion)

## Common Translation Patterns

| Feature | MySQL | PostgreSQL | SQLite |
|---------|-------|------------|--------|
| String concat | `CONCAT(a, b)` | `a \|\| b` | `a \|\| b` |
| Limit | `LIMIT n` | `LIMIT n` | `LIMIT n` |
| Upsert | `ON DUPLICATE KEY UPDATE` | `ON CONFLICT DO UPDATE` | `ON CONFLICT DO UPDATE` |
| Auto ID | `AUTO_INCREMENT` | `SERIAL` / `GENERATED ALWAYS` | `AUTOINCREMENT` |
| Current time | `NOW()` | `NOW()` | `datetime('now')` |
| IF/IIF | `IF(cond, a, b)` | `CASE WHEN ... END` | `IIF(cond, a, b)` |
| JSON access | `JSON_EXTRACT(col, '$.key')` | `col->>'key'` | `json_extract(col, '$.key')` |
