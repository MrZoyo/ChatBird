# ChatBird 生产状态与修改总览

最后核对：2026-08-13（Europe/Berlin）

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
| 策略插件 | `chatbird-policy` `1.3.1` |

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
- Guild 频道（包括语音频道内置文字聊天）需要明确提及 Bot；讨论串也需要提及。
- 最近历史回填开启，最多读取 50 条可见消息作为有界上下文。
- 未列入 `discord.allowed_guilds` 的服务器 fail closed，即使公开 Bot 被邀请进去也不能使用 Agent。

## 用户与管理员权限

普通用户可以在允许的 Guild 和频道中聊天、提问、搜索网页、提取静态网页正文和进行视觉分析。生产使用无需密钥的 DDGS 搜索后端，以及无需密钥、按请求工作的 `simple-http` 静态 HTML/text/JSON/XML 提取后端。普通用户还能列出和读取经过独立审批、与当前文件 SHA-256 绑定的公开 Skill；未审批、被修改或无法验证的 Skill 不可见。公开读取不会执行 Skill 模板、内联命令或密钥初始化。普通用户不能使用终端、文件、代码执行、内置记忆、会话搜索、Cron、Skill 管理、代理委派、跨平台消息、计算机控制或 Kanban 等敏感工具。

生产已启用透明本地 Chromium 回退：公开用户仍只调用 `web_search`/`web_extract`，主提供方遇到 403、5xx、超时、JS challenge 或空正文时，Hermes 在后台启动一个短时浏览器，执行固定 DOM 读取后立即关闭。全进程最多同时运行一个回退，单次最多处理两个页面，不向公开用户暴露点击、输入、登录、下载或任意 JavaScript 能力，也不会切换 IP 绕过 HTTP 429 限流。本地 Chromium 可以处理 JavaScript 渲染，但不能保证通过验证码、住宅 IP 或高级反检测挑战。

两个炉石站点采用不同的合规路径。HSGuru 的页面在本机数据中心 IP 下仍返回 Cloudflare challenge，且其公开 `robots.txt` 明确禁止自动访问 `/api`、`/decks` 和带查询参数的统计页；Hermes 因此只通过 DDGS 的公开索引检索 HSGuru 页面与摘要，不逆向或绕过这些接口。查询明确提到 HSGuru、但普通结果没有 HSGuru 链接时，Hermes 最多查询 Yahoo 的 Meta/Decks 与全站两个公开索引，并过滤掉非 HSGuru 结果；明确限流不重试。Vicious Syndicate 的本地浏览器、WordPress API、RSS 和站点地图同样被 challenge 拦截，但 Jina Reader 能返回公开文章正文；即使本地 Chromium requirements 不满足，Reader 仍独立尝试。生产只把精确域名 `www.vicioussyndicate.com` 的无查询参数公开页面交给该只读后端，并复核返回源域名和挑战页标记。

所有 Discord 回合都会收到网页能力验收规则，包括管理员频道：必须先测试正式 `web_search`/`web_extract` 入口。直接浏览器只作为单一路径诊断；其 Cloudflare challenge 不能被表述成完整检索链失败。`gaming-references` Skill 同样按此口径维护，并分别要求 HSGuru 使用自然语言搜索、Vicious Syndicate 使用搜索定位后的正文提取。

公开频道触发的后台自我改进可以提议新建公开 Skill，或更新已经公开审批的 Skill；改动必须先进入候选目录，经过静态惰性内容校验，再由一个无工具、无记忆的独立 Agent 审批。拒绝、超时、输出格式错误、身份丢失或策略异常都 fail closed，并保留旧版本。公开后台任务不能修改未审批/私有 Skill，也不能删除 Skill。

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
| [`../patches/hermes-discord-category-channel-allowlist.patch`](../patches/hermes-discord-category-channel-allowlist.patch) | Guild 频道（含语音频道内置文字聊天）继承 Category 白名单，并在频道删除后取消遗留回合 |
| [`../patches/hermes-skill-policy-exception.patch`](../patches/hermes-skill-policy-exception.patch) | 公共频道跳过不可用的 Skill 加载并直接使用网页工具 |
| [`../patches/hermes-public-skills-web-extract.patch`](../patches/hermes-public-skills-web-extract.patch) | 公开 Skill 哈希审批、自我改进二次审批与无密钥静态网页提取 |
| [`../patches/hermes-web-browser-fallback.patch`](../patches/hermes-web-browser-fallback.patch) | `web_search`/`web_extract` 内部受限浏览器回退，不扩大公开工具权限 |
| [`../patches/hermes-gateway-browser.conf`](../patches/hermes-gateway-browser.conf) | Hermes 服务的本地 Chromium 可执行文件位置 |
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

修复后，Guild 频道（包括语音频道内置文字聊天）读取 `category`/`category_id`，Thread 读取
`parent`/`parent_id`；普通消息和 Slash Command 使用同一继承逻辑。测试替身也改为
模拟 discord.py 的真实字段，避免再次掩盖该问题。生产定向频道控制测试 18 项通过；
网关重启后为 `active`、`NRestarts=0`，短日志确认已连接 Discord。

Category `1149352792532734052` 用于动态创建的临时语音频道。语音频道的内置文字
聊天与语音频道共用同一个 channel ID，并通过 `category_id` 继承该 Category 的
白名单权限；被正确 `@` 的消息会进入 Agent。Discord 删除临时频道时，适配器会取消
该频道正在运行、排队或等待聚合的 Agent 回合。历史 transcript 仍按 Hermes 的保留
策略存在；新建临时频道会获得新的 channel ID，不会复用旧 session。

## 最近验证结果

- `chatbird-policy` 本地定向测试：14 项通过。
- 公开 Skill、二次审批、提取器及相邻 Skill 回归：63 项通过。
- 浏览器/Reader 回退定向测试：15 项通过。生产使用 `agent-browser 0.26.0` 和按需本地 Chromium；自然语言 HSGuru 查询通过公开索引返回 HSGuru Meta 链接，Vicious Syndicate 正文通过正式 `web_extract` 的精确域名 Reader 返回约 16K 字。
- `simple-http` 真实提取 `https://arammayhem.com/zh-cn/tier-list/`：标题和 13,702 字符正文成功返回，包含盲僧 `40.41%`、星界游神 `40.66%`、离群之刺 `40.91%`。
- Hermes 技能提示与 ChatBird 公共策略直接断言：通过。
- DDGS 真实搜索烟测：中文“艾克打野最新攻略”返回 3 条结果，`web_search` 已进入模型工具列表。
- 6 个既有 Discord 会话的旧系统提示缓存已刷新；聊天历史、会话 ID 和记忆未删除，数据库 `quick_check` 为 `ok`。
- 生产 Discord ChatBird 定向测试：10 项通过。
- Discord 频道控制定向测试：18 项通过，包含普通文字消息、语音频道内置文字聊天、
  Slash Command 的 Category 白名单继承，以及频道删除后的回合取消。
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

本地浏览器运行时安装在 `/root/.agent-browser/browsers/`，稳定入口是
`/usr/local/bin/chatbird-chromium`。systemd drop-in 使用
`AGENT_BROWSER_EXECUTABLE_PATH` 将 Hermes 指向该入口。升级 `agent-browser` 或
Chromium 后，应更新稳定入口并重新执行浏览器 requirements、公开网页导航、DOM
读取和进程清理四项定向烟测。不要在这台小服务器上配置常驻浏览器池或并发浏览器。
