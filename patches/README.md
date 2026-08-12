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

The production checkout remains a normal Hermes Git worktree. When upgrading
Hermes, update the base commit, refresh patches as needed, rebuild in a
temporary worktree, run the targeted tests, and compare the rebuilt files with
the intended production files before deployment.
