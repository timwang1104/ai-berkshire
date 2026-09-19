#!/usr/bin/env python3
"""verify_reports.py — bottleneck-hunter 周报的估值凭据校验。

背景：2026-09 AAOI 与云南锗业市值曾因"直接抄单一来源市值、未手算 股价×总股本"
被低估 30~40%（前者 $600M ATM 增发后总股本 +49% 未更新）。为让这类错误不再静默
进报告，bottleneck-hunter-scan.sh 在本轮报告写完后调用本脚本做机器校验。

规则（对每个报告文件）：
  1. 按 `##` 标题切段；凡段内出现"市值 / market cap"且带数字的段落，
     必须**同段**附股本披露（总股本 / X 亿股 / X 万股 / shares）和来源名。
  2. 全报告必须 ≥2  个独立数据来源（名单见 KNOWN_SOURCES）。
  3. 全报告必须 ≥1 个数据日期（YYYY-MM-DD）。

任一违反 -> 列出问题并退出码 1（wrapper 据此把定时任务退出码置 1，暴露缺跑）。

用法:
    python3 tools/verify_reports.py <报告.md> [更多报告.md...]
退出码: 0 全部通过; 1 存在缺凭据的估值数字。
"""

from __future__ import annotations

import re
import sys

# 已知行情/财务数据源（归一化比对用，≥2 个独立来源才算达标）
KNOWN_SOURCES = [
    "新浪", "stockanalysis", "东方财富", "东财", "腾讯", "雪球",
    "Morningstar", "FinMind", "tushare", "雅虎", "investing",
    "seekingalpha", "gurufocus", "marketbeat", "金十",
]

# 实质市值金额：市值/`$`/`¥` 后 40 字符内有 数字+单位（亿/万/B/M/美元/人民币/港元）
_AMOUNT = re.compile(r"(?:市值|market cap).{0,40}?[\d,.]+\s*(?:亿|万|B|M)|[$¥]\s*[\d,.]+\s*(?:亿|万|B|M)")
_MS = re.compile(r"\d")  # 触发行须带数字
_SHARE = re.compile(r"总股本|[\d,.]+\s*(?:亿|万)?股|shares", re.IGNORECASE)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _sections(text: str) -> list[tuple[str, str]]:
    """按 `## ` 标题切段，返回 [(标题, 正文)]。无标题时整体一段。"""
    parts = re.split(r"(?m)^(## +.*)$", text)
    secs: list[tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        secs.append((parts[i], body))
    if not secs:
        secs = [("", text)]
    return secs


def _source_count(text: str) -> int:
    low = text.lower()
    return len({s for s in KNOWN_SOURCES if s.lower() in low})


def check_report(path: str) -> list[str]:
    """校验单个报告，返回问题描述列表（空 = 通过）。"""
    problems: list[str] = []
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        return [f"无法读取报告: {e}"]

    n_src = _source_count(text)
    has_date = bool(_DATE.search(text))
    if n_src < 2:
        problems.append(f"全报告独立来源仅 {n_src} 个（要求 ≥2），存在单源市值风险")
    if not has_date:
        problems.append("全报告缺少数据日期（YYYY-MM-DD）")

    for title, body in _sections(text):
        # 只对"出现实质市值金额"的段落做严格要求（市值+数字+单位/币种）；
        # 纯 PE/PS 或语法提及"市值"的段不强制，避免表格式误伤。
        val_lines = [ln for ln in body.splitlines()
                     if _AMOUNT.search(ln) and _MS.search(ln)]
        if not val_lines:
            continue
        seg = title + "\n" + body
        if not _SHARE.search(seg):
            problems.append(
                f"[{title.strip() or '无标题'}] 段内含市值数字但同段无股本披露"
                f"（总股本/亿股/万股/shares）"
            )
        if not _source_count(seg):
            problems.append(f"[{title.strip() or '无标题'}] 段内含市值数字但同段无数据来源")

    return problems


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2

    rc = 0
    for path in argv:
        problems = check_report(path)
        if problems:
            rc = 1
            print(f"✗ {path}")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"✓ {path}: 估值凭据校验通过")
    return rc


if __name__ == "__main__":
    sys.exit(main())