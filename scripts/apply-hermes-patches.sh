#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 HERMES_CHECKOUT [--check]" >&2
    echo "  HERMES_CHECKOUT must be a clean checkout at the locked base commit." >&2
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage
    exit 2
fi

hermes_checkout=$1
mode=apply
if [[ $# -eq 2 ]]; then
    if [[ $2 == "--check" ]]; then
        mode=check
    else
        usage
        exit 2
    fi
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
lock_file="$repo_root/hermes-stack.lock"

if [[ ! -d $hermes_checkout/.git && ! -f $hermes_checkout/.git ]]; then
    echo "Not a Git checkout: $hermes_checkout" >&2
    exit 1
fi

if [[ ! -f $lock_file ]]; then
    echo "Missing lock file: $lock_file" >&2
    exit 1
fi

base_commit=$(awk '$1 == "base_commit" { print $2; exit }' "$lock_file")
upstream_repo=$(awk '$1 == "upstream_repo" { print $2; exit }' "$lock_file")
mapfile -t patch_files < <(awk '$1 == "patch" { print $2 }' "$lock_file")
mapfile -t overlay_files < <(awk '$1 == "overlay" { print $2 "\t" $3 }' "$lock_file")

if [[ -z $base_commit || -z $upstream_repo || ${#patch_files[@]} -eq 0 ]]; then
    echo "Invalid Hermes lock file: $lock_file" >&2
    exit 1
fi

if [[ -n $(git -C "$hermes_checkout" status --porcelain) ]]; then
    echo "Hermes checkout must be clean before applying patches: $hermes_checkout" >&2
    exit 1
fi

current_commit=$(git -C "$hermes_checkout" rev-parse HEAD)
if [[ $current_commit != "$base_commit" ]]; then
    echo "Hermes checkout is at $current_commit; expected locked base $base_commit" >&2
    echo "Upstream: $upstream_repo" >&2
    exit 1
fi

temp_index=""
if [[ $mode == check ]]; then
    temp_index=$(mktemp "${TMPDIR:-/tmp}/chatbird-hermes-index.XXXXXX")
    trap 'rm -f "$temp_index"' EXIT
    GIT_INDEX_FILE="$temp_index" git -C "$hermes_checkout" read-tree HEAD
fi

for patch_rel in "${patch_files[@]}"; do
    case $patch_rel in
        patches/*) ;;
        *)
            echo "Refusing patch outside ChatBird patches/: $patch_rel" >&2
            exit 1
            ;;
    esac

    patch_file="$repo_root/$patch_rel"
    if [[ ! -f $patch_file ]]; then
        echo "Missing patch: $patch_file" >&2
        exit 1
    fi

    if [[ $mode == check ]]; then
        GIT_INDEX_FILE="$temp_index" git -C "$hermes_checkout" apply --cached "$patch_file"
    else
        git -C "$hermes_checkout" apply --check "$patch_file"
        git -C "$hermes_checkout" apply "$patch_file"
    fi
done

for overlay_row in "${overlay_files[@]}"; do
    IFS=$'\t' read -r source_rel target_rel <<< "$overlay_row"
    case $source_rel in
        patches/*) ;;
        *)
            echo "Refusing overlay source outside ChatBird patches/: $source_rel" >&2
            exit 1
            ;;
    esac
    case $target_rel in
        tests/*) ;;
        *)
            echo "Refusing overlay target outside Hermes tests/: $target_rel" >&2
            exit 1
            ;;
    esac

    source_file="$repo_root/$source_rel"
    target_file="$hermes_checkout/$target_rel"
    if [[ ! -f $source_file ]]; then
        echo "Missing overlay source: $source_file" >&2
        exit 1
    fi

    if [[ $mode == check ]]; then
        if GIT_INDEX_FILE="$temp_index" git -C "$hermes_checkout" ls-files --error-unmatch "$target_rel" >/dev/null 2>&1; then
            echo "Overlay target already exists in the patched Hermes tree: $target_rel" >&2
            exit 1
        fi
    else
        if [[ -e $target_file ]]; then
            echo "Overlay target already exists: $target_file" >&2
            exit 1
        fi
        install -D -m 0644 "$source_file" "$target_file"
    fi
done

if [[ $mode == apply ]]; then
    git -C "$hermes_checkout" diff --check
    echo "Applied ${#patch_files[@]} Hermes patches and ${#overlay_files[@]} overlay(s) to $hermes_checkout"
else
    echo "Hermes patch stack is applicable to $hermes_checkout"
fi
