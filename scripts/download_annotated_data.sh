#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$ROOT_DIR/annotated_data"
BACKUP_DIR="$ROOT_DIR/annotated_data_backup"
REPO_URL="${REPO_URL:-https://github.com/icip-cas/LiveMCPBench.git}"
BRANCH="${BRANCH:-main}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd git
require_cmd rsync
require_cmd mktemp

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

echo "Fetching annotated_data from $REPO_URL (branch $BRANCH)..."
git clone --depth 1 --filter=blob:none --sparse --branch "$BRANCH" "$REPO_URL" "$tmp_dir" >/dev/null
(
  cd "$tmp_dir"
  git sparse-checkout set annotated_data >/dev/null
)

mkdir -p "$TARGET_DIR"
rsync -a --delete "$tmp_dir/annotated_data/" "$TARGET_DIR/"

cat >"$TARGET_DIR/env" <<'EOF'
OPENAI_API_KEY="sk-123456"
user_id="123456"
EOF

cat >"$TARGET_DIR/mcp_config.json" <<'EOF'
{
  "filesystem": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "./annotated_data"
    ]
  },
  "fetch": {
    "command": "uvx",
    "args": [
      "mcp-server-fetch"
    ]
  }
}
EOF

echo "Updating backup at $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
rsync -a --delete "$TARGET_DIR/" "$BACKUP_DIR/"

echo "Done. annotated_data synced and backup refreshed."
