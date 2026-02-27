# Reflection: require_confirmation Config Ignored

## The Bug

When `safety.require_confirmation` was set to `false` in config, DROP TABLE and other destructive operations still prompted for confirmation. The user's explicit preference was ignored.

## Root Cause Analysis

### 1. Two-Layer Design, Incomplete Integration

The safety layer has two distinct roles:

| Layer | Role | Example |
|-------|------|---------|
| **QueryValidator** | Identifies *what* operations are risky (DROP, TRUNCATE, DELETE without WHERE) | `validation.requires_confirmation = True` |
| **SafetyPolicy** | Encodes *user preference* (whether to enforce confirmation) | `policy.require_confirmation = False` |

The tools received both but **only honored the validator**. The policy's `require_confirmation` was never checked before triggering the confirmation flow.

### 2. Inconsistent Usage Pattern

- **DataModifyTool**: Used `policy.requires_confirmation_for(rows)` for the *row-count* threshold, but treated `validation.requires_confirmation` (operation-type risk) as unconditional.
- **DDLExecuteTool**: Checked only `validation.requires_confirmation`; never consulted `policy.require_confirmation`.

### 3. Why This Is "Low-Level"

- Config exists and is correctly passed from `config.json` → `SafetyPolicy` → tools.
- The policy method `requires_confirmation_for()` already respected `require_confirmation=False`.
- The bug was a **missing AND** in the tool logic: we needed `validation.requires_confirmation AND policy.require_confirmation`, not just the former.

## Similar Risks (Audit)

| Config | Used? | Risk |
|--------|-------|------|
| `read_only` | ✓ Yes | Low — checked at entry |
| `require_confirmation` | ✗ Was not | **Fixed** |
| `max_affected_rows` | ✓ Yes | Low — via `requires_confirmation_for` |
| `allowed_tables` | ✓ Yes | Low — checked per table |
| `blocked_patterns` | ✓ Yes | Low — passed to validator |
| `audit_enabled` | ✓ Yes | Low — checked before `audit.log` |

**Added regression tests** for `audit_enabled=False` to guard against future removal of that check.

## Prevention: Test Strategy

**Principle**: For every config that *disables* a behavior, add a test that verifies the behavior is actually disabled.

| Config | Test Added |
|--------|------------|
| `require_confirmation=False` + DROP | `test_drop_no_confirmation_when_disabled` |
| `require_confirmation=False` + DELETE without WHERE | `test_delete_without_where_no_confirmation_when_disabled` |
| `audit_enabled=False` | `test_audit_skipped_when_disabled` (DataModify + DDL) |

## Fix Summary

```python
# DDLExecuteTool: only confirm when BOTH validator and policy say so
if validation.requires_confirmation and self._policy.require_confirmation:

# DataModifyTool: gate entire confirmation branch on policy
needs_confirm = self._policy.require_confirmation and (
    validation.requires_confirmation
    or self._policy.requires_confirmation_for(dry_result.estimated_rows)
)
```
