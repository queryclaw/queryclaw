# Channel-Mode Interactive Confirmation — Technical Design

## Problem

When `safety.require_confirmation` is true, destructive operations (INSERT/UPDATE/DELETE/DDL) require user confirmation. In CLI mode, the confirmation handler prompts via stdin. In channel mode, `confirmation_callback=None` is passed, so the tools return an error and reject the operation.

**Goal**: Support interactive confirmation in channel mode (Feishu, DingTalk) so users can approve or cancel destructive operations via chat.

---

## Approach: Pending Confirmation + Message Routing

### Core Idea

1. When a tool needs confirmation, instead of rejecting, register a **pending confirmation** for the current session.
2. Send a message to the channel: "The following operation requires confirmation: [summary]. Reply **确认** to proceed, **取消** to cancel."
3. **Intercept** the next inbound message for that session: if it matches confirm/cancel, resolve the pending confirmation and do **not** forward it to the agent.
4. The tool's confirmation callback awaits the result and continues or aborts.

### Key Challenge: Message Routing

The agent consumes from `bus.consume_inbound()`. When a tool is executing and awaiting confirmation, the agent is blocked. The next user message ("确认" or "取消") would be published to the inbound queue. We need to route it to the pending confirmation instead of the agent.

**Solution**: Intercept at `bus.publish_inbound()`. Before putting the message in the queue, check if there is a pending confirmation for `msg.session_key`. If yes, resolve the future and return; do not enqueue. If no, enqueue as usual.

---

## Implementation Design

### 1. ConfirmationStore (in MessageBus or separate)

```python
# In bus/queue.py or bus/confirmation.py
class ConfirmationStore:
    """Tracks pending confirmations per session."""
    def __init__(self):
        self._pending: dict[str, tuple[asyncio.Future[bool], str]] = {}

    def register(self, session_key: str, future: asyncio.Future[bool], summary: str) -> None:
        self._pending[session_key] = (future, summary)

    def resolve(self, session_key: str, content: str) -> bool | None:
        """If session has pending confirmation, parse content and resolve. Returns True/False if resolved, None if no pending."""
        entry = self._pending.pop(session_key, None)
        if entry is None:
            return None
        future, _ = entry
        result = _parse_confirm(content)
        future.set_result(result)
        return result

    def cancel_all(self, session_key: str) -> None:
        """Cancel pending confirmation (e.g. on timeout)."""
        entry = self._pending.pop(session_key, None)
        if entry:
            entry[0].cancel()
```

### 2. Parse Confirm/Cancel

```python
CONFIRM_KEYWORDS = {"确认", "confirm", "yes", "y", "ok", "批准", "执行"}
CANCEL_KEYWORDS = {"取消", "cancel", "no", "n", "拒绝", "不"}

def _parse_confirm(content: str) -> bool:
    normalized = content.strip().lower()
    if any(kw in normalized for kw in CONFIRM_KEYWORDS):
        return True
    if any(kw in normalized for kw in CANCEL_KEYWORDS):
        return False
    # Ambiguous: default to cancel for safety
    return False
```

### 3. MessageBus Changes

```python
class MessageBus:
    def __init__(self):
        self.inbound = asyncio.Queue()
        self.outbound = asyncio.Queue()
        self._confirm_store = ConfirmationStore()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        resolved = self._confirm_store.resolve(msg.session_key, msg.content)
        if resolved is not None:
            # Message was a confirmation reply; don't forward to agent
            return
        await self.inbound.put(msg)

    def register_confirmation(self, session_key: str, future: asyncio.Future[bool], summary: str) -> None:
        self._confirm_store.register(session_key, future, summary)
```

### 4. Channel Confirmation Callback

The callback needs: `session_key`, `bus`, and `chat_id`/`channel` to send the confirmation message. It is created when starting the agent in serve mode, with access to the current message context.

**Problem**: The confirmation callback is invoked from inside a tool, which does not know the current `session_key` or `chat_id`. The agent's `_process_message` has that context, but the tool does not.

**Solution**: Pass session context into the agent loop. When we call `_run_agent_loop`, we're processing a message with `session_key`, `channel`, `chat_id`. We need to make this available to the confirmation callback. Options:

- **A. Thread-local / contextvars**: Set `current_session` in contextvars before processing each message. The callback reads it.
- **B. Wrap the callback**: Create a closure when dispatching each message that captures `session_key`, `channel`, `chat_id`. Pass that as the confirmation callback for that request.

Option B is cleaner. We'd need to create the agent (or the tools) per-request, or we'd need to inject the session context before each `_run_agent_loop`. Simpler: **store current session in the agent** and update it at the start of each `_process_message`. The confirmation callback can then read `agent.current_session` and `agent.current_channel`, `agent.current_chat_id`.

```python
# In AgentLoop
async def _process_message(self, msg):
    self._current_msg = msg  # session_key, channel, chat_id
    # ... build messages, run loop ...
    self._current_msg = None

# Confirmation callback (created in serve command):
async def channel_confirm_callback(sql: str, confirm_msg: str) -> bool:
    msg = agent._current_msg  # or pass via closure
    if msg is None:
        return False
    session_key = msg.session_key
    future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
    bus.register_confirmation(session_key, future, confirm_msg[:100])
    await bus.publish_outbound(OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content=f"{confirm_msg}\n\n回复 **确认** 执行，**取消** 取消。",
    ))
    try:
        return await asyncio.wait_for(future, timeout=300)  # 5 min
    except asyncio.TimeoutError:
        bus._confirm_store.cancel_all(session_key)
        return False
```

### 5. Serve Command Integration

In `cli/commands.py`, instead of `confirmation_callback=None`, create the channel confirmation callback and pass it. The callback needs access to `agent`, `bus`, and the current message. Since the callback is invoked during `agent._process_message`, we can set `agent._current_msg` at the start of that method.

---

## Flow Diagram

```
User: "删除 orders 表里 status=1 的记录"
    │
    ▼
Agent receives message, runs loop
    │
    ▼
LLM calls data_modify(DELETE ...)
    │
    ▼
DataModifyTool.execute() → needs confirmation
    │
    ▼
confirmation_callback(sql, msg) invoked
    │
    ├─► Register future in ConfirmationStore[session_key]
    ├─► publish_outbound("需要确认：... 回复 确认/取消")
    └─► await future  (blocks)
            │
            │  Channel sends message to user
            │  User replies: "确认"
            │
            ▼
Channel receives "确认" → publish_inbound(InboundMessage)
            │
            ▼
MessageBus.publish_inbound():
    session_key in _pending? YES
    → resolve(session_key, "确认") → future.set_result(True)
    → return (do NOT put in queue)
            │
            ▼
Tool's await future returns True
    │
    ▼
Tool proceeds with execution, returns result
    │
    ▼
Agent continues, sends final response to user
```

---

## Edge Cases

| Case | Handling |
|------|----------|
| User sends another question instead of 确认/取消 | Treated as cancel (safe). The message is consumed by `resolve()` and not forwarded. User would need to retry the operation. Alternatively: only treat exact/short confirm/cancel; if ambiguous, could re-ask. For simplicity, treat as cancel. |
| Timeout (user doesn't respond in 5 min) | `wait_for` raises; callback returns False; tool returns "Operation cancelled (timeout)". |
| Multiple sessions | Each session has its own pending confirmation. No cross-session interference. |
| User sends "确认" in a different chat | session_key includes channel+chat_id, so only the same chat's reply is matched. |

---

## Optional: Interactive Cards (Feishu/DingTalk)

Feishu and DingTalk support **message cards with buttons**. Instead of asking the user to type "确认", we could send a card with "确认" and "取消" buttons. When the user clicks, the platform sends a callback with the action.

- **Feishu**: Card with `action` elements; callback receives `action.value`.
- **DingTalk**: Similar card actions.

This would require:
1. Channel-specific logic to send a card instead of plain text.
2. Handling the callback event (different from a regular message) and mapping it to the confirmation store. The callback might use a `confirmation_id` in the button value to correlate.

This is a UX enhancement; the text-based "回复 确认/取消" approach works without channel-specific changes and can be implemented first.

---

## Summary

| Component | Change |
|-----------|--------|
| **MessageBus** | Add `ConfirmationStore`; in `publish_inbound`, check and resolve pending confirmations before enqueueing. |
| **AgentLoop** | Set `_current_msg` at start of `_process_message` so callback knows session/channel/chat_id. |
| **CLI serve** | Create `channel_confirm_callback` that registers future, sends outbound, awaits; pass to AgentLoop. |
| **OutboundMessage** | No change; confirmation prompt is plain text. |

Estimated effort: ~1–2 days for the text-based flow; additional time for card-based UX if desired.
