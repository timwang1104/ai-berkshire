#!/usr/bin/env python3
"""compliance_lint.py — 公众号发布合规闸门（纯文本，无网络）。

## 为什么存在

2026-09 平台对推送的供应链扫描文章给出违规提示，原文口径是

    「可能存在涉嫌不当使用国家机关、国家机关工作人员的名义或形象的表述内容」

即 **《广告法》第九条第(二)项**，而不是时政敏感。触发前提是内容被当作**商业宣传**——
而「具体标的 + 操作建议」正好提供了营销属性。所以两条合规问题是同一件事的两面：
内容越像荐股，里面出现政要名义就越像「借用国家权威为投资标的引流」。

当时的成因是结构性的：改写提示词明确要求「估值检查保留但用通俗表述」，于是模型
合理地写出了「我们把分批观察区间设在 13.5 至 15 美元」。三层防线全空——提示词主动
要求、`skills/wechat-article.md` 零合规要求、现有闸门只管日期绑定。

## 边界（说清楚，不给假保证）

- **B 类 = 硬阻断**：政要名义、对具体证券的操作语义、选择语汇。这些是**词汇级**，
  词表/正则能高精度判定 → 退出码 1，管线映射为 exit 7，**无放行开关**。
- **C 类 = 只告警**：国家机关名称、工作人员泛称、时政叙事词。硬删会砸掉「出口管制」
  这类产业论证骨架，只能人工判：**去掉机关名，论证还成立吗？**
- **抓不到的**：「判断对象是证券还是环节」是**语义级**——`PE 304倍，情绪远超盈利支撑`
  与 `InP 缺口70%，扩产周期18个月` 是同一个句式。这一层没有机制兜底，只能靠
  `skills/wechat-article.md`「合规红线」的三条判据人工自查。

## 唯一来源

本工具读 `tools/compliance_blocklist.json`（**数据**唯一来源）；规则散文写在
`skills/wechat-article.md` 的「合规红线」（**规则**唯一来源）。两者由 `--self-test` 的
自洽自检绑定：规则点名的每个类别都必须在词表里有非空条目，否则「规则说了、闸门没管」。

**政要姓名表刻意不进版本控制**：`tools/compliance_blocklist.json` 里 `b1_names` 为空，
真实姓名从 gitignored 的 `local/compliance/blocklist.names.json` 运行时合入
（模板见 `tools/compliance_blocklist.example.json`）。理由：本仓库是 public 的，
把姓名清单连同剥离脚本一起公开，会被读成审查规避工具链——风险比原问题更大。

用法：
    python3 tools/compliance_lint.py <文章.md>            # 0 通过 / 1 B 类命中 / 2 用法错误
    python3 tools/compliance_lint.py --warn-only <日报.md>  # 日报侧：只告警，永不阻断
    python3 tools/compliance_lint.py --strip <日报.md>      # 剥离内部块，结果写 stdout
    python3 tools/compliance_lint.py --list [--show-names]  # 只读诊断
    python3 tools/compliance_lint.py --self-test            # 内嵌用例自检
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_BLOCKLIST = REPO_ROOT / "tools" / "compliance_blocklist.json"
LOCAL_NAMES = REPO_ROOT / "local" / "compliance" / "blocklist.names.json"
HIT_LOG_DIR = REPO_ROOT / "logs"

INTERNAL_OPEN = "<!-- INTERNAL -->"
INTERNAL_CLOSE = "<!-- /INTERNAL -->"
JUDGE_MARK = "**内部判断**"
FACT_MARK = "**事实**"

# B 类（硬阻断）与 C 类（告警）的类别名 → 中文标签
BLOCK_LABELS = {
    "b1_names": "政要姓名",
    "b2_country_titles": "国别+头衔短语（变相使用）",
    "b3_patterns": "国别词+头衔共现",
    "operations": "操作语义",
    "operations_patterns": "操作语义（模式）",
    "selection": "选择语汇",
    "selection_patterns": "选择语汇（模式）",
}
WARN_LABELS = {
    "state_organs": "国家机关名称",
    "official_roles": "工作人员泛称",
    "political_narrative": "时政叙事词",
}


def normalize(text: str) -> str:
    """归一化：NFKC（全角→半角）+ 去掉空白与间隔号。

    否则 `特 朗 普` / `特·朗普` / 全角字符的绕过成本为零，闸门形同虚设。
    **不做简繁折叠**——那需要 opencc 依赖；简繁与中英变体由词表逐一收录，保持零依赖。
    """
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"[\s\u00b7\u30fb\uff0e\uff65]+", "", text)


def load_blocklist(base_path: Path = BASE_BLOCKLIST, names_path: Path = LOCAL_NAMES):
    """返回 (blocklist, warnings)。姓名表缺失时退化并告警（告警不透露缺哪个人名）。"""
    warnings: list[str] = []
    bl = json.loads(base_path.read_text(encoding="utf-8"))

    names: list[str] = []
    if names_path.exists():
        try:
            names = [str(n) for n in json.loads(names_path.read_text(encoding="utf-8")).get("names", [])]
            names = [n for n in names if n and not n.startswith("<")]
        except (json.JSONDecodeError, OSError) as exc:
            warnings.append(f"姓名表解析失败（{exc.__class__.__name__}），本次退化为纯模式匹配")
    if not names:
        warnings.append(
            "未加载到政要姓名表（b1_names 为空）——本次仅靠「国别+头衔」模式拦截，"
            "**单独出现的姓名抓不到**。补表见 tools/compliance_blocklist.example.json"
        )
    bl.setdefault("block", {})["b1_names"] = names
    return bl, warnings


def _compile(entries: list[str]) -> list[re.Pattern]:
    return [re.compile(normalize(str(e))) for e in entries if str(e).strip()]


def _section(bl: dict, key: str, sub: str) -> list[str]:
    return list(bl.get(key, {}).get(sub, []) or [])


def scan(text: str, bl: dict) -> tuple[list[tuple], list[tuple]]:
    """返回 (blocks, warns)，元素为 (行号, 类别, 命中内容, 该行原文)。

    逐行归一化后再匹配，以保留行号可读性。代价：跨行断开的词抓不到（极少见，接受）。
    """
    block_cfg = bl.get("block", {})
    warn_cfg = bl.get("warn", {})

    literal = [(k, _compile(block_cfg.get(k, []))) for k in
               ("b1_names", "b2_country_titles", "operations", "selection")]
    patterns = [(k, _compile(block_cfg.get(k, []))) for k in
                ("b3_patterns", "operations_patterns", "selection_patterns")]
    warn_lit = [(k, _compile(warn_cfg.get(k, []))) for k in
                ("state_organs", "official_roles", "political_narrative")]

    blocks: list[tuple] = []
    warns: list[tuple] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        norm = normalize(raw)
        if not norm:
            continue
        seen: set[tuple[int, int]] = set()   # 同跨度去重

        def _emit(bucket: list, cat: str, m: re.Match) -> None:
            span = (m.start(), m.end())
            if span in seen:
                return          # B2 短语表与 B3 模式会命中同一跨度，只报一次
            seen.add(span)
            bucket.append((lineno, cat, m.group(0), raw.strip()))

        for cat, pats in literal:
            for pat in pats:
                for m in pat.finditer(norm):
                    _emit(blocks, cat, m)
        for cat, pats in patterns:
            for pat in pats:
                for m in pat.finditer(norm):
                    _emit(blocks, cat, m)
        for cat, pats in warn_lit:
            for pat in pats:
                for m in pat.finditer(norm):
                    _emit(warns, cat, m)
    return blocks, warns


# ---------------------------------------------------------------------------
# 内部块剥离（防线 1）：让模型物理上拿不到内部判断，而不是靠指令抑制
# ---------------------------------------------------------------------------
_STRUCT = re.compile(r"^(?:#{1,6}\s|\*\*[^*]{1,12}\*\*\s*[:：]|---\s*$)")


def strip_internal(text: str) -> tuple[str, int]:
    """剥离 `<!-- INTERNAL -->…<!-- /INTERNAL -->` 与 `**内部判断**：` 起至下一结构标记。"""
    out: list[str] = []
    lines = text.splitlines()
    i, removed, in_internal = 0, 0, False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == INTERNAL_OPEN:
            in_internal = True
            i += 1
            removed += 1
            continue
        if stripped == INTERNAL_CLOSE:
            in_internal = False
            i += 1
            removed += 1
            continue
        if in_internal:
            removed += 1
            i += 1
            continue

        if stripped.startswith(JUDGE_MARK):
            # 从本行起，删到下一个结构标记（标题 / 另一块标记 / 分隔线）为止
            removed += 1
            i += 1
            while i < len(lines) and not _STRUCT.match(lines[i].strip()):
                removed += 1
                i += 1
            continue

        out.append(line)
        i += 1

    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), removed


def log_hits(path: str, hits: list[tuple]) -> None:
    if not hits:
        return
    HIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = HIT_LOG_DIR / f"compliance-hits-{datetime.now():%Y-%m}.log"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log.open("a", encoding="utf-8") as fh:
        for lineno, cat, matched, _ in hits:
            fh.write(f"{stamp}\t{path}\tL{lineno}\t{cat}\t{matched}\n")


# ---------------------------------------------------------------------------
# 自检：既要证明该抓的抓得到，也要证明不该抓的没被抓到
# **源码里不得出现任何政要姓名** —— B1 只测机制，姓名运行时从词表读取
# ---------------------------------------------------------------------------
_SELF_CASES: list[tuple[str, str, int]] = [
    # (用例名, 文本, 期望 B 类命中条数)
    ("B2 国别+头衔短语", "美国总统今日就关税发表讲话。", 1),
    ("B3 国别+头衔共现", "德国总理在柏林会见产业界代表。", 1),
    ("B3 抓表外新面孔", "韩国总统办公室否认了该报道。", 1),
    ("单独特朗普式绕写·归一化", "美 国 总 统 表 示 关 税 将 调 整。", 1),
    ("操作语义·观察区间", "我们把分批观察区间设在 13.5 至 15 美元。", 1),
    ("操作语义·价格区间组合", "价格区间定在 13.5 至 15 美元。", 1),
    ("操作语义·安全边际", "若续跌破 12 美元，安全边际还会更厚。", 2),
    ("操作语义·买卖动词", "该标的是不错的买点，建议买入。", 2),
    ("操作语义·目标价换算", "目标价 19.6 美元，较现价约 +42%。", 2),
    ("操作语义·个股星级", "维持 ★★★★ 评级。", 1),
    ("选择语汇", "云南锗业是国内磷化铟的纯正标的。", 1),
    ("选择语汇·唯一组合", "它是本周唯一价格与基本面共振的标的。", 1),
    ("条件式触发线", "若续跌破 12 美元，安全边际还会更厚。", 2),
    ("加码+交易动作", "若续跌破 $15 则加码观察该标的。", 2),
    # --- 以下必须 0 命中（误报是杀死闸门的元凶）---
    ("裸「加码」政策动作不拦", "中国已先行加码反制：收紧钇出口，10 家实体被管制。", 0),
    ("第三方目标价区间不拦", "卖方共识给出的目标价区间是 19.83 至 25.79 美元。", 0),
    ("裸价格穿越陈述不拦", "股价本周跌穿 15 美元观察线，收于 13.84 美元。", 0),
    ("裸头衔不拦·公司董事长", "TSMC主席魏哲家在会上表示 AI 需求强劲。", 0),
    ("裸头衔不拦·董事会", "董事会主席主持了本次会议。", 0),
    ("瓶颈分级不拦", "InP/EML 维持 S 级瓶颈，钨 S 级强化。", 0),
    ("估值数据不拦", "该股 PE(TTM) 304 倍、市值 2284.6 亿元。", 0),
    ("政策事实不拦", "美方限制中国大容量电力设备，出口管制收紧。", 0),
    ("业务构成事实不拦", "磷化铟业务占营收 62%，全球市占 80%。", 0),
    ("唯一供应商不拦", "该公司是台积电的唯一供应商。", 0),
]


def self_test() -> int:
    bl, warns = load_blocklist()
    failed = 0

    print("=== 自洽自检：规则点名的类别是否都在词表里 ===")
    block_cfg = bl.get("block", {})
    for key in bl.get("required_categories", []):
        top, _, sub = key.partition(".")
        present = isinstance(bl.get(top, {}).get(sub), list)
        # b1_names 允许在仓库基础表里为空（真实姓名从 gitignored 的 local/ 合入）
        non_empty = bool(bl.get(top, {}).get(sub)) or sub == "b1_names"
        ok = present and non_empty
        failed += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} {key}"
              f"{'（基础表为空属正常，运行时从 local/ 合入）' if sub == 'b1_names' else ''}")

    print("\n=== B1 姓名表机制（不依赖表内容） ===")
    if bl["block"]["b1_names"]:
        probe = bl["block"]["b1_names"][0]
        hits, _ = scan(f"据外媒报道，{probe}在会议上发表了讲话。", bl)
        ok = any(h[1] == "b1_names" for h in hits)
        failed += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} 表内条目可命中（{len(bl['block']['b1_names'])} 条，姓名不在此处回显）")
    else:
        ok = any("姓名表" in w for w in warns)
        failed += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} 表缺失时正确告警退化（不硬失败）")

    print("\n=== 阻断用例 ===")
    for name, text, expect in _SELF_CASES:
        got = len(scan(text, bl)[0])
        ok = got == expect
        failed += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} {name}：期望 {expect} 条，实得 {got} 条")
        if not ok:
            for h in scan(text, bl)[0]:
                print(f"        ↳ L{h[0]} [{h[1]}] 「{h[2]}」")

    print("\n=== 内部块剥离 ===")
    src = (
        "# 标题\n\n"
        "### 某标的\n\n"
        f"{FACT_MARK}：收于 13.84 美元、市值 3.99B。\n\n"
        f"{JUDGE_MARK}：\n- 分批观察区间 13.5 至 15 美元\n- ★★★★ 维持\n\n"
        "### 另一标的\n\n"
        f"{FACT_MARK}：周涨 5.7%。\n"
    )
    stripped, removed = strip_internal(src)
    ok = "观察区间" not in stripped and "收于 13.84" in stripped and "周涨 5.7%" in stripped
    failed += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} 剥离内部判断、保留事实（删 {removed} 行）")

    src2 = f"{INTERNAL_OPEN}\n## 行动建议\n买入并持有\n{INTERNAL_CLOSE}\n## 事实段\n安全边际\n"
    stripped2, _ = strip_internal(src2)
    ok2 = "行动建议" not in stripped2 and "事实段" in stripped2
    failed += 0 if ok2 else 1
    print(f"  {'✅' if ok2 else '❌'} 剥离 INTERNAL 整块（保留块外内容）")

    print(f"\n自检：{'全部通过' if not failed else f'{failed} 个用例失败'}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="公众号发布合规闸门（纯文本，无网络）")
    ap.add_argument("files", nargs="*", help="待校验的 Markdown 文件")
    ap.add_argument("--self-test", action="store_true", help="运行内嵌自检用例")
    ap.add_argument("--strip", action="store_true", help="剥离内部块，结果写 stdout（诊断走 stderr）")
    ap.add_argument("--warn-only", action="store_true", help="只告警不阻断（日报侧用），恒返回 0")
    ap.add_argument("--list", action="store_true", help="只读诊断：打印词表摘要")
    ap.add_argument("--show-names", action="store_true", help="配合 --list：连姓名表内容一起打印")
    ap.add_argument("--json", action="store_true", help="机读输出")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    bl, load_warns = load_blocklist()

    if args.list:
        print(f"词表：{BASE_BLOCKLIST}")
        print(f"姓名表：{LOCAL_NAMES}（{'已加载' if bl['block']['b1_names'] else '缺失'}）")
        print("\nlegal_basis:", bl.get("legal_basis", "")[:80], "…")
        for group, labels in (("block", BLOCK_LABELS), ("warn", WARN_LABELS)):
            mode = "硬阻断" if group == "block" else "仅告警"
            print(f"\n[{mode}]")
            for key, label in labels.items():
                entries = bl.get(group, {}).get(key, [])
                if key == "b1_names" and not args.show_names:
                    print(f"  {key:22s} {len(entries):3d} 条  {label}（内容不回显，需 --show-names）")
                else:
                    print(f"  {key:22s} {len(entries):3d} 条  {label}")
                    for e in entries:
                        print(f"      - {e}")
        return 0

    if not args.files:
        ap.print_help(sys.stderr)
        return 2

    for w in load_warns:
        print(f"⚠️  {w}", file=sys.stderr)

    rc = 0
    for path in args.files:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"✗ {path}: 无法读取（{exc}）", file=sys.stderr)
            rc = 2
            continue

        if args.strip:
            out, removed = strip_internal(text)
            print(f"[strip] {path}: 剥离 {removed} 行内部内容", file=sys.stderr)
            sys.stdout.write(out)
            continue

        blocks, warns = scan(text, bl)
        log_hits(path, blocks)

        if args.json:
            print(json.dumps({
                "file": path,
                "blocked": [{"line": l, "category": c, "matched": m} for l, c, m, _ in blocks],
                "warned": [{"line": l, "category": c, "matched": m} for l, c, m, _ in warns],
            }, ensure_ascii=False, indent=2))
        else:
            for l, c, m, raw in warns:
                print(f"  ⚠️  L{l} [{WARN_LABELS.get(c, c)}] 「{m}」 → …{raw[:70]}…")
            if warns:
                print(f"  ⚠️  {len(warns)} 处告警。判据：去掉机关名，论证还成立吗？成立=描述政策，可留；不成立=借用权威，删。")

            if blocks:
                print(f"✗ {path}: {len(blocks)} 处**命中硬阻断**，不得发布")
                for l, c, m, raw in blocks:
                    print(f"    L{l} [{BLOCK_LABELS.get(c, c)}] 「{m}」 → …{raw[:70]}…")
                rc = 1
            else:
                print(f"✓ {path}: 无硬阻断命中")

    if args.warn_only:
        if rc == 1:
            print("（--warn-only：命中的硬阻断已降级为告警，不阻断）", file=sys.stderr)
        return 0
    return rc


if __name__ == "__main__":
    sys.exit(main())
