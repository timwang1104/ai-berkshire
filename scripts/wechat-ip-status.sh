#!/usr/bin/env bash
# ============================================================================
# 公众号发布 · 出口 IP 白名单巡检（「每周仪式」的那一条命令）
#
# 背景：
#   家庭宽带出口 IP 会漂移，漂出公众号后台的「API IP 白名单」后，所有服务端
#   接口都返回 40164，草稿建不出来。本脚本把"该不该去后台更新白名单"这件事
#   变成一条命令的结论，并顺手积累漂移历史（用于判断是否值得改用固定出口）。
#
# 做什么：
#   1. 查当前出口 IP（多个公开回显服务轮询，全部失败也不致命）
#   2. 实测微信接口：凭证 + IP 白名单（真实调用 /cgi-bin/token）
#   3. 把本次观测追加到 local/wechat_mp/ip_history.log（local/ 不入库）
#   4. 打印结论 / 需要手动做的步骤 / 漂移频率统计
#
# 用法：
#   bash scripts/wechat-ip-status.sh              # 巡检一次
#   bash scripts/wechat-ip-status.sh --history    # 巡检 + 打印完整漂移历史
#
# 退出码：与 wechat_mp_publish.py --check 一致
#   0 = 白名单正常      3 = 出口 IP 未在白名单      其他 = 凭证/网络等其他问题
# ============================================================================
set -uo pipefail

REPO_ROOT="/home/timwang/Documents/workspace/tradebot_workspace/vnpy"
AB_DIR="$REPO_ROOT/ai-berkshire"
TOOL="$AB_DIR/tools/wechat_mp_publish.py"
ENV_FILE="$AB_DIR/.env"
HISTORY="$AB_DIR/local/wechat_mp/ip_history.log"
DAILY_DIR="$AB_DIR/reports/供应链瓶颈/daily"

SHOW_HISTORY=0
[ "${1:-}" = "--history" ] && SHOW_HISTORY=1

echo "=== 公众号发布 · IP 白名单巡检 $(date +'%F %T') ==="
echo

# ---- 1) 当前出口 IP ----------------------------------------------------------
EGRESS_IP=""
IP_SOURCE=""
for url in "https://myip.ipip.net" "https://ifconfig.me/ip" "https://api.ipify.org" "https://ip.sb"; do
  body="$(curl -fsS --max-time 8 "$url" 2>/dev/null || true)"
  candidate="$(printf '%s' "$body" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -1 || true)"
  if [ -n "$candidate" ]; then
    EGRESS_IP="$candidate"
    IP_SOURCE="$url"
    break
  fi
done

if [ -n "$EGRESS_IP" ]; then
  echo "[1/4] 当前出口 IP : $EGRESS_IP    (来源 $IP_SOURCE)"
else
  echo "[1/4] 当前出口 IP : 查询失败（网络或回显服务不可用）—— 不致命，继续实测接口"
fi

# 若走了代理，实际出口 IP 与上面查到的可能不同，必须先说清楚
if [ -n "${HTTPS_PROXY:-}${https_proxy:-}${ALL_PROXY:-}${all_proxy:-}" ]; then
  echo "      ⚠️  检测到代理环境变量，微信看到的出口 IP 可能不是上面这个："
  echo "          HTTPS_PROXY=${HTTPS_PROXY:-}  https_proxy=${https_proxy:-}  ALL_PROXY=${ALL_PROXY:-}"
fi
echo

# ---- 2) 实测微信接口（凭证 + IP 白名单） -------------------------------------
echo "[2/4] 实测微信接口（真实调用 /cgi-bin/token 校验凭证与白名单）..."
echo
python3 "$TOOL" --check --env "$ENV_FILE"
RC=$?
echo

case "$RC" in
  0) STATUS="OK" ;;
  3) STATUS="REJECTED" ;;
  *) STATUS="ERROR" ;;
esac

# ---- 3) 记录观测 -------------------------------------------------------------
mkdir -p "$(dirname "$HISTORY")"
printf '%s\t%s\t%s\t%s\n' "$(date +'%F %T')" "${EGRESS_IP:-?}" "$STATUS" "巡检" >> "$HISTORY"

echo "[3/4] 已记录本次观测 → $HISTORY"

# ---- 4) 漂移统计 -------------------------------------------------------------
if [ -s "$HISTORY" ]; then
  OBS_TOTAL="$(wc -l < "$HISTORY" | tr -d ' ')"
  IP_UNIQUE="$(awk -F'\t' '{print $2}' "$HISTORY" | sort -u | wc -l | tr -d ' ')"
  echo "      累计 $OBS_TOTAL 次观测，出现过 $IP_UNIQUE 个不同出口 IP"
  if [ "$SHOW_HISTORY" = "1" ]; then
    echo
    echo "      --- 每个 IP 的首末次观测 ---"
    awk -F'\t' '
      { cnt[$2]++; if (!($2 in first)) first[$2]=$1; last[$2]=$1 }
      END { for (ip in cnt) printf "      %-16s %3d 次   首次 %s   最近 %s\n", ip, cnt[ip], first[ip], last[ip] }
    ' "$HISTORY" | sort
    echo
    echo "      --- 原始记录（最近 15 条） ---"
    tail -15 "$HISTORY" | sed 's/^/      /'
  else
    echo "      （加 --history 看每个 IP 的首末次观测与原始记录）"
  fi
fi
echo

# ---- 结论 --------------------------------------------------------------------
# 顺便提示发布管线关心的另一件事：daily/ 下最新日报的日期
LATEST_REPORT="$(ls -t "$DAILY_DIR"/*-pm.md 2>/dev/null | head -1 || true)"
if [ -n "$LATEST_REPORT" ]; then
  REPORT_DATE="$(basename "$LATEST_REPORT" .md | sed -E 's/^([0-9]{4}-[0-9]{2}-[0-9]{2})-.*/\1/')"
  REPORT_TS="$(date -d "$REPORT_DATE" +%s 2>/dev/null || true)"
  if [ -n "$REPORT_TS" ]; then
    AGE=$(( ( $(date +%s) - REPORT_TS ) / 86400 ))
    echo "      最新日报：$REPORT_DATE（距今 $AGE 天）"
    if [ "$AGE" -gt 10 ]; then
      echo "      ⚠️  超过 10 天，说明扫描可能漏跑了（笔记本睡眠时 cron 不补跑）。"
    fi
    echo
  fi
fi

case "$STATUS" in
  OK)
    echo "✅ 结论：白名单正常，当前出口 IP 已放行 —— 本周无需操作。"
    echo "   直接建草稿：bash ai-berkshire/scripts/publish-scan-daily.sh"
    ;;
  REJECTED)
    echo "❌ 结论：出口 IP 已漂出白名单，需要你手动更新（约 1 分钟）："
    echo
    echo "   ① 打开微信开发者平台 https://developers.weixin.qq.com/platform"
    echo "      → 我的业务 → 公众号/服务号 → 基础信息 → 开发信息 → API IP 白名单"
    echo "   ② 添加 ${EGRESS_IP:-（上面提示里的那个 IP）}   保存后约 10 分钟生效"
    echo "      （旧的 IP 可以先留着，多放几条不冲突）"
    echo "   ③ 约 10 分钟后重跑本命令确认："
    echo "      bash ai-berkshire/scripts/wechat-ip-status.sh"
    ;;
  *)
    echo "⚠️  结论：预检失败，但看起来不是 IP 白名单问题（退出码 $RC）。"
    echo "     常见原因：.env 凭证缺失/失效、公众号未认证无草稿箱权限、网络不通。"
    echo "     详见上面的报错信息。"
    ;;
esac

exit "$RC"
