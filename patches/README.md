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
Ordinary guild channels expose their category through `category` or
`category_id`; threads expose their parent through `parent` or `parent_id`.
Message and slash-command authorization must apply the same inheritance rule.

Channel-control tests must model those real attributes. In particular, a fake
text channel must not invent thread-only `parent` fields, because that hides
category lookup regressions and can make a correctly mentioned bot appear
silent in a category-allowed channel.

The production checkout remains a normal Hermes Git worktree. When upgrading
Hermes, update the base commit, refresh patches as needed, rebuild in a
temporary worktree, run the targeted tests, and compare the rebuilt files with
the intended production files before deployment.

ChatBird uses `main` as its only long-lived integration branch. Once a feature
branch is merged, keep the patch stack and documentation on `main` and delete
the obsolete branch.
