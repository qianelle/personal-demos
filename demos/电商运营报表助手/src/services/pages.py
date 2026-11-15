# -*- coding: utf-8 -*-
# 页面数据
# 作用：把筛选、指标、表格和图表数据组织成页面模板需要的结构。
""" 页面装配：经营分析 / 链接管理 / 数据报表。"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

import config
from src.etl import field_spec
from src.models import db as dbmod
from src.services import (analysis, goals as goal_store, link_management,
                          metrics, my_links, reports)
from src.services.filters import Filters

FMT_MONEY = "money"
FMT_INT = "int"
FMT_PCT = "pct"
FMT_RATIO = "ratio"

KPI_CARDS = [
    {"key": "sales_amount", "data_key": "sales", "label": "销售额",
     "fmt": "money", "unit": "元", "delta_kind": "pct"},
    {"key": "net_sales_amount", "data_key": "net_sales", "label": "净销售额",
     "fmt": "money", "unit": "元", "delta_kind": "pct"},
    {"key": "qty", "data_key": "units", "label": "销量",
     "fmt": "int", "unit": "件", "delta_kind": "pct"},
    {"key": "visitors", "data_key": "visitors", "label": "访客数",
     "fmt": "int", "unit": "人", "delta_kind": "pct"},
    {"key": "cvr", "data_key": "conversion_rate", "label": "转化率",
     "fmt": "pct", "unit": "", "delta_kind": "pp"},
    {"key": "refund_rate", "data_key": "refund_rate", "label": "退款率",
     "fmt": "pct", "unit": "", "delta_kind": "pp"},
    {"key": "ad_spend", "data_key": "ad_cost", "label": "推广花费",
     "fmt": "money", "unit": "元", "delta_kind": "pct"},
    {"key": "ad_ratio", "data_key": "ad_spend_ratio", "label": "付费占比",
     "fmt": "pct", "unit": "", "delta_kind": "pp"},
]
KPI_METRICS = [(c["label"], c["key"], c["fmt"], c["unit"], c["delta_kind"])
               for c in KPI_CARDS]


# _kpi_spec
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _kpi_spec(key):
    return next((c for c in KPI_CARDS if c["key"] == key), KPI_CARDS[1])


INFO = {
    "sales": "销售额 = 订单行级实付合计；净销售额 = 实付 − 当期退款。",
    "plan_aggregate": "比率与成本按计划汇总后相除。",
    "plan_note": "本结果仅作日常核对参考。",
    "scene_ratio": "投产比与支付转化率按合计相除。",
    "target_empty": "目标字段可空；空值不展示对应判定。",
    "target_log": "变更写入 output/目标变更日志.md。",
    "paid_formula": "付费占比 = 推广花费 / 订单实付销售额。",
    "my_links": "链接池由左侧「设置我的链接池」统一维护，三个模块共享。",
    "tag_manual": "标签为人工单选，系统不自动判定。",
    "export": "导出自包含 HTML，文件名带报表类型、区间与范围。",
    "detail": "按日期、店铺、链接展开。",
    "launch_buyers": "上架30天支付买家数 = 上架日起30天内支付买家数合计。",
}


# _num
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _num(value):
    return round(float(value or 0), 2)


# _url_with
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _url_with(filters: Filters, path: str = "/", **extra) -> str:
    pairs = list(filters._pairs())
    for key, value in extra.items():
        if value in (None, ""):
            continue
        pairs.append((key, value))
    query = urlencode(pairs, doseq=True)
    return f"{path}?{query}" if query else path


# _kpi_line
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _kpi_line(conn, filters: Filters, metric: str) -> dict:
    cur = metrics.period_kpis(conn, filters)
    prev = metrics.period_kpis(conn, filters.previous())
    cards = []
    for spec in KPI_CARDS:
        value = cur.get(spec["data_key"])
        before = prev.get(spec["data_key"])
        if spec["delta_kind"] == "pct":
            delta = ((value - before) / abs(before)) if (value is not None
                                                          and before not in (None, 0)) else None
        else:
            delta = (value - before) if (value is not None and before is not None) else None
        cards.append({"label": spec["label"], "key": spec["key"], "data_key": spec["data_key"],
                      "value": value, "prev": before, "unit": spec["unit"],
                      "fmt": spec["fmt"], "delta": delta, "delta_kind": spec["delta_kind"],
                      "active": spec["key"] == metric, "metric": spec["key"], "url": "#"})
    return {"cards": cards, "metric": metric, "full_range": filters.is_full_range,
            "compare_label": filters.compare_label}


# _daily_series
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _daily_series(conn, filters: Filters):
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT w.stat_date, ROUND(SUM(w.pay_amount),2) AS sales, "
        f"       ROUND(SUM(w.net_amount),2) AS net_sales, "
        f"       COALESCE(SUM(w.units),0) AS units, "
        f"       COALESCE(SUM(w.visitors),0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers),0) AS pay_buyers, "
        f"       ROUND(SUM(w.refund_amount),2) AS refund_amount, "
        f"       ROUND(SUM(w.ad_cost),2) AS ad_cost "
        f"FROM fact_wide_daily w WHERE {where} GROUP BY w.stat_date ORDER BY w.stat_date",
        params)
    df["conversion_rate"] = df.apply(
        lambda r: r["pay_buyers"] / r["visitors"] if r["visitors"] else None, axis=1)
    df["refund_rate"] = df.apply(
        lambda r: r["refund_amount"] / r["sales"] if r["sales"] else None, axis=1)
    df["ad_spend_ratio"] = df.apply(
        lambda r: r["ad_cost"] / r["sales"] if r["sales"] else None, axis=1)
    return df


# _metric_trend
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _metric_trend(conn, filters: Filters, metric: str = "net_sales_amount") -> dict:
    # ① 准备输入与上下文
    spec = _kpi_spec(metric)
    key = spec["data_key"]
    label = spec["label"]
    cur = _daily_series(conn, filters)
    prev = _daily_series(conn, filters.previous())
    is_pct = spec["fmt"] == "pct"
    cur_vals = cur[key].fillna(0).tolist()
    prev_vals = prev[key].fillna(0).tolist()
    if is_pct:
        cur_vals = [round(float(v) * 100, 2) for v in cur_vals]
        prev_vals = [round(float(v) * 100, 2) for v in prev_vals]
    prev_vals = prev_vals[-len(cur_vals):] if cur_vals else []
    if len(prev_vals) < len(cur_vals):
        prev_vals = [0.0] * (len(cur_vals) - len(prev_vals)) + prev_vals
    # ② 处理主体数据
    x_raw = cur["stat_date"].tolist() if not cur.empty else []
    x = [str(v)[5:7] + "/" + str(v)[8:10] if len(str(v)) >= 10 else str(v) for v in x_raw]
    bars = [{"name": f"{label}（本期）", "data": cur_vals}]
    lines = []
    if not filters.is_full_range:
        lines = [{"name": f"{label}（上期 {filters.compare_label}）", "data": prev_vals}]
    option = analysis._combo_option(
        x, bars, lines, y_name="%" if is_pct else (spec["unit"] or "数值"))
    for series in option.get("series", [])[len(bars):]:
        series["lineStyle"] = {"type": "dashed"}
    last_label = x[-1] if x else ""
    option["grid"]["bottom"] = 38
    option["graphic"] = [{
        "type": "text", "right": 28, "bottom": 4,
        "style": {"text": f"昨日\n{last_label}", "fill": "#E8944A",
                  "fontSize": 11, "fontWeight": "bold", "lineHeight": 15,
                  "textAlign": "right"},
    }]
    # ③ 整理并返回结果
    return {"option": option, "metric": metric, "label": label,
            "unit": "%" if is_pct else spec["unit"], "is_pct": is_pct,
            "compare_label": filters.compare_label}


# _scene_block
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _scene_block(conn, filters: Filters) -> dict:
    # ① 准备输入与上下文
    where, params = filters.wide_where("w")
    rows = conn.execute(
        f"SELECT p.scene_l1 AS scene, ROUND(SUM(p.cost),2) AS cost, "
        f"       ROUND(SUM(p.total_gmv),2) AS gmv, "
        f"       COALESCE(SUM(p.total_orders),0) AS orders, "
        f"       COALESCE(SUM(p.clicks),0) AS clicks "
        f"FROM fact_ad_plan_daily p "
        f"JOIN fact_wide_daily w ON p.stat_date=w.stat_date AND p.shop_id=w.shop_id "
        f"  AND p.item_id=w.item_id "
        f"WHERE {where} GROUP BY p.scene_l1", params).fetchall()
    by_scene = {row["scene"]: dict(row) for row in rows}
    scenes = []
    # ② 处理主体数据
    for scene in config.SCENE_L1_OPTIONS:
        rec = by_scene.get(scene, {"scene": scene, "cost": 0.0, "gmv": 0.0,
                                   "orders": 0, "clicks": 0})
        cost = float(rec["cost"] or 0)
        rec["roi"] = (float(rec["gmv"] or 0) / cost) if cost else None
        rec["cvr"] = (float(rec["orders"] or 0) / rec["clicks"]) if rec["clicks"] else None
        rec["cost"] = cost
        scenes.append(rec)
    total_cost = sum(r["cost"] for r in scenes)
    donut = analysis._donut([(r["scene"], r["cost"]) for r in scenes])
    combo = analysis._combo_option(
        [r["scene"] for r in scenes],
        [{"name": "总投产比", "data": [round(r["roi"], 2) if r["roi"] is not None else 0
                                       for r in scenes]}],
        [{"name": "支付转化率（%）",
          "data": [round(r["cvr"] * 100, 2) if r["cvr"] is not None else 0
                   for r in scenes]}],
        y_name="总投产比", y2_name="支付转化率（%）")
    # ③ 整理并返回结果
    return {"scenes": scenes, "total_cost": round(total_cost, 2),
            "donut": donut, "combo": combo}


# _plan_rows
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _plan_rows(conn, filters: Filters) -> list[dict]:
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT p.plan_id, MAX(p.plan_name) AS plan_name, MAX(p.scene_l1) AS scene, "
        f"       COALESCE(SUM(p.clicks),0) AS clicks, ROUND(SUM(p.cost),2) AS cost, "
        f"       COALESCE(SUM(p.cart_users_click),0) AS cart_users, "
        f"       COALESCE(SUM(p.total_orders),0) AS total_orders, "
        f"       COALESCE(SUM(p.direct_orders),0) AS direct_orders, "
        f"       ROUND(SUM(p.total_gmv),2) AS total_gmv, "
        f"       ROUND(SUM(p.direct_gmv),2) AS direct_gmv "
        f"FROM fact_ad_plan_daily p "
        f"JOIN fact_wide_daily w ON p.stat_date=w.stat_date AND p.shop_id=w.shop_id "
        f" AND p.item_id=w.item_id "
        f"WHERE {where} GROUP BY p.plan_id", params)
    rows = []
    for rec in df.to_dict(orient="records"):
        clicks = rec["clicks"] or 0
        cost = rec["cost"] or 0
        carts = rec["cart_users"] or 0
        orders = rec["total_orders"] or 0
        rec["avg_cpc"] = round(cost / clicks, 2) if clicks else None
        rec["cart_rate"] = carts / clicks if clicks else None
        rec["click_cvr"] = orders / clicks if clicks else None
        rec["roi"] = rec["total_gmv"] / cost if cost else None
        rec["direct_roi"] = rec["direct_gmv"] / cost if cost else None
        rec["cart_cost"] = cost / carts if carts else None
        rec["order_cost"] = cost / orders if orders else None
        rows.append(rec)
    rows.sort(key=lambda r: (-(r["total_gmv"] or 0), str(r["plan_id"])))
    return rows


PLAN_SORT_KEYS = ["plan_id", "plan_name", "scene", "clicks", "cost", "avg_cpc",
                  "cart_rate", "click_cvr", "roi", "direct_roi", "total_orders",
                  "direct_orders", "total_gmv", "direct_gmv", "cart_cost", "order_cost"]


PLAN_COLUMNS = [
    {"key": "plan_id", "label": "计划ID", "align": "left", "width": 110, "kind": "text"},
    {"key": "plan_name", "label": "计划名称", "align": "left", "width": 240, "kind": "text"},
    {"key": "scene", "label": "推广场景", "align": "left", "width": 120, "kind": "text"},
    {"key": "clicks", "label": "点击量", "align": "right", "width": 80, "kind": "int"},
    {"key": "cost", "label": "花费", "align": "right", "width": 100, "kind": "money"},
    {"key": "avg_cpc", "label": "平均点击单价", "align": "right", "width": 110, "kind": "money"},
    {"key": "cart_rate", "label": "加购率", "align": "right", "width": 90, "kind": "pct"},
    {"key": "click_cvr", "label": "支付转化率", "align": "right", "width": 100, "kind": "pct"},
    {"key": "roi", "label": "总投产比", "align": "right", "width": 90, "kind": "ratio"},
    {"key": "direct_roi", "label": "直接投产比", "align": "right", "width": 100, "kind": "ratio"},
    {"key": "total_orders", "label": "总成交笔数", "align": "right", "width": 100, "kind": "int"},
    {"key": "direct_orders", "label": "直接成交笔数", "align": "right", "width": 110, "kind": "int"},
    {"key": "total_gmv", "label": "总成交金额", "align": "right", "width": 120, "kind": "money"},
    {"key": "direct_gmv", "label": "直接成交金额", "align": "right", "width": 120, "kind": "money"},
    {"key": "cart_cost", "label": "加购成本", "align": "right", "width": 100, "kind": "money"},
    {"key": "order_cost", "label": "总成交成本", "align": "right", "width": 110, "kind": "money"},
]


# _plan_page
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def _plan_page(conn, filters: Filters, args) -> dict:
    # parse
    # 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
    # ① 准备输入与上下文
    def parse(key):
        raw = (args.get(key, "") or "").strip() if hasattr(args, "get") else ""
        return float(raw) if raw not in ("",) else None

    try:
        roi_below = parse("roi_below")
    except ValueError:
        roi_below = None
    try:
        cvr_below = parse("cvr_below")
    except ValueError:
        cvr_below = None
    rows = _plan_rows(conn, filters)
    filtered = []
    for row in rows:
        if roi_below is not None and (row["roi"] is None or row["roi"] >= roi_below):
            continue
        if cvr_below is not None and (row["click_cvr"] is None
                                      or row["click_cvr"] >= cvr_below / 100.0):
            continue
        filtered.append(row)
    sort = (args.get("psort", "total_gmv") if hasattr(args, "get") else "total_gmv")
    sort = sort if sort in PLAN_SORT_KEYS else "total_gmv"
    order = "asc" if str(args.get("porder", "desc")).lower() == "asc" else "desc"
    reverse = order == "desc"

    # sort_key
    # 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
    def sort_key(row):
        value = row.get(sort)
        if value is None:
            return (1, "")
        if isinstance(value, (int, float)):
            return (0, float(value))
        return (0, str(value))

    filtered.sort(key=sort_key, reverse=reverse)
    total = len(filtered)
    try:
        page = max(1, int((args.get("ppage", 1) or 1)))
    except (TypeError, ValueError):
        page = 1
    size = config.PLAN_PAGE_SIZE
    # ② 处理主体数据
    pages = max(1, (total + size - 1) // size)
    page = min(page, pages)
    start = (page - 1) * size
    page_rows = filtered[start:start + size]

    base = {key: args.get(key) for key in ("start", "end", "style", "item", "tag")
            if hasattr(args, "get") and args.get(key)}
    if hasattr(args, "getlist"):
        base["tags"] = args.getlist("tags")

    # plan_url
    # 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
    def plan_url(target, next_sort=None, next_order=None):
        pairs = []
        for key, value in base.items():
            if isinstance(value, list):
                pairs.extend((key, v) for v in value)
            elif value:
                pairs.append((key, value))
        if roi_below is not None:
            pairs.append(("roi_below", roi_below))
        if cvr_below is not None:
            pairs.append(("cvr_below", cvr_below))
        pairs.extend((("psort", next_sort if next_sort else sort),
                      ("porder", next_order if next_order else order)))
        pairs.append(("ppage", target))
        return "/?" + urlencode(pairs)

    sort_urls = {}
    for key in PLAN_SORT_KEYS:
        next_order = "asc" if not (sort == key and order == "desc") else "desc"
        # 点击同列时切换方向；其他列默认降序
        next_order = "desc" if sort != key else ("asc" if order == "desc" else "desc")
        sort_urls[key] = plan_url(1, key, next_order)
    export_pairs = [(key, value) for key, value in base.items()
                    if not isinstance(value, list) and value]
    for key in base.get("tags", []):
        export_pairs.append(("tag", key))
    if roi_below is not None:
        export_pairs.append(("roi_below", roi_below))
    if cvr_below is not None:
        export_pairs.append(("cvr_below", cvr_below))
    export_pairs.extend([("psort", sort), ("porder", order)])
    # ③ 整理并返回结果
    return {"rows": page_rows, "all_rows": filtered, "columns": PLAN_COLUMNS,
            "total": total, "page": page, "pages": pages,
            "size": size, "roi_below": roi_below, "cvr_below": cvr_below,
            "sort": sort, "order": order, "sort_urls": sort_urls,
            "prev_url": plan_url(page - 1) if page > 1 else "",
            "next_url": plan_url(page + 1) if page < pages else "",
            "reset_url": _url_with(filters),
            "export_url": "/export/table/plan?" + urlencode(export_pairs),
            "all_plan_count": len(rows)}


# page_analysis
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def page_analysis(conn, filters: Filters, args=None) -> dict:
    # ① 准备输入与上下文
    args = args or {}
    metric = args.get("metric") if args.get("metric") in {c["key"] for c in KPI_CARDS} else "net_sales_amount"
    trend = _metric_trend(conn, filters, metric)
    trend_options = {}
    # ② 处理主体数据
    for spec in KPI_CARDS:
        item = _metric_trend(conn, filters, spec["key"])
        trend_options[spec["key"]] = {"label": item["label"], "unit": item["unit"],
                                      "is_pct": item["is_pct"],
                                      "compare_label": item["compare_label"],
                                      "option": item["option"]}
    kpis = _kpi_line(conn, filters, metric)
    scene = _scene_block(conn, filters)
    plan = _plan_page(conn, filters, args)
    # ③ 整理并返回结果
    return {
        "title": "经营分析", "active": "analysis", "subtitle": "",
        "kpis": kpis, "trend": trend, "trend_options": trend_options,
        "scene": scene, "plan": plan,
        "range_label": filters.short_range, "compare_label": filters.compare_label,
        "dictionary": {"metrics": [
            {"name": "销售额", "formula": "订单行级实付合计", "date": "订单付款日期"},
            {"name": "净销售额", "formula": "销售额 − 当期退款", "date": "订单付款日期"},
            {"name": "销量", "formula": "购买数量合计", "date": "订单付款日期"},
            {"name": "访客数", "formula": "商品访客数合计", "date": "T2 日期"},
            {"name": "转化率", "formula": "支付买家数 / 访客数", "date": "T2 日期"},
            {"name": "退款率", "formula": "退款金额 / 销售额", "date": "订单付款日期"},
            {"name": "推广花费", "formula": "推广花费合计", "date": "T3 日期"},
            {"name": "付费占比", "formula": "推广花费 / 订单实付销售额", "date": "报表统计区间"},
        ]},
        "info": INFO,
        "charts": {"chart_trend": trend["option"],
                   "chart_scene_cost": scene["donut"],
                   "chart_scene_roi": scene["combo"]},
        "chart_layout": [
            {"id": "chart_trend", "title": "趋势", "height": 320, "span": 2},
            {"id": "chart_scene_cost", "title": "场景花费", "height": 300, "span": 1},
            {"id": "chart_scene_roi", "title": "场景对齐", "height": 300, "span": 1},
        ],
        "tables": [],
    }


# page_links
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def page_links(conn, filters: Filters, args=None) -> dict:
    args = args or {}
    my_links.ensure_seeded(conn)
    view = link_management.table_view(conn, filters, args)
    view.update({
        "title": "链接管理", "active": "links", "subtitle": "",
        "range_label": filters.short_range,
        "tag_action": "/links/tag", "remove_action": "/links/remove",
        "export_url": "/export/table/links?" + urlencode(
            [(k, v) for k, v in (args.items() if hasattr(args, "items") else [])
             if k not in ("page", "my_ok", "my_missing", "remove_ok", "write_ok")]),
        "info": INFO,
        "add_result": {
            "ok": args.get("my_ok"), "missing": args.get("my_missing"),
            "mode": args.get("my_mode"), "missing_ids": [
                i for i in (args.get("my_missing_ids") or "").split(",") if i],
        },
        "remove_result": {"removed": args.get("remove_ok")},
        "write_result": {"ok": args.get("write_ok"), "tag": args.get("write_tag")},
        "modal_open": bool(args.get("modal")),
    })
    view["top_range"] = (f"当前区间 {filters.start} ~ {filters.end}（{filters.days} 天）"
                         f"｜取数时点 {config.DATA_CUTOFF_LABEL}"
                         f"｜范围 {filters.scope_label}")
    return view


# page_reports
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def page_reports(conn, filters: Filters, args=None) -> dict:
    # ① 准备输入与上下文
    args = args or {}
    tab = args.get("tab") if args.get("tab") in {"daily", "weekly", "monthly"} else "weekly"
    period = reports.report_period(tab)
    sections = reports.report_sections(conn, filters, period)
    targets = reports.target_dashboard(conn, filters, period)
    targets["scene"] = reports.scene_spend_block(conn, filters, period)
    target_month = targets["monthly"]
    paid = targets["paid"]
    charts = {}
    # ② 处理主体数据
    layout = []
    chart_id = {"daily": "chart_daily", "weekly": "chart_week",
                "monthly": "chart_month"}[tab]
    if tab == "daily":
        series = reports.daily_series_7(conn, filters)
    elif tab == "weekly":
        series = reports.weekly_series(conn, filters, 8)
    else:
        series = reports.monthly_series(conn, filters, 12)
    charts[chart_id + "_gauge"] = reports.gauge_option(target_month["rate"])
    endpoint_tag = {"daily": "昨日", "weekly": "本周", "monthly": "本月"}[tab]
    charts[chart_id + "_combo"] = reports.net_ratio_combo(series, paid["limit"],
                                                          endpoint_tag)
    layout = [
        {"id": chart_id + "_gauge", "title": "月度达成", "height": 260, "span": 1},
        {"id": chart_id + "_combo", "title": "净销售额与付费占比", "height": 330, "span": 2},
    ]
    tabs = [{"key": item["key"], "label": item["label"],
             "url": f"/reports?tab={item['key']}", "active": item["key"] == tab}
            for item in config.REPORT_TABS]
    # ③ 整理并返回结果
    return {
        "title": "数据报表", "active": "reports", "subtitle": "",
        "tabs": tabs, "tab": tab, "period": period,
        "range_label": period["range_label"], "compare_label": period["prev_label"],
        "chart_range_label": (
            f"{(config.END_DATE - timedelta(days=6)).strftime('%m/%d')}-"
            f"{config.END_DATE.strftime('%m/%d')}（7天）" if tab == "daily"
            else period["range_label"]),
        "sections": sections, "targets": targets,
        "goals": goal_store.get_goals(conn),
        "text_modules": reports.build_text_modules(conn, filters, period, tab),
        "export_action": "/export/reports/html",
        "export_label": f"导出{'日报' if tab == 'daily' else '周报' if tab == 'weekly' else '月报'}",
        "info": INFO, "charts": charts, "chart_layout": layout, "tables": [],
        "top_range": (f"当前区间 {period['start']} ~ {period['end']} "
                      f"（{(period['end'] - period['start']).days + 1} 天）"
                      f"｜对比 {period['prev_start']} ~ {period['prev_end']}"
                      f"｜取数时点 {config.DATA_CUTOFF_LABEL}"
                      f"｜范围 {filters.scope_label}"),
        "date_switched": False,
    }


# page_item_detail
# 作用：完成页面数据中的该步骤，结果交给调用方继续使用。
def page_item_detail(conn, filters: Filters, item_id: str) -> dict:
    page = analysis.page_item_detail(conn, filters, item_id)
    page["range_label"] = filters.short_range
    page["active"] = "analysis"
    page["back_url"] = "/"
    page["info"] = INFO
    return page
