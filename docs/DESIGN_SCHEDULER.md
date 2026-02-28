# QueryClaw Scheduler Design (Cron + Heartbeat)

> [中文版](zh/DESIGN_SCHEDULER.md)

## Overview

The scheduler enables **proactive database operations**:

- **Cron**: User-defined jobs run at fixed schedules (e.g. daily index check, weekly report).
- **Heartbeat**: Agent periodically inspects the database and reports anomalies.

Both inject prompts into the message bus; the Agent processes them and publishes results to configured channels (Feishu, DingTalk) or logs when no channel is configured.

## Architecture

```
CronService / HeartbeatService
        │
        │ InboundMessage (channel=cron|heartbeat)
        ▼
   MessageBus
        │
        ▼
   AgentLoop (processes as usual)
        │
        │ OutboundMessage
        ▼
   ChannelManager (broadcast to all channels or log)
```

## Schedule Formats

| Format | Example | Meaning |
|--------|---------|---------|
| `at HH:MM` | `at 09:00` | Daily at 9:00 |
| `every Nm` | `every 30m` | Every 30 minutes |
| `every Nh` | `every 1h` | Every hour |
| `cron min hour day month weekday` | `cron 0 9 * * 1` | Monday 9:00 |

## Configuration

See [USER_MANUAL.md](USER_MANUAL.md#cron) for full config schema.

- **Cron**: `cron.enabled`, `cron.jobs[]` with `id`, `schedule`, `prompt`.
- **Heartbeat**: `heartbeat.enabled`, `heartbeat.interval_minutes`, `heartbeat.prompt`.
- **Channels**: Set `cron_chat_id` and `heartbeat_chat_id` per channel (Feishu, DingTalk) to receive output.

## Output Routing

When the Agent produces a response for a cron or heartbeat task:

1. `OutboundMessage` has `channel="cron"` or `channel="heartbeat"`.
2. `ChannelManager._dispatch_outbound` detects this and **broadcasts** to all enabled channels.
3. For each channel, it uses `cron_chat_id` or `heartbeat_chat_id` (or `default_chat_id`).
4. If no channel has a configured chat ID, the output is logged with `logger.info`.

## Run Mode

Cron and Heartbeat run only in **`queryclaw serve`** mode. They are started alongside the agent loop and channel manager. If no channels are enabled but cron/heartbeat is enabled, serve still runs; output goes to logs.

## Dependencies

- `apscheduler>=3.10` (included in base dependencies)
