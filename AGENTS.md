# ChatBird Project Guidance

## Production Server

- The `aliyun-germany` host is resource-constrained (about 1.6 GiB RAM with
  2 GiB swap). Treat it as a small production server.
- Prefer targeted file reads, narrow searches, and single-test runs.
- Do not run repository-wide scans, full test suites, high-concurrency jobs,
  builds, or upgrades on the server without first checking available memory,
  disk space, and service load.
- Develop and validate changes locally or in a temporary worktree when
  practical. On the server, deploy only the required files and run focused
  smoke tests.
- Keep `hermes-gateway.service` interruption brief and verify its status and
  recent logs after every deployment.
- Never print or commit values from `/root/.hermes/.env`.

## ChatBird Isolation Contract

- One Discord bot account may serve multiple Discord guilds.
- Conversation sessions and persistent memory must never cross Discord guild
  boundaries. Include `guild_id` in every Discord session and memory scope.
- Production deployments must configure `discord.allowed_guilds`; guilds that
  are absent from that allowlist must be denied.

## Git Workflow

- After the requested changes pass focused validation, commit and push them
  directly to `main` by default.
- Do not create a feature branch or pull request unless the user explicitly
  asks for one, repository protection prevents a direct push, or the change
  still needs review before it is safe to merge.
- If a temporary branch or pull request was created unnecessarily, merge the
  validated commit into `main`, push `main`, close the pull request, and delete
  the temporary branch.
