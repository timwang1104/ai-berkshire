# AI Berkshire Spec

> 项目级编码规范和开发指南。这个项目是一个基于 Claude Code 的价值投资研究 Skill 合集。

## 目录结构

```
.trellis/spec/
├── index.md               ← 你在这里
├── skills/                — Skill 定义（Markdown 格式）规范和模式
├── tools/                 — Python 工具开发规范和模式
├── reports/               — 研究报告命名、结构、质量标准
└── guides/                — 通用思考框架（在实现前帮助发现遗漏）
```

## 各 Spec 速览

| Spec | 适用对象 | 核心内容 |
|------|----------|----------|
| [Skills](./skills/index.md) | `skills/*.md` | Skill Markdown 格式、frontmatter、变量、多 Agent 范式、流程图 |
| [Tools](./tools/index.md) | `tools/*.py` | Python CLI 工具结构、decimal 精确计算、错误处理、数据源规范 |
| [Reports](./reports/index.md) | `reports/*.md` | 报告命名规范、目录结构、质量审计、GitHub 发布流程 |
| Guides | 所有开发 | 代码复用思考、跨层数据流思考 |

## 核心原则

1. **源决定规则**：每条规范必须有项目中的实际文件支持。不要写通用框架建议。
2. **客观、客观、客观**：所有投研分析必须基于事实和数据。严禁主观臆断。
3. **Skills 是 canonical source**：`skills/*.md` 是所有工作流的源头。`codex-skills/` 由脚本生成，禁止手动编辑。
4. **数据来源必须交叉验证**：关键财务数据至少 2 个独立来源，偏差 >1% 须标记。

## 验证命令

```bash
# 检查是否有遗留的模板占位符
grep -R "To be filled\|TODO: fill\|placeholder\|To fill" .trellis/spec/

# 验证 Codex 同步是否最新
python3 scripts/sync-codex-skills.py --check
```
