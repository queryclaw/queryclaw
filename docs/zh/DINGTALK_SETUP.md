# 钉钉通道对接操作手册

> [English](DINGTALK_SETUP.md)

本文档说明如何将 QueryClaw 接入钉钉，使 Agent 能在钉钉中接收用户提问并回复。

---

## 前置条件

- 钉钉企业账号（需有应用开发权限）
- 本地或服务器能访问钉钉 API（`api.dingtalk.com`、`wss-open-connection.dingtalk.com`）
- QueryClaw 已配置数据库和 LLM（参见 [USER_MANUAL.md](USER_MANUAL.md)）

---

## 一、安装钉钉依赖

```bash
pip install queryclaw[dingtalk]
```

或安装完整依赖：

```bash
pip install queryclaw[all]
```

---

## 二、在钉钉开放平台创建应用

### 2.1 登录开发者后台

1. 打开 [钉钉开放平台](https://open-dev.dingtalk.com)
2. 使用钉钉扫码登录
3. 选择开发组织（需有应用开发权限）

### 2.2 创建应用

1. 点击「应用开发」→「企业内部开发」→「机器人」
2. 点击「创建应用」
3. 填写应用名称（如「QueryClaw 数据库助手」）和描述
4. 点击「确认创建」

### 2.3 获取凭证

1. 进入应用详情页
2. 左侧导航点击「应用信息」
3. 复制 **Client ID**（即 AppKey）和 **Client Secret**（即 AppSecret）
4. 妥善保管，后续配置 QueryClaw 时使用

### 2.4 配置机器人

1. 左侧导航点击「机器人与消息推送」
2. 开启「机器人配置」
3. **接收模式**：选择 **Stream 模式**（推荐，无需公网 IP 或 Webhook 地址）
4. 填写机器人名称、头像等（可选）
5. 点击「发布」保存

### 2.5 配置权限

1. 左侧导航点击「权限管理」
2. 搜索并添加以下权限：
   - **机器人接收消息**（`im:bot:receive_message` 或类似）
   - **机器人发送消息**（`im:bot:send_message` 或类似）
   - **获取用户信息**（如需识别用户，可选）
3. 点击「申请权限」，等待管理员审批

### 2.6 发布应用

1. 左侧导航点击「版本管理与发布」
2. 创建版本，填写更新说明
3. 选择「可用范围」（建议先选「全部成员」或指定测试人员）
4. 提交发布，等待审批

---

## 三、配置 QueryClaw

### 3.1 编辑配置文件

编辑 `~/.queryclaw/config.json`（或通过 `-c` 指定路径），在 `channels.dingtalk` 中填入：

```json
{
  "channels": {
    "feishu": {
      "enabled": false,
      "app_id": "",
      "app_secret": "",
      "allow_from": []
    },
    "dingtalk": {
      "enabled": true,
      "client_id": "你的 Client ID (AppKey)",
      "client_secret": "你的 Client Secret (AppSecret)",
      "allow_from": []
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| `enabled` | 设为 `true` 启用钉钉通道 |
| `client_id` | 钉钉应用的 Client ID（AppKey） |
| `client_secret` | 钉钉应用的 Client Secret（AppSecret） |
| `allow_from` | 允许的 staff_id 列表；空数组表示允许所有人 |

### 3.2 限制访问用户（可选）

若只允许特定用户使用，在钉钉中获取用户的 staff_id，填入 `allow_from`：

```json
"allow_from": ["staff_id_1", "staff_id_2"]
```

---

## 四、启动服务

```bash
queryclaw serve
```

启动成功后，终端会显示类似：

```
DingTalk bot started with Stream Mode
```

---

## 五、在钉钉中使用

### 5.1 私聊

1. 打开钉钉客户端
2. 在顶部搜索框输入应用名称（如「QueryClaw 数据库助手」）
3. 选择该应用，发起私聊
4. 直接发送问题，如「帮我查一下 users 表有多少条记录」

### 5.2 群聊（当前限制）

当前实现中，群聊消息会接收，但回复会发送到**私聊**。若需群内回复，需后续版本支持。

---

## 六、常见问题

### 6.1 收不到消息

| 可能原因 | 排查步骤 |
|----------|----------|
| 凭证错误 | 确认 `client_id`、`client_secret` 与开放平台一致，无多余空格 |
| 未选择 Stream 模式 | 在「机器人与消息推送」中确认接收模式为 Stream |
| 权限未开通 | 在「权限管理」中确认机器人收发消息权限已审批 |
| 应用未发布 | 在「版本管理与发布」中确认应用已发布且可用范围包含当前用户 |
| serve 未运行 | 确保 `queryclaw serve` 持续运行 |

### 6.2 发消息无回复

| 可能原因 | 排查步骤 |
|----------|----------|
| 数据库/LLM 配置错误 | 检查 `config.json` 中 `database`、`providers` 配置 |
| 网络问题 | 确认服务器能访问 `api.dingtalk.com` |
| 查看日志 | 终端会输出 `[DingTalk]` 相关日志，根据报错排查 |

### 6.3 提示「DingTalk Stream SDK not installed」

执行：

```bash
pip install queryclaw[dingtalk]
```

### 6.4 提示「client_id and client_secret not configured」

检查 `config.json` 中 `channels.dingtalk` 的 `client_id`、`client_secret` 是否已填写且非空。

---

## 七、配置示例（完整）

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
    "feishu": {
      "enabled": false,
      "app_id": "",
      "app_secret": "",
      "allow_from": []
    },
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

## 八、与飞书对比

| 方面 | 飞书 | 钉钉 |
|------|------|------|
| 接收模式 | WebSocket 长连接 | Stream 模式（WebSocket） |
| 公网要求 | 无需 | 无需 |
| 凭证字段 | app_id, app_secret | client_id, client_secret |
| 用户 ID | open_id | staff_id |
| 群聊回复 | 支持 | 当前仅私聊回复 |
