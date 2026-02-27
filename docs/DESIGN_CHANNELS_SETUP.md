# Design: Interactive Channel Setup

> [中文版](zh/DESIGN_CHANNELS_SETUP.md)

## Goal

Simplify Feishu/DingTalk onboarding with an interactive `queryclaw channels add` command and a permissions JSON template, reducing manual steps and copy-paste errors.

---

## Implementation Plan

### 1. New CLI Command: `queryclaw channels add`

**Location:** `cli/commands.py` (add `channels` subcommand group)

**Flow:**

```
queryclaw channels add [feishu|dingtalk]
```

1. Prompt user to choose channel (feishu / dingtalk) if not specified
2. Load existing config from `~/.queryclaw/config.json` (or `-c` path)
3. Interactive prompts:
   - **Feishu:** App ID, App Secret
   - **DingTalk:** Client ID (AppKey), Client Secret
4. Optionally: restrict to allowlist (comma-separated open_ids / staff_ids)
5. Write to config: set `enabled: true`, fill credentials
6. Print next steps (open platform checklist)

**Dependencies:** `typer`, `rich` (already used). Optional: `typer.Option` for non-interactive mode (e.g. `--app-id`, `--app-secret` for scripting).

### 2. Permissions JSON Template

**Location:** `queryclaw/data/feishu_permissions.json` (new file)

A JSON file that users can copy-paste into Feishu Open Platform → Permissions → Batch import.

```json
{
  "scopes": {
    "tenant": [
      "im:message",
      "im:message:readonly",
      "im:message:send_as_bot",
      "im:message.group_at_msg:readonly",
      "im:message.p2p_msg:readonly",
      "im:chat.access_event.bot_p2p_chat:read",
      "im:chat.members:bot_access",
      "im:resource"
    ]
  }
}
```

**CLI integration:** `queryclaw channels add feishu` prints the path to this file or shows a short instruction: "Batch import permissions from: `queryclaw data feishu-permissions`" (or embed minimal JSON in help).

### 3. Subcommand Structure

```
queryclaw channels add feishu [--config PATH]
queryclaw channels add dingtalk [--config PATH]
queryclaw channels status [--config PATH]   # optional: show enabled channels, mask secrets
```

`channels` becomes a Typer group; `add` and `status` are subcommands.

### 4. File Changes Summary

| File | Change |
|------|--------|
| `cli/commands.py` | Add `channels` Typer group, `add`, optional `status` |
| `queryclaw/data/feishu_permissions.json` | New: permissions template |
| `queryclaw/data/dingtalk_permissions.json` | New: DingTalk scope template (if applicable) |
| `docs/USER_MANUAL*.md` | Add "Quick setup via `channels add`" section |

---

## Expected Effect (User Experience)

### Before (current)

1. Open USER_MANUAL
2. Manually create app on Feishu
3. Manually add each permission one by one
4. Configure event subscription (remember to run serve first)
5. Publish app
6. Manually edit `config.json` with app_id, app_secret
7. Run `queryclaw serve`

### After (with `channels add`)

1. Run `queryclaw channels add feishu`
2. Follow prompts: paste App ID, App Secret (from Feishu)
3. Config is written automatically
4. CLI prints a short checklist:
   ```
   ✓ Config updated. Next steps:
   1. Create app at https://open.feishu.cn/app (if not done)
   2. Permissions → Batch import from: <path>/feishu_permissions.json
   3. Enable Bot, Event subscription (long connection, im.message.receive_v1)
   4. Publish app, add bot to group/DM
   5. Run: queryclaw serve
   ```
5. User completes Feishu steps (still manual, but guided)
6. Run `queryclaw serve`

### Effect Summary

| Aspect | Before | After |
|--------|--------|-------|
| Config editing | Manual JSON edit | Interactive prompts |
| Permissions | One-by-one in UI | Batch import from JSON |
| Checklist | Scattered in docs | Printed after `channels add` |
| Typos | Easy to make | Reduced (prompts validate format) |

---

## Optional Enhancements (Phase 2)

- **`queryclaw channels status`**: Show which channels are enabled, credential presence (masked), connection state if serve is running
- **Env var fallback**: Support `FEISHU_APP_ID`, `FEISHU_APP_SECRET` for non-interactive deploy
- **Validation**: After `channels add`, optionally ping Feishu API to verify credentials (adds network dependency)

---

## Effort Estimate

| Task | Effort |
|------|--------|
| `channels add feishu` | ~1–2 hours |
| `channels add dingtalk` | ~0.5 hour (similar pattern) |
| Permissions JSON + docs | ~0.5 hour |
| `channels status` (optional) | ~1 hour |

**Total (core):** ~2–3 hours.
