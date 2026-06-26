#!/usr/bin/env python3
"""Generate daily report and send by email."""

from __future__ import annotations

import html
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.analyze import analyze_stock, generate_report, save_report
from src.email_notify import send_report_email
from src.portfolio_pnl import compute_portfolio_pnl_summary
from src.recommend import discover_buy_candidates
from src.storage import load_portfolio


def _esc(text: str) -> str:
    return html.escape(str(text))


def build_digest_html() -> tuple[str, str]:
    portfolio = load_portfolio()
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"A股每日报告 {today}"

    lines: list[str] = [
        "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;line-height:1.6;'>",
        f"<h2>📈 A股持仓分析 · {today}</h2>",
    ]

    app_url = os.getenv("APP_URL", "").strip()
    if app_url:
        lines.append(f'<p><a href="{_esc(app_url)}">打开完整网页</a></p>')

    if portfolio.holdings:
        try:
            summary = compute_portfolio_pnl_summary(portfolio)
            ch1 = summary.get("changes", {}).get(1, {}).get("pnl_delta", 0)
            ch5 = summary.get("changes", {}).get(5, {}).get("pnl_delta", 0)
            lines += [
                "<h3>组合概览</h3>",
                "<ul>",
                f"<li>市值：¥{summary['total_market_value']:,.0f}</li>",
                f"<li>总浮动盈亏：¥{summary['total_pnl']:+,.0f}（{summary['total_pnl_pct']:+.2f}%）</li>",
                f"<li>近1日变化：¥{ch1:+,.0f}</li>",
                f"<li>近5日变化：¥{ch5:+,.0f}</li>",
                "</ul>",
            ]
        except Exception as exc:
            lines.append(f"<p><b>组合概览暂不可用：</b>{_esc(exc)}</p>")

        lines += ["<h3>持仓速览</h3>", "<ul>"]
        for h in portfolio.holdings:
            try:
                r = analyze_stock(h.code, h.name, holding=True, cost_price=h.cost_price, shares=h.shares)
                pnl = r.get("pnl_pct")
                pnl_text = f"{pnl:+.1f}%" if pnl is not None else "—"
                lines.append(
                    f"<li><b>{_esc(h.name)}</b>（{h.code}）"
                    f" · {pnl_text} · {_esc(r['action'])}</li>"
                )
            except Exception as exc:
                lines.append(f"<li>{_esc(h.name)}（{h.code}）· 分析暂不可用：{_esc(exc)}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>当前暂无持仓。</p>")

    if portfolio.watchlist:
        lines += ["<h3>关注股动向</h3>", "<ul>"]
        for w in portfolio.watchlist:
            try:
                r = analyze_stock(w.code, w.name, holding=False)
                q = r.get("quote", {})
                ind = r.get("indicators", {})
                price = q.get("price") or ind.get("price") or 0
                chg = q.get("change_pct", 0)
                ch5 = ind.get("change_5d", 0)
                ch20 = ind.get("change_20d", 0)
                lines.append(
                    f"<li><b>{_esc(w.name)}</b>（{w.code}）"
                    f" · ¥{price:.2f} · 今日 {chg:+.2f}%"
                    f" · 5日 {ch5:+.1f}% · 20日 {ch20:+.1f}%"
                    f" · {_esc(r['action'])}</li>"
                )
            except Exception as exc:
                lines.append(f"<li>{_esc(w.name)}（{w.code}）· 分析暂不可用：{_esc(exc)}</li>")
        lines.append("</ul>")

    exclude = {h.code for h in portfolio.holdings} | {w.code for w in portfolio.watchlist}
    try:
        candidates, meta = discover_buy_candidates(
            exclude_codes=exclude,
            limit=portfolio.settings.get("max_new_recommendations", 5),
            scan_limit=20,
        )
    except Exception as exc:
        candidates, meta = [], {"message": f"扫描失败：{exc}"}

    lines.append("<h3>今日买入参考</h3>")
    if candidates:
        lines.append("<ul>")
        for c in candidates[:5]:
            reason = c.get("reasons", ["—"])[0]
            lines.append(
                f"<li><b>{_esc(c['name'])}</b>（{c['code']}）"
                f" · ¥{c['price']:.2f} · {c['change_pct']:+.2f}%"
                f" · {_esc(reason)}</li>"
            )
        lines.append("</ul>")
        if meta.get("message"):
            lines.append(f"<p><i>{_esc(meta['message'])}</i></p>")
    else:
        msg = meta.get("message") or "暂无高评分买入推荐"
        lines.append(f"<p>{_esc(msg)}</p>")

    lines.append("<p style='color:#666;'><i>仅供参考，不构成投资建议。</i></p></div>")
    return title, "\n".join(lines)


def main() -> int:
    print("→ 检查邮件配置 ...")
    from src.email_notify import get_email_config

    cfg = get_email_config()
    transport = cfg.get("transport", "smtp")
    print(f"→ 方式：{transport}")
    print(f"→ 发件：{cfg['from']}  收件：{cfg['to']}  服务器：{cfg['host']}:{cfg['port']}")

    print("→ 生成每日报告 ...")
    title, digest_html = build_digest_html()

    full_report = ""
    try:
        full_report = generate_report(load_portfolio())
        report_path = save_report(full_report, ROOT / "reports")
        print(f"→ 完整报告已保存：{report_path}")
    except Exception as exc:
        print(f"⚠️ 完整 Markdown 报告生成失败，仍发送 HTML 摘要：{exc}")

    print("→ 发送邮件 ...")
    send_report_email(title, digest_html, markdown_body=full_report or None)
    print("✅ 邮件发送成功")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"❌ 失败：{exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
