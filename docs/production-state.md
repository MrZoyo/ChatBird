# ChatBird 生产状态与修改总览

最后核对：2026-08-12（Europe/Berlin）

这份文档是 ChatBird 当前生产部署的非敏感总览，用于在仓库长期休眠后快速恢复上下文。它记录架构、ID 映射、安全边界、Hermes 补丁和验证方式，但不保存 API Key、Bot Token 或其他凭据。

## 生产位置

| 项目 | 当前值 |
|---|---|
| SSH 主机别名 | `aliyun-germany` |
| Hermes 源码 | `/usr/local/lib/hermes-agent` |
| Hermes 配置 | `/root/.hermes/config.yaml` |
| Hermes 环境变量 | `/root/.hermes/.env`，权限应为 `0600` |
| ChatBird 身份提示词 | `/root/.hermes/SOUL.md` |
| systemd 服务 | `hermes-gateway.service` |
| 模型 | Xiaomi MiMo `mimo-v2.5` |
| 策略插件 | `chatbird-policy` `1.2.1` |

生产机只有约 1.6 GiB 内存。只能做定向读取、单文件测试和短日志检查；不要在生产机运行全仓扫描、完整测试套件、高并发构建或无必要升级。不要打印、复制到日志或提交 `/root/.hermes/.env` 的实际值。

本地非敏感配置镜像是 [`../patches/chatbird-production-config.yaml`](../patches/chatbird-production-config.yaml)，环境变量格式参考 [`../.env.example`](../.env.example)。

## Discord ID 映射

管理员用户：`518184812381732865`

| Guild | Guild ID | 管理频道 | 显式投递频道 |
|---|---:|---:|---:|
| Bird Gaming | `1146359014968537089` | `1154706638901612625` | `1148897557947367474` |
| 测试服 / 秘密研究 | `921407984586866778` | `1220876330913234944` | `921407984586866781` |

当前配置中的交互白名单 ID：

- `1146359015715110992`
- `1170057013569536100`
- `1395894673792569374`
- `921407984586866781`
- `1154706638901612625`
- `1220876330913234944`

`1395894673792569374` 是 Bird Gaming 的 `🎙️nsfw-祖安广场`。2026-08-11 已通过 Discord API 验证 Bot 可以查看该频道。

## 会话与历史边界

- 同一 Discord 频道中的所有用户共享一份聊天历史，符合多人共同讨论一个话题的使用方式。
- 每个会话键都包含 `guild_id`，不同 Discord Guild 的聊天历史和持久记忆绝不互通。
- `group_sessions_per_user: false`，不会按频道内用户拆分会话。
- `auto_thread: false`，回复留在原频道，不自动创建讨论串。
- 普通频道需要明确提及 Bot；讨论串也需要提及。
- 最近历史回填开启，最多读取 50 条可见消息作为有界上下文。
- 未列入 `discord.allowed_guilds` 的服务器 fail closed，即使公开 Bot 被邀请进去也不能使用 Agent。

## 用户与管理员权限

普通用户可以在允许的 Guild 和频道中聊天、提问、搜索网页和进行视觉分析。生产使用无需密钥的 DDGS 搜索后端；网页正文提取尚未配置独立后端。普通用户不能使用终端、文件、代码执行、内置记忆、会话搜索、Cron、Skill 管理、代理委派、跨平台消息、计算机控制或 Kanban 等敏感工具。

管理员上下文必须同时满足：

1. Discord 用户 ID 在 `CHATBIRD_ADMIN_USERS` 中；
2. 当前 `guild_id:channel_id` 精确匹配 `CHATBIRD_ADMIN_CHANNELS`。

因此管理员在普通频道里也只获得普通用户能力。未知 Guild、错误频道、缺失用户信息和 DM 都不能进入管理员上下文。详细规则见 [`multi-user-policy.md`](multi-user-policy.md)。

## 记忆设计

| 记忆层 | 路径 | 访问规则 |
|---|---|---|
| Guild 公共记忆 | `memories/scopes/discord-guild-<guild_id>/MEMORY.md` | 当前 Guild 可读取；写入要求管理员上下文 |
| 用户档案 | `memories/chatbird/profiles/discord-guild-<guild_id>/<user_id>.md` | 只注入当前用户；管理员可检查 |
| 管理员记忆 | `memories/chatbird/admin/discord-guild-<guild_id>/ADMIN.md` | 只在当前 Guild 的管理员上下文中注入和写入 |

普通用户不能命令 Agent “记住”或“忘记”某件事。Agent 只能主动保留稳定的偏好、特点、交流风格或长期背景；任务指令、完成记录、凭据、提示注入和短期状态不能进入用户档案。

Hermes 的 `/memory` 命令管理“写入审批队列”，不是查看已有记忆：

- `memory.write_approval = off` 是当前默认值，表示已获策略允许的写入直接保存；它不表示关闭记忆。
- `/memory approval on` 会把后续内置记忆写入放入待审批队列。
- `/memory approve <id>`、`/memory approve all`、`/memory reject <id>` 和 `/memory reject all` 用于处理队列。
- `No pending memory writes.` 只表示队列为空，不表示当前没有任何持久记忆。

## Slash Commands

原生 Slash Commands 已开启并以 Discord 全局命令注册。当前共 55 个命令；全局命令首次同步后 Discord 客户端可能需要刷新或等待传播。

普通用户可使用：

- `/help`
- `/whoami`
- `/status`
- `/version`
- `/usage`

其他所有内置、插件和未来动态发现的 Slash Command 默认管理员专属，必须同时通过管理员用户 ID 与当前 Guild 管理频道校验。DM 中所有 Slash Command 均拒绝；普通用户的 `/skill` 自动补全返回空列表，避免泄露已安装 Skill 目录。

Discord 命令面板中的应用名称是“小鸟AI”。邀请应用需要 `bot` 和 `applications.commands` 范围。用户所在频道还应允许“使用应用命令”。

## 私信

- Human DM 不回复，也不进入 Agent。
- DM 文本与有限的附件元数据追加到 `/root/.hermes/logs/chatbird-discord-dm.jsonl`。
- 日志文件权限固定为 `0600`。
- 仅记录附件 ID、文件名、类型和大小，不为了日志下载附件内容。

## 跨平台投递

Hermes 只有一个平台级 Discord home channel：

```text
DISCORD_HOME_CHANNEL=921407984586866781
```

这是公开测试频道，不得用于管理员记忆、私信日志、凭据或其他敏感结果。Guild 显式目标为：

```text
1146359014968537089:1148897557947367474
921407984586866778:921407984586866781
```

定时任务优先投递到 `origin`；确需明确目标时使用当前 Guild 的映射频道。ChatBird 已关闭 Hermes 的“未设置 home channel”首次提示。

## Bot 身份

`/root/.hermes/SOUL.md` 当前定义 Bot 为“小鸟聊天助手”，昵称“乌鸦”，英文名“ChatBird”，默认使用中文并采用俏皮、轻快、略带吐槽的语气。

Hermes 核心提示词仍会说明底层框架是 Hermes Agent。为了防止模型把框架名当成自己的名字，身份文件应明确写明：Hermes Agent 只是底层框架，Bot 自称应使用“乌鸦”或“ChatBird”。Discord 显示名称与模型自称是两套设置；显示名称需要在 Discord 应用或服务器成员昵称中修改。

## 本地补丁与代码

`hermes-stack.lock` 固定上游 Hermes 提交、补丁顺序和测试覆盖文件。对一个干净的 Hermes
checkout，可用 `scripts/apply-hermes-patches.sh <checkout> --check` 先做无写入
验证，再去掉 `--check` 应用完整 ChatBird 补丁栈。生产机当前保留 Hermes 自身的
Git 工作树；该脚本用于重建和升级验证，不直接覆盖生产工作树。

| 文件 | 用途 |
|---|---|
| [`../patches/hermes-discord-guild-memory-isolation.patch`](../patches/hermes-discord-guild-memory-isolation.patch) | Guild 会话键、历史与记忆隔离 |
| [`../patches/hermes-discord-public-access-dm-log.patch`](../patches/hermes-discord-public-access-dm-log.patch) | Guild 全员使用、DM 不回复与私密日志 |
| [`../patches/hermes-chatbird-home-notice.patch`](../patches/hermes-chatbird-home-notice.patch) | 关闭 Discord home-channel onboarding 提示 |
| [`../patches/hermes-chatbird-slash-policy.patch`](../patches/hermes-chatbird-slash-policy.patch) | Slash Command 公开集合与管理员频道双重校验 |
| [`../patches/hermes-discord-category-channel-allowlist.patch`](../patches/hermes-discord-category-channel-allowlist.patch) | 普通文字频道继承所属 Category 的 Discord 频道白名单 |
| [`../patches/hermes-skill-policy-exception.patch`](../patches/hermes-skill-policy-exception.patch) | 公共频道跳过不可用的 Skill 加载并直接使用网页工具 |
| [`../plugins/chatbird-policy/`](../plugins/chatbird-policy/) | 请求级工具权限、管理员上下文与分层记忆 |
| [`../patches/hermes-tests/test_discord_chatbird_access.py`](../patches/hermes-tests/test_discord_chatbird_access.py) | 生产 Hermes Discord 定向回归测试 |
| [`../patches/hermes-tests/test_chatbird_skill_policy_exception.py`](../patches/hermes-tests/test_chatbird_skill_policy_exception.py) | 公共频道 Skill 例外回归测试 |
| [`../tests/test_chatbird_policy.py`](../tests/test_chatbird_policy.py) | 本地策略插件测试 |

生产 Hermes 基线提交：

| 提交 | 说明 |
|---|---|
| `49d2aa56` | Guild 会话与记忆隔离 |
| `0b111a56` | Guild 成员开放与 DM 日志 |
| `bb0c3fff` | 关闭全局 home onboarding 提示 |
| `dc1aa78f` | Slash Command 分级与管理员频道校验 |

生产工作树还应用了两项由本仓库补丁栈跟踪的差异：

- `hermes-discord-category-channel-allowlist.patch`
- `hermes-skill-policy-exception.patch`

这些差异、生产配置、策略插件和测试均以 ChatBird 仓库 `main` 为唯一长期来源；
`codex/track-hermes-stack` 只是已合并的历史开发分支，不再承载独有内容。

### 2026-08-13 Discord Category 修复

频道 `1148897557947367474` 属于 Category `1146359015715110992`。用户已经正确
`@` Bot，但旧补丁只读取 `parent`/`parent_id`；discord.py 的普通
`TextChannel` 实际使用 `category`/`category_id`，因此 Category 没有进入频道
白名单判断。由于该频道自身未显式列入白名单，消息在提及检查前被静默拒绝。

修复后，普通 Guild 频道读取 `category`/`category_id`，Thread 读取
`parent`/`parent_id`；普通消息和 Slash Command 使用同一继承逻辑。测试替身也改为
模拟 discord.py 的真实字段，避免再次掩盖该问题。生产定向频道控制测试 16 项通过；
网关重启后为 `active`、`NRestarts=0`，短日志确认已连接 Discord。

## 最近验证结果

- `chatbird-policy` 本地定向测试：9 项通过。
- Hermes 技能提示与 ChatBird 公共策略直接断言：通过。
- DDGS 真实搜索烟测：中文“艾克打野最新攻略”返回 3 条结果，`web_search` 已进入模型工具列表。
- 6 个既有 Discord 会话的旧系统提示缓存已刷新；聊天历史、会话 ID 和记忆未删除，数据库 `quick_check` 为 `ok`。
- 生产 Discord ChatBird 定向测试：10 项通过。
- Discord 频道控制定向测试：16 项通过，包含普通消息和 Slash Command 的 Category
  白名单继承回归。
- Discord API：55 个全局命令已注册，5 个公开命令均存在。
- `hermes-gateway.service`：部署后核对为 `active`、`NRestarts=0`，短日志确认已连接 Discord。
- Bird Gaming 频道 `1395894673792569374`：Discord API 返回 `200`。

## 安全运维

常用只读检查：

```bash
ssh aliyun-germany
systemctl is-active hermes-gateway.service
systemctl show hermes-gateway.service -p MainPID -p NRestarts -p MemoryCurrent
journalctl -u hermes-gateway.service --since "10 minutes ago" --no-pager -n 100
git -C /usr/local/lib/hermes-agent status --short
git -C /usr/local/lib/hermes-agent log -5 --oneline
```

部署或升级时：

1. 先在本地审阅和测试补丁。
2. 检查生产内存、磁盘和服务负载。
3. 只上传需要变化的文件并保留临时备份。
4. 在生产只运行相关的单个测试文件。
5. 配置和源码都就绪后只重启网关一次。
6. 检查服务状态、重启次数、短日志和 Discord API 状态。
7. Hermes 升级后逐项确认补丁仍可应用，尤其是 Guild 会话键、DM 早退、Slash 授权入口和 `/skill` 自动补全。
