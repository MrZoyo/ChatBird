# ChatBird 生产状态与修改总览

模型与服务状态最后核对：2026-11-02（Europe/Berlin）。其他功能的历史验证日期见各节。

这份文档是 ChatBird 当前生产部署的非敏感总览，用于在仓库长期休眠后快速恢复上下文。它记录架构、ID 映射、安全边界、Hermes 补丁和验证方式，但不保存 API Key、Bot Token 或其他凭据。

## 生产位置

| 项目 | 当前值 |
|---|---|
| SSH 主机别名 | `aliyun-germany`（端口 `22222`；`22` 由云防火墙限制来源 IP） |
| Hermes 源码 | `/usr/local/lib/hermes-agent` |
| Hermes 配置 | `/root/.hermes/config.yaml` |
| Hermes 环境变量 | `/root/.hermes/.env`，权限应为 `0600` |
| ChatBird 身份提示词 | `/root/.hermes/SOUL.md` |
| systemd 服务 | `hermes-gateway.service` |
| 模型 | Anthropic Claude Sonnet 5.5 `claude-sonnet-5-5`（主模型、文本辅助任务和图片分析） |
| 备用模型 | Xiaomi `mimo-v2.6-flash`（主模型调用失败时切换；图片分析不跟随） |
| 策略插件 | `chatbird-policy` `1.5.0` |

生产机只有约 1.6 GiB 内存。只能做定向读取、单文件测试和短日志检查；不要在生产机运行全仓扫描、完整测试套件、高并发构建或无必要升级。不要打印、复制到日志或提交 `/root/.hermes/.env` 的实际值。

本地非敏感配置镜像是 [`../patches/chatbird-production-config.yaml`](../patches/chatbird-production-config.yaml)，环境变量格式参考 [`../.env.example`](../.env.example)。

### 待部署：Hermes v0.22.5（2026-11-02）

已在本地重建并验证，**生产未部署**。仓库里的 `hermes-stack.lock`、`patches/` 和插件 1.6.0 对应新版本，生产还跑在下面记录的旧基线和
插件 1.5.0 上。去留清单、部署和回滚方案见 [`hermes-upgrade-0.22.5.md`](hermes-upgrade-0.22.5.md)。

本地发现一个**生产现有漏洞**：文本命令 `@Bot /restart` 不经过 Slash 闸门，任何成员都可能运行管理命令。修复在新补丁里，部署前仍然存在。

### 2026-11-02 远程代码执行与文件发送收紧

用户已在 Discord 确认频道历史和图片分析正常，这是 11 月 1 日部署的用户侧验收。下一步在 Hermes 升级和代码
执行之间先做代码执行：它只是一个插件工具，不动 Hermes 核心，以后升级不用为它解冲突。私聊和关闭 SSH 密码
登录由用户决定暂不做。部署前由 Fable subagent 做了只读安全审查。

- **`chatbird_run_code`（公开工具）：** 用单独的 Anthropic 请求调用托管的 `code_execution_20260521`，代码在
  Anthropic 的容器里运行，没有外网，也碰不到这台服务器。工具只接受 `task` 字符串（上限 4 万字符），所以数据
  要写进去；用户上传的附件目前不会传进沙箱。每次调用都开新容器，容器 ID 只用于在同一次调用内恢复
  `pause_turn`，防止文件跨 Guild。单次调用最多 3 个请求，每个超时 150 秒，SDK 不重试（重试会让代码再跑一遍）。
  生成文件只从 API 的工具结果块里取，扩展名白名单，最多 4 个、每个 8 MiB，每次最多检查 8 个文件 ID；写入
  Hermes 文档缓存（24 小时后清理），并尽力从 Anthropic 文件存储删除。工具返回 `MEDIA:` 行，由主模型写进回复。
  这个工具不在 Hermes 的自动附加名单里，所以代码打印的 `MEDIA:` 字符串不会触发上传。
- **文件发送严格模式：** 回复里的 `MEDIA:` 行或本地路径会让网关把文件传到频道。Hermes 默认只拦一份简短的
  凭据名单；网关以 root 运行时 `/root` 本身放行，所以实测会话 JSON、Guild 记忆、用户画像和 `SOUL.md` 都能被
  发到公开频道，唯一的防线是模型自己拒绝。这是已有漏洞，会破坏 Guild 隔离，与代码执行无关，但代码输出多了
  一条注入途径，所以一起修。现在 `gateway.strict: true` 加 `gateway.trust_recent_files: false`，只有 Hermes 的
  缓存目录能发送。代价是管理员要发其他位置的文件时，得先复制到 `~/.hermes/cache/documents/`。

```yaml
gateway:
  strict: true
  trust_recent_files: false
```

Hermes 每回合用覆盖模式重载 `.env`，但只重新桥接 `max_turns`，所以 `.env` 里不能有 `HERMES_MEDIA_*`，否则会在第
一回合后悄悄覆盖上面的配置。当前数量为 0。

Fable 审查结论是可以部署，并发现两处已修复的问题：代码生成几百个文件时，文件 API 调用次数没有上限；SDK 重试
会让代码跑两遍。

成本：一次简单调用输入约 6,300、输出约 370 token，约 1.6 美分。输入主要是工具自带的提示词。容器时长每月
1,550 小时内免费，之后每小时 0.05 美元。

验证结果：

- 本地：ChatBird 单元测试 54 项通过。用真实 Anthropic SDK 0.87.0 对本地模拟服务器验证了 `pause_turn` 的请求体、
  文件元数据、下载和删除，以及严格模式下的路径判断。
- 生产（重启前，独立进程）：`gateway.run` 导入后两个环境变量为 `1` 和 `0`，重载 `.env` 后不变；会话 JSON、
  Guild 记忆、用户画像、`SOUL.md`、`.env` 都不可发送。用生产 Key 真实运行一次：计算斐波那契并生成 `fib.png`，
  文件通过严格模式校验，`extract_media` 能识别，结果里没有 Key。
- 生产（重启后）：Discord 平台工具解析包含 `chatbird_run_code`，共 22 个工具。网关于 01:07:50 CET 重启，新 PID 为
  `764075`，Discord 已连接，`NRestarts=0`，日志没有新错误。

未验证：

- 未在 Discord 实际对话验收。生成文件依赖主模型照抄 `MEDIA:` 行，模型漏写时文件不会发出。
- 无法在线上进程里直接读取严格模式的环境变量，上面的结论来自走同一启动代码的独立进程。
- API 返回的容器 `expires_at` 约为 1 小时后，文档写容器保留 30 天。隐私政策按更长的 30 天写。

升级 Hermes 时要重新确认：SDK 0.87.0 用的是 `client.beta.files`，新版 SDK 中其结构有破坏性变化，应改用
`client.files`。

部署前备份（仅生产机，目录权限 `0700`）：
`/root/.hermes/backups/code-execution-20261102T000711Z/`。

配置 SHA-256：

- 部署前：`ef1a875d3ebebbc68fb9d295d0e4e4f840a22ac0a98407017a7ec5f20397a229`
- 部署后：`8187250350a19b402aba3e0c28b12f5c45700b707a8fa33d546581830fb02c82`

### 2026-11-01 安全修复、频道历史与 MiMo 备用

用户让一个 Fable subagent 作为安全顾问，先确认问题和修复方案，再实施。本次部署：

- **图片下载 SSRF：** `vision_analyze` 的重定向防护检查 `response.next_request`，而 httpx 0.28.1
  在响应钩子里不设置它，防护从不生效，公开用户可以让一个公网图片 URL 302 到内部地址。非图片
  内容会被拒绝，但目标若返回图片，内容会被模型描述。回补上游 `500c2b1e46`，新增补丁
  `hermes-vision-redirect-ssrf.patch` 和回归测试。
- **策略闸门不再放行丢失身份的调用：** 旧逻辑对非 Discord 上下文一律放行，而网关里丢失身份的
  工作线程（已确认的路径是 `delegate_task` 的批量子任务）正好属于这一类。现在由网关进程标记
  `_HERMES_GATEWAY` 判断：网关内只有 cron（空 platform 且 session ID 以 `cron_` 开头）可以不带
  Discord 身份，其余一律拒绝；本地 CLI 不受影响。Fable 原方案用 ContextVar 的 `_UNSET` 识别 CLI，
  但丢失身份的线程同样是 `_UNSET`，因此没有采用。代价是管理员回合的批量 `delegate_task` 子任务
  现在没有工具可用。
- **`session_search` 在 Discord 和 cron 中禁用：** 它不按 Guild 过滤，管理员回合可以读到其他 Guild
  的会话，违反隔离约定。
- **新增 `chatbird_channel_history`：** 见“会话与历史边界”。
- **备用模型：** 配置 `fallback_model`（Xiaomi `mimo-v2.6-flash`），`XIAOMI_API_KEY` 已在 `.env` 中。
  每个新回合先试主模型，额度恢复后自动切回。图片分析固定走 Anthropic，额度耗尽时会失败。

```yaml
fallback_model:
  provider: xiaomi
  model: mimo-v2.6-flash
```

用户决定不设按人或按频道的配额，额度用完可以接受。10 月 11 日切换到 Claude 后至 11 月 1 日：
6 个会话、42 条用户消息、9 次工具调用，均在公开白名单内。按 token 数估算主对话花费约 2.6–4 美元
（Hermes 的费用字段为 0，且不含辅助任务；准确数字以 Anthropic Console 为准）。

验证结果：

- 本地：ChatBird 单元测试 36 项通过；11 个补丁可干净应用到锁定基线；重建后的栈上 URL 安全、
  重定向回归、静态提取、浏览器回退、Discord 访问、频道控制和公开 Skill 相关定向测试通过。去掉修复后
  新回归测试会失败。
- 闸门用真实的 `gateway.session_context` 和真实线程探测：网关内丢失身份、公开回合和管理员回合的裸线程
  都被拒绝；管理员主线程、cron 和本地 CLI 保持可用。
- 模型切换：用真实 `AIAgent` 和 Anthropic SDK 对本地模拟服务器验证，“API 用量上限” 400、“余额不足” 400
  和模拟的“消费上限” 403 都切到备用。Anthropic 实际额度耗尽时的错误文本未能实测。生产上用故意无效的
  Anthropic Key 跑了一次真实切换，返回 `FALLBACK_OK`，当前 provider 为 `xiaomi`。
- 生产：补丁 `git apply --check` 通过；定向测试 129 项通过；Discord 平台工具解析包含
  `chatbird_channel_history`。频道历史实测（只输出计数）：测试频道读 20 条返回 19 行；`limit=5000` 被
  限制为扫描 200 条；用另一 Guild 的身份读该频道被拒绝。curator 上次运行为
  `llm: skipped (consolidation off)`，不启动 Agent，不受闸门影响。
- 网关于 23:31:47 CET 重启，新 PID 为 `762846`，Discord 已连接，`NRestarts=0`。旧进程收到 SIGTERM 后以
  状态 1 退出，与前几次切换相同。重启后日志只有 Hermes 安全审计的两条既有警告。

这些不是 Discord 用户侧的对话验收。

尚未处理：

- sshd 仍允许 root 密码登录，由用户执行。服务仍以 root 运行，没有 systemd 沙箱。
- 图片下载的 DNS 重绑定防护（上游 `42626da1ce`）改动面较大，留待升级 Hermes。
- Hermes 升级：锁定基线为 v0.17.0（2026-06-27），最新稳定版 v0.22.5（2026-10-23）。把补丁栈与 2026-11-01
  的上游 main 试合并，17 个文件冲突，包括 `gateway/session.py`、`gateway/run.py`、Discord 适配器和
  `tools/memory_tool.py`。升级应单独安排，并以稳定 tag 为目标。main 已有原生 `scope_id` 会话隔离，可能替代
  部分 Guild 隔离补丁；但 `session_search` 仍无 Guild 过滤，适配器也未识别 `sk-ant-usr`。

部署前备份（仅生产机，目录权限 `0700`）：
`/root/.hermes/backups/security-history-fallback-20261101T222947Z/`。

配置 SHA-256：

- 部署前：`884e68901e7e54e0b0b752caf271c063f897a68f6518154ba47c595264895bac`
- 部署后：`ef1a875d3ebebbc68fb9d295d0e4e4f840a22ac0a98407017a7ec5f20397a229`

### 2026-11-01 Anthropic Key 轮换

用户换用一把带限制的新 `sk-ant-usr-` Key。只改 `.env` 中 `ANTHROPIC_API_KEY` 这一行，
模型和配置不变。`auth.json` 的凭据池不保存 Key 本身，只保存 `env:ANTHROPIC_API_KEY`
引用和指纹，加载时从 `.env` 重新读取，因此不需要手改。

具体限制在创建 Key 时设置，这里无法读取。API 响应头只显示速率上限（请求 13,000、
输入 token 10,000,000、输出 token 2,000,000），看不到消费限额。生产没有配置
`fallback_model`，Key 达到限额后 Bot 会报错，不会自动切到 `XIAOMI_API_KEY`（这是当时的状态，
同日稍后已配置备用模型，见上一节）。

验证结果：

- 替换前在生产机用新 Key 串行烟测 `claude-sonnet-5-5`：文本 1.52 秒；流式 1.16 秒；
  合成工具调用及结果回传合计约 2.8 秒，未执行外部工具；合成纯红 PNG 识别为 `RED`，
  1.21 秒。
- 网关于 20:29:30 CET 重启，新 PID 为 `760278`，20:29:40 确认 Discord 已连接
  （状态文件 PID 与 `MainPID` 一致），服务为 `active/running`、`NRestarts=0`。
  重启后日志没有认证错误。旧进程收到 SIGTERM 后以状态 1 退出，与前几次切换相同。
- 按生产配置解析：主 runtime 为 `anthropic` / `anthropic_messages` /
  `https://api.anthropic.com`，读取新 Key，认证方式为 `x-api-key`，实际调用返回
  `MAIN_OK`，1.29 秒。压缩、标题生成、网页摘要和视觉客户端均为 `claude-sonnet-5-5`；
  标题生成客户端实际调用返回 `PROD_OK`，1.19 秒。
- 凭据池条目的 `auth_type` 仍显示 `oauth`：`credential_pool.py` 把 `sk-ant-api` 以外的
  前缀都这样标记，补丁未改动此处。实际认证由 `anthropic_adapter.py` 决定，已确认不走 OAuth。

这些是简短 API 烟测，不是 Discord 用户侧的对话验收。

替换前备份（仅生产机，目录权限 `0700`）：
`/root/.hermes/backups/anthropic-key-rotation-20261101T192930Z/`，包含 `.env` 和
`auth.json`，其中有旧 Key。`config.yaml` 未修改，SHA-256 为
`884e68901e7e54e0b0b752caf271c063f897a68f6518154ba47c595264895bac`。

### 2026-10-11 Claude Sonnet 5.5 切换

用户每月有 200 美元仅限 API 使用的 Claude 额度，确认主对话和辅助任务改用
Claude Sonnet 5.5（`claude-sonnet-5-5`），通过 Anthropic 原生 Messages API
`https://api.anthropic.com` 调用。生产仅修改以下两项，文本辅助任务继续继承主模型：

```yaml
model:
  provider: anthropic
  default: claude-sonnet-5-5

auxiliary:
  vision:
    provider: anthropic
    model: claude-sonnet-5-5
```

新凭据以 `ANTHROPIC_API_KEY` 追加到 `.env`，权限保持 `0600`；`XIAOMI_API_KEY`
保留用于回退。该 Key 的前缀是 `sk-ant-usr-`。当前 Hermes（上游 2026-10-09 的
`main` 仍然如此）把 `sk-ant-api*` 以外的所有 `sk-ant-*` 视为 OAuth token，会改用
Bearer 认证并套用 Claude Code 身份转换：系统提示前置 Claude Code 身份、把
“Hermes Agent” 替换为 “Claude Code”、给工具名加 `mcp__` 前缀并伪装 CLI
User-Agent，从而改写 ChatBird 人设。新增补丁
[`hermes-anthropic-user-api-key.patch`](../patches/hermes-anthropic-user-api-key.patch)
让 `sk-ant-usr-*` 与普通 API Key 一样走 `x-api-key`。

Hermes 的 Anthropic SDK 是可选依赖，生产 venv 原先没有安装。本次只安装 Hermes
锁定的 `anthropic==0.87.0` 及其新增依赖 `docstring_parser`，未升级 Hermes 或其他依赖。

`agent.reasoning_effort` 仍未设置。此时 Hermes 不发送 `thinking` 和 `effort`，
Sonnet 5.5 按 API 默认值运行：自适应思考、effort `high`。Sonnet 5.5 会拒绝
`thinking: disabled`、强制 `tool_choice` 和非默认采样参数；已核对当前 Hermes
不会在这些路径上发送它们：关闭思考时省略参数，Claude 4.7 及以后的模型自动去掉采样参数，
非测试代码不使用强制 `tool_choice`。旧轮次的 thinking 块会被剥离，只保留最新助手回合的签名块。

验证结果：

- 本地：9 个补丁可干净应用到锁定基线；Hermes Anthropic 相关测试 438 项通过。
  另有 3 项 `TestRunOauthSetupToken` 在 macOS 上失败，未打补丁的基线同样失败
  （钥匙串读取路径），与生产 Linux 无关。本地配置守卫和 21 项 ChatBird 单元测试通过。
- 生产切换前：`anthropic_adapter.py` 与锁定基线逐字节一致，补丁 `git apply --check`
  通过，生产定向测试 18 项通过。经打补丁的适配器串行烟测，认证方式均为
  `x-api-key`，模型均为 `claude-sonnet-5-5`：流式文本 1.31 秒；合成工具调用及结果
  回传两次请求合计约 2.0 秒，未执行外部工具；合成纯红 PNG 识别为 `RED`，1.02 秒。
- 配置按 YAML 结构比较，只有 `model` 与 `auxiliary.vision` 变化；生产配置守卫通过。
- 网关于 22:28:24 CEST 重启，新 PID 为 `633777`，22:28:30 确认 Discord 以
  `小鸟AI#6255` 连接，服务为 `active/running`、`NRestarts=0`。重启后的错误日志只有
  Hermes 安全审计的两条既有警告：以 root 运行、SSH 允许密码登录。旧进程收到
  SIGTERM 后以状态 1 退出，与前两次切换相同。
- 切换后按生产配置解析：主 runtime 为 `anthropic` / `anthropic_messages` /
  `https://api.anthropic.com`；压缩、标题生成、网页摘要、后台审阅和视觉客户端均为
  `claude-sonnet-5-5` 且不走 OAuth。标题生成客户端实际调用返回 `PROD_OK`，耗时 1.34 秒。

这些是简短 API 烟测，不是 Discord 用户侧的对话验收。

切换前备份（仅生产机，目录权限 `0700`）：
`/root/.hermes/backups/claude-sonnet-5-5-20261011T202608Z/`，包含 `config.yaml`、
`.env`、`anthropic_adapter.py` 及其测试文件。回退时先核对此后的配置变更，再定向
恢复两处模型设置并重启网关；`XIAOMI_API_KEY` 仍在 `.env` 中，补丁和 SDK 可以保留。

配置 SHA-256：

- 切换前：`9df20a239be68f4d64047e453762256441e39e04f5b1ee29aa56cb189904cc92`
- 切换后：`2d3b8180ebd3e48a4c58773ac3db0eabd8343768e1e3591fa36087cc4c393ae4`

### 2026-09-27 MiMo V2.6 Flash 切换

用户反馈切换 Pro 后对话过慢。生产日志中的这次查询耗时 576.7 秒，共 9 轮
主模型调用、14 次工具调用；主模型请求及其重试合计 496.7 秒。首轮请求耗时
111.9 秒，末轮出现连续 180 秒没有流式数据后断开重试。网页提取与模型摘要
另耗时约 49.9 秒。服务器负载接近零、可用内存约 917 MiB，未使用 swap。
日志能够定位等待环节，但无法区分模型推理、供应商排队和网络停顿各占多少。
`iteration 8/90` 表示调用轮数与预算上限；本次在第 9 轮结束。

用户确认主对话和辅助任务都先换成非 Pro 的
[`mimo-v2.6-flash`](https://mimo.mi.com/models/en-US/mimo-v2.6-flash)。
生产仅修改以下两项，文本辅助任务继续继承主模型：

```yaml
model:
  provider: xiaomi
  default: mimo-v2.6-flash

auxiliary:
  vision:
    provider: xiaomi
    model: mimo-v2.6-flash
```

按 YAML 结构比较确认其他配置完全相同，包括两个 Guild、10 个频道/Category
白名单、策略插件、记忆隔离、思考设置和 90 轮预算。配置权限保持 `0600`。
本地配置守卫及其 4 项单元测试通过；生产临时配置也在替换前通过守卫。

切换前用现有生产凭据串行烟测，均返回目标模型 `mimo-v2.6-flash`：

- 两次简短流式文本测试通过，总耗时分别为 6.515 秒和 3.009 秒。
- 合成工具调用及结果回传通过，两次请求合计 13.736 秒，未执行外部工具。
- 合成纯红 PNG 识别为 `RED`，耗时 6.539 秒。

网关于 19:23:25 CEST 重启，新 PID 为 `556464`，19:23:32 确认 Discord
已连接，服务为 `active/running`、`NRestarts=0`。这里只重启一次，未升级
Hermes 或依赖，也未修改会话与持久记忆。

切换后，通过 Hermes 按生产配置解析的客户端完成简短流式文本烟测，响应模型
为 `mimo-v2.6-flash`，首个流式数据块耗时 15.303 秒，总耗时 16.072 秒。
压缩、网页摘要、标题生成、后台审阅和视觉客户端均解析为 Flash；此项只检查
辅助客户端选型，未逐项运行完整业务流程。网关状态文件确认 Discord
`connected`，没有连接错误。

这些简短 API 烟测不是原问题的受控重放，也不是 Discord 用户侧的对话验收；
三次文本烟测总耗时约 3–16 秒，接口仍有波动，不能据此承诺复杂查询的端到端耗时。

切换前备份（仅生产机，权限 `0600`）：
`/root/.hermes/backups/mimo-v2.6-flash-20260927T172322Z/config.yaml`。
如需回退，先核对后续配置变更，再定向恢复两处模型设置。

配置 SHA-256：

- 切换前：`192f8952151282ead3f1c51c11d3634de7476f6d28a291ba340d59a5b7885746`
- 切换后：`9df20a239be68f4d64047e453762256441e39e04f5b1ee29aa56cb189904cc92`

### 2026-09-22 MiMo V2.6 Pro 切换

Mac 已通过现有 `aliyun-germany` SSH 配置连接生产机。切换前服务为
`active/running`、`NRestarts=0`；可用内存约 875 MiB，根分区剩余约 20 GiB。
生产原模型实际为 `mimo-v2.5`，不是 `mimo-v2.5-pro`。

新模型使用官方标识 [`mimo-v2.6-pro`](https://mimo.mi.com/models/zh-CN/mimo-v2.6-pro)，
继续通过 Xiaomi 的 `https://api.xiaomimimo.com/v1` 和原有生产凭据调用。
只修改模型配置，未升级 Hermes 或依赖：

```yaml
model:
  provider: xiaomi
  default: mimo-v2.6-pro

auxiliary:
  vision:
    provider: xiaomi
    model: mimo-v2.6-pro
```

使用 `model.default` 是因为当前 Hermes 的辅助客户端读取该字段；旧的
`model.model` 虽能被 Gateway 识别，却不能被所有辅助任务读取。
图片分析需单独指定，避免当前 Hermes 的 Xiaomi 视觉默认值继续选择 `mimo-v2.5`。
已验证上下文长度自动识别为 1,048,576 tokens，无需增加覆盖值。

生产配置在原文件上定向修改，并按 YAML 结构比较确认其他设置完全不变，包含
两个 Guild、10 个频道/Category 白名单、策略插件和记忆隔离设置。本地配置镜像
保留原有示例白名单，不应整份覆盖生产配置。API Key、Bot Token、会话和持久记忆
均未修改。

验证结果：

- 本地生产配置守卫和其 4 项单元测试通过。
- 切换前，现有生产凭据可列出并调用 V2.6 Pro；文本请求和带推理内容回传的
  合成工具调用完整往返通过。
- 切换后，经 Hermes 客户端解析的流式文本返回 `MIMO_STREAM_OK`，图片分析将
  合成纯红 PNG 识别为 `RED`；两次响应的模型均为 `mimo-v2.6-pro`。
- 文本压缩、网页提取、标题生成和后台审阅的客户端均解析为 `mimo-v2.6-pro`。
  此项验证客户端选型，未逐项运行对应完整业务流程。
- 网关于 19:05:13 CEST 重启，新进程 PID 为 `529347`，19:05:23 确认 Discord
  已连接。服务为 `active/running`、`NRestarts=0`，启动配置守卫通过。
- Discord Bot 身份接口及两个允许 Guild 的接口均返回 HTTP 200。
- 旧日志中的 Discord 503 重连异常在切换前最近半小时没有重现。重启时旧进程
  收到 SIGTERM 后以状态 1 退出；新进程正常启动并连接，未发生自动重启。

本次未代用户在 Discord 发送消息，因此未声称完成 Discord 用户侧的实际对话验收。

切换前配置备份（仅生产机，权限 `0600`）：
`/root/.hermes/backups/mimo-v2.6-pro-20260922T170502Z/config.yaml`。
回退时先确认此后是否有其他配置修改，再恢复对应模型设置并重启网关；不要覆盖
后续白名单或其他运维变更。

配置 SHA-256：

- 切换前：`6378b12c49b5ee6aa4b72ace2f19e48dab4f61219995d9839db571d20439648a`
- 切换后：`192f8952151282ead3f1c51c11d3634de7476f6d28a291ba340d59a5b7885746`

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
- 最近历史回填开启，按需抓取：只在 Bot 被提及时，从触发消息向前读取最多 200 条
  Discord 消息（2026-10-11 由 50 调整，备份为
  `/root/.hermes/backups/backfill-200-20261011T203630Z/config.yaml`）。读取遇到 Bot
  自己上一条对话回复即停止，因为更早内容已在会话记录中；系统消息、空消息和其他
  Bot 的消息被过滤，纯附件只显示为 `(attachment)`，Bot 处理期间的新消息不会补抓。
  用户通过 Discord“回复”指向更早消息时，另外读取该消息及其之前最多 10 条。
- 会话按 Hermes 默认策略重置：每天 04:00（服务器时区 Asia/Shanghai）或闲置 24 小时，
  以先到者为准。重置后，Bot 上一条回复之前的内容既不在会话中，也不会被回填。
- 需要更早的内容时，模型可以自己调用 `chatbird_channel_history`，通过 Discord REST 读取当前频道最近最多
  200 条消息，可按关键词筛选。频道只取自请求身份，不接受模型传参，并核对频道所属 Guild。结果标记为不可信
  数据，总长度上限约 4 万字符；系统消息、空消息和其他 Bot 的消息被过滤。在讨论串中只读该讨论串，不读父频道。
- 未列入 `discord.allowed_guilds` 的服务器 fail closed，即使公开 Bot 被邀请进去也不能使用 Agent。

## 用户与管理员权限

普通用户可以在允许的 Guild 和频道中聊天、提问、搜索网页、提取静态网页正文和进行视觉分析。生产使用无需密钥的 DDGS 搜索后端，以及无需密钥、按请求工作的 `simple-http` 静态 HTML/text/JSON/XML 提取后端。普通用户还能列出和读取经过独立审批、与当前文件 SHA-256 绑定的公开 Skill；未审批、被修改或无法验证的 Skill 不可见。公开读取不会执行 Skill 模板、内联命令或密钥初始化。普通用户还可以通过 `chatbird_channel_history` 让 Bot 读取当前频道最近最多 200 条消息，通过 `chatbird_run_code` 让 Bot 在 Anthropic 托管的无外网沙箱里运行代码。普通用户不能使用终端、文件、本地代码执行、内置记忆、会话搜索、Cron、Skill 管理、代理委派、跨平台消息、计算机控制或 Kanban 等敏感工具。`session_search` 在管理员频道和 cron 中同样禁用，因为它不按 Guild 过滤。

生产已启用透明本地 Chromium 回退：公开用户仍只调用 `web_search`/`web_extract`，主提供方遇到 403、5xx、超时、JS challenge 或空正文时，Hermes 在后台启动一个短时浏览器，执行固定 DOM 读取后立即关闭。全进程最多同时运行一个回退，单次最多处理两个页面，不向公开用户暴露点击、输入、登录、下载或任意 JavaScript 能力，也不会切换 IP 绕过 HTTP 429 限流。本地 Chromium 可以处理 JavaScript 渲染，但不能保证通过验证码、住宅 IP 或高级反检测挑战。

两个炉石站点采用不同的合规路径。HSGuru 的页面在本机数据中心 IP 下仍返回 Cloudflare challenge，且其公开 `robots.txt` 明确禁止自动访问 `/api`、`/decks` 和带查询参数的统计页；Hermes 因此只通过 DDGS 的公开索引检索 HSGuru 页面与摘要，不逆向或绕过这些接口。查询明确提到 HSGuru、但普通结果没有 HSGuru 链接时，Hermes 最多查询 Yahoo 的 Meta/Decks 与全站两个公开索引，并过滤掉非 HSGuru 结果；明确限流不重试。Vicious Syndicate 的本地浏览器、WordPress API、RSS 和站点地图同样被 challenge 拦截，但 Jina Reader 能返回公开文章正文；即使本地 Chromium requirements 不满足，Reader 仍独立尝试。生产只把精确域名 `www.vicioussyndicate.com` 的无查询参数公开页面交给该只读后端，并复核返回源域名和挑战页标记。

Discord 帮助中心 `support.discord.com` 由 Zendesk 提供，其文章页对所有非浏览器
客户端返回 Cloudflare 挑战（HTTP 403，`cf-mitigated: challenge`），机房 IP 和家庭
宽带都一样，生产的本地 Chromium 也无法通过；这不是网络封锁，`discord.com` 的其他页面
均返回 200。其 robots 规则允许文章页和文章 API，只禁止访问统计端点。2026-10-11 起，
`web_extract` 主提取失败后，`web.browser_fallback.zendesk_article_api_hosts` 中精确
列出的主机的文章 URL（`/hc/<locale>/articles/<id>`）改为在启动 Chromium 前读取公开的
Help Center 文章 API。请求沿用 simple-http 的公网、重定向和大小限制，要求同主机、
文章 ID 一致且非草稿，不转发查询参数。生产按真实配置端到端调用 `web_extract` 读取
Age-Restricted Channels 文章：3.9 秒返回 2,746 字符正文，没有启动浏览器。部署前
备份位于 `/root/.hermes/backups/help-center-api-20261011T211937Z/`；网关于
23:20:50 CEST 重启，新 PID 为 `636982`，Discord 已连接，`NRestarts=0`。

所有 Discord 回合都会收到网页能力验收规则，包括管理员频道：必须先测试正式 `web_search`/`web_extract` 入口。直接浏览器只作为单一路径诊断；其 Cloudflare challenge 不能被表述成完整检索链失败。`gaming-references` Skill 同样按此口径维护，并分别要求 HSGuru 使用自然语言搜索、Vicious Syndicate 使用搜索定位后的正文提取。

公开频道触发的后台自我改进可以提议新建公开 Skill，或更新已经公开审批的 Skill；改动必须先进入候选目录，经过静态惰性内容校验，再由一个无工具、无记忆的独立 Agent 审批。拒绝、超时、输出格式错误、身份丢失或策略异常都 fail closed，并保留旧版本。公开后台任务不能修改未审批/私有 Skill，也不能删除 Skill。

管理员上下文必须同时满足：

1. Discord 用户 ID 在 `CHATBIRD_ADMIN_USERS` 中；
2. 当前 `guild_id:channel_id` 精确匹配 `CHATBIRD_ADMIN_CHANNELS`。

因此管理员在普通频道里也只获得普通用户能力。未知 Guild、错误频道、缺失用户信息和 DM 都不能进入管理员上下文。网关内没有 Discord 身份的工具调用一律拒绝，只有 cron 例外。详细规则见 [`multi-user-policy.md`](multi-user-policy.md)。

## 记忆设计

| 记忆层 | 路径 | 访问规则 |
|---|---|---|
| Guild 公共记忆 | `memories/scopes/discord-guild-<guild_id>/MEMORY.md` | 当前 Guild 可读取；写入要求管理员上下文 |
| 用户档案 | `memories/chatbird/profiles/discord-guild-<guild_id>/<user_id>.md` | 只注入当前用户；管理员可检查 |
| 管理员记忆 | `memories/chatbird/admin/discord-guild-<guild_id>/ADMIN.md` | 只在当前 Guild 的管理员上下文中注入和写入 |

普通用户不能命令 Agent “记住”或“忘记”某件事。Agent 只能主动保留稳定的偏好、特点、交流风格或长期背景；任务指令、完成记录、凭据、提示注入和短期状态不能进入用户档案。

`memory.user_profile_enabled` 必须保持 `false`。该开关控制 Hermes 内建的共享
`USER.md`，不是 ChatBird 用户画像。ChatBird 的画像功能由 `chatbird-policy` 和
`chatbird_memory` 提供，并按 `guild_id + user_id` 隔离。systemd 在每次启动 Hermes
前运行 `validate-production-config.py`：它会自动把这一开关恢复为 `false`，并在
`discord.allowed_guilds` 缺失、包含通配符或策略插件未启用时拒绝启动。

2026-08-13，Hermes 曾把该开关误解为 ChatBird 画像开关并写成 `true`。当时运行中
的 Gateway 仍使用修改前的安全配置，因此共享 `USER.md` 从未生效。修复已恢复
`false`、更正持久化的 `chatbird-admin` Skill、升级策略插件并安装上述启动守卫。

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

下表和“生产 Hermes 基线提交”记录的是生产当前运行的旧补丁栈。v0.22.5 的新补丁栈有 8 个补丁，去掉了
`hermes-skill-policy-exception`、`hermes-anthropic-user-api-key` 和 `hermes-vision-redirect-ssrf`，部署后这里要同步改。

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
| [`../patches/hermes-anthropic-user-api-key.patch`](../patches/hermes-anthropic-user-api-key.patch) | `sk-ant-usr-*` Anthropic API Key 走 `x-api-key`，不套用 Claude Code OAuth 身份转换 |
| [`../patches/hermes-help-center-article-api.patch`](../patches/hermes-help-center-article-api.patch) | 白名单 Zendesk 帮助中心文章在浏览器回退前改读公开文章 API |
| [`../patches/hermes-vision-redirect-ssrf.patch`](../patches/hermes-vision-redirect-ssrf.patch) | 回补上游修复，让图片下载的重定向防护真正生效 |
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

2026-10-11 起，生产工作树另外应用 `hermes-anthropic-user-api-key.patch` 和
`hermes-help-center-article-api.patch`。2026-11-01 起另外应用
`hermes-vision-redirect-ssrf.patch`。

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
fail2ban-client status sshd
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

### SSH 与 fail2ban

2026-10-11 核对：

- sshd 同时监听 `22` 和 `22222`。`22` 由云防火墙限制来源 IP，日常从 Mac 使用
  `22222`；`~/.ssh/config` 中的 `aliyun-germany` 已设为 `Port 22222`。主机 ED25519
  指纹为 `SHA256:KtKiq81KDydvJ5ZW3TPvLXXM1h3B+mwyBLeb0XlNZqQ`。
- 本机 ufw 未启用，iptables 没有规则，端口限制只在云安全组一层。
- fail2ban `1.0.2`（Ubuntu 包）使用 systemd journal 和 nftables。本地规则位于
  `/etc/fail2ban/jail.d/chatbird.local`，仓库副本为
  [`../deploy/fail2ban/chatbird.local`](../deploy/fail2ban/chatbird.local)：
  - `sshd` 同时封禁 `22,22222`：10 分钟内失败 5 次封 1 小时，`mode = aggressive`；
    重复违规的封禁时间按 2 倍递增，最长 1 周。
  - `recidive`：1 天内被封 3 次的地址全端口封禁 1 周。
- 演练封禁测试地址 `192.0.2.123` 后，nftables 规则覆盖 `tcp dport { 22, 22222 }`；
  解封后规则清空。fail2ban 常驻内存约 38 MiB。
- 9 月 13 日以来的 auth 日志没有失败登录记录。
- sshd 仍允许 root 使用密码登录（`PasswordAuthentication yes`），Hermes 安全审计也对此告警。

2026-11-02 核对：过去 7 天有 2,009 次密码登录失败，来自 1,003 个 IP，其中 357 次针对 root。密码登录成功 0 次，公钥
登录成功 27 次。只有 39 个 IP 失败达到 5 次，所以 fail2ban 拦不住大部分这种分散的尝试。用户决定暂不关闭密码登录，
前提是 root 密码足够长且随机，并且没有在别处用过。

误封自己时，通过阿里云控制台登录后执行 `fail2ban-client set sshd unbanip <IP>`。
