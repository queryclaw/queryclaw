# 反思：require_confirmation 配置被忽略

## 问题

当在配置中将 `safety.require_confirmation` 设为 `false` 时，DROP TABLE 等破坏性操作仍会弹出确认提示，用户显式偏好被忽略。

## 根因分析

### 1. 双层设计，集成不完整

安全层有两个职责：

| 层级 | 职责 | 示例 |
|------|------|------|
| **QueryValidator** | 识别*哪些*操作有风险（DROP、TRUNCATE、无 WHERE 的 DELETE） | `validation.requires_confirmation = True` |
| **SafetyPolicy** | 表达*用户偏好*（是否强制确认） | `policy.require_confirmation = False` |

工具同时接收两者，但**只按 validator 的结果行事**，从未在触发确认流程前检查 `policy.require_confirmation`。

### 2. 使用方式不一致

- **DataModifyTool**：对*行数阈值*使用了 `policy.requires_confirmation_for(rows)`，但把 `validation.requires_confirmation`（操作类型风险）当作无条件触发。
- **DDLExecuteTool**：只检查 `validation.requires_confirmation`，未参考 `policy.require_confirmation`。

### 3. 为何是「低级」问题

- 配置存在且正确从 `config.json` → `SafetyPolicy` → 工具传递。
- 策略方法 `requires_confirmation_for()` 已正确在 `require_confirmation=False` 时返回 False。
- 问题出在工具逻辑中**少了一个 AND**：需要 `validation.requires_confirmation AND policy.require_confirmation`，而不是只看前者。

## 类似风险排查

| 配置 | 是否使用 | 风险 |
|------|----------|------|
| `read_only` | ✓ 是 | 低 — 入口即检查 |
| `require_confirmation` | ✗ 否 | **已修复** |
| `max_affected_rows` | ✓ 是 | 低 — 通过 `requires_confirmation_for` |
| `allowed_tables` | ✓ 是 | 低 — 按表检查 |
| `blocked_patterns` | ✓ 是 | 低 — 传给 validator |
| `audit_enabled` | ✓ 是 | 低 — 调用 `audit.log` 前检查 |

**新增回归测试**：`audit_enabled=False`，防止将来误删该检查。

## 预防：测试策略

**原则**：对每个用于*关闭*某行为的配置，增加测试以验证该行为确实被关闭。

| 配置 | 新增测试 |
|------|----------|
| `require_confirmation=False` + DROP | `test_drop_no_confirmation_when_disabled` |
| `require_confirmation=False` + 无 WHERE 的 DELETE | `test_delete_without_where_no_confirmation_when_disabled` |
| `audit_enabled=False` | `test_audit_skipped_when_disabled`（DataModify + DDL） |

## 修复摘要

```python
# DDLExecuteTool：仅当 validator 与 policy 都要求时才确认
if validation.requires_confirmation and self._policy.require_confirmation:

# DataModifyTool：用 policy 控制整个确认分支
needs_confirm = self._policy.require_confirmation and (
    validation.requires_confirmation
    or self._policy.requires_confirmation_for(dry_result.estimated_rows)
)
```
