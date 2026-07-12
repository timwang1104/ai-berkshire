# Skills — Skill 定义规范

> 编写和修改 `skills/*.md` 文件的规范指南。这些 Markdown 文件是 Claude Code / Codex 的 command / skill 定义。

---

## 文件结构

所有 Skill 文件位于 `skills/*.md`，是项目的 **canonical source**。`codex-skills/` 由 `scripts/sync-codex-skills.py` 从 `skills/*.md` 生成，禁止手动编辑。

### 标准 Markdown 格式

每个 Skill 文件包含：

1. **一级标题**：Skill 名称 + 功能描述，例如 `# 投资研究：巴菲特-芒格-段永平-李录 四大师综合分析框架`
2. **参数说明**（可选）：对 `$ARGUMENTS` 的说明
3. **引用语句**（可选）：大师语录或信条
4. **执行流程**：分步骤的详细执行流程，使用二级标题 `##`
5. **检查清单**：`- [ ]` 格式的 checklist

### Frontmatter（部分 Skill 使用）

少数 Skill 使用 YAML frontmatter：

```markdown
---
name: <skill-name>
description: <简短描述>
---
```

当 Skill 需要在 Codex 环境中作为独立包使用时，frontmatter 会被 `sync-codex-skills.py` 处理成 Codex 兼容格式。

**参考文件**：`scripts/sync-codex-skills.py` lines 16-23 的 `split_frontmatter` 函数

---

## 参数约定

### `$ARGUMENTS` 变量

所有接受用户输入的 Skill 使用 `$ARGUMENTS` 作为参数占位符。支持格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| 单参数 | `$ARGUMENTS` | 直接替换为用户输入 |
| 多参数 | `$ARGUMENTS` | 在文档中解释输入格式，如 `公司名 季度` |

**示例**（`skills/earnings-review.md` line 5）：
```markdown
**支持输入格式**：`公司名 季度`，例如：`腾讯 2025Q4`、`PDD 2025年报`、`美团 最新`
```

### 嵌入 URL（仅 `skills/wechat-article.md`）

微信公众号文章 Skill 的 `$ARGUMENTS` 可以是 URL。在 Skill 主体中通过 `$ARGUMENTS` 引用。

---

## 大师引语使用规范

多个 Skill 开头引用大师语录，引用时应：

1. 使用 `<blockquote>` 格式
2. 注明出处人
3. 引语应与 Skill 主题直接相关

**示例**（`skills/earnings-review.md` lines 8-11）：
```markdown
> "我从不看卖方研报，只读原始财报。" —— 李录
>
> "我每天读500页。知识就是这样积累的，像复利一样。" —— 巴菲特
```

---

## 执行流程结构

Skill 主体使用层级化 Markdown 标题组织流程。标准模式：

### 前置步骤

在正式研究前执行的检查/评估步骤。例如信息丰富度评级、偏见自查清单、资料可得性评级。

**示例**（`skills/investment-research.md` lines 11-33）：
- `### 前置步骤：AI研究偏见自觉（必须执行）`
- 包含信息丰富度评级表（ABC三级）
- 偏见自查清单（`- [ ]` 格式）

### 执行步骤

使用编号或功能标题组织。深度 Skill 使用 `###` 三级标题：

```markdown
### 第一步：数据收集
### 第二步：财务分析
### 第三步：管理层评估
```

### 检查清单

每个步骤结尾使用 `- [ ]` 格式的 checklist：

```markdown
- [ ] 任务 1
- [ ] 任务 2
```

---

## 信息评级表格式

多个 Skill 使用信息评级表来评估可研究性。标准格式（三级分类 + 应对策略表）：

```markdown
| 等级 | 特征 | AI研究陷阱 | 应对策略 |
|------|------|-----------|---------|
| A级 | ... | ... | ... |
| B级 | ... | ... | ... |
| C级 | ... | ... | ... |
```

**参考文件**：
- `skills/investment-research.md` lines 14-18（信息丰富度评级）
- `skills/earnings-review.md` lines 24-29（资料可得性评级）

---

## 多 Agent 并⾏范式

深度研究 Skill 使用 Task 工具启动多个后台 Agent 并行执行。标准模式：

```markdown
使用 Task 工具启动多个后台 Agent **并行**获取以下材料：
1. **源A**：从 X 获取
2. **源B**：从 Y 获取
3. **源C**：从 Z 获取
```

**参考文件**：
- `skills/earnings-review.md` lines 34-38
- `skills/investment-team.md`（四大师并行分析框架）

### 四大师并行流程（`skills/investment-team.md`）

投资团队 Skill 使用 4 个独立 Agent 并行分析：
1. 段永平视角 — 商业模式分析
2. 巴菲特视角 — 财务估值分析  
3. 芒格视角 — 行业竞争分析
4. 李录视角 — 风险管理层评估

最终由 Team Lead Agent 综合成一份最终报告。

**目录结构产出**：
```
reports/{公司名}/
├── README.md
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md
```

---

## 数据源规范

所有需要获取财务数据的 Skill，必须引用 `skills/financial-data.md` 的数据源规范。不能硬编码来源。

```markdown
> **数据源规范**：参见 `skills/financial-data.md`。所有财务数据必须来自两个独立来源。
> - 美股：macrotrends（主）+ stockanalysis（副）
> - 港股：aastocks（主）+ macrotrends ADR（副）
> - A股：东方财富（主）+ 巨潮资讯（副）
```

**参考文件**：`skills/investment-research.md` lines 37-40

---

## 文件命名规范

每个 Skill 使用小写 + 连字符命名，对应一个独立的功能领域。

| Skill | 文件名 | 核心功能 |
|-------|--------|----------|
| 投资研究 | `investment-research.md` | 四大师综合分析框架 |
| 财报精读 | `earnings-review.md` | 一手资料财报解读 |
| 投资团队 | `investment-team.md` | 四大师并行分析 |
| 财务数据 | `financial-data.md` | 数据源规范 |
| 选中检查 | `investment-checklist.md` | 买入前检查 |
| 组合管理 | `portfolio-review.md` | 投资组合跟踪 |
| 管理层研究 | `management-deep-dive.md` | 管理层纵深研究 |
| 行业研究 | `industry-research.md` | 产业链全景分析 |
| 行业漏斗 | `industry-funnel.md` | 全市场到3家精选 |
| 公众号 | `wechat-article.md` | 公众号文章发布 |
| 质量控制 | `quality-screen.md` | 7条指标快速排除 |
| 财报团队 | `earnings-team.md` | 四大师并行财报解读 |
| 论文追踪 | `thesis-tracker.md` | 买入后纪律系统 |
| 论文漂移 | `thesis-drift.md` | 事实变化与措辞变化 |
| 新闻脉搏 | `news-pulse.md` | 股价异动快速归因 |
| 深度公司 | `deep-company-series.md` | 3-8篇长文拆公司 |
| 瓶颈猎手 | `bottleneck-hunter.md` | 产业链瓶颈套利 |
| 段永平问答 | `dyp-ask.md` | 以他的方式思考 |
| 未上市公司 | `private-company-research.md` | 未上市公司研究 |

---

## 修改 Skill 后的同步流程

每次修改 `skills/*.md` 后必须运行：

```bash
# 同步到 codex-skills/（强制性）
python3 scripts/sync-codex-skills.py

# 验证同步是否最新（只比对不写文件）
python3 scripts/sync-codex-skills.py --check

# 如有需要，同步 Codex slash prompts
python3 scripts/sync-codex-prompts.py
python3 scripts/sync-codex-prompts.py --check
```

**参考文件**：
- `AGENTS.md` lines 26-36（兼容性规则）
- `scripts/sync-codex-skills.py`（生成逻辑：解析 frontmatter + Markdown → Codex YAML）

---

## 反模式

### ❌ 在 Skill 中硬编码数据源
```markdown
# BAD
数据来自东方财富和巨潮资讯

# GOOD
> **数据源规范**：参见 `skills/financial-data.md`。
```

### ❌ 在 Skill 中包含废话或冗余说明
Skill 是执行指令，不是营销文案。Keep it concise and actionable.

### ❌ 修改 skill 后忘记同步 Codex 格式
同步失败会导致 Codex 用户使用到过时的 skill 版本。

### ❌ 在同一个 Markdown 文件中混合多个独立的 research flow
一个 Skill 文件应该只定义一个工作流。如果工作流有子流程，用多 Agent 模式实现。
