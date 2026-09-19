#!/usr/bin/env bash
# ============================================================================
# 瓶颈猎手周报流水线：扫描 → 建公众号草稿
#
# 由 systemd timer 每周五 21:00 调用（见同目录 bottleneck-weekly.{service,timer}）。
#
# 为什么把两步串成一条链，而不是两个独立定时任务：
#   机器睡眠会让两个定时点双双错过。若它们是独立 timer，唤醒后会在同一时刻
#   一起补触发 —— 发布先跑，此时本周报告还没产出，`latest` 指向上周日报，
#   撞上 publish-scan-daily.sh 的新鲜度守卫（>2 天拒绝）→ 本周草稿静默丢失。
#   串联执行从结构上消除这个竞争；顺带也不再需要"扫描后固定等 45 分钟"
#   这个拍脑袋的时间差 —— 扫描快就早发，慢就等它。
#
# 为什么不管扫描退出码都要尝试发布：
#   bottleneck-hunter-scan.sh 在"报告已写出、但估值凭据校验未通过"时也返回 1
#   （2026-09-18 即如此）。若拿扫描退出码当闸门，会把本来可用的周报一起丢掉。
#   真正的闸门是 publish-scan-daily.sh 自己的日报新鲜度守卫。
#
# 用法：
#   bash bottleneck-weekly.sh              # 完整跑：扫描 + 发布
#   bash bottleneck-weekly.sh --dry-run    # 只打印将要执行的步骤与前置状态
#   bash bottleneck-weekly.sh --skip-scan  # 跳过扫描，只跑发布（补发用）
#
# 退出码：0 = 两步都成功   非 0 = 至少一步失败（具体见日志与 journal）
# ============================================================================
set -uo pipefail   # 刻意不用 -e：单阶段失败也要走完后续阶段并汇总

REPO_ROOT="/home/timwang/Documents/workspace/tradebot_workspace/vnpy"
AB_DIR="$REPO_ROOT/ai-berkshire"
LOG_DIR="$AB_DIR/logs"
DAILY_DIR="$AB_DIR/reports/供应链瓶颈/daily"
SCAN="$AB_DIR/scripts/bottleneck-hunter-scan.sh"
PUBLISH="$AB_DIR/scripts/publish-scan-daily.sh"
LOCK_FILE="/tmp/bottleneck-weekly.lock"

# systemd 环境的 PATH 很窄，显式补全（脚本内部还会各设一次，这里是双保险）
export PATH="/home/timwang/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONPATH="$REPO_ROOT/tbot:$AB_DIR${PYTHONPATH:+:$PYTHONPATH}"

DRY=0
SKIP_SCAN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)   DRY=1; shift ;;
    --skip-scan) SKIP_SCAN=1; shift ;;
    *) echo "未知参数: $1（支持 --dry-run / --skip-scan）" >&2; exit 2 ;;
  esac
done

TODAY="$(date +%Y-%m-%d)"
LOG_FILE="$LOG_DIR/bottleneck-weekly-$TODAY.log"
LATEST_REPORT="$(ls -t "$DAILY_DIR"/*-pm.md 2>/dev/null | head -1 || true)"

# ---- dry-run：只报告计划与前置状态，不执行任何副作用 ----
if [ "$DRY" = "1" ]; then
  echo "=== DRY RUN（不执行任何步骤）$(date +'%F %T') ==="
  echo "扫描脚本 : $SCAN"
  echo "发布脚本 : $PUBLISH"
  if [ "$SKIP_SCAN" = "1" ]; then
    echo "阶段 1   : （--skip-scan，跳过）"
  else
    echo "阶段 1   : bash $SCAN"
  fi
  echo "阶段 2   : bash $PUBLISH   # --date latest + 新鲜度守卫 + 白名单预检"
  if [ -n "$LATEST_REPORT" ]; then
    echo "将发布   : $LATEST_REPORT"
  else
    echo "将发布   : ⚠️ daily/ 下没有 *-pm.md，发布阶段会被守卫拒绝"
  fi
  echo "日志     : $LOG_FILE"
  echo "=== DRY RUN 结束 ==="
  exit 0
fi

mkdir -p "$LOG_DIR"

# ---- 并发锁：整条链只允许一个实例（覆盖"cron 与 timer 同时存在"的过渡期） ----
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date +'%F %T')] 已有流水线在运行（$LOCK_FILE），本次跳过。" >&2
  exit 0
fi

# 汇总消息同时写「管线日志」和 journal（systemd 下 stderr 进 journal）
exec 10>&2
exec >> "$LOG_FILE" 2>&1

say() {
  for line in "$@"; do
    printf '%s\n' "$line"
    printf '%s\n' "$line" >&10
  done
}

say "===== 瓶颈猎手周报流水线启动：$(date +'%F %T')（扫描=$([ "$SKIP_SCAN" = 1 ] && echo 跳过 || echo 执行)） ====="

SCAN_RC=0
PUB_RC=0

# ---- 阶段 1：扫描 ----
if [ "$SKIP_SCAN" = "1" ]; then
  say "[1/2] 跳过扫描（--skip-scan）"
else
  say "[1/2] 扫描：$SCAN"
  bash "$SCAN"
  SCAN_RC=$?
  say "[1/2] 扫描结束，退出码 $SCAN_RC"
  if [ "$SCAN_RC" -ne 0 ]; then
    # 退出码 1 常见于"报告已写出但估值凭据校验未通过"，不代表本周没有报告，
    # 因此这里只提示，不中止 —— 交给阶段 2 的新鲜度守卫判断。
    say "      注意：扫描非零退出。若原因是估值凭据校验未过（报告仍已写出），"
    say "            下面的发布仍会按周报正常进行；请人工复核报告数字来源。"
  fi
fi

# ---- 阶段 2：建公众号草稿 ----
say "[2/2] 发布：$PUBLISH"
bash "$PUBLISH"
PUB_RC=$?
say "[2/2] 发布结束，退出码 $PUB_RC"

case "$PUB_RC" in
  0) say "      ✅ 草稿已创建，请到公众号后台「草稿箱」人工确认后发布。" ;;
  3) say "      ❌ 出口 IP 不在白名单 —— 按上面的提示加白名单后重跑本脚本。" ;;
  4) say "      ❌ 微信接口预检未通过 —— 见上面的具体原因。" ;;
  5) say "      ❌ 日报过旧被守卫拒绝 —— 本周扫描很可能没有产出报告，见阶段 1 日志。" ;;
  *) say "      ❌ 发布失败（退出码 $PUB_RC），见上面的错误信息。" ;;
esac

say "===== 流水线结束：$(date +'%F %T')（扫描 $SCAN_RC / 发布 $PUB_RC） ====="

# 扫描失败但发布成功（或反之）都算整体非零，便于 journal 里一眼看出
if [ "$SCAN_RC" -ne 0 ] || [ "$PUB_RC" -ne 0 ]; then
  exit 1
fi
exit 0
