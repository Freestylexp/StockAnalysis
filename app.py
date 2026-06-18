"""Streamlit web UI for stock portfolio analysis."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import streamlit as st

RUNNING_ON_HF = bool(os.getenv("SPACE_ID"))

from src.analyze import analyze_stock, generate_report, save_report
from src.charts import build_price_chart
from src.market import fetch_realtime_quotes, fetch_stock_list, get_stock_name, normalize_code, search_stocks
from src.models import Holding, WatchItem
from src.recommend import discover_buy_candidates
from src.storage import load_portfolio, save_portfolio

st.set_page_config(
    page_title="A股持仓分析",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
  .search-hit {
        padding: 0.4rem 0.6rem;
        border-radius: 6px;
        background: #f0f4f8;
        margin-bottom: 0.25rem;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if RUNNING_ON_HF:
    st.info(
        "☁️ **云端模式**：手机/微信可直接打开此链接。"
        " 行情数据来自境外服务器，可能偶发失败；"
        " 在此修改的持仓在 Space 重启后会恢复为默认数据。"
    )


@st.cache_data(ttl=3600, show_spinner="正在加载股票列表…")
def _cached_stock_list() -> list[dict[str, str]]:
    return fetch_stock_list()


def _get_stock_list() -> list[dict[str, str]]:
    try:
        return _cached_stock_list()
    except Exception:
        from src.storage import load_stocks_cache
        return load_stocks_cache()


def _reload() -> None:
    st.session_state.pop("portfolio", None)


def get_pf():
    return load_portfolio()


def _save_holding(portfolio, code: str, name: str, shares: float, cost: float, notes: str = "") -> None:
    code = normalize_code(code)
    for h in portfolio.holdings:
        if h.code == code:
            h.name = name or h.name
            h.shares = shares
            h.cost_price = cost
            h.notes = notes
            save_portfolio(portfolio)
            return
    portfolio.holdings.append(Holding(
        code=code, name=name or get_stock_name(code) or code,
        shares=shares, cost_price=cost, notes=notes,
    ))
    save_portfolio(portfolio)


def render_price_plan_ui(result: dict[str, Any]) -> None:
    """Display profit-oriented price advice."""
    plan = result.get("price_plan") or {}
    if not plan:
        return

    st.markdown("#### 💰 盈利导向操作建议")

    if plan.get("pnl_pct") is not None:
        pnl = plan["pnl_pct"]
        if pnl > 0:
            st.success(f"当前浮盈 **{pnl:+.1f}%** — 以持有扩大盈利、分批止盈为主")
        elif pnl < -8:
            st.warning(f"当前浮亏 **{pnl:.1f}%** — 策略：摊低成本 + 等反弹扭亏，目标先回本再止盈")
        else:
            st.info(f"当前盈亏 **{pnl:+.1f}%** — 等待突破成本线后持有看更高目标")

    if plan.get("profit_targets"):
        st.markdown("**🎯 盈利目标价**")
        for t in plan["profit_targets"]:
            st.markdown(f"- **¥{t['price']:.2f}** — {t['label']}：{t['action']}")

    if plan.get("add_zones"):
        st.markdown("**📈 加仓博盈利**")
        for z in plan["add_zones"]:
            st.markdown(f"- **¥{z['low']:.2f} – ¥{z['high']:.2f}** — {z['label']}：{z['reason']}")

    if plan.get("take_profit_targets"):
        st.markdown("**💵 止盈卖出**")
        for t in plan["take_profit_targets"]:
            st.markdown(f"- **¥{t['price']:.2f}** — {t['label']}：{t['action']}")

    c1, c2 = st.columns(2)
    c1.metric("风控底线", f"¥{plan.get('stop_loss', 0):.2f}")
    if plan.get("rebound_add"):
        c2.metric("反弹加仓参考", f"¥{plan['rebound_add']:.2f}")

    for n in plan.get("notes", []):
        st.info(n.replace("**", ""))


def render_stock_chart(code: str, name: str = "", price_plan: dict | None = None, days: int = 120) -> None:
    fig = build_price_chart(code, name, days=days, price_plan=price_plan)
    if fig:
        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("暂无历史数据，无法绘制价格曲线")


def render_stock_picker(
    key_prefix: str,
    label: str = "搜索股票（输入代码或名称）",
    placeholder: str = "如 茅台、600519、万年青",
) -> dict[str, str] | None:
    """Stock search with autocomplete suggestions. Returns {code, name} or None."""
    selected_key = f"{key_prefix}_selected"
    query_key = f"{key_prefix}_query"

    if selected_key in st.session_state and st.session_state.get(f"{key_prefix}_show_selected"):
        sel = st.session_state[selected_key]
        c1, c2 = st.columns([5, 1])
        c1.success(f"已选：**{sel['name']}**（{sel['code']}）")
        if c2.button("换一只", key=f"{key_prefix}_change"):
            st.session_state.pop(selected_key, None)
            st.session_state.pop(f"{key_prefix}_show_selected", None)
            st.rerun()
        return sel

    query = st.text_input(label, key=query_key, placeholder=placeholder)

    if not query or len(query.strip()) < 1:
        return st.session_state.get(selected_key)

    stock_list = _get_stock_list()
    if not stock_list:
        cleaned = query.strip()
        if cleaned.isdigit() and len(cleaned) <= 6:
            code = normalize_code(cleaned)
            return {"code": code, "name": get_stock_name(code) or code}
        st.warning("股票列表不可用，请检查网络后点击侧边栏「刷新股票列表」")
        return None

    results = search_stocks(query, stock_list, limit=12)
    if not results:
        st.caption("未找到匹配，试试输入完整代码或更多关键字")
        return None

    st.caption(f"找到 {len(results)} 条，点击选择：")
    cols = st.columns(3)
    for i, r in enumerate(results):
        label_btn = f"{r['name']}\n{r['code']}"
        if cols[i % 3].button(label_btn, key=f"{key_prefix}_hit_{r['code']}", width="stretch"):
            st.session_state[selected_key] = r
            st.session_state[f"{key_prefix}_show_selected"] = True
            st.rerun()

    return st.session_state.get(selected_key)


def page_overview():
    st.title("📈 A股持仓分析")
    st.caption("管理持仓、关注股，一键生成每日买卖建议")

    portfolio = get_pf()
    codes = [h.code for h in portfolio.holdings] + [w.code for w in portfolio.watchlist]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("持仓数量", len(portfolio.holdings))
    col2.metric("关注股", len(portfolio.watchlist))
    col3.metric("市场", "A股")

    quotes: dict = {}
    if codes:
        if st.button("🔄 刷新行情", type="primary", key="overview_refresh"):
            st.session_state["do_refresh_quotes"] = True
        if st.session_state.get("do_refresh_quotes"):
            with st.spinner("正在获取实时行情..."):
                try:
                    quotes = fetch_realtime_quotes(codes)
                    st.session_state["quotes_cache"] = quotes
                    st.session_state["do_refresh_quotes"] = False
                except Exception as e:
                    st.error(f"获取行情失败：{e}")
                    quotes = st.session_state.get("quotes_cache", {})
        else:
            quotes = st.session_state.get("quotes_cache", {})
            if not quotes:
                st.info("点击「刷新行情」获取最新股价")

    total_value = 0.0
    total_cost = 0.0
    for h in portfolio.holdings:
        q = quotes.get(h.code, {})
        price = q.get("price", 0) or 0
        total_value += price * h.shares
        total_cost += h.cost_price * h.shares

    pnl = total_value - total_cost
    pnl_pct = (pnl / total_cost * 100) if total_cost else 0
    col4.metric("持仓市值", f"¥{total_value:,.0f}", f"{pnl_pct:+.1f}%")

    st.divider()

    if portfolio.holdings:
        st.subheader("我的持仓")
        rows = []
        for h in portfolio.holdings:
            q = quotes.get(h.code, {})
            price = q.get("price", 0) or 0
            pnl_v = (price - h.cost_price) * h.shares if price else None
            pnl_p = (price / h.cost_price - 1) * 100 if price and h.cost_price else None
            rows.append({
                "代码": h.code,
                "名称": h.name or q.get("name", ""),
                "持仓": f"{h.shares:,.0f} 股",
                "成本": f"¥{h.cost_price:.3f}",
                "现价": f"¥{price:.3f}" if price else "—",
                "涨跌幅": f"{q.get('change_pct', 0):+.2f}%" if q else "—",
                "浮动盈亏": f"¥{pnl_v:+,.0f} ({pnl_p:+.1f}%)" if pnl_v is not None else "—",
            })
        st.dataframe(rows, width="stretch", hide_index=True)

        st.subheader("持仓操作建议速览")
        for h in portfolio.holdings:
            try:
                r = analyze_stock(h.code, h.name, holding=True, cost_price=h.cost_price, shares=h.shares)
                plan = r.get("price_plan") or {}
                with st.expander(f"{h.name} — {r['action']}", expanded=False):
                    render_price_plan_ui(r)
                    if st.button("查看走势", key=f"chart_ov_{h.code}"):
                        st.session_state["chart_code"] = h.code
                        st.session_state["chart_name"] = h.name
                        st.session_state["goto_page"] = "价格走势"
                        st.rerun()
            except Exception:
                pass
    else:
        st.info("暂无持仓，请在「持仓管理」中添加")

    if portfolio.watchlist:
        st.subheader("关注股")
        rows = []
        for w in portfolio.watchlist:
            q = quotes.get(w.code, {})
            price = q.get("price", 0) or 0
            rows.append({
                "代码": w.code,
                "名称": w.name or q.get("name", ""),
                "现价": f"¥{price:.3f}" if price else "—",
                "涨跌幅": f"{q.get('change_pct', 0):+.2f}%" if q else "—",
                "添加日期": w.added_at,
            })
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_holding_editor(h: Holding, portfolio) -> None:
    """Inline edit form for a single holding."""
    with st.form(key=f"edit_holding_{h.code}"):
        st.markdown(f"**编辑 {h.name}（{h.code}）**")
        c1, c2, c3 = st.columns(3)
        new_name = c1.text_input("名称", value=h.name, key=f"ename_{h.code}")
        new_shares = c2.number_input("持股数量", min_value=0.0, value=float(h.shares), step=100.0, key=f"eshares_{h.code}")
        new_cost = c3.number_input("成本价（元）", min_value=0.0, value=float(h.cost_price), step=0.01, format="%.3f", key=f"ecost_{h.code}")
        new_notes = st.text_input("备注", value=h.notes or "", key=f"enotes_{h.code}")
        c_save, c_del, _ = st.columns([1, 1, 3])
        save = c_save.form_submit_button("保存修改", type="primary")
        delete = c_del.form_submit_button("删除持仓")
        if save:
            h.name = new_name.strip() or h.name
            h.shares = new_shares
            h.cost_price = new_cost
            h.notes = new_notes
            save_portfolio(portfolio)
            st.success("已保存")
            st.rerun()
        if delete:
            portfolio.holdings = [x for x in portfolio.holdings if x.code != h.code]
            save_portfolio(portfolio)
            st.success("已删除")
            st.rerun()


def page_holdings():
    st.header("持仓管理")

    tab_add, tab_list = st.tabs(["➕ 添加持仓", "📋 编辑持仓"])

    with tab_add:
        st.subheader("搜索并添加")
        prefill = st.session_state.get("hold_add_selected")
        if prefill:
            st.session_state["hold_add_show_selected"] = True

        picked = render_stock_picker("hold_add", placeholder="输入股票名称或代码，如 万年青、000789")

        # 若已有持仓，预填股数和成本
        portfolio = get_pf()
        default_shares, default_cost = 0.0, 0.0
        code_for_defaults = picked["code"] if picked else ""
        if code_for_defaults:
            for h in portfolio.holdings:
                if h.code == code_for_defaults:
                    default_shares = float(h.shares)
                    default_cost = float(h.cost_price)
                    st.info(f"该股票已在持仓中，保存将**更新**现有记录")
                    break

        with st.form("add_holding_form"):
            c1, c2 = st.columns(2)
            code_default = picked["code"] if picked else ""
            name_default = picked["name"] if picked else ""
            code = c1.text_input("股票代码", value=code_default, placeholder="6位代码")
            name = c2.text_input("股票名称", value=name_default)
            c3, c4 = st.columns(2)
            shares = c3.number_input("持股数量", min_value=0.0, step=100.0, value=default_shares)
            cost = c4.number_input("成本价（元）", min_value=0.0, step=0.01, format="%.3f", value=default_cost)
            notes = st.text_input("备注（可选）")
            submitted = st.form_submit_button("保存持仓", type="primary", width="stretch")
            if submitted:
                if not code:
                    st.error("请填写股票代码")
                elif shares <= 0:
                    st.error("请填写持股数量")
                elif cost <= 0:
                    st.error("请填写成本价")
                else:
                    _save_holding(portfolio, code, name, shares, cost, notes)
                    for k in ("hold_add_selected", "hold_add_show_selected"):
                        st.session_state.pop(k, None)
                    st.success(f"已保存：{name or code}（{normalize_code(code)}）")
                    st.rerun()

    with tab_list:
        portfolio = get_pf()
        if not portfolio.holdings:
            st.info("暂无持仓")
        else:
            for h in portfolio.holdings:
                with st.expander(f"{h.name}（{h.code}）— {h.shares:,.0f} 股 @ ¥{h.cost_price:.3f}", expanded=False):
                    _render_holding_editor(h, portfolio)


def page_watchlist():
    st.header("关注股管理")

    tab_add, tab_list = st.tabs(["➕ 添加关注", "📋 管理关注"])

    with tab_add:
        picked = render_stock_picker("watch_add", placeholder="输入股票名称或代码")
        if picked and st.button("添加至关注列表", type="primary", key="add_watch_btn"):
            portfolio = get_pf()
            code = picked["code"]
            if any(w.code == code for w in portfolio.watchlist):
                st.warning("已在关注列表中")
            else:
                portfolio.watchlist.append(WatchItem(
                    code=code,
                    name=picked["name"],
                    added_at=datetime.now().strftime("%Y-%m-%d"),
                ))
                save_portfolio(portfolio)
                st.session_state.pop("watch_add_selected", None)
                st.success(f"已添加：{picked['name']}（{code}）")
                st.rerun()

    with tab_list:
        portfolio = get_pf()
        if not portfolio.watchlist:
            st.info("暂无关注股")
        else:
            for w in portfolio.watchlist:
                with st.expander(f"{w.name}（{w.code}）", expanded=False):
                    with st.form(key=f"edit_watch_{w.code}"):
                        new_name = st.text_input("名称", value=w.name, key=f"wname_{w.code}")
                        new_notes = st.text_input("备注", value=w.notes or "", key=f"wnotes_{w.code}")
                        c1, c2 = st.columns(2)
                        save = c1.form_submit_button("保存", type="primary")
                        delete = c2.form_submit_button("删除")
                        if save:
                            w.name = new_name.strip() or w.name
                            w.notes = new_notes
                            save_portfolio(portfolio)
                            st.rerun()
                        if delete:
                            portfolio.watchlist = [x for x in portfolio.watchlist if x.code != w.code]
                            save_portfolio(portfolio)
                            st.rerun()


def page_search():
    st.header("🔍 搜索股票")
    st.caption("输入名称或代码，支持模糊联想")

    picked = render_stock_picker("global_search", placeholder="如 宁德、白酒、000001")
    if not picked:
        return

    code, name = picked["code"], picked["name"]
    st.divider()

    col1, col2, col3 = st.columns(3)
    if col1.button("➕ 添加为持仓", type="primary", key="search_to_hold"):
        st.session_state["hold_add_selected"] = picked
        st.session_state["goto_page"] = "持仓管理"
        st.rerun()
    if col2.button("👁 添加为关注", key="search_to_watch"):
        portfolio = get_pf()
        if not any(w.code == code for w in portfolio.watchlist):
            portfolio.watchlist.append(WatchItem(code=code, name=name, added_at=datetime.now().strftime("%Y-%m-%d")))
            save_portfolio(portfolio)
        st.success(f"已添加关注：{name}")
    if col3.button("📊 立即分析", key="search_analyze"):
        st.session_state["quick_code"] = code
        st.session_state["goto_page"] = "个股速查"
        st.rerun()

    with st.spinner("获取行情..."):
        try:
            quotes = fetch_realtime_quotes([code])
            q = quotes.get(code, {})
            if q:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("最新价", f"¥{q.get('price', 0):.3f}")
                m2.metric("涨跌幅", f"{q.get('change_pct', 0):+.2f}%")
                m3.metric("今开", f"¥{q.get('open', 0):.3f}")
                m4.metric("昨收", f"¥{q.get('prev_close', 0):.3f}")
        except Exception as e:
            st.warning(f"行情获取失败：{e}")


def page_analysis():
    st.header("每日分析报告")
    st.caption("含持仓明细价位建议、全市场买入推荐（趋势/超卖反弹/均线支撑）")

    portfolio = get_pf()
    tab_report, tab_rec = st.tabs(["📄 完整报告", "⭐ 今日买入推荐"])

    with tab_rec:
        st.markdown("扫描 A 股市场，推荐当前适合买入的标的（**不限于新股**）")
        exclude = {normalize_code(h.code) for h in portfolio.holdings}
        exclude |= {normalize_code(w.code) for w in portfolio.watchlist}

        if st.button("🔍 扫描市场", type="primary", key="scan_market"):
            with st.spinner("正在扫描市场（约 1–3 分钟）..."):
                try:
                    st.session_state["buy_candidates"] = discover_buy_candidates(
                        exclude_codes=exclude, limit=portfolio.settings.get("max_new_recommendations", 5)
                    )
                except Exception as e:
                    st.error(f"扫描失败：{e}")

        for cand in st.session_state.get("buy_candidates", []):
            with st.expander(f"⭐ {cand['name']}（{cand['code']}）— 评分 {cand['score']}", expanded=True):
                st.markdown(f"现价 **¥{cand['price']:.2f}** · 今日 {cand['change_pct']:+.2f}%")
                for reason in cand.get("reasons", []):
                    st.markdown(f"- {reason}")
                try:
                    result = analyze_stock(cand["code"], cand["name"], holding=False)
                    render_price_plan_ui(result)
                    render_stock_chart(cand["code"], cand["name"], result.get("price_plan"), days=90)
                except Exception as e:
                    st.warning(str(e))

        if not st.session_state.get("buy_candidates"):
            st.info("点击「扫描市场」获取今日买入推荐")

    with tab_report:
        if not portfolio.holdings and not portfolio.watchlist:
            st.warning("请先添加持仓或关注股")
            return

        if st.button("🔄 生成今日报告", type="primary", width="stretch"):
            with st.spinner("正在分析，获取行情数据中..."):
                try:
                    report = generate_report(portfolio)
                    path = save_report(report)
                    st.session_state["last_report"] = report
                    st.session_state["report_path"] = str(path)
                except Exception as e:
                    st.error(f"分析失败：{e}")
                    return

        if "last_report" in st.session_state:
            st.success(f"报告已保存：{st.session_state.get('report_path', '')}")
            st.markdown(st.session_state["last_report"])
            st.download_button(
                "下载报告 (Markdown)",
                st.session_state["last_report"],
                file_name=f"{datetime.now().strftime('%Y-%m-%d')}.md",
                mime="text/markdown",
            )


def page_quick():
    st.header("个股速查")

    portfolio = get_pf()
    default_code = st.session_state.pop("quick_code", "")

    picked = render_stock_picker("quick", placeholder="搜索或输入代码")
    code = picked["code"] if picked else default_code

    # 自动从持仓带入成本
    default_cost, default_shares = 0.0, 0.0
    if code:
        for h in portfolio.holdings:
            if h.code == normalize_code(code):
                default_cost = float(h.cost_price)
                default_shares = float(h.shares)
                st.caption(f"已从持仓读取：{h.shares:,.0f} 股 @ ¥{h.cost_price:.3f}")
                break

    is_holding = st.checkbox("按持仓角度分析", value=bool(default_shares))
    cost = st.number_input("成本价（可选）", min_value=0.0, step=0.01, format="%.3f", value=default_cost)
    shares = st.number_input("持股数（可选）", min_value=0.0, step=100.0, value=default_shares)

    if st.button("分析", type="primary") and code:
        with st.spinner("分析中..."):
            try:
                result = analyze_stock(
                    code, holding=is_holding,
                    cost_price=cost if cost else 0,
                    shares=shares if shares else 0,
                )
                st.subheader(f"{result['name']}（{result['code']}）")
                q = result.get("quote", {})
                if q:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("最新价", f"¥{q.get('price', 0):.3f}")
                    c2.metric("涨跌幅", f"{q.get('change_pct', 0):+.2f}%")
                    c3.metric("换手率", f"{q.get('turnover_rate', 0) or 0:.2f}%")
                render_price_plan_ui(result)
                st.markdown(f"**操作建议**：{result['action']}")
                render_stock_chart(result["code"], result["name"], result.get("price_plan"))
                if result.get("reasons"):
                    st.markdown("**分析理由**：")
                    for r in result["reasons"]:
                        st.markdown(f"- {r}")
            except Exception as e:
                st.error(f"分析失败：{e}")


def page_charts():
    st.header("📉 持仓价格走势")
    st.caption("K 线 + 均线 + 成本线 + 加仓/减仓/止损参考线")

    portfolio = get_pf()
    days = st.slider("显示天数", 30, 250, 120, step=10, key="chart_days")

    if not portfolio.holdings:
        st.info("暂无持仓，请先在「持仓管理」中添加")
        picked = render_stock_picker("chart", placeholder="或搜索其他股票查看")
        if picked:
            _render_single_chart(picked["code"], picked["name"], 0, 0, days)
        return

    st.subheader(f"我的持仓（共 {len(portfolio.holdings)} 只）")
    for h in portfolio.holdings:
        st.markdown(f"### {h.name}（{h.code}）")
        st.caption(f"持仓 {h.shares:,.0f} 股 · 成本 ¥{h.cost_price:.3f}")
        _render_single_chart(h.code, h.name, h.cost_price, h.shares, days)
        st.divider()

    with st.expander("查看其他股票"):
        picked = render_stock_picker("chart_extra", placeholder="搜索要查看的股票")
        if picked:
            _render_single_chart(picked["code"], picked["name"], 0, 0, days)


def _render_single_chart(code: str, name: str, cost: float, shares: float, days: int) -> None:
    from src.market import compute_indicators, fetch_history
    from src.recommend import compute_price_plan

    portfolio = get_pf()
    holding = any(h.code == normalize_code(code) for h in portfolio.holdings)
    h_match = next((h for h in portfolio.holdings if h.code == normalize_code(code)), None)
    if h_match:
        cost = h_match.cost_price
        shares = h_match.shares

    with st.spinner(f"加载 {name} 图表..."):
        hist = fetch_history(code, days=days)
        if hist.empty:
            st.error("无法获取历史数据。请确认网络正常，或关闭 VPN/代理 后点击侧边栏「刷新股票列表」重试。")
            return

        ind = compute_indicators(hist)
        price_plan = None
        if ind:
            plan_input = {"price": ind.get("price", 0), "change_pct": 0}
            price_plan = compute_price_plan(ind, plan_input, cost_price=cost, holding=holding)
            if cost > 0:
                price_plan["cost_price"] = cost

            c1, c2, c3, c4 = st.columns(4)
            price = ind.get("price", 0)
            c1.metric("最新价(收盘)", f"¥{price:.3f}")
            if cost > 0:
                c2.metric("相对成本", f"{(price / cost - 1) * 100:+.1f}%")
            if ind.get("rsi"):
                c3.metric("RSI", f"{ind['rsi']:.1f}")
            if price_plan.get("stop_loss"):
                c4.metric("止损参考", f"¥{price_plan['stop_loss']:.2f}")

        render_stock_chart(code, name, price_plan, days=days)

        try:
            result = analyze_stock(code, name, holding=holding, cost_price=cost, shares=shares)
            render_price_plan_ui(result)
        except Exception as e:
            st.caption(f"实时行情分析暂不可用：{e}")


# --- Sidebar ---
PAGE_NAMES = ["总览", "价格走势", "搜索股票", "持仓管理", "关注股", "每日分析", "个股速查"]

with st.sidebar:
    st.title("导航")
    default_page = st.session_state.pop("goto_page", "总览")
    default_idx = PAGE_NAMES.index(default_page) if default_page in PAGE_NAMES else 0
    page = st.radio("选择页面", PAGE_NAMES, index=default_idx, label_visibility="collapsed")

    st.divider()
    st.markdown("**快捷搜索**")
    sq = st.text_input("代码/名称", key="sidebar_search", placeholder="如 万年青", label_visibility="collapsed")
    if sq:
        hits = search_stocks(sq, _get_stock_list(), limit=6)
        for r in hits:
            if st.button(f"{r['name']} ({r['code']})", key=f"sb_{r['code']}", width="stretch"):
                st.session_state["global_search_selected"] = r
                st.session_state["global_search_show_selected"] = True
                st.session_state["goto_page"] = "搜索股票"
                st.rerun()

    if st.button("🔄 刷新股票列表", width="stretch"):
        _cached_stock_list.clear()
        st.rerun()

    st.divider()
    pf = get_pf()
    st.caption(f"持仓 {len(pf.holdings)} · 关注 {len(pf.watchlist)}")
    if RUNNING_ON_HF:
        st.caption("☁️ 云端：默认读仓库 `data/portfolio.json`，修改重启后可能丢失")
    else:
        st.caption("数据保存在本地 `data/portfolio.json`")
    st.caption("⚠️ 仅供参考，不构成投资建议")

pages: dict[str, Any] = {
    "总览": page_overview,
    "价格走势": page_charts,
    "搜索股票": page_search,
    "持仓管理": page_holdings,
    "关注股": page_watchlist,
    "每日分析": page_analysis,
    "个股速查": page_quick,
}
pages[page]()
