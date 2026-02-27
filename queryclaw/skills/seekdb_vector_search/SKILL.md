---
description: "SeekDB vector search, semantic search, AI_EMBED, hybrid search"
---
# SeekDB Vector Search

When the user asks for vector search, semantic search, similar documents, or hybrid search in SeekDB, follow these steps:

## 1. Check Schema

- Use `schema_inspect` to list tables and columns
- Identify columns with `VECTOR(dim)` type — these support vector similarity search

## 2. Vector Column and Index

If the table has no vector column yet:

```sql
CREATE TABLE t1 (
    id INT PRIMARY KEY,
    doc VARCHAR(500),
    embedding VECTOR(768),
    VECTOR INDEX idx_emb(embedding) WITH (distance=L2, type=hnsw)
);
```

## 3. Similarity Search

Use `l2_distance` or `cosine_distance` with `ORDER BY ... APPROXIMATE LIMIT k`:

```sql
SELECT id, doc FROM t1
ORDER BY l2_distance(embedding, '[0.1,0.2,...]')
APPROXIMATE LIMIT 10;
```

## 4. AI_EMBED (Text to Vector)

If the user wants to search by natural language, use `AI_EMBED`. Requires model/endpoint registered via `DBMS_AI_SERVICE`:

```sql
SELECT id, doc FROM t1
ORDER BY l2_distance(embedding, AI_EMBED('model_name', 'user query text'))
APPROXIMATE LIMIT 10;
```

## 5. Hybrid Search

Combine keyword filter with vector similarity:

```sql
SELECT id, doc FROM t1
WHERE doc LIKE '%keyword%'
ORDER BY l2_distance(embedding, '[...]')
APPROXIMATE LIMIT 10;
```

## 6. Present Results

- Return the query results clearly
- Explain the search logic if the user asks
