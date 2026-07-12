# Cross-Layer Thinking Guide

> **Purpose**: Think through data flow across project layers before implementing — especially between skills, tools, reports, and synchronization.

---

## The Problem

**Most bugs happen at layer boundaries**, not within layers.

In this project, the layers are:

| Layer | What it is | Location |
|-------|-----------|----------|
| **Skills** | Markdown workflow definitions | `skills/*.md` |
| **Tools** | Python computation/validation scripts | `tools/*.py` |
| **Reports** | Generated research output documents | `reports/` |
| **Data** | External data caches (JSON, CSV) | `data/` |
| **Codex Sync** | Generated Codex-compatible skill packages | `codex-skills/`, `codex-prompts/` |

Common cross-layer bugs:

- Skill says "cross-validate X" but the tool expects a different JSON format
- Report uses a calculation that doesn't match the tool's verified output
- Skills are updated but Codex sync is not run
- Data source specified in a skill doesn't match what the tool script actually reads

---

## Before Implementing Cross-Layer Features

### Step 1: Map the Data Flow

For each change, trace how data moves across layers:

```
Skill prompt → Tool CLI args → Tool stdout → Report text
                    ↑
               Data source (API / file)
```

For each arrow, ask:

- What format is the data in?
- What could go wrong?
- Who is responsible for validation?

### Step 2: Identify Boundaries

| Boundary | Common Issues |
|----------|---------------|
| Skill → Tool | Tool CLI args changed but Skill prompts still call old format |
| Tool → Report | Tool outputs raw numbers, report writer misinterprets units |
| Skill → Codex Sync | Skills updated but `sync-codex-skills.py` not run |
| Data → Tool | Data source URL/API changed, tool still reads old path |
| Skill ↔ Skill | Data source spec duplicated across multiple skills |

### Step 3: Define Contracts

For each boundary:

- Skill → Tool: What CLI arguments does the tool expect? What format does it output?
- Tool → Report: What currency/units are used? Any caveats?
- Skill → Codex: `scripts/sync-codex-skills.py` parses frontmatter — what if a new skill has no frontmatter?

---

## Common Cross-Layer Mistakes

### Mistake 1: Tool CLI Interface Changes Without Updating Skills

**Bad**: `financial_rigor.py verify-valuation` changes flag names, but `skills/investment-research.md` still tells the LLM to use the old flags.

**Good**: Before changing a tool's CLI interface, search all `skills/*.md` for references to that tool and update them in the same PR.

**Reference**: `tools/financial_rigor.py` — before renaming any `add_argument`, `grep -r "financial_rigor" skills/`.

### Mistake 2: Skills Duplicate Computation Logic

**Bad**: A skill says "calculate PE = price / eps". A tool also does the same calculation. They diverge when one uses float and the other uses Decimal.

**Good**: Computation lives in the tool layer (`tools/financial_rigor.py`), Skills just say "use the tool".

### Mistake 3: Skills Updated, Codex Not Synced

**Bad**: Modified `skills/investment-research.md`. Codex users continue using the old version.

**Good**: Always run `python3 scripts/sync-codex-skills.py` after any `skills/*.md` change.

### Mistake 4: Currency/Unit Confusion

**Bad**: A report says "市值 4.65 万亿" without specifying currency. The tool outputs HKD but the report reader assumes CNY.

**Good**: Always specify currency in tool output (`--currency HKD`) and report text. Use the `unit` parameter consistently.

**Reference**: `tools/financial_rigor.py` — `verify_market_cap(currency="HKD")`.

---

## Checklist for Cross-Layer Changes

Before modifying any layer:

- [ ] Identify all layers this change touches
- [ ] Trace data flow from input to output
- [ ] Define format/contract at each boundary
- [ ] Update all affected layers in the same batch

After implementation:

- [ ] Ran `python3 scripts/sync-codex-skills.py` (if skills changed)
- [ ] Ran `python3 scripts/sync-codex-skills.py --check` to verify
- [ ] Checked that tool output format matches what skills expect
- [ ] Verified currency/unit consistency across all layers
- [ ] Checked for duplicate data source definitions across skills
- [ ] Tested the full skill → tool → report flow end-to-end

---

## Data Source Ref: Changing a Financial Data Source

When a financial data source changes (e.g., a website restructures its URLs):

1. Update the tool that reads that source (`tools/*.py`)
2. Update `skills/financial-data.md` if the source name or URL changed
3. Search all `skills/*.md` for mentions of the old source
4. Update any existing reports that reference the old source (only if explicitly asked)
5. Run `python3 scripts/sync-codex-skills.py` to sync Codex packages

**Real-world pattern**: Multiple skills reference "macrotrends" as the primary US stock data source. If macrotrends changes its URL scheme, all skills that mention it need updating — not just a single function.

---

## Skills → Reports Boundary

The skill defines the report's structure. When changing a report structure in a skill:

1. Update the skill's report template/instructions (`skills/*.md`)
2. Update `CLAUDE.md` if the naming convention changes
3. Update the Reports spec (`.trellis/spec/reports/index.md`) if conventions change
4. Run Codex sync

**Example**: When `earnings-team` added "读者评审" to the report directory structure, the Reports spec needed updating too.

---

## When to Create Flow Documentation

Create detailed flow docs when:

- Change touches 3+ layers (e.g., new Skill → new Tool → new Report format)
- A new data source is added
- The same concept has caused bugs before
