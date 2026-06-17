"""CLI for portfolio management."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .analyze import generate_report, save_report
from .market import get_stock_name, normalize_code
from .models import Holding, WatchItem
from .storage import load_portfolio, save_portfolio


def cmd_add_holding(args: argparse.Namespace) -> None:
    portfolio = load_portfolio()
    code = normalize_code(args.code)

    for h in portfolio.holdings:
        if h.code == code:
            print(f"已更新持仓: {code}")
            h.shares = args.shares
            h.cost_price = args.cost
            if args.name:
                h.name = args.name
            if args.notes:
                h.notes = args.notes
            save_portfolio(portfolio)
            return

    name = args.name or get_stock_name(code) or code
    portfolio.holdings.append(Holding(
        code=code,
        name=name,
        shares=args.shares,
        cost_price=args.cost,
        notes=args.notes or "",
    ))
    save_portfolio(portfolio)
    print(f"已添加持仓: {name}（{code}）{args.shares} 股，成本 {args.cost} 元")


def cmd_add_watch(args: argparse.Namespace) -> None:
    portfolio = load_portfolio()
    code = normalize_code(args.code)

    for w in portfolio.watchlist:
        if w.code == code:
            print(f"已在关注列表中: {code}")
            return

    name = args.name or get_stock_name(code) or code
    portfolio.watchlist.append(WatchItem(
        code=code,
        name=name,
        notes=args.notes or "",
        added_at=datetime.now().strftime("%Y-%m-%d"),
    ))
    save_portfolio(portfolio)
    print(f"已添加关注: {name}（{code}）")


def cmd_remove(args: argparse.Namespace) -> None:
    portfolio = load_portfolio()
    code = normalize_code(args.code)

    if args.type == "holding":
        before = len(portfolio.holdings)
        portfolio.holdings = [h for h in portfolio.holdings if h.code != code]
        if len(portfolio.holdings) < before:
            save_portfolio(portfolio)
            print(f"已移除持仓: {code}")
        else:
            print(f"未找到持仓: {code}")
    else:
        before = len(portfolio.watchlist)
        portfolio.watchlist = [w for w in portfolio.watchlist if w.code != code]
        if len(portfolio.watchlist) < before:
            save_portfolio(portfolio)
            print(f"已移除关注: {code}")
        else:
            print(f"未找到关注股: {code}")


def cmd_list(args: argparse.Namespace) -> None:
    portfolio = load_portfolio()

    print("=" * 50)
    print("持仓")
    print("=" * 50)
    if not portfolio.holdings:
        print("  （空）")
    for h in portfolio.holdings:
        print(f"  {h.name}（{h.code}）  {h.shares} 股  成本 {h.cost_price:.2f} 元")
        if h.notes:
            print(f"    备注: {h.notes}")

    print()
    print("=" * 50)
    print("关注股")
    print("=" * 50)
    if not portfolio.watchlist:
        print("  （空）")
    for w in portfolio.watchlist:
        print(f"  {w.name}（{w.code}）  添加于 {w.added_at}")
        if w.notes:
            print(f"    备注: {w.notes}")


def cmd_analyze(args: argparse.Namespace) -> None:
    print("正在分析，请稍候（需要获取行情数据）...")
    report = generate_report()
    print(report)

    if args.save:
        path = save_report(report, args.output)
        print(f"\n报告已保存: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A股持仓分析 Agent — 管理持仓/关注股，生成每日分析报告",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add-holding
    p = sub.add_parser("add-holding", help="添加/更新持仓")
    p.add_argument("code", help="股票代码，如 600519")
    p.add_argument("--shares", type=float, required=True, help="持股数量")
    p.add_argument("--cost", type=float, required=True, help="成本价（元）")
    p.add_argument("--name", default="", help="股票名称（可选，自动获取）")
    p.add_argument("--notes", default="", help="备注")
    p.set_defaults(func=cmd_add_holding)

    # add-watch
    p = sub.add_parser("add-watch", help="添加关注股")
    p.add_argument("code", help="股票代码，如 000001")
    p.add_argument("--name", default="", help="股票名称（可选）")
    p.add_argument("--notes", default="", help="备注")
    p.set_defaults(func=cmd_add_watch)

    # remove
    p = sub.add_parser("remove", help="移除持仓或关注股")
    p.add_argument("code", help="股票代码")
    p.add_argument("--type", choices=["holding", "watch"], required=True, help="类型")
    p.set_defaults(func=cmd_remove)

    # list
    p = sub.add_parser("list", help="查看持仓和关注股")
    p.set_defaults(func=cmd_list)

    # analyze
    p = sub.add_parser("analyze", help="生成每日分析报告")
    p.add_argument("--save", action="store_true", help="保存报告到 reports/ 目录")
    p.add_argument("--output", default="reports", help="报告输出目录")
    p.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
