<p align="center">
  <img src="assets/chatbird-banner.png" alt="ChatBird banner" width="100%">
</p>

<h1 align="center">ChatBird</h1>

<p align="center">
  <strong>面向多 Discord 服务器的安全 AI 助手</strong>
</p>

<p align="center">
  简体中文 · <a href="README_EN.md">English</a>
</p>

<p align="center">
  <a href="https://github.com/NousResearch/hermes-agent">
    <img src="https://img.shields.io/badge/BUILT%20ON-HERMES%20AGENT-6C5CE7?style=for-the-badge" alt="Built on Hermes Agent">
  </a>
  <a href="PRIVACY.md">
    <img src="https://img.shields.io/badge/PRIVACY-GUILD%20ISOLATED-2EA44F?style=for-the-badge" alt="Guild-isolated privacy">
  </a>
  <a href="hermes-stack.lock">
    <img src="https://img.shields.io/badge/INTEGRATION-REPRODUCIBLE-0969DA?style=for-the-badge" alt="Reproducible integration">
  </a>
</p>

ChatBird（小鸟聊天助手，昵称“乌鸦”）是一套基于
[Hermes Agent](https://github.com/NousResearch/hermes-agent) 的 Discord AI 助手
集成方案。它让一个 Bot 账号安全地服务多个 Guild，并为公开频道补充权限控制、
会话与记忆隔离、受限工具、网页检索和可重建的补丁管理。

ChatBird 不绑定特定模型提供商、云平台或服务器。你可以按自己的环境选择模型、
主机和部署方式；仓库只定义行为、安全边界和 Hermes 集成补丁。

## 主要能力

| 能力 | 说明 |
| --- | --- |
| 多 Guild 隔离 | 会话和持久记忆均包含 `guild_id`，防止跨服务器读取上下文 |
| 默认拒绝的访问控制 | 仅接受 `allowed_guilds` 和 `allowed_channels` 明确允许的范围 |
| Category 继承 | 文字频道继承所属 Category 的白名单；Thread 继承父频道 |
| 明确触发 | 普通频道仅在用户 `@` Bot 或回复 Bot 时触发模型 |
| 公开频道工具策略 | 普通用户只获得对话、受限网页查询、支持的附件分析和受限记忆能力 |
| 管理员双重校验 | 敏感能力同时校验管理员用户和当前 `guild_id:channel_id` |
| 私信隔离 | 私信不进入模型会话，也不获得 Bot 回复 |
| 可重建集成 | 上游提交、补丁顺序和测试覆盖统一记录在 `hermes-stack.lock` |

## 工作方式

```text
Discord message
  -> Guild allowlist
  -> Channel / Category allowlist
  -> Mention or reply check
  -> Guild-scoped session and memory
  -> Request-scoped tool policy
  -> Configured model provider
```

最重要的隔离契约是：**任何 Discord 会话和持久记忆都不能跨 Guild 边界访问。**
未列入 `discord.allowed_guilds` 的 Guild 必须默认拒绝。

## 快速开始

ChatBird 不是 Hermes Agent 的完整副本。部署时先准备一个干净的 Hermes checkout，
再应用本仓库维护的补丁栈。

### 1. 准备 Hermes Agent

```bash
git clone https://github.com/NousResearch/hermes-agent.git hermes-agent
git -C hermes-agent checkout f53b184c48712bcbb98556a6314cd1f240fc104d
```

该提交以 [`hermes-stack.lock`](hermes-stack.lock) 为准；上游基线更新后应使用锁文件
中的新值。

### 2. 检查并应用补丁

```bash
scripts/apply-hermes-patches.sh ./hermes-agent --check
scripts/apply-hermes-patches.sh ./hermes-agent
```

脚本会在 checkout 不干净、基础提交不匹配、补丁缺失、补丁无法应用或测试覆盖文件
发生冲突时停止。

### 3. 配置部署

从示例文件开始：

```bash
cp config.example.yaml /path/to/hermes/config.yaml
cp .env.example /path/to/hermes/.env
```

至少需要完成以下配置：

- 按 Hermes Agent 的配置方式选择模型提供商和模型；
- 设置 Discord Bot Token；
- 在 `discord.allowed_guilds` 中列出每个允许的 Guild；
- 在 `discord.allowed_channels` 中列出允许的频道或 Category；
- 配置 `CHATBIRD_ADMIN_USERS` 和 `CHATBIRD_ADMIN_CHANNELS`；
- 保持 `group_sessions_per_user: false` 和 `memory.user_profile_enabled: false`，
  以使用 ChatBird 的共享频道会话与分层记忆策略。

示例中的 ID 和凭据均为占位内容。真实密钥只应保存在部署环境中，不得提交到 Git。

### 4. 配置 Discord 应用

在 [Discord Developer Portal](https://discord.com/developers/applications) 中：

1. 创建应用和 Bot 用户。
2. 启用 **Message Content Intent**。
3. 如果使用角色授权、用户名白名单或成员查询，启用 **Server Members Intent**。
4. 使用 `bot` 和 `applications.commands` scope 邀请 Bot。
5. 仅授予读取频道、查看历史、发送消息、嵌入链接、上传文件、添加反应和使用应用
   命令等实际需要的权限；不要授予 `Administrator`。

权限明细见 [Discord 权限说明](docs/discord-permissions.md)。

## 配置原则

### 模型与运行环境

ChatBird 不限制模型 API、推理后端、操作系统或云平台。模型连接按 Hermes Agent 的
方式配置；部署目录、服务管理器和资源限额由运营者决定。主 README 不记录某个实例
当前使用的模型或服务器，避免把单一部署状态误写成项目要求。

### Guild 与频道白名单

```yaml
discord:
  allowed_guilds:
    - "111111111111111111"
  allowed_channels:
    - "222222222222222222" # 频道或 Category ID
  require_mention: true
  thread_require_mention: true
  auto_thread: false
```

普通文字频道通过 discord.py 的 `category`/`category_id` 读取所属 Category；Thread
通过 `parent`/`parent_id` 读取父频道。普通消息和 Slash Command 使用相同的继承规则。

### 管理员边界

```env
CHATBIRD_ADMIN_USERS=123456789012345678
CHATBIRD_ADMIN_CHANNELS=111111111111111111:222222222222222222
```

管理员能力只有在用户 ID 和当前 `GuildID:ChannelID` 同时匹配时才会开放。格式错误、
缺少映射或在公开频道调用都会默认拒绝。

### 网页能力

仓库包含公开频道网页查询的权限策略。搜索和正文提取后端由运营者按部署需求配置；
公开用户不会因此获得终端、文件、代码执行或交互式浏览器能力。

## 常见问题

### 已经 `@Bot`，为什么没有回复？

频道授权发生在提及检查之前。依次确认：

1. 当前 Guild 已加入 `discord.allowed_guilds`；
2. 当前频道 ID 或所属 Category ID 已加入 `discord.allowed_channels`；
3. 普通频道能通过 `category`/`category_id` 解析 Category；
4. Thread 能通过 `parent`/`parent_id` 解析父频道；
5. 消息确实提及了 Bot，或回复了 Bot 的消息。

旧实现只读取 Thread 的 `parent` 字段，导致位于已允许 Category 内的普通文字频道被
误判为未授权。当前补丁已分别处理 Category 与 Thread，并为普通消息和 Slash
Command 提供回归测试。

### 为什么要维护补丁栈？

ChatBird 保留完整的 Hermes 上游历史，只跟踪经过审阅的差异。升级时可以从锁定的
上游提交重建、逐个处理冲突，并比较最终文件，而无需长期维护一份上游源码副本。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| [`hermes-stack.lock`](hermes-stack.lock) | 锁定上游仓库、基础提交、补丁顺序和测试覆盖 |
| [`patches/`](patches/) | Hermes 补丁、参考配置和补丁说明 |
| [`plugins/chatbird-policy/`](plugins/chatbird-policy/) | 请求级权限与分层记忆策略插件 |
| [`scripts/apply-hermes-patches.sh`](scripts/apply-hermes-patches.sh) | 检查或应用完整补丁栈 |
| [`config.example.yaml`](config.example.yaml) | 不含凭据的行为配置示例 |
| [`.env.example`](.env.example) | 环境变量占位示例 |
| [`docs/`](docs/) | 权限、隔离、隐私和运维文档 |

## 验证

补丁变更至少应完成：

1. 对干净的锁定基线执行 `--check`；
2. 从锁定基线实际应用完整补丁栈；
3. 对修改过的 Python 文件执行语法检查；
4. 运行受影响功能的定向测试；
5. 检查重建文件是否符合预期。

避免在资源有限的生产主机上运行全仓扫描、完整测试套件或高并发构建。优先在本地或
临时 worktree 验证，再部署必要文件并执行定向烟测。

## 文档

| 文档 | 内容 |
| --- | --- |
| [生产状态](docs/production-state.md) | 当前实例的非敏感部署状态、验证记录和运维说明 |
| [多人权限策略](docs/multi-user-policy.md) | 公开用户、管理员、工具和记忆边界 |
| [多 Guild 记忆](docs/multi-guild-memory.md) | Guild 级会话与持久记忆隔离 |
| [Discord 权限](docs/discord-permissions.md) | Bot 所需权限与附件行为 |
| [Discord Intent 申请](docs/discord-intent-application.md) | 特权 Intent 申请材料 |
| [补丁栈说明](patches/README.md) | 补丁维护、升级和验证约束 |
| [隐私政策](PRIVACY.md) | 数据处理和保留边界 |

## 上游与许可

ChatBird 基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 构建。
使用和分发本仓库内容前，请同时遵守本仓库及上游项目的许可条款。
