#!/usr/bin/env bash
set -euo pipefail

# Package a patched Hermes checkout as a release tarball for side-by-side
# deployment. Desktop, website and most tests stay out; the production smoke
# tests stay in. Run scripts/apply-hermes-patches.sh on the checkout first.

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 PATCHED_HERMES_CHECKOUT OUTPUT.tar.gz" >&2
    exit 2
fi

checkout=$(CDPATH= cd -- "$1" && pwd)
output=$2
repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
lock_file="$repo_root/hermes-stack.lock"

base_commit=$(awk '$1 == "base_commit" { print $2; exit }' "$lock_file")
if [[ $(git -C "$checkout" rev-parse HEAD) != "$base_commit" ]]; then
    echo "Checkout is not at the locked base $base_commit" >&2
    exit 1
fi
# A checkout with no local changes has not had the stack applied.
if [[ -z $(git -C "$checkout" status --porcelain) ]]; then
    echo "Checkout has no patches applied: $checkout" >&2
    exit 1
fi

file_list=$(mktemp "${TMPDIR:-/tmp}/chatbird-release-files.XXXXXX")
trap 'rm -f "$file_list"' EXIT

{
    git -C "$checkout" ls-files --cached --others --exclude-standard
    awk '$1 == "overlay" { print $3 }' "$lock_file"
} | sort -u | awk '
    /^(apps|website|web|docs|docker|datagen-config-examples|\.github|nix|packaging|assets)\// { next }
    /^tests\// {
        if ($0 ~ /(^|\/)conftest\.py$|^tests\/.*__init__\.py$|^tests\/_fixtures\//) { print; next }
        if ($0 ~ /^tests\/[^\/]+\.py$/ && $0 !~ /^tests\/test_/) { print; next }
        if ($0 ~ /test_chatbird_|test_public_skill_|test_discord_chatbird_access|test_discord_guild_memory_isolation|test_discord_channel_controls|test_simple_http_extract|test_web_browser_fallback|test_vision_redirect_guard/) { print }
        next
    }
    { print }
' > "$file_list"

trap 'rm -f "$file_list" "$checkout/CHATBIRD_RELEASE"' EXIT
{
    echo "hermes_base $base_commit"
    echo "chatbird_commit $(git -C "$repo_root" rev-parse HEAD)"
    echo "built_at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$checkout/CHATBIRD_RELEASE"
echo CHATBIRD_RELEASE >> "$file_list"

# COPYFILE_DISABLE keeps macOS tar from adding AppleDouble files.
COPYFILE_DISABLE=1 tar -czf "$output" -C "$checkout" -T "$file_list"
echo "Wrote $output ($(wc -l < "$file_list" | tr -d ' ') files)"
cat "$checkout/CHATBIRD_RELEASE"
