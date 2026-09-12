#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CLAUDE_COMMANDS_DIR:-$HOME/.claude/commands}"

# 单源化 skill：其运行器（如 bottleneck-hunter-scan.sh）直接读仓库 skills/ canonical，
# 不安装到 ~/.claude/commands/，避免副本与源漂移（曾致 cron 长期跑旧版 skill）。
# 新增此类 skill 时，把文件名加到此数组。
EXCLUDE=(
  "bottleneck-hunter.md"
)

mkdir -p "$DEST"
for src in "$ROOT"/skills/*.md; do
    name="$(basename "$src")"
    excluded=0
    for ex in "${EXCLUDE[@]}"; do
        if [ "$name" = "$ex" ]; then
            excluded=1
            break
        fi
    done
    if [ "$excluded" = "1" ]; then
        echo "  skip (single-source): $name"
        rm -f "$DEST/$name"   # 清理历史遗留副本，防止漂移回潮
        continue
    fi
    cp "$src" "$DEST"/
done
chmod +x "$ROOT"/tools/*.py "$ROOT"/tools/*.sh 2>/dev/null || true

echo "Installed Claude Code commands to $DEST"
