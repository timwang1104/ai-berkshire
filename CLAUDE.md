# AI Berkshire — 项目指令

## 项目概述

基于 Claude Code 的价值投资研究 Skill 合集。四大师框架：巴菲特、芒格、段永平、李录。
GitHub: xbtlin/ai-berkshire

## 项目结构

```
skills/          — 投研 Skill 定义（.md），复制到 ~/.claude/commands/ 使用
tools/           — 辅助工具（financial_rigor.py 精确计算）
reports/         — 投资研究报告输出
assets/          — 图片等静态资源
```

## 报告目录结构

所有报告按**分类目录**存放：

```
reports/
├── 公司研究/          # 所有公司级深度研究（含研究报告、财报、管理层、论文等）
│   └── {公司名}/
│       ├── {公司名}-research-{日期}.md            ← investment-research
│       ├── {公司名}-checklist-{日期}.md            ← investment-checklist
│       ├── {公司名}-earnings-{期间}.md              ← earnings-review / earnings-team
│       ├── {公司名}-management-{日期}.md            ← management-deep-dive
│       ├── {公司名}-private-{日期}.md               ← private-company-research
│       ├── {公司名}-thesis.md                      ← thesis-tracker
│       ├── {公司名}-thesis-{日期}.md                ← thesis-drift 快照
│       ├── {公司名}-team-{日期}.md                  ← investment-team（含多文件）
│       ├── {公司名}-公众号-{日期}.md                ← wechat-article
│       └── 《看懂{公司名}》/                        ← deep-company-series
│
├── 行业分析/          # 行业级全景、漏斗筛选、技术综述
│   ├── {行业名}-industry-{日期}.md                 ← industry-research
│   ├── {行业名}-funnel-{日期}.md                   ← industry-funnel
│   ├── 大模型技术/                                  ← 技术科普综述
│   ├── 白酒周期/
│   └── AI产业/
│
├── 跨公司对比/        # 跨公司对比报告（XXvsYY、多公司筛选等）
├── 投资理念/          # 投资方法论、大师思想（巴菲特镜子测试、段永平vs李录等）
├── 阅读扩展/          # 播客笔记、读书笔记、政策解读
├── 组合管理/          # 组合管理
│   └── portfolio-latest.md                         ← portfolio-review
├── 舆情扫描/          # 新闻事件归因
│   └── {公司名}/
│       └── {公司名}-news-{日期}.md                 ← news-pulse
├── 供应链瓶颈/        # 瓶颈地图（原 bottleneck-map，保留 daily/ 子目录）
├── 筛选池/            # 晨星等数据驱动的筛选结果
│   ├── 晨星深度低估/
│   └── 晨星估值筛选/
├── 召回池/            # 各市场/主题的候选池
└── 宏观分析/          # 宏观利率、房产研究
```

## 报告命名规范

| Skill | 文件命名格式 | 示例 |
|------|---------|------|
| /investment-team | `公司研究/{公司名}/` 目录内含4个视角+最终报告 | `公司研究/拼多多/最终报告.md` |
| /investment-research | `公司研究/{公司名}/{公司名}-research-{YYYYMMDD}.md` | `公司研究/腾讯/腾讯-research-20260408.md` |
| /investment-checklist | `公司研究/{公司名}/{公司名}-checklist-{YYYYMMDD}.md` | `公司研究/腾讯/腾讯-checklist-20260408.md` |
| /industry-research | `行业分析/{行业名}-industry-{YYYYMMDD}.md` | `行业分析/核电-industry-20260409.md` |
| /industry-funnel | `行业分析/{行业名}-funnel-{YYYYMMDD}.md` | `行业分析/AI算力-funnel-20260509.md` |
| /private-company-research | `公司研究/{公司名}/{公司名}-private-{YYYYMMDD}.md` | `公司研究/字节跳动/字节跳动-private-20260408.md` |
| /earnings-review | `公司研究/{公司名}/{公司名}-earnings-{期间}.md` | `公司研究/腾讯/腾讯-earnings-2025Q4.md` |
| /earnings-team | `公司研究/{公司名}/` 目录内含4个大师视角+研究底稿+公众号文章+读者评审 | `公司研究/腾讯/腾讯-earnings-2025Q4.md`（公众号定稿） |
| /thesis-tracker | `公司研究/{公司名}/{公司名}-thesis.md`（长期维护） | `公司研究/腾讯/腾讯-thesis.md` |
| /thesis-drift | `公司研究/{公司名}/{公司名}-thesis-{YYYYMMDD}.md`（快照） | `公司研究/腾讯/腾讯-thesis-20260601.md` |
| /portfolio-review | `组合管理/portfolio-latest.md`（持续更新） | `组合管理/portfolio-latest.md` |
| /management-deep-dive | `公司研究/{公司名}/{公司名}-management-{YYYYMMDD}.md` | `公司研究/腾讯/腾讯-management-20260409.md` |
| /news-pulse | `舆情扫描/{公司名}/{公司名}-news-{YYYYMMDD}.md` | `舆情扫描/腾讯/腾讯-news-20260409.md` |
| /deep-company-series | `公司研究/{公司名}/《看懂{公司名}》/` | `公司研究/腾讯/《看懂腾讯》/` |
| /bottleneck-hunter | `供应链瓶颈/` 目录下 | `供应链瓶颈/master-map.md` |
| /wechat-article（公司分析类） | `公司研究/{公司名}/{公司名}-公众号-{YYYYMMDD}.md` | `公司研究/腾讯/腾讯-公众号-20260616.md` |
| /wechat-article（行业分析类） | `行业分析/公众号-{行业关键词}-{YYYYMMDD}.md` | `行业分析/公众号-AI五层蛋糕-20260605.md` |
| /wechat-article（投资理念类） | `投资理念/公众号-{主题关键词}-{YYYYMMDD}.md` | `投资理念/公众号-凯利公式-20260616.md` |
| /wechat-article（阅读扩展类） | `阅读扩展/公众号-{主题关键词}-{YYYYMMDD}.md` | `阅读扩展/公众号-播客笔记-20260616.md` |

## /investment-team 文件结构

```
reports/公司研究/{公司名}/
├── README.md                         — 研究框架概览+核心结论
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md                       — Team Lead 综合报告
```

## 投研分析核心原则（最高优先级）

- **客观、客观、客观**——所有投研分析必须基于事实和数据，严禁主观臆断
- 严格区分"事实"与"观点"：事实用数据支撑，观点必须明确标注为"观点"或"推测"
- **不预设立场**：不预设看多或看空，先摆数据、再推逻辑、最后得结论。结论必须从数据中自然推出
- 禁止使用"我认为"、"我觉得"、"显然"等主观表述，改用"数据显示"、"证据表明"、"根据XX来源"
- **呈现正反两面**：每个核心判断都必须附带反面论据（"但另一方面..."），让读者自己权衡
- 对不确定的事情诚实说"不确定"或"数据不足"，不要用推测填充确定性
- 所有skill（investment-team、investment-research、earnings-review等）在执行时都必须遵守以上原则

## 报告语言与风格

- 所有报告使用**中文**
- 风格：直接、犀利、不说废话
- 数据必须标注来源，关键数据至少2个来源交叉验证
- 估计值必须注明"估计"
- 评分使用★符号（★1-5），不含半星
- 穿插巴菲特/芒格/段永平/李录的语录点评

## GitHub 操作

- 本地克隆路径：`~/ai-berkshire/`
- 远程仓库：`https://github.com/xbtlin/ai-berkshire.git`
- 推送前先 `git pull --rebase origin main`（远程经常有新提交）
- commit message 用中文，描述清楚改了什么
- 不要推送中间过程文件（如 data_collection.md），只推最终报告

## 常用命令

```bash
# 推送报告到GitHub
cd ~/ai-berkshire
git add reports/xxx.md
git commit -m "添加xxx报告"
git pull --rebase origin main
git push origin main
```

## 注意事项

- 市值必须手算校验：股价 × 总股本，与报告市值对比
- 货币单位要明确（港币/人民币/美元），防止混淆
- PE/ROE等指标用 tools/financial_rigor.py 精确计算
- 报告写完后主动询问是否推送到GitHub
