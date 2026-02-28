# QueryClaw 定时任务设计（Cron + Heartbeat）

> [English](../DESIGN_SCHEDULER.md)

## 概述

定时任务支持**主动式数据库运维**：

- **Cron**：按固定时间执行用户定义任务（如每日索引检查、周报）。
- **Heartbeat**：Agent 定期巡查数据库，发现异常时主动报告。

两者均向消息总线注入提示，由 Agent 处理后将结果推送到已配置通道（飞书、钉钉），或在无通道时写入日志。

## 架构

```
CronService / HeartbeatService
        │
        │ InboundMessage (channel=cron|heartbeat)
        ▼
   MessageBus
        │
        ▼
   AgentLoop（按常规流程处理）
        │
        │ OutboundMessage
        ▼
   ChannelManager（广播到所有通道或写日志）
```

## 调度格式

| 格式 | 示例 | 含义 |
|------|------|------|
| `at HH:MM` | `at 09:00` | 每天 9:00 |
| `every Nm` | `every 30m` | 每 30 分钟 |
| `every Nh` | `every 1h` | 每小时 |
| `cron min hour day month weekday` | `cron 0 9 * * 1` | 周一 9:00 |

## 配置

完整配置说明见 [USER_MANUAL.md](USER_MANUAL.md#定时任务-cron)。

- **Cron**：`cron.enabled`、`cron.jobs[]`（含 `id`、`schedule`、`prompt`）。
- **Heartbeat**：`heartbeat.enabled`、`heartbeat.interval_minutes`、`heartbeat.prompt`。
- **通道**：在各通道（飞书、钉钉）中设置 `cron_chat_id`、`heartbeat_chat_id` 以接收输出。

## 输出路由

Agent 完成 cron 或 heartbeat 任务后：

1. `OutboundMessage` 的 `channel` 为 `"cron"` 或 `"heartbeat"`。
2. `ChannelManager._dispatch_outbound` 识别后**广播**到所有已启用通道。
3. 每个通道使用 `cron_chat_id` 或 `heartbeat_chat_id`（或 `default_chat_id`）。
4. 若所有通道均未配置 chat_id，则输出写入 `logger.info`。

## 运行模式

Cron 与 Heartbeat 仅在 **`queryclaw serve`** 模式下运行，与 agent 循环和通道管理器一起启动。若未启用任何通道但启用了 cron/heartbeat，serve 仍会运行，输出仅写入日志。

## 依赖

- `apscheduler>=3.10`（已包含在基础依赖中）
