# Code Reuse Thinking Guide

> **Purpose**: Stop and think before creating new code - does it already exist?

---

## The Problem

**Duplicated code is the #1 source of inconsistency bugs.**

When you copy-paste or rewrite existing logic:
- Bug fixes don't propagate
- Behavior diverges over time
- Codebase becomes harder to understand

---

## Before Writing New Code

### Step 1: Search First

```bash
# Search for similar function names
grep -r "functionName" .

# Search for similar logic
grep -r "keyword" .
```

### Step 2: Ask These Questions

| Question | If Yes... |
|----------|-----------|
| Does a similar function exist? | Use or extend it |
| Is this pattern used elsewhere? | Follow the existing pattern |
| Could this be a shared utility? | Create it in the right place |
| Am I copying code from another file? | **STOP** - extract to shared |

---

## Common Duplication Patterns

### Pattern 1: Copy-Paste Functions

**Bad**: Copying a validation function to another file

**Good**: Extract to shared utilities, import where needed

### Pattern 2: Similar Components

**Bad**: Creating a new component that's 80% similar to existing

**Good**: Extend existing component with props/variants

### Pattern 3: Repeated Constants

**Bad**: Defining the same constant in multiple files

**Good**: Single source of truth, import everywhere

### Pattern 4: Repeated Payload Field Extraction

**Bad**: Multiple consumers cast the same JSON/event fields locally:

```typescript
const description = (ev as { description?: string }).description;
const context = (ev as { context?: ContextEntry[] }).context;
```

This is duplicated contract logic even when the code is only two lines. Each
consumer now has its own definition of what a valid payload means.

**Good**: Put the decoder, type guard, or projection next to the data owner:

```typescript
if (isThreadEvent(ev)) {
  renderThreadEvent(ev);
}
```

**Rule**: If the same untyped payload field is read in 2+ places, create a
shared type guard / normalizer / projection before adding a third reader.

---

## When to Abstract

**Abstract when**:
- Same code appears 3+ times
- Logic is complex enough to have bugs
- Multiple people might need this

**Don't abstract when**:
- Only used once
- Trivial one-liner
- Abstraction would be more complex than duplication

---

## After Batch Modifications

When you've made similar changes to multiple files:

1. **Review**: Did you catch all instances?
2. **Search**: Run grep to find any missed
3. **Consider**: Should this be abstracted?

### Skills 仓库中的代码复用模式

在这个项目中，"代码复用"主要体现为：

- **数据源规范复用**：多个 Skill 引用同一个 `skills/financial-data.md`，不要在每个 Skill 中重复写数据来源
- **工具调用复用**：多个 Skill 调用 `tools/financial_rigor.py` 进行市值验算，不要在 Skill 中重复写计算逻辑
- **大师引语复用**：跨 Skill 复用大师语录
- **评级表格复用**：信息丰富度评级、资料可得性评级等标准表格

**具体规则**：
- 如果两个 Skill 需要同一个数据源或同一个检查步骤，提取到 `skills/financial-data.md` 或创建一个共享的 section
- 如果两个 Tool 需要相同的计算逻辑，提取到 `tools/financial_rigor.py` 的公共函数
- 避免在多个 `skills/*.md` 中复制同一段 Markdown 表格

---

## Checklist Before Commit

- [ ] Searched for existing similar code
- [ ] No copy-pasted logic that should be shared
- [ ] Constants defined in one place
- [ ] Similar patterns follow same structure
- [ ] After modifying `skills/*.md`, ran `python3 scripts/sync-codex-skills.py --check`

---

## Gotcha: Python if/elif/else Exhaustive Check

**Problem**: Python's if/elif/else chains have no compile-time exhaustive check. When you add a new value to a `Literal` type (e.g., `Platform`), existing if/elif/else chains silently fall through to `else` with wrong defaults.

**Symptom**: New platform works partially — some methods return Claude defaults instead of platform-specific values. No error is raised.

**Example** (`cli_adapter.py`):
```python
# BAD: "gemini" falls through to else, returns "claude"
@property
def cli_name(self) -> str:
    if self.platform == "opencode":
        return "opencode"
    else:
        return "claude"  # gemini silently gets "claude"!

# GOOD: explicit branch for every platform
@property
def cli_name(self) -> str:
    if self.platform == "opencode":
        return "opencode"
    elif self.platform == "gemini":
        return "gemini"
    else:
        return "claude"
```

**Prevention**: When adding a new value to a Python `Literal` type, search for ALL if/elif/else chains that switch on that type and add explicit branches. Don't rely on `else` being correct for new values.

---

## Skill ↔ Codex 不对称问题

**问题**：`skills/*.md` 是 canonical source，`codex-skills/` 由 `scripts/sync-codex-skills.py` 生成。如果只改 `skills/` 不同步到 Codex 格式，Codex 用户使用的就是旧版本。

**预防措施**：
- 修改 `skills/*.md` 后立即运行 `python3 scripts/sync-codex-skills.py`
- 使用 `--check` 标志验证是否已同步：`python3 scripts/sync-codex-skills.py --check`
- 生成脚本 `scripts/sync-codex-skills.py` 是同步的唯一路径，不要手动拷贝 skills 到 codex-skills

**参考文件**：
- `AGENTS.md`（兼容性规则）
- `scripts/sync-codex-skills.py`（同步逻辑）
