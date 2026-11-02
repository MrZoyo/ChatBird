# Hermes 升级到 v0.22.5

状态：本地重建和验证已完成，生产尚未部署。生产仍是旧基线 `f53b184c` 加旧补丁栈，生产事实以
[`production-state.md`](production-state.md) 为准。

| 项目 | 旧 | 新 |
|---|---|---|
| 基线 | `f53b184c`（2026-06-27，文档里称 v0.17.0） | `v0.22.5` = `bf0203a7`（2026-10-22） |
| 补丁 | 11 个 | 8 个 |
| Python | 3.11 | 3.14（见“解释器”） |
| 策略插件 | 1.5.0 | 1.6.0 |
| Anthropic SDK | 0.87.0 | 0.87.0（v0.22.5 仍锁这个版本） |
| 状态库 schema | 16 | 32（首次打开时自动迁移） |

2026-11-02 确认最新稳定 tag 仍是 `v0.22.5`。`rc.1-v0.22.6` 和 `v0.22.5+canary.*` 不算稳定版。

## 补丁去留

| 旧补丁 | 去留 | 原因 |
|---|---|---|
| `hermes-discord-guild-memory-isolation` | 重写 | 上游的 `scope_id` 只隔离 Slack，`build_session_key` 的注释写明 Discord Guild 故意不进会话键，所以不能替代。键格式不变（`agent:main:discord:group:<chat>:guild-<id>`），现有会话能接上。原来两处构造 agent 改成五处，新增的是后台任务、定时压缩、`/compress` 和 cron。mem0 已移出上游主树，相关改动删除；外部记忆提供方的用户 ID 前缀改在通用入口。 |
| `hermes-discord-public-access-dm-log` | 重写 | 上游只在没有白名单时才看 allow-all，生产同时配了 `DISCORD_ALLOWED_USERS`，所以仍需要。私信拦截移到 `_discord_message_admission`，实时消息和恢复消息都经过这里。 |
| `hermes-chatbird-home-notice` | 重写 | 提示移到 `gateway/run_turn_prepare.py`。 |
| `hermes-chatbird-slash-policy` | 重写并扩大 | 授权移到 `adapter_slash_auth.py`。新增：文本命令也过同一道闸门，见下节。 |
| `hermes-discord-category-channel-allowlist` | 重写 | 改在 `_discord_channel_keys_from_channel` 这一个入口做。`_get_parent_channel_id` 恢复上游语义，否则 Category ID 会进入 `parent_chat_id`。讨论串只继承父频道，和旧行为一致。 |
| `hermes-skill-policy-exception` | 并入下一个 | 下一个补丁本来就会整段改写这句提示。 |
| `hermes-public-skills-web-extract` | 重写 | 上游拆了文件。审批逻辑放进新文件 `tools/public_skill_review.py`，对上游文件的改动降到几行。必须新增：`skill_manage` 现在对外的调用形式是 `operations` 数组，审批也拦截这条路径，否则公开后台任务可以绕过审批。按能力分开判断 web 工具可用性的改动不再需要。`simple-http` 不再参与未配置时的自动探测。 |
| `hermes-web-browser-fallback` | 重写 | 接入点改到 `_memoized_search` 之后和 `_dispatch_extract` 内部。修了三处上游挪动：`cleanup_browser`、`check_browser_requirements`、`_get_cloud_provider`。不修的话，报错被吞掉，回退被悄悄禁用，浏览器也不会被清理。 |
| `hermes-help-center-article-api` | 保留 | 原样应用。 |
| `hermes-anthropic-user-api-key` | 删除 | 上游 `agent/anthropic_credentials.py` 已识别 `sk-ant-usr`。用真实 `AIAgent` 和 SDK 对本地服务器验证过，走 `x-api-key`，没有 OAuth 头。 |
| `hermes-vision-redirect-ssrf` | 删除 | 上游 `500c2b1e46` 已在基线内。回归测试保留在 overlay。 |

图片下载的 DNS 重绑定防护（上游 `42626da1ce`）随基线带上，新增了一条连接时拒绝内部地址的回归测试。

## 升级中发现的问题

**生产已存在、这次一并修掉的漏洞。** 公开频道里发文本 `@Bot /restart` 走的是和原生 Slash 同一条命令分发，但
ChatBird 的闸门只拦原生 Slash。生产的 `gateway/run.py` 确认有 `_check_slash_access`，但没有配置
`group_allow_admin_from`，所以这道检查是关闭的。按代码路径，任何成员都能这样运行 `/restart`、`/model`、`/new`，也能通过技能
命令加载未公开的 Skill。新补丁让文本命令和原生命令用同一个判断，被拒的命令退回普通聊天，不执行任何东西。

这个漏洞在升级部署之前一直存在。如果不想等升级，可以先在生产配置里加：

```yaml
platforms:
  discord:
    extra:
      group_allow_admin_from: ["<管理员 ID>"]
      group_user_allowed_commands: [status, version, usage]
```

这只挡内置命令，不挡技能命令，也不检查管理员是否在管理频道，所以只算临时措施。上面的配置片段没有在旧版本上实测过。

**升级才会出现、已修复的回归：**

- `pre_llm_call` 现在跑在带超时的工作线程上，上下文是复制的。插件用 ContextVar 记录的用户消息传不回工具处理函数，
  “普通用户不能命令写记忆”会悄悄失效。改为按 session key 保存。钩子没有运行时拒绝写入。旧插件在新契约测试下会失败。
- 由 owner 启动的 cron 用普通 session ID，不再以 `cron_` 开头。闸门现在同时接受调度器设置的 `HERMES_CRON_SESSION`。
- `/memory` 的待审批队列和磁盘存储是整个 profile 共用的，从 Guild 调用会看到并应用别的 Guild 暂存的写入。现在 Discord 上直接拒绝，
  配置校验也要求 `memory.write_approval` 保持关闭。

**上游新默认值，生产配置必须覆盖：**

| 配置 | 上游默认 | 生产 | 不改的后果 |
|---|---|---|---|
| `tools.tool_search.enabled` | `auto` | `"off"` | 插件工具藏到 `tool_search` 后面，闸门不放行这个名字，`chatbird_*` 在公开频道全部不可用 |
| `web.keyless_fallback`、`web.keyless_rescue` | 开 | 关 | 搜索或提取失败时，查询和 URL 发给 Exa、Parallel、Firecrawl、Keenable 的匿名接口，还会抓取 robots 只允许索引的站点 |
| `security.allow_lazy_installs` | 开 | 关 | 公开请求可能触发运行时安装软件包 |
| `tools.connectors.enabled` | 开 | 关 | 暴露 Nous 连接器网关 |
| `hooks.output_spill.enabled` | 开，阈值 1 万字符 | 关 | 管理员回合的策略提示超过阈值时被换成文件引用 |

这些都写进了 [`../patches/chatbird-production-config.yaml`](../patches/chatbird-production-config.yaml)，除 connectors 和 hooks 外由
`scripts/validate-production-config.py` 在启动前强制。校验还拒绝 `.env` 里出现 `HERMES_MEDIA_*`，并要求 `.env` 含有两个
`CHATBIRD_ADMIN_*` 变量。它只看变量名，错误信息里不会出现值。

## 依赖逐项复查

| 依赖 | 结果 | 依据 |
|---|---|---|
| `_HERMES_GATEWAY` 进程标记 | 仍在 `gateway/run.py` 导入时设置 | 契约测试，独立进程 |
| cron 空 platform、`cron_` 前缀 | platform 仍为空；owner 模式的 ID 变了，闸门已适配 | 契约测试用真实 `_CronRunScope` |
| `pre_tool_call` 参数 | `tool_name`、`args`、`session_id` 不变，现在跑在工作线程上，上下文会复制，超时拒绝 | 真实 `PluginManager` |
| `pre_llm_call` 参数 | `user_message`、`platform` 不变，线程变化见上 | 真实 `invoke_hook` |
| `gateway.strict`、`trust_recent_files` | 配置键不变，环境变量名变为 `HERMES_MEDIA_DELIVERY_STRICT` 和 `HERMES_MEDIA_TRUST_RECENT_FILES` | 独立进程读取 |
| 严格模式下的发送路径 | 启动后和每回合重载 `.env` 后，两个变量都是 `1` 和 `0`。会话 JSON、`state.db`、Guild 记忆、用户画像、`SOUL.md`、`.env`、`config.yaml` 都不可发送；缓存文件和 `chatbird_run_code` 生成的文件可发送，`extract_media` 能识别 | 独立进程，`HERMES_HOME` 放在 `$HOME` 下，和生产的 `/root` 豁免结构相同 |
| 每回合重载 `.env` | 行为不变，`.env` 里的 `HERMES_MEDIA_DELIVERY_STRICT=0` 仍会关掉严格模式，此时 Guild 记忆和用户画像又能发送。生产 `.env` 的 `HERMES_MEDIA_*` 行数为 0（2026-11-02 只读核对） | 专门的测试 |
| `_AUTO_APPEND_MEDIA_TOOL_NAMES` | 不含 `chatbird_run_code` | 真实 `_collect_auto_append_media_tags` |
| `client.beta.files` | SDK 未升级，仍用这个接口。SDK 版本变化时契约测试会失败提醒 | 真实 SDK 对本地服务器，含下载和删除 |
| `fallback_model` | 仍被读取。“用量上限”400、“余额不足”400、“消费上限”403 都切到备用 | 真实 `AIAgent` 和 SDK 对本地服务器 |
| Discord DM 早退 | 实时消息记录并丢弃，恢复消息丢弃不重复记录 | 测试 |
| Slash 授权、`/skill` 自动补全 | 公开集合和管理员频道校验不变，自动补全返回空 | 测试 |
| `delegate_task` 批量子任务 | **行为变了**：上游现在用 `copy_context().run` 派发，子任务继承身份。公开回合调不了 `delegate_task`；管理员回合的子任务不再没有工具，而是继承管理员身份 | 真实闸门 |
| `session_search` | 上游仍不按 Guild 过滤，闸门继续拦截 | 测试 |
| 现有会话和记忆 | 键和 session ID 不变，记录还在，schema 16 到 32 迁移成功，`quick_check` 为 ok，旧代码还能读迁移后的库 | 用旧代码建库再用新代码打开 |

## 安全审查

Fable subagent 做了只读审查，结论是修复后可部署：没有发现公开或管理员回合能读写其他 Guild 会话或记忆的路径。修复后再次复核，结论为通过。

已修复：

- 命令闸门在两个 `CHATBIRD_ADMIN_*` 都缺失时会放行所有命令。现在只要配置了 `discord.allowed_guilds`（生产必有），缺失就只开放公开命令，配置校验也要求这两个变量存在，`.env` 缺失时直接报错。没配 `allowed_guilds` 时保持 Hermes 原行为。
- 压缩用的临时 agent 在拿不到 Guild 时会落到未隔离的记忆目录。现在这种情况不加载记忆。没有 Guild 也没有用户的 Discord agent 同样不建存储。
- cron 共用未隔离的记忆，不同 Guild 建的任务会互相看到。这是旧版本就有的问题，生产目前没有 cron 任务。现在 Discord 建的任务用来源 Guild 的记忆。
- 部署步骤原来用 shell 执行 `.env`，改成只读取一个键。

没有采纳：

- 把空 platform 也当作公开上下文。管理员的技能命令在绑定身份之前执行，这样改会弄坏 `/skill`，也会影响本地会话。提示索引是在绑定身份之后构建的，独立审批线程没有工具。
- 文本批次合并时传递 `allow_gateway_control`。被拒的命令只会接在批次后面，不会成为开头，所以 `is_command()` 不会变真。

审查提出的另一个疑点（`/stop` 解析键尾部会看到 `guild-<id>`）已对照代码确认没有影响：它按聊天 ID 匹配，生产每个频道只有一个键，
而且 `/stop` 在 Discord 上只有管理员能用。

## 验证结果

- 补丁栈用 `scripts/apply-hermes-patches.sh` 干净应用到 `v0.22.5`，overlay 10 个。
- ChatBird 单元测试 65 项通过。
- 发布包演练：`scripts/build-hermes-release.sh` 打包、解压、`uv sync --locked`，在只装 discord、anthropic、ddgs 三个 extra 的 Python
  3.14 环境里，12 个测试文件 147 项通过。
- Hermes 定向测试：429 个文件，结果见文末。
- 真实网络：`web_extract` 经 `simple-http` 读到 `example.com`，`web_search` 经 DDGS 返回 Discord 帮助中心文章。
- 网关用占位 token 启动：插件加载，工具解析出 23 个，含三个 `chatbird_*`，走到 Discord 登录后按 401 退出。

**没有验证：** Discord 真实对话；真实 Anthropic 和小米请求；真实额度耗尽时的错误文本；Linux 上的本地 Chromium；生产机上的实际内存。
本地启动峰值 RSS 约 261 MiB（macOS），生产当前运行中约 135 MiB。

## 解释器

v0.22.5 的 `pyproject.toml` 只给 `python_version >= '3.14'` 固定依赖版本，较旧的 Python 只为旧安装完成自更新而保留。生产现在是 3.11，
所以要新建 3.14 环境。这是原地 `git pull` 不可行的主要原因，也是采用并排部署的原因。

## 部署方案

原则：新版本放到新目录，旧目录完全不动，切换和回滚都只是改 systemd drop-in。不在生产机构建，只下载 wheel。

### 本地准备

```bash
git clone https://github.com/NousResearch/hermes-agent.git /tmp/hermes-release
git -C /tmp/hermes-release checkout --detach bf0203a794a07aac3ff764972ab9087baa4e4f4e
scripts/apply-hermes-patches.sh /tmp/hermes-release --check
scripts/apply-hermes-patches.sh /tmp/hermes-release
scripts/build-hermes-release.sh /tmp/hermes-release /tmp/hermes-0.22.5.tar.gz
shasum -a 256 /tmp/hermes-0.22.5.tar.gz
```

### 生产预检（只读）

```bash
free -m; df -h /; uptime
systemctl show hermes-gateway.service -p MainPID -p NRestarts -p MemoryCurrent
grep -c '^HERMES_MEDIA_' /root/.hermes/.env   # 必须是 0
grep -c -E '^CHATBIRD_ADMIN_(USERS|CHANNELS)=' /root/.hermes/.env   # 必须是 2
```

可用内存低于 500 MiB、磁盘低于 3 GiB 或负载持续高于 1 时，先不继续。

### 安装新版本（不影响运行中的服务）

```bash
R=/usr/local/lib/hermes-agent-0.22.5
mkdir -p "$R" && tar -xzf /tmp/hermes-0.22.5.tar.gz -C "$R"
cd "$R"
/root/.local/bin/uv python install 3.14
UV_PROJECT_ENVIRONMENT="$R/venv" nice -n 10 /root/.local/bin/uv sync --locked --python 3.14 --no-dev \
  --extra discord --extra anthropic --extra ddgs
/root/.local/bin/uv pip install --python "$R/venv" pytest==9.1.1 pytest-asyncio==1.3.0
"$R/venv/bin/python" -c 'import anthropic, discord, ddgs; print(anthropic.__version__, discord.__version__)'
```

`uv sync` 只下载 wheel。如果它开始编译，停下。

### 重启前验证（独立进程，不碰线上数据）

先把仓库里的 1.6.0 插件放到临时目录，并设好 `CHATBIRD_PLUGIN_DIR`：

```bash
cd "$R"
PATH="$R/venv/bin:$PATH" CHATBIRD_PLUGIN_DIR=/tmp/chatbird-policy-1.6.0 nice -n 10 python -m pytest -q \
  tests/gateway/test_chatbird_upgrade_contract.py tests/plugins/test_discord_chatbird_access.py
```

**不要**用新代码打开 `/root/.hermes/state.db`，首次打开就会迁移。要检查迁移，先复制到临时目录：

```bash
T=$(mktemp -d)
cp -p /root/.hermes/state.db "$T/state.db"
cd "$R" && HERMES_HOME="$T" "$R/venv/bin/python" -c 'from hermes_state import SessionDB; SessionDB(); print("ok")'
python3 -c "import sqlite3,sys; c=sqlite3.connect('$T/state.db'); print(c.execute('PRAGMA quick_check').fetchone(), c.execute('select count(*) from messages').fetchone())"
rm -rf "$T"
```

再用生产 Key 真实调用一次 `chatbird_run_code`，确认文件走得通。这是唯一用真实 Anthropic 接口验证代码执行的一步，放在重启前做。
它用临时 `HERMES_HOME`，所以不碰线上数据；脚本只从 `.env` 读 `ANTHROPIC_API_KEY` 这一个键，输出只有结果和文件名：

```bash
T=$(mktemp -d)
( cd "$R" && HERMES_HOME="$T" _HERMES_GATEWAY=1 HERMES_MEDIA_DELIVERY_STRICT=1 HERMES_MEDIA_TRUST_RECENT_FILES=0 \
  "$R/venv/bin/python" - <<'PY'
import importlib.util, json, os
from dotenv import dotenv_values
os.environ["ANTHROPIC_API_KEY"] = dotenv_values("/root/.hermes/.env")["ANTHROPIC_API_KEY"]
spec = importlib.util.spec_from_file_location("chatbird_policy", "/tmp/chatbird-policy-1.6.0/__init__.py")
plugin = importlib.util.module_from_spec(spec); spec.loader.exec_module(plugin)
from gateway.platforms.base import BasePlatformAdapter, validate_media_delivery_path
result = json.loads(plugin._handle_run_code({"task": "Compute the first 10 Fibonacci numbers and save them as fib.csv."}))
media = [path for line in result["files"] for path, _ in BasePlatformAdapter.extract_media(line)[0]]
print({"success": result["success"], "files": [os.path.basename(p) for p in media],
       "deliverable": [bool(validate_media_delivery_path(p)) for p in media]})
PY
)
rm -rf "$T"
```

要看到 `success` 为真，至少一个文件，`deliverable` 全为真。这一步花约 2 美分。

### 切换（中断时间应在 30 秒内）

```bash
B=/root/.hermes/backups/hermes-0.22.5-$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 0700 "$B"
sha256sum /root/.hermes/config.yaml
systemctl stop hermes-gateway.service
cp -a /root/.hermes/state.db* /root/.hermes/config.yaml /root/.hermes/.env /root/.hermes/auth.json \
      /root/.hermes/channel_directory.json /root/.hermes/sessions /root/.hermes/memories \
      /root/.hermes/chatbird /root/.hermes/plugins/chatbird-policy /root/.hermes/skills "$B/"
```

然后：

1. 把 `/root/.hermes/plugins/chatbird-policy/` 换成 1.6.0。
2. 把 `validate-production-config.py` 换到 `/root/.hermes/chatbird/`。
3. 把 `display`、`hooks`、`tools`、`security`、`web.keyless_*` 这几项合并进 `/root/.hermes/config.yaml`（改前改后都记 SHA-256）。
   旧 Hermes 会忽略这些键，新校验要求有它们。
4. 跑一次校验：`/usr/bin/python3 /root/.hermes/chatbird/validate-production-config.py /root/.hermes/config.yaml`。
5. 写 drop-in `/etc/systemd/system/hermes-gateway.service.d/release.conf`：

```ini
[Service]
ExecStart=
ExecStart=/usr/local/lib/hermes-agent-0.22.5/venv/bin/python -m hermes_cli.main gateway run
Environment="PATH=/usr/local/lib/hermes-agent-0.22.5/venv/bin:/root/.hermes/node/bin:/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="VIRTUAL_ENV=/usr/local/lib/hermes-agent-0.22.5/venv"
```

```bash
systemctl daemon-reload
systemctl start hermes-gateway.service
```

`/usr/local/bin/hermes` 这个软链接在确认运行稳定后再改到新目录，改之前管理命令还是旧版本。

### 重启后检查

```bash
systemctl is-active hermes-gateway.service
systemctl show hermes-gateway.service -p MainPID -p NRestarts -p MemoryCurrent
journalctl -u hermes-gateway.service --since "5 minutes ago" --no-pager -n 100
free -m
```

要确认：Discord 已连接，`NRestarts=0`，日志没有 `chatbird-policy` 加载错误，`MemoryCurrent` 低于 800 MiB，公开审批 Skill 仍可见
（`gaming-references`），全局 Slash 命令里 `/help`、`/whoami`、`/status`、`/version`、`/usage` 还在，
`agent-browser` 0.26.0 的 requirements、公开网页导航、DOM 读取和进程清理四项烟测通过。

Discord 验收（需要你在频道里操作）：

1. 公开频道 `@Bot 你好`，模型回复；工具进度卡片不出现。
2. 公开频道 `@Bot /restart`，**不应**重启，网关 PID 不变。
3. 公开频道 `/status` 可用，`/restart` 被拒绝。管理员频道 `/status` 和 `@Bot /status` 都可用。
4. 让 Bot 算一个数并生成图表，文件能发出来。
5. 让 Bot 读频道历史和一张图片。
6. 给 Bot 发私信，没有回复，`chatbird-discord-dm.jsonl` 多一行。
7. 让 Bot 发送 `~/.hermes/SOUL.md`，发不出来。

### 观察与清理

观察 7 天再删旧目录和备份。期间关注 RSS、`journalctl` 的 `Hook .* timed out`、`/root/.hermes/cache/web` 的大小。
新版本把被截断网页的全文存到 `cache/web`，这是新增的磁盘占用。

## 回滚方案

```bash
systemctl stop hermes-gateway.service
rm /etc/systemd/system/hermes-gateway.service.d/release.conf
systemctl daemon-reload
systemctl start hermes-gateway.service
```

旧目录和旧虚拟环境没动过，这样就回到了旧代码。其他部分这样处理：

- **配置和校验脚本：** 不用回退。旧 Hermes 忽略新增的键，插件 1.6.0 在旧版本上也能跑（钩子同步执行，按 session key 存消息没有副作用）。
- **`state.db`：** 默认保留。本地测试里 v0.17 代码能读写 schema 32 的库。只有旧代码报错时才恢复：停服务，把备份里的 `state.db*` 复制回去，
  再启动。这样会丢掉升级后的对话记录。
- **Skill：** 新版本启动时同步内置 Skill。公开审批按内容哈希绑定，不受影响。需要时从备份恢复 `skills/`。

回滚后同样检查服务状态和短日志。

## Hermes 定向测试结果

429 个文件逐个运行（Discord、会话、媒体、记忆、Skill、web、视觉、委派、提示构建、插件）：4162 项通过，12 项失败，61 项跳过。

这 12 项在同一环境下未打补丁的 `v0.22.5` 上同样失败，所以不是补丁引入的，也不影响生产路径：

- `test_session_edit_policy.py`（2 项）、`test_session_policy_refusal_fields.py`（2 项）：本地会话编辑器策略，生产不用。
- `test_plugin_validate.py`（1 项）：插件校验命令。
- `test_delegate.py::test_child_dedicated_db_follows_parents_db_path`（1 项）。
- `test_web_free_fast_search.py`（4 项）、`test_web_providers_searxng.py`（1 项）、`test_web_tools_config.py`（1 项）：这些用例假定未安装 `ddgs`，
  测试环境装了它。
