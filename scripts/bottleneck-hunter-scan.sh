#!/usr/bin/env bash
# ============================================================================
# 每周供应链瓶颈扫描（bottleneck-hunter 定时任务）
#
# 由 systemd user timer 每周五 21:00、经 scripts/bottleneck-weekly.sh 串联调用
# （见同目录 bottleneck-weekly.{service,timer}）。2026-09-19 之前是 crontab，
# 因 vixie-cron 不补跑睡眠期间错过的任务而弃用：2026-09-11 那周因此整周漏跑且无告警。
#   0. 趋势清单时效前置检查（技能第〇·五步）：trend-universe.md 缺失或上次重估
#      >30 天时，先强制执行"趋势清单月度重估"再进入信号扫描。
#   1. 以 headless 模式调用 claude CLI，注入 bottleneck-hunter 技能指令，
#      执行"每周扫描"：扫描供应链紧缺信号、检查 watchlist、更新瓶颈地图。
#   2. 报告写入：
#        ai-berkshire/reports/供应链瓶颈/daily/{YYYY-MM-DD}-pm.md
#        并增量更新 master-map.md / watchlist.md / trend-universe.md（重估轮）
#   3. 会话与脚本日志写入 ai-berkshire/logs/bottleneck-hunter-{日期}.log
#
# 用法：
#   bash bottleneck-hunter-scan.sh            # 正常执行每周扫描
#   bash bottleneck-hunter-scan.sh --check    # 只做环境自检，不执行扫描
# ============================================================================
set -euo pipefail

REPO_ROOT="/home/timwang/Documents/workspace/tradebot_workspace/vnpy"
AB_DIR="$REPO_ROOT/ai-berkshire"
REPORT_ROOT="$AB_DIR/reports/供应链瓶颈"
DAILY_DIR="$REPORT_ROOT/daily"
LOG_DIR="$AB_DIR/logs"
CLAUDE_BIN="/home/timwang/.local/bin/claude"
LOCK_FILE="/tmp/bottleneck-hunter-scan.lock"

# 定时任务环境 PATH 很窄（cron 与 systemd user 环境皆然），必须显式补全
export PATH="/home/timwang/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
# 让 ai-berkshire 的 tools/ 能调用 tbot 模块（见 CLAUDE.md）
export PYTHONPATH="$REPO_ROOT/tbot:$AB_DIR${PYTHONPATH:+:$PYTHONPATH}"

TODAY="$(date +%Y-%m-%d)"
NOW="$(date +'%Y-%m-%d %H:%M')"
LOG_FILE="$LOG_DIR/bottleneck-hunter-$TODAY.log"

mkdir -p "$DAILY_DIR" "$LOG_DIR"

# ---- 并发锁：避免上一轮未结束时重复启动 ----
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date +'%F %T')] 已有扫描在运行（$LOCK_FILE），本次跳过。" >> "$LOG_FILE" 2>&1 || true
  exit 0
fi

# ---- 环境自检模式（输出到终端，不写日志） ----
if [ "${1:-}" = "--check" ]; then
  echo "[check] REPO_ROOT=$REPO_ROOT"
  echo "[check] REPORT_ROOT=$REPORT_ROOT"
  echo "[check] DAILY_DIR=$DAILY_DIR"
  echo "[check] LOG_FILE=$LOG_FILE"
  echo "[check] CLAUDE_BIN=$CLAUDE_BIN"
  echo "[check] date=$(date '+%F %T %Z')"
  if [ -x "$CLAUDE_BIN" ]; then
    echo "[check] claude 可执行，版本：$("$CLAUDE_BIN" --version)"
  else
    echo "[check] 警告：找不到 claude，$CLAUDE_BIN" >&2
  fi
  if command -v flock >/dev/null 2>&1; then echo "[check] flock 可用"; else echo "[check] 警告：flock 不可用" >&2; fi
  echo "[check] 自检完成。"
  exit 0
fi

# ---- 全部输出进当日日志；调用方的重定向只兜底脚本级早期错误 ----
exec >> "$LOG_FILE" 2>&1

echo "===== bottleneck-hunter 每周扫描启动：$NOW ====="

# ---- 趋势清单时效前置检查（技能第〇·五步）----
# trend-universe.md 缺失 / 无上次重估日期 / 上次重估 >30 天 → 本轮先强制重估。
TREND_FILE="$REPORT_ROOT/trend-universe.md"
REVAL_FLAG=0
REVAL_TEXT="【趋势清单检查】无需重估：沿用 trend-universe.md 现有清单，但在报告“超级趋势健康度”小节逐条标注 维持/升级/降级/移除（技能“清单是活的，不是档案”）。"

if [ ! -f "$TREND_FILE" ]; then
  REVAL_FLAG=1
  REVAL_TEXT="【趋势清单强制重估（缺失）】$TREND_FILE 不存在，必须先执行技能第〇·五步“趋势清单月度重估”：①扫全市场新趋势候选（WebSearch，含中英文源）；②对候选套用 1.1 四标准（持续/物理/规模/加速，≥3 条通过才新增）；③对现有清单逐条复核 保持/降级/移除；④按模板完整更新 $TREND_FILE（上次重估：今天 / 下期重估：+30 天 / 新增 / 保持 / 降级移除 / 候选池）；⑤清单变更写入当周报告。重估完成后再继续信号扫描。"
  echo "[check] ⚠️ $TREND_FILE 不存在，本轮先执行趋势清单月度重估。"
else
  LAST_REVAL="$(grep -oE '上次重估[：:][[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}' "$TREND_FILE" | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)"
  if [ -z "$LAST_REVAL" ]; then
    REVAL_FLAG=1
    REVAL_TEXT="【趋势清单强制重估（无日期）】$TREND_FILE 缺少“上次重估”日期，必须先执行技能第〇·五步完整月度重估，并按模板重写 $TREND_FILE（上次重估：今天 独立成行），完成后再继续信号扫描。"
    echo "[check] ⚠️ $TREND_FILE 缺少 上次重估 日期，本轮先执行趋势清单月度重估。"
  elif ! date -d "$LAST_REVAL" >/dev/null 2>&1; then
    REVAL_FLAG=1
    REVAL_TEXT="【趋势清单强制重估（日期无效）】$TREND_FILE 的 上次重估 日期 $LAST_REVAL 无法解析，必须先执行技能第〇·五步完整月度重估并更新 $TREND_FILE，完成后再继续信号扫描。"
    echo "[check] ⚠️ $TREND_FILE 上次重估日期 $LAST_REVAL 无法解析，本轮先执行趋势清单月度重估。"
  else
    DAYS_SINCE=$(( ( $(date -d "$TODAY" +%s) - $(date -d "$LAST_REVAL" +%s) ) / 86400 ))
    if [ "$DAYS_SINCE" -gt 30 ]; then
      REVAL_FLAG=1
      REVAL_TEXT="【趋势清单月度重估（过期）】$TREND_FILE 上次重估 $LAST_REVAL 距今 ${DAYS_SINCE} 天 >30，必须先执行技能第〇·五步完整月度重估并更新 $TREND_FILE（上次重估：今天 / 下期重估：+30 天 / 新增 / 保持 / 降级移除 / 候选池），完成后再继续信号扫描。"
      echo "[check] ⚠️ $TREND_FILE 上次重估 $LAST_REVAL 距今 ${DAYS_SINCE} 天 >30，本轮先执行趋势清单月度重估。"
    else
      echo "[check] ✅ $TREND_FILE 上次重估 $LAST_REVAL 距今 ${DAYS_SINCE} 天（≤30），无需重估。"
    fi
  fi
fi

# ---- 取技能指令：优先已安装的 command，缺失则回退仓库内 canonical 版本 ----
SKILL_FILE="$HOME/.claude/commands/bottleneck-hunter.md"
if [ ! -f "$SKILL_FILE" ]; then
  SKILL_FILE="$AB_DIR/skills/bottleneck-hunter.md"
fi
if [ ! -f "$SKILL_FILE" ]; then
  echo "[ERROR] $(date +'%F %T') 找不到 bottleneck-hunter 技能文件，请检查：$AB_DIR/skills/bottleneck-hunter.md" >&2
  exit 1
fi
SKILL_BODY="$(cat "$SKILL_FILE")"

# ---- 构造任务提示词 ----
# 注意：技能文本里含 $ARGUMENTS、$XX 等，必须用带引号的 heredoc + 占位符插值，
# 避免 bash 把它们当作变量展开。
PROMPT="$(cat <<'BOTTLE_EOF'
你是"供应链瓶颈猎手"，现在执行一次每周供应链瓶颈扫描。今天日期：@@TODAY@@。

## 趋势清单时效检查（优先执行）

@@REVAL@@

## 技能指令（必须完整遵循，不可跳过任何步骤）

@@SKILL@@

## 本次任务要求（每周扫描模式，每周五 21:00 运行）

1. 先运行 date 确认今天日期，作为数据截止日写入报告头（遵循 ai-berkshire/AGENTS.md 的数据纪律）。
2. 以每周扫描模式执行技能全部相关步骤。将技能中"每小时扫描模式"与"每日扫描"的时间窗放大到最近 7 天：
   - 新闻扫描：搜索最近 7 天供应链相关新闻。WebSearch 优先；若 WebSearch 返回空结果，改用 WebFetch
     抓取行业新闻源（如 trendforce.com/news、digitimes.com 新闻页、Reuters/Nikkei 供应链栏目、集微网、36kr 等）
     并重试一次；仍拿不到数据就如实写"数据不足"，禁止编造新闻或来源。
   - 市场信号：检查 watchlist.md 中已跟踪公司是否有异常波动（>5%）。
   - 财报/公告：检查跟踪公司近期财报与重大公告。
   - 估值机会：检查 watchlist 中是否有公司进入买入区间。
3. 报告输出（全部中文）：
   - 主报告必须写入 @@DAILYDIR@@/@@TODAY@@-pm.md，标题用《瓶颈猎手周报 — @@TODAY@@》，
     采用技能中"报告模板（有标的时）"或"（仅信号扫描时）"的格式；若发现通过估值检查的明确标的，
     文件名可含标的代码（如 @@DAILYDIR@@/@@TODAY@@-pm-FORM.md），但请先沿用 @@TODAY@@-pm.md 并附标的清单。
   - 同步增量更新 @@REPORTROOT@@/master-map.md 与 @@REPORTROOT@@/watchlist.md
     （升级/降级/新增/移除），无变化则在报告相应小节写"无变化"。
   - 阅读 @@REPORTROOT@@ 下最近一期的报告（含 daily/ 内最近一份），完成"最近变化（vs 上次扫描）"对比。
4. 数据与估值纪律：所有数据标注来源 URL；估计值标"估计"；涉及市值/PS/PE/安全边际等估值计算时，
   cd 到 @@ABDIR@@ 后用 python3 tools/financial_rigor.py 精确计算；估值是硬门槛，不可被瓶颈叙事覆盖。
5. 即使本轮无新信号，也必须生成本周报告，在报告中明确写"本周无新信号"并简述存量状态。
6. 报告全部写完后，在回复最后单独输出一行：REPORT_WRITTEN=@@DAILYDIR@@/@@TODAY@@-pm.md
BOTTLE_EOF
)"
PROMPT="${PROMPT//@@TODAY@@/$TODAY}"
PROMPT="${PROMPT//@@SKILL@@/$SKILL_BODY}"
PROMPT="${PROMPT//@@DAILYDIR@@/$DAILY_DIR}"
PROMPT="${PROMPT//@@REPORTROOT@@/$REPORT_ROOT}"
PROMPT="${PROMPT//@@ABDIR@@/$AB_DIR}"
PROMPT="${PROMPT//@@REVAL@@/$REVAL_TEXT}"

echo "[run] 技能文件：$SKILL_FILE"
echo "[run] 调用 claude headless 执行扫描（预计 10-30 分钟，日志见 $LOG_FILE）..."

set +e
"$CLAUDE_BIN" -p "$PROMPT" \
  --add-dir "$AB_DIR" \
  --permission-mode bypassPermissions \
  --output-format text
RC=$?
set -e

echo "[run] claude 退出码：$RC（$(date +'%F %T')）"

if [ -f "$DAILY_DIR/$TODAY-pm.md" ]; then
  echo "[run] ✅ 本周报告已生成：$DAILY_DIR/$TODAY-pm.md"
  ls -la "$DAILY_DIR/$TODAY-pm.md"
else
  echo "[run] ⚠️ 未检测到 $DAILY_DIR/$TODAY-pm.md，请检查日志确认是否有报告未写入或文件名不同。"
fi

# ---- 报告估值凭据校验：出估值数字的标的必须带 总股本 ≥2来源 日期 ----
# 防"市值=股价×总股本"错算默默进报告（历史：AAOI/云南锗业单源旧股本低估 30~40%）。
if [ -f "$DAILY_DIR/$TODAY-pm.md" ]; then
  echo "[run] 校验报告估值凭据（verify_reports.py）..."
  set +e
  python3 "$AB_DIR/tools/verify_reports.py" "$DAILY_DIR/$TODAY-pm.md"
  VERIFY_RC=$?
  set -e
  if [ "$VERIFY_RC" -ne 0 ]; then
    echo "[ERROR] 报告估值凭据校验未通过：存在出估值数字但缺 总股本/双源/日期 的标的，请补齐后重跑或人工修订。退出码置 1。" >&2
    RC=1
  else
    echo "[run] ✅ 报告估值凭据校验通过"
  fi
fi

# ---- 发布合规预检（**只告警，不阻断**）----
# 日报是内部研究底稿，允许保留操作结论与个股评级；但公众号稿由它改写而来，
# 而模型有保留原文要素的天然倾向（2026-09 实证：连"上轮给的参考区间"都保留成了
# "13.5至15美元"）。所以在**源头**就把会被闸门拦下的东西照出来，让人当场看到
# "这句会传下去"，而不是等发布时才发现。
#
# 为什么不阻断：硬保证在 publish-scan-daily.sh 预检 4（exit 7，无放行开关）；
# 且日报本就该保留判断。这里只做反馈，顺带为「命中率监控」提供数据。
if [ -f "$DAILY_DIR/$TODAY-pm.md" ]; then
  echo "[run] 发布合规预检（compliance_lint --warn-only，只告警不阻断）..."
  set +e
  python3 "$AB_DIR/tools/compliance_lint.py" --warn-only "$DAILY_DIR/$TODAY-pm.md"
  set -e
  echo "[run] （以上告警不影响本轮结果；处理方式见 skills/wechat-article.md『合规红线』）"
fi

# ---- 重估轮产物校验：触发重估则该轮必须把 trend-universe.md 更新到今天 ----
if [ "$REVAL_FLAG" = "1" ]; then
  NEW_REVAL="$(grep -oE '上次重估[：:][[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}' "$TREND_FILE" 2>/dev/null | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)"
  if [ "$NEW_REVAL" = "$TODAY" ]; then
    echo "[run] ✅ 趋势清单重估产物已更新：$TREND_FILE（上次重估=$NEW_REVAL）"
  else
    echo "[ERROR] 本轮触发重估，但 $TREND_FILE 未更新到 $TODAY（当前=$NEW_REVAL 或文件缺失），重估失败，请人工检查。" >&2
    RC=1
  fi
fi

echo "===== bottleneck-hunter 每周扫描结束：$(date +'%F %T')（退出码 $RC） ====="
exit "$RC"