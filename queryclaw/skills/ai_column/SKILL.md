---
description: "Generate column values using LLM (summaries, sentiment, translations, scores)"
---
# AI Column

When the user asks to generate or populate a column using AI/LLM, follow these steps:

## 1. Understand the Request

Identify:
- **Source table** and **source column(s)** — the data the LLM will read
- **Target column** — where generated values will be stored (may or may not exist yet)
- **Generation type** — what kind of transformation:
  - Summary / abstract
  - Sentiment analysis (positive/negative/neutral)
  - Translation (language A -> B)
  - Classification / categorization
  - Score / rating
  - Custom prompt-based generation

## 2. Inspect the Schema

- Use `schema_inspect` with `action: describe_table` to check if the target column exists
- If the target column does NOT exist, use `ddl_execute` to create it:

```sql
ALTER TABLE table_name ADD COLUMN target_column TEXT;
```

- Choose the appropriate data type:
  - `TEXT` for summaries, translations, classifications
  - `REAL` / `FLOAT` for scores
  - `INTEGER` for ratings (1-5, etc.)

## 3. Sample and Preview

- Use `query_execute` to sample 3-5 rows:

```sql
SELECT id, source_column FROM table_name LIMIT 5;
```

- Generate values for these sample rows using the LLM (in your reasoning)
- Present the preview to the user for confirmation before proceeding

## 4. Batch Processing

- Use `query_execute` to get the total row count:

```sql
SELECT COUNT(*) FROM table_name WHERE target_column IS NULL;
```

- Process in batches of 10-20 rows:
  1. Fetch a batch: `SELECT id, source_column FROM table_name WHERE target_column IS NULL LIMIT 20`
  2. Generate values for each row using the LLM
  3. Update each row: `UPDATE table_name SET target_column = 'value' WHERE id = X`
  4. Use `data_modify` for each UPDATE statement

- For large tables (>100 rows), use `spawn_subagent` to delegate batch processing
- Wrap each batch in a transaction for consistency

## 5. Verify Results

After processing:
- Use `query_execute` to check completion:

```sql
SELECT COUNT(*) AS total, 
       COUNT(target_column) AS filled,
       COUNT(*) - COUNT(target_column) AS remaining
FROM table_name;
```

- Show a few sample results to the user

## Generation Prompt Templates

### Summary
For each row, generate a one-sentence summary of the source text.

### Sentiment
Classify as: positive, negative, or neutral. Return only the label.

### Translation
Translate the source text from [source language] to [target language].

### Classification
Given the categories [list], classify the source text. Return only the category name.

### Custom
Use the user's exact prompt template, substituting `{value}` with the source column value.

## Example Interaction

User: "Add a summary column to the products table based on the description"

Steps:
1. `schema_inspect` — check products table structure
2. `ddl_execute` — `ALTER TABLE products ADD COLUMN summary TEXT`
3. `query_execute` — sample 5 products, generate summaries as preview
4. User confirms
5. Process all rows in batches of 20
6. `query_execute` — verify all rows have summaries
