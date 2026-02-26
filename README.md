# 🦞 QueryClaw

**The AI-Native Database Agent for Safe & Autonomous Operations.**

> 🚀 **Mission**: To bridge the gap between Natural Language and Transactional Database Operations with enterprise-grade safety.

QueryClaw is not just a Text-to-SQL chatbot. It is an intelligent agent that plans, validates, executes, and self-corrects database operations (CRUD + DDL) with built-in safety guardrails, transaction management, and audit trails.

## ✨ Key Features

- 🛡️ **Safety First**: AST-based static analysis, execution plan dry-runs, and auto-rollback mechanisms.
- 🧠 **Multi-Agent Planning**: Decomposes complex natural language tasks into atomic, transactional SQL steps.
- 🔗 **Business Context Aware**: RAG-powered understanding of schema, foreign keys, and business metrics.
- 🔄 **Self-Healing**: Automatically detects errors, rewrites SQL, and retries.
- 📜 **Full Audit**: Complete lineage from natural language prompt to before/after data snapshots.

## 🏗 Architecture

- **Core**: Python
- **Protocol**: Model Context Protocol (MCP) Ready
- **Support**: MySQL, PostgreSQL, SQLite (More coming soon)

## 🚀 Roadmap

- [ ] **Phase 1**: MVP - Safe Read-Only Queries & Schema RAG
- [ ] **Phase 2**: Write Operations with Dry-Run & Rollback
- [ ] **Phase 3**: Multi-Agent Planning & Human-in-the-Loop
- [ ] **Phase 4**: MCP Server & Ecosystem Integrations

## 🤝 Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting PRs.

## 📄 License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.

---
<p align="center">
  Made with ❤️ by the QueryClaw Team
</p>
