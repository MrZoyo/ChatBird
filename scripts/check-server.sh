#!/usr/bin/env bash
set -euo pipefail

host="${1:-aliyun-germany}"

ssh "$host" '
set -e
echo "== host =="
hostname
echo "== hermes =="
command -v hermes
hermes --version
echo "== memory =="
free -h
echo "== swap =="
swapon --show
echo "== service =="
systemctl status hermes-gateway --no-pager --lines=20 2>/dev/null || true
'
