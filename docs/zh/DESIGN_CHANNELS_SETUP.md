# 设计：交互式通道配置

> [English](DESIGN_CHANNELS_SETUP.md)

## 目标

通过交互式命令 `queryclaw channels add` 和权限 JSON 模板，简化飞书/钉钉接入流程，减少手动步骤和配置错误。

---

## 实现方案

### 1. 新 CLI 命令：`queryclaw channels add`

**位置：** `cli/commands.py`（新增 `channels` 子命令组）

**流程：**

```
queryclaw channels add [feishu|dingtalk]
```

1. 若未指定通道，提示用户选择 feishu 或 dingtalk
2. 从 `~/.queryclaw/config.json`（或 `-c` 指定路径）加载现有配置
3. 交互式输入：
   - **飞书：** App ID、App Secret
   - **钉钉：** Client ID（AppKey）、Client Secret
4. 可选：限制允许用户（逗号分隔的 open_id / staff_id）
5. 写入配置：设置 `enabled: true`，填入凭证
6. 打印后续步骤（开放平台操作清单）

**依赖：** 已有 `typer`、`rich`。可选：`--app-id`、`--app-secret` 等非交互模式，便于脚本化。

### 2. 权限 JSON 模板

**位置：** `queryclaw/data/feishu_permissions.json`（新文件）

用户可复制到飞书开放平台 → 权限管理 → 批量导入。

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

**CLI 集成：** `queryclaw channels add feishu` 打印该文件路径或说明：「权限批量导入：使用 `queryclaw data feishu-permissions` 获取 JSON」。

### 3. 子命令结构

```
queryclaw channels add feishu [--config PATH]
queryclaw channels add dingtalk [--config PATH]
queryclaw channels status [--config PATH]   # 可选：显示已启用通道、脱敏凭证
```

`channels` 为 Typer 命令组，`add`、`status` 为子命令。

### 4. 涉及文件

| 文件 | 变更 |
|------|------|
| `cli/commands.py` | 新增 `channels` 命令组、`add`、可选 `status` |
| `queryclaw/data/feishu_permissions.json` | 新增：飞书权限模板 |
| `queryclaw/data/dingtalk_permissions.json` | 新增：钉钉权限模板（如适用） |
| `docs/USER_MANUAL*.md` | 新增「通过 channels add 快速配置」说明 |

---

## 大致效果（用户体验）

### 当前流程

1. 打开用户手册
2. 在飞书开放平台手动创建应用
3. 在权限管理里逐项勾选权限
4. 配置事件订阅（需记得先运行 serve）
5. 发布应用
6. 手动编辑 `config.json` 填入 app_id、app_secret
7. 执行 `queryclaw serve`

### 使用 `channels add` 后

1. 执行 `queryclaw channels add feishu`
2. 按提示粘贴 App ID、App Secret（从飞书复制）
3. 配置自动写入
4. CLI 打印简短清单：
   ```
   ✓ 配置已更新。后续步骤：
   1. 若未创建应用，前往 https://open.feishu.cn/app 创建
   2. 权限管理 → 批量导入：使用 <path>/feishu_permissions.json
   3. 启用机器人、事件订阅（长连接，im.message.receive_v1）
   4. 发布应用，将机器人添加到群聊/私聊
   5. 执行：queryclaw serve
   ```
5. 用户在飞书侧完成剩余步骤（仍为手动，但有清晰指引）
6. 执行 `queryclaw serve`

### 效果对比

| 方面 | 当前 | 改进后 |
|------|------|--------|
| 配置编辑 | 手动改 JSON | 交互式输入 |
| 权限配置 | 在 UI 里逐项勾选 | 从 JSON 批量导入 |
| 操作清单 | 分散在文档中 | `channels add` 后直接打印 |
| 拼写错误 | 容易出错 | 减少（可做格式校验） |

---

## 可选增强（后续阶段）

- **`queryclaw channels status`**：显示已启用通道、凭证是否填写（脱敏）、若 serve 运行中可显示连接状态
- **环境变量**：支持 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`，便于非交互部署
- **凭证校验**：`channels add` 后可选调用飞书 API 验证凭证（会增加网络依赖）

---

## 工作量估算

| 任务 | 预估 |
|------|------|
| `channels add feishu` | 约 1–2 小时 |
| `channels add dingtalk` | 约 0.5 小时（模式类似） |
| 权限 JSON + 文档 | 约 0.5 小时 |
| `channels status`（可选） | 约 1 小时 |

**核心功能合计：** 约 2–3 小时。
