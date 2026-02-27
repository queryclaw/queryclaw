# 通道模式交互式确认 — 技术方案

## 问题

当 `safety.require_confirmation` 为 true 时，破坏性操作（INSERT/UPDATE/DELETE/DDL）需要用户确认。CLI 模式下通过 stdin 提示；通道模式下传入 `confirmation_callback=None`，工具直接返回错误并拒绝执行。

**目标**：在通道模式（飞书、钉钉）下支持交互式确认，让用户通过聊天回复「确认」或「取消」。

---

## 方案：待确认队列 + 消息路由

### 核心思路

1. 工具需要确认时，为当前会话注册**待确认项**。
2. 向通道发送：「以下操作需要确认：[摘要]。回复 **确认** 执行，**取消** 取消。」
3. **拦截**该会话的下一条入站消息：若为确认/取消，则解析并完成待确认项，**不**转发给 Agent。
4. 工具的确认回调等待结果，继续执行或中止。

### 关键难点：消息路由

Agent 通过 `bus.consume_inbound()` 消费消息。工具执行并等待确认时，Agent 被阻塞。用户回复「确认」或「取消」会进入入站队列，需要被路由到待确认逻辑，而不是 Agent。

**做法**：在 `bus.publish_inbound()` 处拦截。入队前检查该 `msg.session_key` 是否有待确认项；若有，则解析并 resolve，不入队；否则正常入队。

---

## 实现设计

### 1. ConfirmationStore（在 MessageBus 或独立模块）

```python
class ConfirmationStore:
    """按会话维护待确认项。"""
    def __init__(self):
        self._pending: dict[str, tuple[asyncio.Future[bool], str]] = {}

    def register(self, session_key: str, future: asyncio.Future[bool], summary: str) -> None:
        self._pending[session_key] = (future, summary)

    def resolve(self, session_key: str, content: str) -> bool | None:
        """若有待确认，解析 content 并 resolve。返回 True/False 表示已处理，None 表示无待确认。"""
        entry = self._pending.pop(session_key, None)
        if entry is None:
            return None
        future, _ = entry
        result = _parse_confirm(content)
        future.set_result(result)
        return result
```

### 2. 解析确认/取消

```python
CONFIRM_KEYWORDS = {"确认", "confirm", "yes", "y", "ok", "批准", "执行"}
CANCEL_KEYWORDS = {"取消", "cancel", "no", "n", "拒绝", "不"}

def _parse_confirm(content: str) -> bool:
    normalized = content.strip().lower()
    if any(kw in normalized for kw in CONFIRM_KEYWORDS):
        return True
    if any(kw in normalized for kw in CANCEL_KEYWORDS):
        return False
    # 歧义时默认取消（安全）
    return False
```

### 3. MessageBus 改动

```python
async def publish_inbound(self, msg: InboundMessage) -> None:
    resolved = self._confirm_store.resolve(msg.session_key, msg.content)
    if resolved is not None:
        # 该消息是确认回复，不转发给 Agent
        return
    await self.inbound.put(msg)
```

### 4. 通道确认回调

回调需要：`session_key`、`bus`、`chat_id`/`channel` 以发送确认提示。在 serve 模式下创建，并能在处理每条消息时拿到当前会话上下文。

**做法**：在 `_process_message` 开始时设置 `agent._current_msg`（含 session_key、channel、chat_id），确认回调从中读取。

```python
async def channel_confirm_callback(sql: str, confirm_msg: str) -> bool:
    msg = agent._current_msg
    if msg is None:
        return False
    session_key = msg.session_key
    future = asyncio.get_event_loop().create_future()
    bus.register_confirmation(session_key, future, confirm_msg[:100])
    await bus.publish_outbound(OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content=f"{confirm_msg}\n\n回复 **确认** 执行，**取消** 取消。",
    ))
    try:
        return await asyncio.wait_for(future, timeout=300)  # 5 分钟
    except asyncio.TimeoutError:
        return False
```

### 5. Serve 命令集成

在 `cli/commands.py` 中，不再传 `confirmation_callback=None`，而是构造上述通道确认回调并传入 AgentLoop。

---

## 流程示意

```
用户：「删除 orders 表里 status=1 的记录」
    │
    ▼
Agent 收到消息，执行循环
    │
    ▼
LLM 调用 data_modify(DELETE ...)
    │
    ▼
DataModifyTool.execute() → 需要确认
    │
    ▼
confirmation_callback(sql, msg) 被调用
    │
    ├─► 在 ConfirmationStore[session_key] 注册 future
    ├─► publish_outbound("需要确认：... 回复 确认/取消")
    └─► await future  （阻塞）
            │
            │  通道向用户发送消息
            │  用户回复：「确认」
            │
            ▼
通道收到「确认」→ publish_inbound(InboundMessage)
            │
            ▼
MessageBus.publish_inbound()：
    session_key 在 _pending 中？是
    → resolve(session_key, "确认") → future.set_result(True)
    → return（不入队）
            │
            ▼
工具的 await future 返回 True
    │
    ▼
工具继续执行，返回结果
    │
    ▼
Agent 继续，向用户返回最终回复
```

---

## 边界情况

| 情况 | 处理 |
|------|------|
| 用户回复其他内容（非确认/取消） | 视为取消（安全）。消息被 resolve 消费，不转发。用户需重新发起操作。 |
| 超时（5 分钟内无回复） | `wait_for` 超时，回调返回 False，工具返回「操作已取消（超时）」。 |
| 多会话 | 每个 session_key 独立待确认，互不干扰。 |
| 用户在其他会话中回复「确认」 | session_key 含 channel+chat_id，仅同一会话的回复会匹配。 |

---

## 可选：交互卡片（飞书/钉钉）

飞书、钉钉支持**带按钮的消息卡片**。可发送带「确认」「取消」按钮的卡片，用户点击后平台回调。

- **飞书**：卡片 `action` 元素；回调携带 `action.value`。
- **钉钉**：类似卡片与回调。

需增加：
1. 通道侧发送卡片而非纯文本的逻辑。
2. 处理回调事件（与普通消息不同），通过 `confirmation_id` 关联待确认项。

这是 UX 增强；先实现基于文本的「回复 确认/取消」即可，无需通道特定改动。

---

## 小结

| 组件 | 改动 |
|------|------|
| **MessageBus** | 增加 ConfirmationStore；在 `publish_inbound` 中检查并 resolve 待确认项。 |
| **AgentLoop** | 在 `_process_message` 开始时设置 `_current_msg`，供回调使用。 |
| **CLI serve** | 创建 `channel_confirm_callback`，注册 future、发送 outbound、await；传入 AgentLoop。 |
| **OutboundMessage** | 无需改动；确认提示为纯文本。 |

预估工作量：文本流程约 1–2 天；若需卡片交互，再增加相应开发时间。
