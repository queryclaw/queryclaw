# Feishu Channel Setup Guide

> [中文版](zh/FEISHU_SETUP.md)

This guide explains how to integrate QueryClaw with Feishu so the Agent can receive questions and reply in the Feishu app.

---

## Prerequisites

- Feishu enterprise account (with app development permissions)
- Local or server access to Feishu API
- QueryClaw configured with database and LLM (see [USER_MANUAL.md](USER_MANUAL.md))

---

## 1. Install Dependencies

```bash
pip install queryclaw[feishu]
```

---

## 2. Create App on Feishu Open Platform

The Feishu channel uses **WebSocket long connection** — no public IP or domain required; only outbound access to Feishu APIs is needed.

1. **Create app**: Create an enterprise app at [Feishu Open Platform](https://open.feishu.cn/app).
2. **Get credentials**: In "Credentials & Basic Info", copy `App ID` and `App Secret`.
3. **Enable bot**: In "Features" → "Bot", enable the bot capability.
4. **Permissions**: In "Permissions", add:
   - `im:message` (receive, send, send in groups).
   - `im:message.p2p_chat` (receive and send private chat messages; required for 1:1 chat).
   - `im:message.group_at_msg` (receive @mentions in groups).
5. **Event subscription**: In "Events & Callbacks", select **"Use long connection to receive events"** and save.
   - **Important**: You must run `queryclaw serve` to establish the connection before saving can succeed.
6. **Publish app**: In "Version & Release", create a version and publish.
7. **Add bot**:
   - **Group chat**: Open the group → tap "⋯" (top right) → "Group bots" → "Add bot" → search for your app name and add. Then @mention the bot in the group to ask questions.
   - **Private chat**: In the Feishu client search bar, type your app name, select it, and start a conversation.

---

## 3. Configure QueryClaw

In `config.json`, set `channels.feishu`:

```json
"feishu": {
  "enabled": true,
  "app_id": "cli_xxx",
  "app_secret": "your_secret",
  "allow_from": []
}
```

---

## 4. Start Service

```bash
queryclaw serve
```

---

## 5. Troubleshooting

### Can find the app in search but private chat does not work?

| Cause | Check and fix |
|-------|---------------|
| **App availability** | When publishing, the "Availability" scope must include your user. In "Version & Release" → create new version → set availability to "All members" or add your org. Re-publish. |
| **Event subscription not saved** | "Events & Callbacks" must use "Use long connection to receive events" and save successfully. Run `queryclaw serve` first to establish the connection, then save. If save fails, check serve is running and network can reach Feishu. |
| **serve not running** | Ensure `queryclaw serve` is running; the bot cannot receive or reply when it is stopped. |
| **Permissions not granted** | In "Permissions", confirm `im:message`, `im:message.p2p_chat` etc. are applied and granted. Re-publish after adding new permissions. |

### Not receiving messages?

If the terminal shows no `[Feishu] Received event` after sending a message:

1. **Confirm WebSocket connected**: After starting `queryclaw serve`, the terminal should show `connected to wss://...` (from lark-oapi). If not, check `app_id`, `app_secret`, and network access to Feishu.
2. **Save event subscription while connected**: You must run `queryclaw serve` and wait for the connection to succeed, then go to "Events & Callbacks" → select "Use long connection to receive events" → add "Receive message" if prompted → save. Saving before the connection is established may fail.
