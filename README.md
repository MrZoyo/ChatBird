# ChatBird

ChatBird（小鸟聊天助手，昵称“乌鸦”）是一个面向 Discord 的多服务器 AI
助手。项目以 [Hermes Agent](https://github.com/NousResearch/hermes-agent)
为运行框架，通过 Xiaomi MiMo 提供模型能力，并针对公开 Discord Bot 的权限、
会话隔离、持久记忆和生产运维进行了定制。

当前生产模型为 `mimo-v2.5`，由 `hermes-gateway.service` 持续运行。
网页搜索使用无需密钥的 DDGS 后端；网页正文提取需另行配置提取后端。

## 核心能力

- 一个 Discord Bot 账号可服务多个经过批准的 Guild。
- 每个 Guild 拥有独立的会话和持久记忆命名空间，数据不会跨 Guild 混用。
- Guild 和频道白名单默认拒绝未配置范围；普通文字频道可继承所属 Category 的白名单。
- 用户仅在明确 `@` Bot 或回复 Bot 时触发模型；同一频道成员共享频道会话。
- 普通用户仅开放对话、网络查询、支持的附件分析和受限记忆能力。
- 管理功能同时校验管理员用户 ID 和当前 Guild 的私密管理员频道。
- Discord 私信不会获得回复，也不会进入模型会话；私信文本和有限附件元数据可记录到受限日志。
- 原生 Slash Commands 分为公开命令和管理员命令，并复用同一套 Guild/频道授权边界。

## 安全边界

ChatBird 的首要隔离契约是：**任何 Discord 会话和持久记忆都不能跨 Guild
边界访问。**

生产访问按以下顺序收紧：

1. `discord.allowed_guilds`：只接受明确批准的 Guild。
2. `discord.allowed_channels`：只接受明确频道、Category 及其继承范围。
3. `discord.require_mention`：普通消息必须明确提及 Bot。
4. 请求级权限：敏感工具和管理员命令必须同时匹配管理员用户与
   `guild_id:channel_id` 管理员频道映射。

普通用户和管理员在公开频道中使用相同的安全工具面。管理员只有在对应 Guild
的私密管理员频道中才进入管理员上下文。生产环境不得使用裸频道 ID 代替
Guild/频道组合，也不得允许未列入 `allowed_guilds` 的服务器。

## 仓库结构

| 路径 | 用途 |
|---|---|
| [`hermes-stack.lock`](hermes-stack.lock) | 锁定 Hermes 上游仓库、基础提交、补丁顺序和测试覆盖文件 |
| [`patches/`](patches/) | ChatBird 的 Hermes 补丁、生产行为配置和补丁说明 |
| [`scripts/apply-hermes-patches.sh`](scripts/apply-hermes-patches.sh) | 检查或应用完整 Hermes 补丁栈 |
| [`scripts/check-server.sh`](scripts/check-server.sh) | 只读检查生产主机资源、Hermes 版本和服务状态 |
| [`scripts/deploy-env.sh`](scripts/deploy-env.sh) | 从本地环境安全更新生产 `.env` |
| [`.env.example`](.env.example) | 不含真实凭据的环境变量示例 |
| [`PRIVACY.md`](PRIVACY.md) | ChatBird 隐私政策 |
| [`docs/discord-intent-application.md`](docs/discord-intent-application.md) | Discord 特权 Intent 申请说明 |
| [`docs/bird-bot-guide.md`](docs/bird-bot-guide.md) | Bird-Bot 功能参考 |

## Hermes 版本管理

ChatBird 不复制整份 Hermes Agent 源码，而是保存一套可重建的补丁栈：

```text
NousResearch/hermes-agent @ locked base commit
  + Guild 会话与记忆隔离
  + Guild 成员访问与私信日志
  + Home Channel 提示控制
  + Slash Command 分级授权
  + Discord Category 白名单继承
  + 公共频道 Skill 例外与直接网页搜索
  + ChatBird 定向测试覆盖
```

具体基线和应用顺序以 [`hermes-stack.lock`](hermes-stack.lock) 为准。这样可以保留
完整上游历史、明确审阅 ChatBird 的差异，并在升级 Hermes 时逐个处理冲突。

`main` 是 ChatBird 唯一的长期集成分支。临时开发分支合并后即可删除；生产配置、
补丁栈、策略插件、测试和运维文档都以 `main` 为准。

### 从锁定基线重建

准备一个干净的 Hermes checkout，并切换到锁定的基础提交：

```bash
git clone https://github.com/NousResearch/hermes-agent.git hermes-agent
git -C hermes-agent checkout f53b184c48712bcbb98556a6314cd1f240fc104d
```

先执行无写入检查：

```bash
scripts/apply-hermes-patches.sh ./hermes-agent --check
```

确认全部补丁可应用后再执行：

```bash
scripts/apply-hermes-patches.sh ./hermes-agent
```

脚本会在以下情况失败并停止：checkout 不干净、基础提交不匹配、补丁缺失、补丁
无法应用，或测试覆盖文件将覆盖上游已有文件。更多说明见
[`patches/README.md`](patches/README.md)。

## 配置

生产行为配置参考
[`patches/chatbird-production-config.yaml`](patches/chatbird-production-config.yaml)。
其中包含当前 Guild、Category 和频道 ID；在其他环境部署前必须替换为目标 Discord
服务器的 ID。

敏感值只应保存在服务器的 `/root/.hermes/.env`，绝不能提交到 Git：

```env
XIAOMI_API_KEY=...
DISCORD_BOT_TOKEN=...
DISCORD_ALLOWED_USERS=...
DISCORD_ALLOW_ALL_USERS=true
CHATBIRD_ADMIN_USERS=...
CHATBIRD_ADMIN_CHANNELS=<guild_id>:<private_admin_channel_id>
CHATBIRD_HOME_CHANNELS=<guild_id>:<delivery_channel_id>
CHATBIRD_DISABLE_HOME_CHANNEL_NOTICE=true
CHATBIRD_DISABLE_DM_REPLIES=true
CHATBIRD_LOG_DMS=true
DISCORD_AUTO_THREAD=false
```

重要配置约束：

- `web.search_backend: ddgs` 提供无需密钥的网页搜索，但不提供网页正文提取。
- `discord.allowed_guilds` 必须列出每一个生产 Guild，未列入者默认拒绝。
- `discord.allowed_channels` 可以列出具体频道或 Category ID；子频道继承 Category
  白名单。
- `group_sessions_per_user: false` 让同一频道成员共享频道会话，但 Guild 后缀仍确保
  跨 Guild 隔离。
- `memory.user_profile_enabled: false` 禁用 Hermes 的共享 `USER.md`，避免多人频道中
  的用户信息混合。
- `CHATBIRD_ADMIN_CHANNELS` 必须使用 `guild_id:channel_id`，格式错误时管理员能力
  默认拒绝。
- `DISCORD_AUTO_THREAD=false` 保持频道内联对话，不为每次提及创建新线程。

### Category 白名单继承

`discord.allowed_channels` 同时支持具体频道 ID 和 Category ID。普通 Guild 频道从
discord.py 的 `category`/`category_id` 读取所属 Category；Thread 从
`parent`/`parent_id` 读取父频道。普通消息和 Slash Command 共用这套继承规则。

频道授权早于提及检查。如果频道及其 Category 都未匹配白名单，消息会被静默拒绝，
即使用户已经正确 `@` Bot。排查“@Bot 无响应”时，应先确认频道对象的 Category
已被正确解析。

## Discord 应用设置

Discord Developer Portal 必须启用：

- Message Content Intent
- 使用角色授权、用户名白名单或成员查询时启用 Server Members Intent

邀请应用时需要：

- `bot`
- `applications.commands`

不要授予 Bot `Administrator`。只开放读取频道、查看历史、发送消息、嵌入链接、
上传文件、添加反应以及使用应用命令等实际需要的权限。

公开 Slash Commands 为 `/help`、`/whoami`、`/status`、`/version` 和 `/usage`。
其他命令只允许配置的管理员在对应 Guild 的私密管理员频道使用；私信中的 Slash
Commands 默认拒绝。

## 验证

补丁栈变更至少应完成以下验证：

1. 在临时 Hermes worktree 上运行 `--check`。
2. 从锁定基线实际应用完整补丁栈。
3. 对修改过的 Python 文件执行语法检查。
4. 运行 Guild 隔离、记忆隔离、Discord 访问、Home Channel 和 Category 白名单的
   定向回归测试。
5. 将重建文件与预期生产文件逐一比较。

当前补丁栈最近一次重建验证通过 20 项相关测试，并与生产修改文件逐字节一致。

## 生产运维

生产主机 `aliyun-germany` 资源有限，约有 1.6 GiB 内存和 2 GiB swap。优先在
本地或临时 worktree 开发和验证；生产机只部署必要文件并运行定向测试。

常用只读检查：

```bash
scripts/check-server.sh aliyun-germany
ssh aliyun-germany systemctl is-active hermes-gateway.service
ssh aliyun-germany systemctl show hermes-gateway.service \
  -p MainPID -p NRestarts -p MemoryCurrent
```

部署时应遵守：

- 先检查内存、磁盘和服务负载。
- 备份将要覆盖的文件。
- 只应用必要补丁并运行相关单测，避免生产机全量构建和高并发任务。
- 所有代码和配置就绪后只重启网关一次，缩短 Discord 中断时间。
- 重启后确认服务为 `active`、`NRestarts=0`，并查看最新短日志是否重新连接
  Discord。
- 永远不要输出、复制到日志或提交 `/root/.hermes/.env` 的真实内容。

## 隐私

ChatBird 会将用户明确触发的消息、必要上下文和支持的附件发送给配置的模型服务。
私信不会发送给模型，但可能写入仅管理员可访问的本地日志。完整政策见
[`PRIVACY.md`](PRIVACY.md)。
