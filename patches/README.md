# ChatBird Hermes Patch Stack

ChatBird tracks its Hermes Agent changes as an ordered patch stack instead of
vendoring the complete upstream repository.

The exact upstream repository, base commit, patch order, and test overlay are
recorded in `../hermes-stack.lock`. To verify the stack against a clean Hermes
checkout without changing it:

```bash
scripts/apply-hermes-patches.sh /path/to/hermes-agent --check
```

To apply the complete stack:

```bash
scripts/apply-hermes-patches.sh /path/to/hermes-agent
```

The checkout must be clean and at the locked base commit. The script fails
closed if the base differs, a patch is missing, a patch no longer applies, or
an overlay would overwrite an existing upstream file.

The Discord category-allowlist patch handles both discord.py channel shapes.
Ordinary guild channels, including a voice channel's built-in text chat,
expose their category through `category` or `category_id`; threads expose their
parent through `parent` or `parent_id`.
Message and slash-command authorization must apply the same inheritance rule.

When Discord deletes a temporary channel, the adapter cancels that channel's
running, queued, debounced, and batched turns. It does not delete transcript
history. A replacement channel receives a different channel ID and starts a
separate session, so no work continues against the deleted channel.

Channel-control tests must model those real attributes. In particular, a fake
text channel must not invent thread-only `parent` fields, because that hides
category lookup regressions and can make a correctly mentioned bot appear
silent in a category-allowed channel.

The public-skill/web-extract patch adds two ChatBird security boundaries:

- Public Discord skill discovery and reads are limited to externally recorded,
  SHA-256-bound approvals. Public reads are inert: they do not preprocess skill
  templates, run inline shell snippets, collect secrets, or expose host paths.
- Public-origin background skill creation and updates are staged and require a
  separate tool-free agent approval. Rejection, malformed output, timeout, or
  policy failure preserves the previously approved version.

It also separates web search and extraction availability and provides the
no-key `simple-http` static HTML/text extractor with redirect, DNS, private
network, response-size, and decompression guards.

The browser-fallback patch keeps the public API limited to `web_search` and
`web_extract` while optionally retrying failed searches, HTTP 403/5xx/timeouts,
JavaScript challenges, and empty pages in a short-lived internal browser. It
does not retry publisher rate limits (`429`), expose click/type/eval tools, or
navigate to URLs that fail independent public-network and website-policy
checks. Cloud browser mode remains the conservative code default; ChatBird
production explicitly permits a local Chromium backend. One fallback session
may run at a time and every session is closed after its fixed DOM read.

Production also enables a final Jina Reader extraction fallback only for the
exact host `www.vicioussyndicate.com`. The Reader attempt is independent of
local Chromium readiness, so a missing local browser runtime does not disable
the compliant exact-host extraction path. It rejects arbitrary hosts, URLs with
credentials or queries, unexpected returned source hosts, oversized bodies,
and challenge content. HSGuru remains search-index-only because its published
robots rules disallow automated API, deck-list, and query-driven statistics
paths. A query that names HSGuru but receives no HSGuru link may issue at most
two bounded queries against DDGS's Yahoo public index; non-HSGuru URLs are
removed and explicit rate limits are not retried.

`hermes-gateway-browser.conf` is the tracked systemd drop-in for the stable
local Chromium launcher. Install it under
`/etc/systemd/system/hermes-gateway.service.d/`, then reload systemd. Keep the
launcher pointed at the tested Chromium version after browser upgrades.

The production checkout remains a normal Hermes Git worktree. When upgrading
Hermes, update the base commit, refresh patches as needed, rebuild in a
temporary worktree, run the targeted tests, and compare the rebuilt files with
the intended production files before deployment.

ChatBird uses `main` as its only long-lived integration branch. Once a feature
branch is merged, keep the patch stack and documentation on `main` and delete
the obsolete branch.
