# Tools — Python 工具开发规范

> 编写和修改 `tools/*.py` 文件的规范。这些 Python 脚本被 Claude Code Skills 自动调用以执行精确计算和数据验证。

---

## 文件结构

所有工具位于 `tools/*.py`，优先使用 Python 3 标准库（零外部依赖原则）。

> ⚠️ **例外**：`xueqiu_scraper.py` 由于需要浏览器自动化和 Cookie 管理，使用 `playwright` 外部依赖。
> 详情见 `CLAUDE.md` 虚拟环境 section。所有其他工具必须保持零外部依赖。

### 标准执行入口

```python
#!/usr/bin/env python3
"""模块级 docstring — 功能描述 + 用法示例。"""
# ... imports ...
def main():
    parser = argparse.ArgumentParser(...)
    sub = parser.add_subparsers(dest="command")
    # ... subcommand definitions ...
    args = parser.parse_args()
    # ... dispatch ...

if __name__ == "__main__":
    main()
```

**参考文件**：
- `tools/financial_rigor.py`（最完整的 argparse CLI 范例）
- `tools/report_audit.py`
- `tools/morningstar_fair_value.py`

---

## 精确计算（`decimal` 模块）

### 必须使用 Decimal 的场景

所有金融计算（市值、PE、ROE、增长率、估值）**必须**使用 `decimal.Decimal`，禁止直接使用 `float` 运算。

```
from decimal import Decimal, Context, ROUND_HALF_EVEN
_CTX = Context(prec=28, rounding=ROUND_HALF_EVEN)
```

**转换规则**：
```python
def exact(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))  # 通过 str 避免 float 精度损失
    return Decimal(str(value))
```

**参考文件**：`tools/financial_rigor.py` lines 24-37

### 乘法/除法

```python
result = _CTX.multiply(a, b)   # a × b
result = _CTX.divide(a, b)     # a ÷ b
result = _CTX.add(a, b)        # a + b
result = _CTX.subtract(a, b)   # a - b
```

**参考文件**：`tools/financial_rigor.py` lines 67-68 (`verify_market_cap`)

### 大数格式化

```python
def fmt_number(d: Decimal, unit: str = "") -> str:
    """亿/T/B/M 格式化。"""
```

**参考文件**：`tools/financial_rigor.py` lines 40-54

---

## 命令行接口规范

### 子命令模式

所有工具使用 `argparse` 的 `subparsers` 实现子命令分派。

**推荐结构**：

```python
sub = parser.add_subparsers(dest="command")

# 每个子命令一个 add_parser
mc = sub.add_parser("verify-market-cap", help="验算市值 = 股价 × 总股本")
mc.add_argument("--price", type=float, required=True)
mc.add_argument("--shares", type=float, required=True)
# ...

# 分派
if args.command == "verify-market-cap":
    verify_market_cap(args.price, args.shares, ...)
```

**参考文件**：`tools/financial_rigor.py` lines 380-447

### 参数命名

- 使用 `--long-option` 格式（kebab-case），而非 `_` 分隔
- 布尔标志使用 `store_true`
- 数组参数使用 `nargs=N`

### --help 输出

```python
formatter_class=argparse.RawDescriptionHelpFormatter,
epilog="""示例:
  %(prog)s verify-market-cap --price 510 --shares 9.11e9 ...
"""
```

**参考文件**：`tools/financial_rigor.py` lines 369-378

---

## 输出格式

### 控制台输出

控制台输出使用 `print()`。关键结构：

```python
print("=" * 60)       # 分隔线
print("标题 (English + 中文)")  # 双语标题
print("=" * 60)
print(f"  {label:20s}: {value}")  # 对齐 + 缩进
print(f"  ️ 警告: {msg}")      # 状态符号 + 级别
print(f"  ✅ 验证通过")          # 最终状态
```

**输出状态符号**：
| 符号 | 含义 | 使用场景 |
|------|------|----------|
| ✅ | 通过 | 验证成功、偏差可接受 |
| ⚠️ | 警告 | 偏差在边缘范围 |
| ❌ | 失败 | 验证不通过、数据异常 |

**参考文件**：`tools/financial_rigor.py` 中的 `verify_market_cap` 和 `cross_validate` 函数

### JSON 输出（可选）

当输出需要被其他工具消费时，返回 dict：

```python
return {"consensus": consensus, "all_consistent": all_ok}
```

---

## 错误处理

### 输入验证

```python
# 安全表达式求值（只允许数字和基本算术符号）
allowed = set("0123456789.+-*/() eE")
if not all(c in allowed for c in expr.replace(" ", "")):
    print(f"  ❌ 不安全的表达式: {expr}")
    return None
```

**参考文件**：`tools/financial_rigor.py` lines 297-301

### 空/零值处理

```python
if e != 0:  # 始终检查除数为零
    pe = _CTX.divide(p, e)
```

### 样本量检查

```python
if n < 50:
    print(f"  ⚠️  样本量不足: {n} < 50, 分析不可靠")
    return None
```

**参考文件**：`tools/financial_rigor.py` lines 231-233（Benford 定律检查）

---

## 已安装的工具清单

| 工具 | CLI 入口 | 核心功能 | 被谁调用 |
|------|----------|----------|----------|
| `financial_rigor.py` | `verify-market-cap` | 市值验算 | investment-research, investment-checklist |
| | `verify-valuation` | 估值指标验算 | investment-research |
| | `cross-validate` | 多源交叉验证 | investment-research, earnings-review |
| | `benford` | Benford 定律检测 | investment-checklist |
| | `calc` | 精确计算器 | 所有 Skill（通用） |
| | `three-scenario` | 三情景估值 | investment-research |
| `report_audit.py` | `extract` | 报告数据抽检 | 报告发布前审计 |
| `morningstar_fair_value.py` | — | 晨星公允价值数据 | 晨星估值筛选报告 |
| `ashare_data.py` | — | A 股数据采集 | 行业研究 |
| `stock_screener.py` | — | 股票筛选 | 行业漏斗 |
| `xueqiu_scraper.py` | — | 雪球数据采集 | 数据补充 |
| `momentum_backtest.py` | — | 动量回测 | 组合研究 |
| `momentum_backtest_v2.py` | — | 动量回测 v2 | 组合研究 |

---

## 反模式

### ❌ 使用 `float` 做财务计算
```python
# BAD — 浮点溢出
market_cap = price * shares  # 可能 4.65e12，float 精度不足

# GOOD — Decimal 精确计算
from decimal import Decimal
_CTX.multiply(exact(price), exact(shares))
```

### ❌ JSON 参数用字符串拼接
```python
# BAD
cross-validate --values '{"年报": 7518, "Yahoo": 7500}'

# GOOD — 通过 argparse 接收 JSON string，用 json.loads 解析
```

### ❌ 没有 docstring 或 --help 输出
每个工具有 `__doc__` 和子命令的 `help=` 说明。做投研的人需要知道怎么用。

### ❌ 依赖第三方包
所有工具使用 Python 标准库。避免 `numpy`、`pandas`、`requests` 等第三方依赖。
