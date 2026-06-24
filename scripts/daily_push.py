#!/usr/bin/env python3
"""Generate daily digest and push to WeChat via PushPlus."""

from __future__ import annotations

import html
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests

from src.analyze import analyze_stock
from src.portfolio_pnl import compute_portfolio_pnl_summary
from src.recommend import discover_buy_candidates
from src.storage import load_portfolio, save_report


def _esc(text: str) -> str:
    return html.escape(str(text))


def _check_token() -> str:
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "未设置 PUSHPLUS_TOKEN。"
            "请在 GitHub → Settings → Secrets → Actions 中添加 PUSHPLUS_TOKEN"
        )
    return token


def build_digest_html() -> tuple[str, str]:
    """Return title and html body for WeChat push."""
    portfolio = load_portfolio()
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"A股每日报告 {today}"

    lines: list[str] = [
        f"<h3>📈 A股持仓分析 · {today}</h3>",
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
                "<p><b>组合概览</b></p>",
                "<ul>",
                f"<li>市值：¥{summary['total_market_value']:,.0f}</li>",
                f"<li>总浮动盈亏：¥{summary['total_pnl']:+,.0f}（{summary['total_pnl_pct']:+.2f}%）</li>",
                f"<li>近1日变化：¥{ch1:+,.0f}</li>",
                f"<li>近5日变化：¥{ch5:+,.0f}</li>",
                "</ul>",
            ]
        except Exception as exc:
            lines.append(f"<p><b>组合概览暂不可用：</b>{_esc(exc)}</p>")

        lines += ["<p><b>持仓速览</b></p>", "<ul>"]
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

    exclude = {h.code for h in portfolio.holdings} | {w.code for w in portfolio.watchlist}
    try:
        candidates, meta = discover_buy_candidates(
            exclude_codes=exclude,
            limit=portfolio.settings.get("max_new_recommendations", 5),
            scan_limit=20,
        )
    except Exception as exc:
        candidates, meta = [], {"message": f"扫描失败：{exc}"}

    lines.append("<p><b>今日买入参考</b></p>")
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

    lines.append("<p><i>仅供参考，不构成投资建议。</i></p>")
    return title, "\n".join(lines)


def push_to_wechat(title: str, content: str, token: str) -> dict:
    payload: dict = {
        "token": token,
        "title": title[:100],
        "content": content,
        "template": "html",
    }
    topic = os.getenv("PUSHPLUS_TOPIC", "").strip()
    if topic:
        payload["topic"] = topic

    resp = requests.post(
        "https://www.pushplus.plus/send",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"PushPlus 响应解析失败：{resp.text[:200]}") from exc

    code = data.get("code")
    if str(code) != "200":
        raise RuntimeError(f"PushPlus 返回错误：{data.get('msg', data)}")
    return data


def main() -> int:
    print("→ 检查 PushPlus Token ...")
    token = _check_token()

    print("→ 生成每日报告摘要 ...")
    title, digest_html = build_digest_html()

    print("→ 尝试保存完整 Markdown 报告 ...")
    try:
        from src.analyze import generate_report

        full_report = generate_report(load_portfolio())
        report_path = save_report(full_report, ROOT / "reports")
        print(f"→ 完整报告已保存：{report_path}")
    except Exception as exc:
        print(f"⚠️ 完整报告保存跳过：{exc}")

    print("→ 推送到微信（PushPlus）...")
    result = push_to_wechat(title, digest_html, token)
    print(f"✅ 推送成功：{result.get('msg', 'ok')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"❌ 失败：{exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
