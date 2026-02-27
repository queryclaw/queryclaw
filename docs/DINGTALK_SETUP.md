# DingTalk Channel Setup Guide

> [中文版](DINGTALK_SETUP_CN.md)

This guide explains how to integrate QueryClaw with DingTalk so the Agent can receive questions and reply in the DingTalk app.

---

## Prerequisites

- DingTalk enterprise account (with app development permissions)
- Local or server access to DingTalk API (`api.dingtalk.com`, `wss-open-connection.dingtalk.com`)
- QueryClaw configured with database and LLM (see [USER_MANUAL.md](USER_MANUAL.md))

---

## 1. Install DingTalk Dependencies

```bash
pip install queryclaw[dingtalk]
```

Or install all optional dependencies:

```bash
pip install queryclaw[all]
```

---

## 2. Create App on DingTalk Open Platform

### 2.1 Log in to Developer Console

1. Open [DingTalk Open Platform](https://open-dev.dingtalk.com)
2. Log in with DingTalk scan
3. Select your development organization (requires app development permissions)

### 2.2 Create Application

1. Go to **Application Development** → **Internal Development** → **Robot**
2. Click **Create Application**
3. Fill in application name (e.g. "QueryClaw Database Assistant") and description
4. Click **Confirm**

### 2.3 Get Credentials

1. Open the application detail page
2. Click **Application Info** in the left sidebar
3. Copy **Client ID** (AppKey) and **Client Secret** (AppSecret)
4. Store them securely for QueryClaw configuration

### 2.4 Configure Robot

1. Click **Robot & Message Push** in the left sidebar
2. Enable **Robot Configuration**
3. **Receive Mode**: Select **Stream Mode** (recommended; no public IP or webhook URL required)
4. Fill in robot name, avatar, etc. (optional)
5. Click **Publish** to save

### 2.5 Configure Permissions

1. Click **Permission Management** in the left sidebar
2. Search and add:
   - **Robot receive message** (`im:bot:receive_message` or similar)
   - **Robot send message** (`im:bot:send_message` or similar)
   - **Get user info** (optional, for user identification)
3. Click **Request Permission** and wait for admin approval

### 2.6 Publish Application

1. Click **Version Management & Release** in the left sidebar
2. Create a version and fill in release notes
3. Select **Availability** (e.g. "All members" or specific test users)
4. Submit for release and wait for approval

---

## 3. Configure QueryClaw

### 3.1 Edit Config File

Edit `~/.queryclaw/config.json` (or path specified by `-c`), and set `channels.dingtalk`:

```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "client_id": "your Client ID (AppKey)",
      "client_secret": "your Client Secret (AppSecret)",
      "allow_from": []
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `enabled` | Set to `true` to enable DingTalk channel |
| `client_id` | DingTalk app Client ID (AppKey) |
| `client_secret` | DingTalk app Client Secret (AppSecret) |
| `allow_from` | List of allowed staff_ids; empty array allows all |

### 3.2 Restrict Access (Optional)

To allow only specific users, add their staff_ids to `allow_from`:

```json
"allow_from": ["staff_id_1", "staff_id_2"]
```

---

## 4. Start Service

```bash
queryclaw serve
```

On success, the terminal will show:

```
DingTalk bot started with Stream Mode
```

---

## 5. Use in DingTalk

### 5.1 Direct Message

1. Open DingTalk client
2. Search for your app name in the top search bar
3. Select the app and start a conversation
4. Send questions directly, e.g. "How many rows are in the users table?"

### 5.2 Group Chat (Current Limitation)

Currently, group messages are received but replies are sent to **direct message** only. Group reply support may be added in a future release.

---

## 6. Troubleshooting

### 6.1 Not Receiving Messages

| Cause | Check |
|-------|-------|
| Wrong credentials | Verify `client_id` and `client_secret` match the Open Platform, no extra spaces |
| Stream mode not selected | In "Robot & Message Push", confirm receive mode is Stream |
| Permissions not granted | In "Permission Management", confirm robot send/receive permissions are approved |
| App not published | In "Version Management & Release", confirm app is published and availability includes your user |
| serve not running | Ensure `queryclaw serve` is running |

### 6.2 No Reply When Sending Messages

| Cause | Check |
|-------|-------|
| Database/LLM config error | Verify `database` and `providers` in `config.json` |
| Network issue | Confirm server can reach `api.dingtalk.com` |
| Check logs | Terminal outputs `[DingTalk]` logs; use them for debugging |

### 6.3 "DingTalk Stream SDK not installed"

Run:

```bash
pip install queryclaw[dingtalk]
```

### 6.4 "client_id and client_secret not configured"

Verify `channels.dingtalk` in `config.json` has non-empty `client_id` and `client_secret`.

---

## 7. Full Config Example

```json
{
  "database": {
    "type": "sqlite",
    "database": "/path/to/your.db"
  },
  "providers": {
    "anthropic": {
      "api_key": "sk-xxx"
    }
  },
  "channels": {
    "dingtalk": {
      "enabled": true,
      "client_id": "dingxxxxxxxxxxxx",
      "client_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "allow_from": []
    }
  }
}
```

---

## 8. Comparison with Feishu

| Aspect | Feishu | DingTalk |
|--------|--------|----------|
| Receive mode | WebSocket long connection | Stream mode (WebSocket) |
| Public IP required | No | No |
| Credential fields | app_id, app_secret | client_id, client_secret |
| User ID | open_id | staff_id |
| Group reply | Supported | Direct message only (current) |
