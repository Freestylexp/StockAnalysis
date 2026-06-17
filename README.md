# A股持仓分析 Agent

每天自动分析你的 A 股持仓和关注股，提供买卖操作建议，并推荐新的投资机会。

## 功能

- **持仓管理** — 添加/更新/删除现有持仓（股票代码、数量、成本价）
- **关注股管理** — 维护你正在观察的股票列表
- **每日分析** — 自动获取行情、计算技术指标（MA、RSI、量比等），生成操作建议
- **新股推荐** — 基于成交额和动量筛选热门标的，附带推荐理由和持仓策略
- **Cursor Automation** — 支持每天定时自动运行分析

## 快速开始

```bash
cd ~/Projects/stock-portfolio-agent

# 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 添加持仓（示例：贵州茅台 100股，成本1800元）
python main.py add-holding 600519 --shares 100 --cost 1800

# 添加关注股
python main.py add-watch 000001 --name 平安银行
python main.py add-watch 300750 --name 宁德时代

# 查看列表
python main.py list

# 生成分析报告（终端输出 + 保存到 reports/）
python main.py analyze --save
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `add-holding <代码> --shares N --cost P` | 添加/更新持仓 |
| `add-watch <代码> [--name 名称]` | 添加关注股 |
| `remove <代码> --type holding\|watch` | 移除持仓或关注股 |
| `list` | 查看所有持仓和关注股 |
| `analyze [--save]` | 生成每日分析报告 |

## 报告内容

每日报告包含四个部分：

1. **持仓分析** — 每只持仓的技术面解读、浮动盈亏、操作建议（持有/加仓/减仓）
2. **关注股分析** — 介入时机判断和买入策略
3. **新股推荐** — 自动筛选的热门标的，附推荐理由和仓位建议
4. **操作建议汇总** — 一览表

## 数据存储

持仓和关注股数据保存在 `data/portfolio.json`，可直接编辑或通过 CLI 管理。

## 免责声明

本工具生成的分析报告仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
