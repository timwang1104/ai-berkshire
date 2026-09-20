#!/usr/bin/env python3
"""claim_lint.py — 「行情数字的日期绑定」校验（纯文本，无网络）。

背景：2026-09-19 复核 2026-09-18 周报的公众号稿，发现开头写

    市场，苹果官宣涨价，股价大跌6%，Mac Studio交付排到明年。

而 AAPL 在 9/18 收 -0.26%（当周还在五周连涨）；那 -6%~-7.35% 发生在 **7/31**
（FY26Q3 财报后）。6% 是真数字，错的是**数字与日期的绑定**——引证里那句
「金十 9/18」是*来源发布日期*，被当成了*事件发生日期*。

为什么现有校验抓不到：`financial_rigor.cross_validate` 比的是同字段的**值**，
两个来源都会报 6%，一致通过。**跨源交叉验证对"绑定错误"结构性失明**——它查
值，不查值与日期的对应关系。

本工具只做一件事：**每条行情数字必须在同句内自带一个能定位时点的标记**
（绝对日期，或 本周/单周/同比 这类明确了基期的周期词）。没有标记 = 不可校验
= 视为未验证，一律报出。目的不是"机器判断事实对不对"，而是把日期绑定从修辞
里拽回到文本表面——写的人必须写出来，人和机器才都能查。

刻意不做（本项目已有一道"期期皆红、被显式降级"的闸门作为教训，误报会杀死闸门）：
  - 不做行情联网核对（下一步，见 skills 讨论；本工具零网络依赖）
  - 不做语义消歧，不猜
  - **不用**「单日 / 当日 / 盘中 / 近日 / 近期 / 上周五之前」这类不定住时点的词
    充当时点标记——它们正是"借来的日期"的载体
  - 表格行从其**表头**继承周期：表头是显式的作用域声明，与"从叙述里借日期"不同
  - 平台字节上限错误另见 --self-test；由 wechat_mp_publish.py 的截断逻辑负责

用法：
    python3 tools/claim_lint.py <文章.md> [更多.md ...]
    python3 tools/claim_lint.py --self-test          # 内嵌用例自检
退出码：0 = 通过；1 = 存在无时点标记的行情数字；2 = 用法错误
"""

from __future__ import annotations

import argparse
import re
import sys

# --- 能定位时点的标记（PIN） -------------------------------------------------
# 绝对日期
_ABS_DATE = r"\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}\s*-\s*\d{2}\s*-\s*\d{2}|\d{1,2}/\d{1,2}"
# 相对但基期明确的周期词（"本周"可对上周报窗口定位；"同比/环比"自带基期）
_PERIOD = (
    "本周|上周|单周|一周|周内|本月|上月|年内|今年以来|年初至今|"
    "同比|环比|当周|该周|上季度|本季度|上半年|下半年"
)
_PIN = re.compile(f"(?:{_ABS_DATE})|(?:{_PERIOD})")

# --- 行情数字（FIGURE） ------------------------------------------------------
# 带涨跌动词的幅度
_MOVE = re.compile(
    r"(?:大涨|大跌|暴涨|暴跌|重挫|上涨|下跌|反弹|回落|回撤|收涨|收跌|涨|跌)"
    r"\s*(?:约|近|超|逾)?\s*\d+(?:\.\d+)?\s*%"
)
# 带正负号的幅度（如 "Coherent +3.9%"、"AOI -0.2%"）
# 注：lookbehind 只能用 ASCII 字母数字/点。Python 的 \w 含中文，"约+86%" 会被
# 中文挡掉（2026-09-19 自检用例当场抓到这个 bug）。
_SIGNED = re.compile(r"(?<![A-Za-z0-9.])[+＋-]\s*\d+(?:\.\d+)?\s*%")
# 价格水平陈述
_PRICE = re.compile(
    r"(?:收于|收盘|收报|报收|报|股价|现价|价格)\s*[$¥€]?\s*\d+(?:\.\d+)?\s*"
    r"(?:美元|港元|元|日元|欧元|韩元|便士|美分)"
)
_FIGURE = re.compile(f"(?:{_MOVE.pattern})|(?:{_SIGNED.pattern})|(?:{_PRICE.pattern})")

# 紧贴数字的"不定住时点"限定词：说"单日/当日/盘中涨 N%"就是在断言某一天的幅度，
# 而要核对它必须知道是*哪一天*——周级周期词（本周/单周）定位不到。所以这类断言
# 要求同句有**绝对日期**。（2026-09-19：Centrus 那句"单日涨7.8%，但当周仍是收跌"
# 就是靠"当周"混过了句子级检查，属于假阴性，故补此条。）
_LOOSE = re.compile(
    r"(?:单日|当日|当天|盘中|盘后|隔夜|一夜)"
    r"\s*(?:大涨|大跌|暴涨|暴跌|重挫|上涨|下跌|反弹|回落|回撤|收涨|收跌|涨|跌)"
)

# 句子切分：。！？；及换行（逗号不切——"苹果官宣涨价，股价大跌6%"必须留在同句）
_SENT_SPLIT = re.compile(r"[。！？；\n]+")
# Markdown 表格行
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _kind(fig: str) -> str:
    if _MOVE.fullmatch(fig) or _MOVE.match(fig):
        return "涨跌幅度"
    if _SIGNED.match(fig):
        return "带符号幅度"
    return "价格水平"


def lint_text(text: str) -> list[tuple[int, str, str]]:
    """返回 [(行号, 数字片段, 所在句)]，即缺时点标记的行情数字。"""
    problems: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    table_header = ""

    for lineno, raw in enumerate(lines, 1):
        line = raw
        if _TABLE_ROW.match(line):
            # 表头行：以"标的/名称/代码"等开头且不含涨跌动词 -> 作为后续数据行的作用域
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if any(c and not re.fullmatch(r"[-: ]*", c) for c in cells) and not _FIGURE.search(line):
                table_header = line
                continue
            if re.fullmatch(r"\s*\|[\s:|-]+\|\s*", line):  # 分隔行 |---|---|
                continue
            scope = table_header + " " + line
        else:
            table_header = "" if line.strip() else table_header
            scope = line

        # 逐句检查（表格行整体作一句，作用域里带上表头）
        for sent in _SENT_SPLIT.split(scope):
            figs = [m.group(0).strip() for m in _FIGURE.finditer(sent)]
            loose = bool(_LOOSE.search(sent))
            if not figs and not loose:
                continue
            has_pin = bool(_PIN.search(sent))
            has_abs = bool(re.search(_ABS_DATE, sent))
            # 含"单日/盘中"类限定词的断言：周级周期词不够，必须有绝对日期
            if loose and figs and not (has_pin and has_abs):
                for m in _LOOSE.finditer(sent):
                    problems.append((lineno, m.group(0), " ".join(sent.split())))
                continue
            if has_pin:
                continue
            for fig in figs:
                problems.append((lineno, fig, " ".join(sent.split())))
    return problems


# ---------------------------------------------------------------------------
# 自检用例（改规则时先跑这个：既要证明该抓的抓得到，也要证明不该抓的没被抓）
# ---------------------------------------------------------------------------
_SELF_CASES: list[tuple[str, str, int]] = [
    # (用例名, 文本, 期望报出的数字条数)
    ("实际事故原句", "市场，苹果官宣涨价，股价大跌6%，Mac Studio交付排到明年。", 1),
    ("实际事故·信号一", "下游传导已经发生。苹果涨价、股价大跌6%，只是最显眼的一环。", 1),
    ("带绝对日期·不报", "9月18日Coherent单日涨7.2%、AAOI涨7.3%。", 0),
    ("带周期词·不报", "一周下来Coherent +3.9%、Lumentum +0.4%、AAOI -0.2%。", 0),
    ("同比自带基期·不报", "TrendForce测算其存储成本同比涨近400%。", 0),
    ("年内·不报", "苹果股价年内累计上涨约23.7%。", 0),
    ("单日不定时点·要报", "签约消息让股价单日涨7.8%。", 1),
    ("单日+周级词仍要报", "签约消息让股价单日涨7.8%，但当周仍是收跌。", 1),
    ("单日+绝对日期·不报", "9月17日股价单日涨7.8%。", 0),
    ("单周不算单日·不报", "股价收于13.84美元，单周跌10.7%。", 0),
    ("价格无日期·要报", "股价跌穿15美元观察线，收于13.84美元。", 1),
    ("表格从表头继承·不报", "| 标的 | 一周涨跌 | 估值信号 |\n|---|---|---|\n| Almonty | -10.7%，收于13.84美元 | 无 |", 0),
    ("表格无表头周期·要报", "| 标的 | 幅度 | 估值信号 |\n|---|---|---|\n| Almonty | -10.7%，收于13.84美元 | 无 |", 2),
    ("非行情百分比·不报", "内存已占材料成本的60%，存储占整机BOM的34%。", 0),
    ("目标价上行空间·要报", "卖方目标均价较现价分别约+86%和+43%。", 2),
]


def self_test() -> int:
    failed = 0
    for name, text, expect in _SELF_CASES:
        got = len(lint_text(text))
        ok = got == expect
        failed += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} {name}：期望 {expect} 条，实得 {got} 条")
        if not ok:
            for ln, fig, sent in lint_text(text):
                print(f"        ↳ L{ln} 「{fig}」 在: {sent[:80]}")
    print(f"\n自检：{'全部通过' if not failed else f'{failed} 个用例失败'}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="行情数字的日期绑定校验（纯文本，无网络）")
    ap.add_argument("files", nargs="*", help="待校验的 Markdown 文件")
    ap.add_argument("--self-test", action="store_true", help="运行内嵌自检用例")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.files:
        ap.print_help(sys.stderr)
        return 2

    rc = 0
    for path in args.files:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError as exc:
            print(f"✗ {path}: 无法读取（{exc}）")
            rc = 1
            continue
        problems = lint_text(text)
        if not problems:
            print(f"✓ {path}: 行情数字均带时点标记")
            continue
        rc = 1
        print(f"✗ {path}: {len(problems)} 处行情数字缺时点标记（无可核对的日期 = 未验证）")
        for lineno, fig, sent in problems:
            print(f"    L{lineno}  「{fig}」  →  …{sent[:90]}…")
    return rc


if __name__ == "__main__":
    sys.exit(main())
