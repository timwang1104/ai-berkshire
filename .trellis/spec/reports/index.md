# Reports — 研究报告规范

> 编写 `reports/*.md` 研究报吿的规范和标准。所有报告必须是客观、数据驱动的投资研究文档。

---

## 目录结构

所有报告按**公司名**建文件夹：

```
reports/
├── AI产业研究/              — AI产业链全景研究（置顶）
├── 腾讯/                    — 腾讯所有研究报告
├── 拼多多/                  — 拼多多所有研究报告
├── 泡泡玛特/                — 泡泡玛特所有研究报告
├── 茅台/                    — 茅台所有研究报告
├── 快手/                    — 快手所有研究报告
├── 核电-industry-20260409.md  — 行业报告放根目录
├── AI算力-funnel-20260509.md  — 漏斗筛选报告放根目录
└── portfolio-latest.md       — 组合报告放根目录
```

**核心原则**：
- 单一公司的所有报告放在一个文件夹内
- 行业/主题报告、漏斗筛选报告、组合报告放 `reports/` 根目录
- 多公司对比报告也放根目录

---

## 文件命名规范

### 按 Skill 类型命名

| Skill | 文件命名格式 | 示例 |
|------|---------|------|
| `investment-team` | `{公司名}/` 目录内含 4 个视角 + 最终报告 | `reports/拼多多/最终报告.md` |
| `investment-research` | `{公司名}-research-{YYYYMMDD}.md` | `reports/腾讯/腾讯-research-20260408.md` |
| `investment-checklist` | `{公司名}-checklist-{YYYYMMDD}.md` | `reports/腾讯/腾讯-checklist-20260408.md` |
| `industry-research` | `{行业名}-industry-{YYYYMMDD}.md`（根目录） | `reports/核电-industry-20260409.md` |
| `industry-funnel` | `{行业名}-funnel-{YYYYMMDD}.md`（根目录） | `reports/AI算力-funnel-20260509.md` |
| `earnings-review` | `{公司名}-earnings-{期间}.md` | `reports/腾讯/腾讯-earnings-2025Q4.md` |
| `earnings-team` | `{公司名}/` 目录内含 4 大师视角 + 定稿 | `reports/腾讯/腾讯-earnings-2025Q4.md`（定稿） |
| `thesis-tracker` | `{公司名}-thesis.md`（长期维护） | `reports/腾讯/腾讯-thesis.md` |
| `portfolio-review` | `portfolio-latest.md`（根目录） | `reports/portfolio-latest.md` |
| `management-deep-dive` | `{公司名}-management-{YYYYMMDD}.md` | `reports/腾讯/腾讯-management-20260409.md` |
| `private-company-research` | `{公司名}-private-{YYYYMMDD}.md` | `reports/字节跳动/字节跳动-private-20260408.md` |
| `news-pulse` | `{公司名}-news-{YYYYMMDD}.md` | `reports/腾讯/腾讯-news-20260501.md` |

### `investment-team` 目录产出的固定文件结构

```
reports/{公司名}/
├── README.md                         — 研究框架概览 + 核心结论
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md                       — Team Lead 综合报告
```

---

## 写作质量标准

### 核心原则（最高优先级）

1. **客观、客观、客观**——所有分析必须基于事实和数据，严禁主观臆断
2. **严格区分"事实"与"观点"**：事实用数据支撑，观点必须明确标注为"观点"或"推测"
3. **不预设立场**：不预设看多或看空，先摆数据、再推逻辑、最后得结论
4. **禁止主观表述**：不用"我认为"、"我觉得"、"显然"
5. **呈现正反两面**：每个核心判断附带反面论据（"但另一方面..."）
6. **诚实对待不确定**：数据不足时说"不确定"，不推测填充

### 数据标注

- 所有数据标注来源
- 关键数据至少 2 个来源交叉验证
- 估计值注明"估计"
- 来源格式：`**来源**：[来源名](URL)`

### 评分系统

- 使用 ★ 符号（1-5），不含半星
- 标准评分维度：护城河、管理层、财务健康、价格/安全边际

### 语言风格

- **中文写作**
- 直接、犀利、不说废话
- 穿插巴菲特/芒格/段永平/李录的语录点评（可选）

---

## 数据验证

### 写报告时必须验证

```bash
# 市值验算（股价 × 总股本 vs 报告市值）
python3 tools/financial_rigor.py verify-market-cap --price X --shares X --reported X --currency HKD

# 估值指标验算
python3 tools/financial_rigor.py verify-valuation --price X --eps X --bvps X
```

**参考文件**：`CLAUDE.md` 注意事项 section（市值必须手算校验）

### 发布前审计

报告发布前（推送 GitHub 或公众号）运行审计抽检：

```bash
# 提取 + 抽检 15% 财务数据点
python3 tools/report_audit.py extract --report reports/xxx/xxx.md --dry-run

# 完整流程：extract → 人工填充 → 准出/打回
```

**参考文件**：`CLAUDE.md`（报告发布前审计 section）

---

## 报告首部信息

每份报告首部包含：

```markdown
---
标题: {公司名} — {报告类型}
日期: {YYYY-MM-DD}
分析师: {AI 模型名}（基于 {Skill 名}）
数据截止: {YYYY-MM-DD}
---

> **免责声明**：本文仅供学习研究之用，不构成投资建议。
```

---

## Tags（标签系统）

> **注意**：Tags 系统正在设计中。当前可选地使用。

可选 Tags 放在报告文件顶部：

```markdown
tags: [腾讯, 社交流量, 护城河, 游戏, AI, 投资组合]
```

---

## 反模式

### ❌ 主观臆断
```markdown
# BAD
腾讯的护城河很深。业绩一定会增长。

# GOOD
腾讯拥有 13 亿微信 MAU（来源：2026Q1 财报）。社交网络具有天然的网络效应护城河。但另一方面，短视频平台持续侵蚀用户时长（来源：QuestMobile 2026年3月报告），这构成了护城河的潜在风险。
```

### ❌ 单一来源
```markdown
# BAD
腾讯营收 7518 亿元。（来源：某公众号）

# GOOD
腾讯营收 7518 亿元（来源：腾讯 2025年报 IR 页面）。交叉验证：Yahoo Finance 显示同年营收 7500 亿元，偏差 0.24%，在可接受范围内。
```

### ❌ 缺少日期/时间戳
所有报告必须包含生成日期和数据截止日期。

### ❌ 不遵循命名规范
```
# BAD — 不知道这是哪种 report
reports/腾讯分析.md

# GOOD — 立即知道类型和时间
reports/腾讯/腾讯-research-20260408.md
```
