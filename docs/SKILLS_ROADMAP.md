# QueryClaw Skills Roadmap

> Chinese version: [SKILLS_ROADMAP_CN.md](SKILLS_ROADMAP_CN.md)

This document lists the functional scenarios that queryclaw can implement through its Skill system, organized by developer workflow stages. Each Skill is annotated with its core value proposition (what traditional tools cannot do but an Agent can) and suggested priority.

---

## I. Development

### 1. AI Column

> Full design document: [DESIGN_AI_COLUMN.md](DESIGN_AI_COLUMN.md)

Generate or fill a target column based on existing table data using LLM -- summaries, classifications, translations, scores, tags, and more. Goes beyond the deterministic expression limits of traditional computed columns.

### 2. Test Data Factory

**Pain point**: Creating test data for unit/integration tests is painful -- must satisfy FK constraints, field formats, business rules, and data distributions.

**What the Skill does**:
- Analyze table structure, FKs, and constraints; understand inter-table dependency order
- Generate **semantically realistic** fake data using LLM (not gibberish, but plausible names, addresses, orders)
- Insert in correct order (parent tables before child tables)
- Support specifying volume and scenarios ("generate 100 users, each with 3-5 orders, include some edge cases")

**Value**: Traditional Faker libraries produce random fills without understanding business semantics. The Agent infers reasonable data from schema and table names.

### 3. Schema Documenter

**Pain point**: Databases lack documentation; new team members don't know the business meaning of tables and columns.

**What the Skill does**:
- Traverse all tables/columns/FKs/indexes
- LLM infers business meaning from naming conventions and data sampling
- Generate Markdown schema documentation (table descriptions, column descriptions, ER relationship narratives)
- Optionally write to the database's `COMMENT` fields

**Value**: Traditional tools can only export structure, not infer meaning. LLM can understand and describe business context from names like `order_status` and `created_at`.

### 4. API Scaffolding

**Pain point**: Writing CRUD endpoints for every table is repetitive work.

**What the Skill does**:
- Read table structure, understand field types and relationships
- Generate CRUD code for the target framework (FastAPI / Express / Spring Boot, etc.)
- Include parameter validation, pagination, sorting, and relational queries

**Value**: Smarter than traditional codegen -- can decide which fields are writable vs read-only, and how to implement search filtering based on business semantics.

---

## II. Debugging & Investigation

### 5. Data Detective

**Pain point**: When a production bug occurs, quickly locating "why is this data wrong" requires tedious manual investigation.

**What the Skill does**:
- User describes the issue ("user ID 12345 has wrong order status")
- Agent automatically traces related tables: `users → orders → payments → refunds`
- Constructs the complete data lineage, identifies the anomaly point
- Explains the root cause in natural language

**Value**: Developers typically need to write multiple JOIN queries manually to trace data flow. The Agent automatically follows foreign keys like a database detective.

### 6. Query Translator

**Pain point**: Encountering a complex SQL (dozens of lines with JOINs, subqueries, window functions) and not understanding what it does.

**What the Skill does**:
- Input a SQL statement, output a natural language explanation (step-by-step breakdown)
- Identify potential issues (missing indexes, Cartesian products, N+1)
- Suggest optimized rewrites

**Value**: Traditional tools can only do EXPLAIN, not "explain." LLM translates SQL into human language.

---

## III. Data Quality & Governance

### 7. Data Healer

**Pain point**: Databases inevitably contain dirty data -- orphaned records, inconsistent formats, values violating business rules.

**What the Skill does**:
- Scan FK integrity (find orphaned records)
- Check format consistency (phone numbers, emails, date formats)
- Use LLM to identify semantic errors (e.g., inconsistent city name spellings: "Beijing" vs "BeiJing" vs "beijing")
- Propose repair plans and execute (with human confirmation)

**Value**: Traditional SQL can only do rule-based checks, not semantic-level dirty data identification.

### 8. Data Masker

**Pain point**: Dev/test environments need realistic structure but anonymized data.

**What the Skill does**:
- Auto-identify PII columns (LLM infers from column names and sampling: names, phone numbers, IDs, emails, addresses...)
- Generate **semantically realistic** substitute data (not `***`, but another plausible fake name/address)
- Maintain relational consistency across tables (same person's name stays consistent across multiple tables)

**Value**: Traditional masking tools require manual marking of sensitive columns. The Agent identifies them automatically.

### 9. Anomaly Scanner

**Pain point**: Are there outliers, statistical anomalies, or suspicious patterns in the data? Hard for humans to discover manually.

**What the Skill does**:
- Distribution analysis on numeric columns (mean, std deviation, outliers)
- Frequency analysis on categorical columns (find extremely low-frequency anomalous values)
- Trend detection on time-series data (spikes, drops, gaps)
- LLM synthesizes findings and suggests possible business explanations

**Value**: Traditional BI tools require the user to already know what to look for. The Agent proactively scans and discovers problems you didn't know existed.

---

## IV. Performance & Operations

### 10. Index Advisor

**Pain point**: Which queries are slow? What indexes to add? Will they hurt write performance?

**What the Skill does**:
- Analyze slow query logs / `SHOW PROCESSLIST`
- Run EXPLAIN on slow queries, identify full table scans, filesorts, etc.
- Suggest indexes (including column order for composite indexes)
- Assess impact on write performance
- Generate `CREATE INDEX` statements (execute after confirmation)

### 11. Change Impact Analyzer

**Pain point**: Before modifying table structure, unclear what queries or applications will be affected.

**What the Skill does**:
- User says "I want to make users.email NOT NULL"
- Agent analyzes: how many NULL values exist? What FK dependencies are there?
- Assesses impact scope
- Generates a safe migration plan (fill data first, then add constraint)

### 12. Capacity Planner

**Pain point**: How long will the tables last? When will scaling be needed at the current growth rate?

**What the Skill does**:
- Collect row counts, data sizes, and growth rates per table
- Analyze index size proportions
- Predict storage needs for the next N days/months
- Suggest partitioning, archiving, or cleanup strategies

---

## V. Compliance & Security

### 13. Compliance Scanner

**Pain point**: Does the database meet GDPR / PCI-DSS / other regulatory requirements?

**What the Skill does**:
- Scan all columns, identify potential PII storage (LLM semantic inference)
- Check for plaintext passwords or credit card numbers
- Review access permissions against principle of least privilege
- Generate compliance reports and remediation recommendations

### 14. Permission Auditor

**Pain point**: Database user permissions are messy; nobody knows who has what access.

**What the Skill does**:
- List all users/roles and their privileges
- Identify over-privileged accounts (e.g., application users with DROP permissions)
- Suggest permission tightening plans
- Generate `REVOKE` / `GRANT` statements

---

## VI. Data Migration & Evolution

### 15. Smart Migrator

**Pain point**: Writing schema migration scripts is complex and error-prone.

**What the Skill does**:
- User describes desired schema changes in natural language
- Agent analyzes current schema, generates DDL migration scripts
- Auto-generates rollback scripts
- Dry-run preview of impact (row counts, estimated lock time)
- Execute in sequence (after confirmation)

### 16. Cross-DB Sync Checker

**Pain point**: Schema or data inconsistencies across environments (dev/test/production).

**What the Skill does** (requires multi-database connection support):
- Compare schema differences between two databases
- Compare key table data differences (row counts, checksums)
- Generate sync scripts

---

## Priority Overview

| Priority | Skill | Suggested Phase | Core Value |
|----------|-------|----------------|------------|
| **High** | AI Column | Phase 2 | Core differentiator; impossible with traditional tools |
| **High** | Test Data Factory | Phase 2 | High-frequency developer need |
| **High** | Data Detective | Phase 2 | Essential debugging tool |
| **High** | Schema Documenter | Phase 2 | Essential for onboarding |
| Medium | Query Translator | Phase 2 | Low cost, high value |
| Medium | Index Advisor | Phase 3 | DBA-level capability for all developers |
| Medium | Data Healer | Phase 3 | Core data governance |
| Medium | Anomaly Scanner | Phase 3 | Proactive problem detection |
| Medium | Data Masker | Phase 3 | Security & compliance |
| Medium | Smart Migrator | Phase 3 | Operations scenario |
| Low | Change Impact Analyzer | Phase 3 | Advanced operations |
| Low | Capacity Planner | Phase 4 | DBA scenario |
| Low | Compliance Scanner | Phase 4 | Enterprise scenario |
| Low | Permission Auditor | Phase 4 | Enterprise scenario |
| Low | API Scaffolding | Phase 4 | Development productivity |
| Low | Cross-DB Sync Checker | Phase 4+ | After multi-DB support |

---

The common thread across all Skills: **they leverage LLM semantic understanding to do what traditional database tools cannot**. This is the core differentiation of queryclaw as an AI-native database Agent.
