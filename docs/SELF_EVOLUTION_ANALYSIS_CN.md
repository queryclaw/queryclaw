# QueryClaw 的 Tools 与 Skills 能否支持自我演进？

> [English](SELF_EVOLUTION_ANALYSIS.md)

本文分析当前 **Tools** 与 **Skills** 的设计是否能让项目「自我演进」（例如由 Agent 或系统在运行中增加新能力），以及需要补足哪些部分。

---

## 简要结论

| 维度 | 当前能否自我演进 | 原因 |
|------|------------------|------|
| **Skills** | **部分可以 / 设计已就绪** | 声明式、基于文件、已有 workspace 支持；只缺 Agent 可用的安全「写技能」路径。 |
| **Tools** | **不能** | 工具是 Python 代码；Agent 无法在运行时定义或注册新工具。 |

因此：**Skills 只需做一次小范围扩展即可支持自我演进；Tools 在现有形态下不能**，除非引入额外机制（例如声明式 / DSL 工具或安全的「添加工具」API）。

---

## 1. 当前架构回顾

### Tools（工具）

- **是什么：** 实现 `Tool` 抽象基类的 Python 类（`name`、`description`、`parameters`、`execute()`）。
- **怎么用：** 在 Agent 初始化时通过 `_register_default_tools()` 注册到 `ToolRegistry`（schema_inspect、query_execute、explain_plan）。Agent 只能**调用**工具，不能创建或注册工具。
- **注册接口：** `ToolRegistry` 已有运行时的 `register()` / `unregister()`，但 Agent 循环和现有工具都没有向 LLM 暴露这一能力。

### Skills（技能）

- **是什么：** 带可选 YAML frontmatter 的 Markdown 文件（`SKILL.md`），描述如何完成某类任务（如「数据分析」）。
- **怎么用：** `SkillsLoader` 从 (1) **内置** `queryclaw/skills/` 与 (2) **工作区** `workspace/skills/`（若设置了 workspace）加载。技能名称与描述会汇总进 system prompt；完整内容可按需加载到上下文中。
- **不执行代码：** Skills 仅是文本，用于引导 Agent 行为，不作为代码执行。

---

## 2. 为什么 Skills 可以支持自我演进

- **声明式、纯文本：** 技能就是 Markdown，LLM 可以直接生成合法的 `SKILL.md` 内容（含 frontmatter），无需写代码。「新能力」在这里就是「新文本」，与 LLM 的输出形式匹配。
- **工作区已在设计内：** `SkillsLoader(workspace=...)` 已支持第二个目录（工作区技能）。新技能的「存放位置」已存在，只差让 Agent（或用户）把文件写进去的途径。
- **不执行代码：** 新增技能不需要执行用户/Agent 生成的代码，只需写文件，安全面小（写操作限定在技能目录内）。
- **即时生效：** 新的 `SKILL.md` 一旦写入工作区（或可重载的内置路径），下次构建 system prompt 时 `SkillsLoader` 就会列出并加载，行为即可演进，无需重新部署应用。

**当前缺失：**  
Agent **没有任何可以创建或更新文件**的工具（例如「将内容写入 `workspace/skills/<name>/SKILL.md`」）。设计已就绪，但「写技能」的路径未暴露。增加一个受限工具（例如 `create_skill(name, content)`，仅允许写入指定技能目录）即可在实践中让 Skills 支持自我演进。

---

## 3. 为什么 Tools 当前不能自我演进

- **工具即代码：** 每个工具都是 Python 类。要「新增工具」，系统要么执行新代码（例如动态加载新的 `Tool` 实现），要么解释某种非代码定义；当前代码库对 Agent 生成的定义两者都不支持。
- **没有对 Agent 可见的「添加工具」API：** Agent 只能看到 `get_definitions()`（用于调用）和 `execute()`，无法调用类似「register_tool(name, description, parameters, handler)」的接口。即便日后有安全 handler（如 DSL），也需要把注册能力暴露给 Agent。
- **安全与正确性：** 若允许 Agent 将任意生成代码作为新工具执行，需要沙箱、校验和严格限制，设计量远大于为 Skills 增加一个写文件工具。

因此：**在「工具 = 仅 Python 类」的当前设计下，系统无法通过新增工具自我演进**，除非引入额外层次（例如声明式工具，或带安全解释器/DSL 的受限「添加工具」API）。

---

## 4. 自我演进的可行方向

### Skills（最小改动）

- 增加 **create_skill**（或 **write_skill**）工具：
  - 允许路径：仅限 `workspace/skills/<name>/SKILL.md`（或可配置的技能目录）。
  - 输入：技能名称 + Markdown 内容（可选 frontmatter）。
- 可选：**reload_skills** 或「刷新上下文」步骤，使同一会话无需重启即可看到新技能。

这样 Agent（或独立的「技能编写」流程）即可用自然语言创建新技能；项目通过磁盘上积累的技能实现演进。

### Tools（较大设计）

- **方案 A — 声明式 / DSL 工具：**  
  引入一类**由数据定义**的工具（例如参数化 SQL 模板或小型 DSL）。Agent（或单独流程）通过创建定义（如 JSON/YAML 文件或表中的一行）来「添加工具」，由现有「元工具」或引擎解释，新能力无需新增 Python 代码即可出现。

- **方案 B — 对 Agent 可见的注册（进阶）：**  
  提供安全的「register_tool」机制（如 name + schema + 已知安全 handler 类型的引用）。Agent 仍不能上传任意代码，但可启用预先批准的「模板」或插件，需要权限与 schema 的谨慎设计。

- **方案 C — 工具保持仅代码、仅技能演进：**  
  所有新「能力」都通过新 Skills 表达（组合现有工具的工作流），工具集合由开发者维护、固定不变，自我演进仅限 Skills。

---

## 5. 总结

| 问题 | 答案 |
|------|------|
| **当前** Tools + Skills 设计能否支持自我演进？ | **Skills：** 设计就绪，实践中只需一条安全的「写技能」路径。**Tools：** 不能，工具是代码且 Agent 无法添加或注册新工具。 |
| 为什么 Skills 可以？ | 声明式、基于文件、工作区已在模型中、不执行代码、仅影响 prompt。 |
| 为什么 Tools 目前不行？ | 工具是 Python 代码；没有对 Agent 可见的定义/注册方式，安全地做到这一点需要新机制（DSL、安全解释器或受限注册 API）。 |
| 建议的下一步 | 实现受限的 **create_skill**（或 **write_skill**）工具，可选 **reload_skills**，使项目通过新 Skills 自我演进；Tools 暂时仅通过代码/配置扩展，除非后续单独设计声明式工具或注册机制。 |
