# Local development on macOS and Linux

ChatBird maintains a Hermes patch stack and a policy plugin. Its standalone
unit tests need Python and PyYAML; running a Discord gateway is a separate step.

## Create the test environment

From the repository root, with `uv` installed:

```bash
uv venv --python 3.12.3 .venv
uv pip sync --python .venv requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/validate-production-config.py --help
```

The dependency file pins the standalone test dependency. The Hermes checkout
has its own dependency manifest and environment. Do not reuse a virtual
environment copied from Windows or Linux; keep it as an archive and create a
native environment. Select `.venv/bin/python` as the IDE interpreter on macOS.

## Validate the integration stack

Use a clean checkout at the `base_commit` in `hermes-stack.lock`:

```bash
scripts/apply-hermes-patches.sh /path/to/hermes-agent --check
scripts/apply-hermes-patches.sh /path/to/hermes-agent
```

The script supports the Bash 3.2 and BSD `install` supplied with macOS. The
check mode uses a temporary Git index and leaves the checkout unchanged.
Application changes only that Hermes checkout. For Hermes integration tests,
install the dependencies required by its own manifest and follow its test
instructions; the standalone tests do not validate a live gateway or API.

The Linux systemd files and `/root/.hermes` paths describe remote deployment.
They are not local Mac paths and should remain unchanged.
