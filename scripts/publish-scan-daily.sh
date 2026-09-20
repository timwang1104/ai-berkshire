#!/usr/bin/env bash
# ============================================================================
# 供应链瓶颈扫描周报 -> 微信公众号草稿 发布管线（官方 API 草稿箱）
#
# 流程：
#   1. 找到最新一份扫描报告（默认 reports/供应链瓶颈/daily/ 下最新的 *-pm.md）
#   2. 用 wechat-article skill（claude CLI headless）把扫描报告改写成公众号文章
#   3. 调用 tools/wechat_mp_publish.py 走官方 API 建草稿（默认不发布，人工确认）
#   4. 生成结果记录到 ai-berkshire/logs/publish-scan-daily-{日期}.log
#
# 前置条件：
#   - ai-berkshire/.env 配置 WECHAT_MP_APPID / WECHAT_MP_SECRET（见 tools/wechat_mp_publish.py 头部）
#   - 公众号为认证服务号/认证订阅号，草稿箱接口可用，脚本运行机 IP 已加白名单
#   - claude CLI 已安装，wechat-article skill 已安装（~/.claude/commands/wechat-article.md）
#
# 用法：
#   bash publish-scan-daily.sh                 # 发布最新一份日报（建草稿）
#   bash publish-scan-daily.sh --date 2026-09-04   # 指定日期
#   bash publish-scan-daily.sh --publish       # 建草稿后立即正式发布（慎用）
#   bash publish-scan-daily.sh --check         # 只校验凭证与接口权限
#   bash publish-scan-daily.sh --allow-stale   # 放行"超过 2 天的旧日报"（默认拒绝）
#   bash publish-scan-daily.sh --allow-lint    # 放行"日期绑定校验未过"的文章（默认拒绝）
#
# 退出码：
#   0 = 成功   1 = 找不到日报   2 = 参数/凭证错误
#   3 = 出口 IP 不在白名单   4 = 微信接口预检未通过   5 = 日报过旧被拒绝
#   6 = 文章行情数字缺时点标记（claim_lint.py）
# ============================================================================
set -euo pipefail

REPO_ROOT="/home/timwang/Documents/workspace/tradebot_workspace/vnpy"
AB_DIR="$REPO_ROOT/ai-berkshire"
REPORT_ROOT="$AB_DIR/reports/供应链瓶颈"
DAILY_DIR="$REPORT_ROOT/daily"
ARTICLE_DIR="$REPORT_ROOT/公众号文章"
LOG_DIR="$AB_DIR/logs"
CLAUDE_BIN="/home/timwang/.local/bin/claude"
LOCK_FILE="/tmp/publish-scan-daily.lock"

export PATH="/home/timwang/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

DATE="${1:-latest}"
PUBLISH_FLAG=""
ALLOW_STALE=0
ALLOW_LINT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --date) DATE="$2"; shift 2 ;;
    --publish) PUBLISH_FLAG="--publish"; shift ;;
    --check) CHECK_MODE=1; shift ;;
    --allow-stale) ALLOW_STALE=1; shift ;;
    --allow-lint) ALLOW_LINT=1; shift ;;
    *) echo "未知参数: $1（支持 --date YYYY-MM-DD / --publish / --check / --allow-stale / --allow-lint）" >&2; exit 2 ;;
  esac
done

mkdir -p "$ARTICLE_DIR" "$LOG_DIR"

# ---- 并发锁 ----
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date +'%F %T')] 已有发布管线在运行（$LOCK_FILE），本次跳过。" >&2
  exit 0
fi

# ---- 预检：凭证缺失时快速失败，避免白跑耗时的改写步骤 ----
if [ ! -f "$AB_DIR/.env" ] || ! grep -q "^WECHAT_MP_APPID=" "$AB_DIR/.env" || ! grep -q "^WECHAT_MP_SECRET=" "$AB_DIR/.env"; then
  echo "[ERROR] 缺少凭证：请先复制 .env.example 为 $AB_DIR/.env 并填入 AppID/AppSecret" >&2
  echo "        凭证获取: mp.weixin.qq.com → 设置与开发 → 基本配置" >&2
  exit 2
fi

# ---- check 模式：只校验凭证 ----
if [ "${CHECK_MODE:-0}" = "1" ]; then
  echo "[check] 校验微信凭证与接口权限..."
  python3 "$AB_DIR/tools/wechat_mp_publish.py" --check --env "$AB_DIR/.env"
  exit $?
fi

# ---- 定位当日日报 ----
if [ "$DATE" = "latest" ]; then
  REPORT_FILE="$(ls -t "$DAILY_DIR"/*-pm.md 2>/dev/null | head -1 || true)"
  if [ -z "$REPORT_FILE" ]; then
    echo "[ERROR] daily/ 下没有找到 *-pm.md 日报" >&2
    exit 1
  fi
  REPORT_DATE="$(basename "$REPORT_FILE" .md | sed -E 's/^([0-9]{4}-[0-9]{2}-[0-9]{2})-.*/\1/')"
else
  REPORT_FILE="$DAILY_DIR/$DATE-pm.md"
  REPORT_DATE="$DATE"
  [ -f "$REPORT_FILE" ] || { echo "[ERROR] 日报不存在: $REPORT_FILE" >&2; exit 1; }
fi

NOW="$(date +'%Y-%m-%d %H:%M')"
LOG_FILE="$LOG_DIR/publish-scan-daily-$REPORT_DATE.log"
exec 9>&2   # 保存原始 stderr：预检消息要同时到终端（人工跑）和定时任务日志（journal）
exec >> "$LOG_FILE" 2>&1

# 预检消息同时写「管线日志」和「原始 stderr」。
# 否则 exec 重定向之后，人工跑脚本只会看到非零退出码、看不到任何原因。
say() {
  for line in "$@"; do
    printf '%s\n' "$line"
    printf '%s\n' "$line" >&9
  done
}

fail() {
  local code="$1"; shift
  say "$@"
  exit "$code"
}

echo "===== 发布管线启动：$NOW 日报=$REPORT_FILE ====="

# ---- 预检 1：日报新鲜度 ----
# `latest` 取的是 daily/ 下最新的 *-pm.md。若本周扫描漏跑或还没跑完，latest 会
# 指向上周的日报 —— 结果是建一份内容重复的草稿，并覆盖上周的文章文件。
#
# 阈值取 2 天而不是更宽：本条管线只在扫描完成后数小时内使用最新日报，一份 7 天
# 前的日报意味着"本周扫描没产出"，而不是"这次想补发旧报告"。要发旧报告就显式
# 用 --date 指定日期（守卫只作用于 latest），或加 --allow-stale。
if [ "$DATE" = "latest" ] && [ "$ALLOW_STALE" != "1" ]; then
  REPORT_TS="$(date -d "$REPORT_DATE" +%s 2>/dev/null || true)"
  if [ -n "$REPORT_TS" ]; then
    REPORT_AGE_DAYS=$(( ( $(date +%s) - REPORT_TS ) / 86400 ))
    MAX_REPORT_AGE_DAYS="${MAX_REPORT_AGE_DAYS:-2}"
    if [ "$REPORT_AGE_DAYS" -gt "$MAX_REPORT_AGE_DAYS" ]; then
      fail 5 \
        "[ERROR] 最新日报 $REPORT_DATE 距今 $REPORT_AGE_DAYS 天，超过 ${MAX_REPORT_AGE_DAYS} 天上限，拒绝执行。" \
        "        通常意味着本周扫描漏跑，先查：logs/bottleneck-hunter-*.log，以及定时任务状态" \
        "        systemctl --user status bottleneck-weekly.timer。" \
        "        如果确实要发这份旧日报，加 --allow-stale 或 --date 显式指定日期。"
    fi
    say "[preflight] ✅ 日报新鲜度正常（$REPORT_DATE，距今 $REPORT_AGE_DAYS 天）"
  fi
fi

# ---- 预检 2：微信凭证与 API IP 白名单 ----
# 必须放在耗时 3-8 分钟的 claude 改写之前：白名单过期时改写结果会全部作废，
# 白白花掉一次模型调用和几分钟等待。
set +e
python3 "$AB_DIR/tools/wechat_mp_publish.py" --check --env "$AB_DIR/.env"
CHECK_RC=$?
set -e
if [ "$CHECK_RC" -ne 0 ]; then
  fail 4 \
    "[ERROR] 微信接口预检未通过（退出码 $CHECK_RC），中止发布。" \
    "        最常见原因：家庭宽带出口 IP 漂移，未在公众号 API IP 白名单内（40164）。" \
    "        补救：按上面提示把该 IP 加入白名单（约 10 分钟生效）后重跑本命令。"
fi
say "[preflight] ✅ 凭证与 IP 白名单正常"

# ---- 用 wechat-article skill 改写日报为公众号文章 ----
ARTICLE_FILE="$ARTICLE_DIR/公众号-瓶颈猎手日报-$REPORT_DATE.md"

SKILL_FILE="$HOME/.claude/commands/wechat-article.md"
if [ ! -f "$SKILL_FILE" ]; then
  SKILL_FILE="$AB_DIR/skills/wechat-article.md"
fi
SKILL_BODY="$(cat "$SKILL_FILE")"
REPORT_BODY="$(cat "$REPORT_FILE")"

PROMPT="$(cat <<'PUB_EOF'
你负责把「供应链瓶颈猎手」的每周扫描报告改写成一篇可直接发布的微信公众号文章。

## 输入：今日扫描日报全文

@@REPORT@@

## 改写要求（必须遵守）

1. 遵循以下公众号写作技能的全部规则：
@@SKILL@@

2. 针对本日报的专项要求：
   - 目标读者：关注 AI 算力/半导体供应链的投资人，有一定基础但不看原始研究笔记。
   - 把日报里的"研究笔记语言"转成"公众号文章语言"：核心结论放最前，数据保留但去掉内部口径
     （如"上轮给的参考区间""watchlist 更新"等内部流程词），估值检查保留但用通俗表述。
   - 结构建议：标题（有冲击力/数据感）→ 今日三条核心结论 → 分主题展开（内存/HBM、电力、
     光学/InP、钨等）→ 风险提示 → 免责声明（本文为研究分享，不构成投资建议）。
   - 控制篇幅：1500-2500 字；表格最多 2 个且要精简；禁止 emoji 堆砌；
     保留关键数据与来源链接（合并到文末"数据来源"清单）。
   - 封面：不需要图片插入，封面由发布管线自动生成。
   - 标题请放在 frontmatter：--- title: "标题" digest: "摘要" ---
   - 结尾挂一句转发钩子，适合截图传播。

3. 只输出最终文章正文（markdown），不要输出 process/说明文字。
PUB_EOF
)"
PROMPT="${PROMPT//@@REPORT@@/$REPORT_BODY}"
PROMPT="${PROMPT//@@SKILL@@/$SKILL_BODY}"

echo "[run] 调用 claude 改写日报为公众号文章（预计 3-8 分钟）..."
set +e
ARTICLE_OUT="$("$CLAUDE_BIN" -p "$PROMPT" \
  --add-dir "$AB_DIR" \
  --permission-mode bypassPermissions \
  --output-format text 2>>"$LOG_FILE")"
RC=$?
set -e

if [ $RC -ne 0 ]; then
  echo "[ERROR] claude 改写失败（退出码 $RC），中止发布。" >&2
  exit $RC
fi

# 清理 claude 回复：去掉代码围栏，并丢弃 frontmatter 之前的说明文字
ARTICLE_OUT="$(printf '%s' "$ARTICLE_OUT" | sed -n '/^```/d;p')"
ARTICLE_OUT="$(printf '%s' "$ARTICLE_OUT" | python3 -c '
import sys, re
text = sys.stdin.read()
m = re.search(r"^---\s*\n(.*?\n)---\s*\n", text, flags=re.DOTALL | re.MULTILINE)
if m:
    sys.stdout.write(text[m.start():])
else:
    sys.stdout.write(text)
')"
printf '%s\n' "$ARTICLE_OUT" > "$ARTICLE_FILE"
echo "[run] ✅ 文章已生成：$ARTICLE_FILE（$(wc -l < "$ARTICLE_FILE") 行）"

# ---- 校验文章非空 ----
if [ ! -s "$ARTICLE_FILE" ]; then
  echo "[ERROR] 生成的文章为空，中止发布。" >&2
  exit 1
fi

# ---- 预检 3：行情数字的日期绑定 ----
# 防"数字对、日期错"这类错误静静进稿。实例（2026-09-19 复核发现）：稿子写
# "苹果 9/18 宣布涨价后股价大跌 6%"，而 AAPL 9/18 收 -0.26%，那 -6% 发生在 7/31
# ——引证里的"金十 9/18"是来源发布日期，被当成了事件发生日期。多源交叉验证对
# 这种"绑定错误"结构性失明（两个来源都会报 6%）。
#
# claim_lint.py 只看一件事：每条行情数字同句内是否自带可定位时点的标记。
# 纯文本、零网络、零误报（15 条内嵌用例自检，见 --self-test）。
# 卡在"改写已完成、尚未调微信接口"这一刻：此时才存在最终要推的产物。
set +e
LINT_OUT="$(python3 "$AB_DIR/tools/claim_lint.py" "$ARTICLE_FILE" 2>&1)"
LINT_RC=$?
set -e
# 注意：本脚本第 97 行 `exec >> "$LOG_FILE" 2>&1` 之后，普通 stdout 只进管线日志
# 文件，终端/journal 只剩 fd 9。claim_lint 的明细必须经 say() 走一次 fd 9，
# 否则报错文案里的"见上"在终端上是空的（2026-09-19 集成测试当场暴露）。
say "$LINT_OUT"
if [ "$LINT_RC" -ne 0 ]; then
  if [ "$ALLOW_LINT" = "1" ]; then
    say "[preflight] ⚠️ 日期绑定校验未过，但 --allow-lint 已放行（本次推送带未验证的行情数字）"
  else
    fail 6 \
      "[ERROR] 文章里的行情数字缺时点标记（明细见上），中止建草稿。" \
      "        规则：每条涨跌/价格数字必须在同句内自带日期（9月18日）或明确基期的" \
      "        周期词（本周/单周/同比）；只说「单日/盘中」不足以定位是哪一天。" \
      "        修完文章重跑即可；确认要放行加 --allow-lint。"
  fi
else
  say "[preflight] ✅ 行情数字日期绑定正常"
fi

# ---- 调官方 API 建草稿（默认不发布） ----
echo "[run] 调用 wechat_mp_publish.py 建草稿 ${PUBLISH_FLAG:-（不发布）}..."
python3 "$AB_DIR/tools/wechat_mp_publish.py" \
  --article "$ARTICLE_FILE" \
  --cover auto \
  --env "$AB_DIR/.env" \
  $PUBLISH_FLAG

RC=$?
echo "===== 发布管线结束：$(date +'%F %T')（退出码 $RC） ====="
exit $RC