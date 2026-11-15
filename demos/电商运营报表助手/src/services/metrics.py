# -*- coding: utf-8 -*-
# 指标计算
# 作用：从宽表计算趋势、结构、排行、推广与汇总指标。
"""指标计算服务（Python 侧完成全部聚合，前端只渲染）。

统一口径：
  * 销售额 = SUM(行级实付)，来自宽表 pay_amount；
  * 净销售额 = 实付 − 当期已完结退款；
  * 转化率 = SUM(支付买家数) / SUM(访客数)；
  * 退款率 = SUM(退款金额) / SUM(实付金额)；
  * 投产比 = SUM(推广成交金额) / SUM(推广花费)；
  * 动销率 = 日均成交链接数 / 在售链接数。
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

import config
from src.models import db as dbmod
from src.services.filters import Filters


# =====================================================================
# 基础指标
# =====================================================================

# period_kpis
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def period_kpis(conn, filters: Filters) -> dict:
    # ① 准备输入与上下文
    where, params = filters.wide_where("w")
    row = dbmod.query_one(
        conn,
        f"SELECT ROUND(COALESCE(SUM(w.pay_amount), 0), 2) AS sales, "
        f"       ROUND(COALESCE(SUM(w.net_amount), 0), 2) AS net_sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(COALESCE(SUM(w.refund_amount), 0), 2) AS refund_amount, "
        f"       ROUND(COALESCE(SUM(w.ad_cost), 0), 2) AS ad_cost, "
        f"       ROUND(COALESCE(SUM(w.ad_gmv), 0), 2) AS ad_gmv, "
        f"       COALESCE(SUM(w.is_active), 0) AS active_link_days, "
        f"       COUNT(DISTINCT CASE WHEN w.is_active = 1 "
        f"             THEN w.shop_id || '|' || w.item_id END) AS active_links, "
        f"       COUNT(DISTINCT w.stat_date) AS day_count "
        f"FROM fact_wide_daily w WHERE {where}",
        params,
    )
    data = dict(row) if row else {}
    data["aov"] = round(data["sales"] / data["order_count"], 2) if data.get("order_count") else None
    data["conversion_rate"] = (data["pay_buyers"] / data["visitors"]
                               if data.get("visitors") else None)
    data["refund_rate"] = (data["refund_amount"] / data["sales"]
                           if data.get("sales") else None)
    data["roi"] = (data["ad_gmv"] / data["ad_cost"]) if data.get("ad_cost") else None
    # ② 处理主体数据
    data["ad_spend_ratio"] = (data["ad_cost"] / data["sales"]) if data.get("sales") else None

    mapping_where, mapping_params = filters.mapping_where("m")
    on_sale = dbmod.scalar(
        conn,
        f"SELECT COUNT(*) FROM dim_item_mapping m WHERE {mapping_where} "
        f"AND m.item_status = '在售'",
        mapping_params,
    ) or 0
    data["on_sale_links"] = int(on_sale)
    day_count = max(int(data.get("day_count") or 0), 1)
    data["avg_daily_active"] = round(data["active_link_days"] / day_count, 2)
    data["active_rate"] = (data["avg_daily_active"] / on_sale) if on_sale else None
    # ③ 整理并返回结果
    return data


# _delta
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def _delta(cur, prev) -> float | None:
    if cur is None or prev is None:
        return None
    if prev == 0:
        return None
    return (cur - prev) / abs(prev)


# kpi_cards
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def kpi_cards(conn, filters: Filters) -> tuple[list[dict], dict, dict]:
    # ① 准备输入与上下文
    current = period_kpis(conn, filters)
    previous = period_kpis(conn, filters.previous())
    items = [
        ("销售额", "sales", "money", "SUM(行级实付)，含运费、不扣跨期退款", "pct",
         filters.with_query("/items")),
        ("净销售额", "net_sales", "money", "销售额 − 当期已完结退款", "pct",
         filters.with_query("/items")),
        ("销量", "units", "int", "SUM(购买数量)", "pct", filters.with_query("/items")),
        ("客单价", "aov", "money", "销售额 / 订单数（订单数 = 去重子订单数）", "pct",
         filters.with_query("/items")),
        ("访客数", "visitors", "int", "SUM(T2 商品访客数)", "pct",
         filters.with_query("/items")),
        ("转化率", "conversion_rate", "pct", "SUM(支付买家数) / SUM(访客数)，合计相除不取平均",
         "pp", filters.with_query("/items")),
        ("退款率", "refund_rate", "pct", "SUM(当期已完结退款) / SUM(销售额)", "pp",
         filters.with_query("/diagnostics")),
        ("推广花费", "ad_cost", "money", "SUM(T3 花费)，多计划相加", "pct",
         filters.with_query("/advertising")),
        ("投产比", "roi", "ratio", "SUM(推广成交金额) / SUM(推广花费)", "pct",
         filters.with_query("/advertising")),
        ("推广花费占比", "ad_spend_ratio", "pct",
         "推广花费 / 订单实付销售额，合计相除；不使用推广成交金额", "pp",
         filters.with_query("/advertising")),
        ("成交链接数", "active_links", "int",
         "区间内实付金额 > 0 的去重链接数；动销率 = 日均动销 / 在售链接数", "pct",
         filters.with_query("/items")),
    ]
    # ② 处理主体数据
    cards = []
    for label, key, fmt, tip, delta_kind, link in items:
        value = current.get(key)
        prev = previous.get(key)
        delta = _delta(value, prev) if delta_kind == "pct" else (
            None if value is None or prev is None else value - prev)
        sub = ""
        if key == "active_links":
            rate = current.get("active_rate")
            sub = (f"动销率 {rate * 100:.2f}% · 在售 {current.get('on_sale_links', 0)} 个链接"
                   if rate is not None else "无在售链接")
        units = {"sales": "元", "net_sales": "元", "units": "件", "aov": "元",
                 "visitors": "人", "conversion_rate": "", "refund_rate": "",
                 "ad_cost": "元", "roi": "", "ad_spend_ratio": "",
                 "active_links": "个"}
        cards.append({
            "label": label, "key": key, "value": value, "prev": prev,
            "unit": units.get(key, ""),
            "delta": delta, "delta_kind": delta_kind, "fmt": fmt,
            "tip": tip, "link": link, "sub": sub,
        })
    # ③ 整理并返回结果
    return cards, current, previous


# trend_daily
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def trend_daily(conn, filters: Filters) -> pd.DataFrame:
    where, params = filters.wide_where("w")
    return dbmod.query_df(
        conn,
        f"SELECT w.stat_date, "
        f"       ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       ROUND(SUM(w.net_amount), 2) AS net_sales, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost, "
        f"       ROUND(SUM(w.ad_gmv), 2) AS ad_gmv "
        f"FROM fact_wide_daily w WHERE {where} "
        f"GROUP BY w.stat_date ORDER BY w.stat_date", params)


# category_structure
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def category_structure(conn, filters: Filters) -> pd.DataFrame:
    where, params = filters.wide_where("w")
    return dbmod.query_df(
        conn,
        f"SELECT COALESCE(w.category_l2, '未映射') AS category_l2, "
        f"       ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(SUM(w.refund_amount), 2) AS refund_amount, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost "
        f"FROM fact_wide_daily w WHERE {where} "
        f"GROUP BY COALESCE(w.category_l2, '未映射') ORDER BY sales DESC", params)


# shop_metrics
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def shop_metrics(conn, filters: Filters) -> pd.DataFrame:
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT w.shop_id, ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       ROUND(SUM(w.net_amount), 2) AS net_sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(SUM(w.refund_amount), 2) AS refund_amount, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost, "
        f"       ROUND(SUM(w.ad_gmv), 2) AS ad_gmv, "
        f"       COUNT(DISTINCT CASE WHEN w.is_active = 1 THEN w.item_id END) AS active_links, "
        f"       COUNT(DISTINCT w.stat_date) AS day_count "
        f"FROM fact_wide_daily w WHERE {where} "
        f"GROUP BY w.shop_id ORDER BY w.shop_id", params)
    df["ad_spend_ratio"] = df.apply(
        lambda r: r["ad_cost"] / r["sales"] if r["sales"] else None, axis=1)
    return df


# weekly_metrics
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def weekly_metrics(conn, filters: Filters) -> pd.DataFrame:
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT w.week_start, ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       ROUND(SUM(w.net_amount), 2) AS net_sales, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost, "
        f"       ROUND(SUM(w.ad_gmv), 2) AS ad_gmv "
        f"FROM fact_wide_daily w WHERE {where} "
        f"GROUP BY w.week_start ORDER BY w.week_start", params)
    df["roi"] = df.apply(
        lambda r: round(r["ad_gmv"] / r["ad_cost"], 2) if r["ad_cost"] else None, axis=1)
    df["aov"] = df.apply(
        lambda r: round(r["sales"] / r["order_count"], 2) if r["order_count"] else None, axis=1)
    return df


# style_summary
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def style_summary(conn, filters: Filters) -> pd.DataFrame:
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT w.style_code, MAX(w.style_name) AS style_name, "
        f"       MAX(w.category_l2) AS category_l2, MAX(w.material) AS material, "
        f"       MAX(w.season_key) AS season_key, "
        f"       ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       ROUND(SUM(w.net_amount), 2) AS net_sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COUNT(DISTINCT w.item_id) AS link_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(SUM(w.refund_amount), 2) AS refund_amount, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost, "
        f"       ROUND(SUM(w.ad_gmv), 2) AS ad_gmv "
        f"FROM fact_wide_daily w WHERE {where} AND w.style_code IS NOT NULL "
        f"GROUP BY w.style_code ORDER BY sales DESC", params)
    df["aov"] = df.apply(
        lambda r: round(r["sales"] / r["order_count"], 2) if r["order_count"] else None, axis=1)
    df["conversion_rate"] = df.apply(
        lambda r: r["pay_buyers"] / r["visitors"] if r["visitors"] else None, axis=1)
    df["refund_rate"] = df.apply(
        lambda r: r["refund_amount"] / r["sales"] if r["sales"] else None, axis=1)
    df["roi"] = df.apply(
        lambda r: round(r["ad_gmv"] / r["ad_cost"], 2) if r["ad_cost"] else None, axis=1)
    df["ad_spend_ratio"] = df.apply(
        lambda r: r["ad_cost"] / r["sales"] if r["sales"] else None, axis=1)
    return df


# attribute_summary
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def attribute_summary(conn, filters: Filters) -> dict:
    where, params = filters.wide_where("w")
    season = dbmod.query_df(
        conn,
        f"SELECT COALESCE(w.season_key, '未映射') AS attr_name, "
        f"       SUM(w.pay_amount) AS sales, COALESCE(SUM(w.units), 0) AS units, "
        f"       COUNT(DISTINCT w.item_id) AS link_count "
        f"FROM fact_wide_daily w WHERE {where} GROUP BY attr_name ORDER BY sales DESC",
        params)
    material = dbmod.query_df(
        conn,
        f"SELECT COALESCE(w.material, '未映射') AS attr_name, "
        f"       SUM(w.pay_amount) AS sales, COALESCE(SUM(w.units), 0) AS units, "
        f"       COUNT(DISTINCT w.item_id) AS link_count "
        f"FROM fact_wide_daily w WHERE {where} GROUP BY attr_name ORDER BY sales DESC",
        params)
    return {"season": season, "material": material}


# =====================================================================
# 商品 / 链接
# =====================================================================

# item_ranking
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def item_ranking(conn, filters: Filters, limit: int = 20) -> pd.DataFrame:
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT w.shop_id, w.item_id, "
        f"       COALESCE(m.item_title, w.item_id) AS item_title, "
        f"       w.style_code, w.category_l2, w.mapping_status, w.is_primary, "
        f"       ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(SUM(w.refund_amount), 2) AS refund_amount, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost, "
        f"       ROUND(SUM(w.ad_gmv), 2) AS ad_gmv "
        f"FROM fact_wide_daily w LEFT JOIN dim_item_mapping m "
        f"  ON w.shop_id = m.shop_id AND w.item_id = m.item_id "
        f"WHERE {where} GROUP BY w.shop_id, w.item_id "
        f"ORDER BY sales DESC LIMIT ?", params + [limit])
    df["aov"] = df.apply(
        lambda r: round(r["sales"] / r["order_count"], 2) if r["order_count"] else None, axis=1)
    df["conversion_rate"] = df.apply(
        lambda r: r["pay_buyers"] / r["visitors"] if r["visitors"] else None, axis=1)
    df["refund_rate"] = df.apply(
        lambda r: r["refund_amount"] / r["sales"] if r["sales"] else None, axis=1)
    df["roi"] = df.apply(
        lambda r: round(r["ad_gmv"] / r["ad_cost"], 2) if r["ad_cost"] else None, axis=1)
    df["ad_spend_ratio"] = df.apply(
        lambda r: r["ad_cost"] / r["sales"] if r["sales"] else None, axis=1)
    return df


# sales_distribution
# 作用：链接分层分布：维度可为支付买家数 / 销量 / 销售额，分箱在 config 中配置。
def sales_distribution(conn, filters: Filters,
                       dimension: str = config.DEFAULT_SALES_DISTRIBUTION
                       ) -> tuple[pd.DataFrame, int, dict]:
    """链接分层分布：维度可为支付买家数 / 销量 / 销售额，分箱在 config 中配置。"""
    dimension = dimension if dimension in config.SALES_DISTRIBUTION_DIMENSIONS \
        else config.DEFAULT_SALES_DISTRIBUTION
    meta = config.SALES_DISTRIBUTION_DIMENSIONS[dimension]
    where, params = filters.wide_where("w")
    items = dbmod.query_df(
        conn,
        f"SELECT w.shop_id, w.item_id, ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers "
        f"FROM fact_wide_daily w WHERE {where} GROUP BY w.shop_id, w.item_id", params)
    items[dimension] = pd.to_numeric(items[dimension], errors="coerce").fillna(0)
    items["band"] = pd.cut(items[dimension], bins=meta["bins"],
                           labels=meta["labels"], right=False)
    dist = items.groupby("band", observed=False).size().reset_index(name="link_count")
    return dist, int(len(items)), {"dimension": dimension, "label": meta["label"],
                                   "unit": meta["unit"], "labels": meta["labels"]}


# slow_items
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def slow_items(conn, filters: Filters, limit: int = 10) -> pd.DataFrame:
    date_where, date_params = filters.wide_where("w")
    mapping_where, mapping_params = filters.mapping_where("m")
    return dbmod.query_df(
        conn,
        f"WITH agg AS (SELECT w.shop_id, w.item_id, "
        f"       SUM(w.pay_amount) AS sales, SUM(w.visitors) AS visitors, "
        f"       SUM(w.units) AS units, SUM(w.pay_buyers) AS pay_buyers, "
        f"       SUM(w.ad_cost) AS ad_cost "
        f"       FROM fact_wide_daily w WHERE {date_where} "
        f"       GROUP BY w.shop_id, w.item_id) "
        f"SELECT m.shop_id, m.item_id, m.item_title, m.style_code, m.category_l2, "
        f"       m.item_status, "
        f"       ROUND(COALESCE(a.sales, 0), 2) AS sales, "
        f"       COALESCE(a.visitors, 0) AS visitors, "
        f"       COALESCE(a.units, 0) AS units, "
        f"       COALESCE(a.pay_buyers, 0) AS pay_buyers, "
        f"       ROUND(COALESCE(a.ad_cost, 0), 2) AS ad_cost "
        f"FROM dim_item_mapping m LEFT JOIN agg a "
        f"  ON m.shop_id = a.shop_id AND m.item_id = a.item_id "
        f"WHERE {mapping_where} AND m.item_status = '在售' "
        f"ORDER BY sales ASC, visitors ASC, m.item_id LIMIT ?",
        date_params + mapping_params + [limit]).assign(
        ad_spend_ratio=lambda d: d.apply(
            lambda r: r["ad_cost"] / r["sales"] if r["sales"] else None, axis=1))


# =====================================================================
# 推广
# =====================================================================

# ad_daily
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def ad_daily(conn, filters: Filters) -> pd.DataFrame:
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT w.stat_date, ROUND(SUM(w.ad_cost), 2) AS ad_cost, "
        f"       ROUND(SUM(w.ad_gmv), 2) AS ad_gmv, "
        f"       COALESCE(SUM(w.ad_orders), 0) AS ad_orders, "
        f"       COALESCE(SUM(w.ad_clicks), 0) AS ad_clicks, "
        f"       COALESCE(SUM(w.ad_impressions), 0) AS ad_impressions "
        f"FROM fact_wide_daily w WHERE {where} GROUP BY w.stat_date "
        f"ORDER BY w.stat_date", params)
    df["roi"] = df.apply(
        lambda r: round(r["ad_gmv"] / r["ad_cost"], 2) if r["ad_cost"] else None, axis=1)
    return df


# plan_efficiency
# 作用：计划级期间汇总；推广计划作为分析对象，不作为独立报表。
def plan_efficiency(conn, filters: Filters) -> pd.DataFrame:
    """计划级期间汇总；推广计划作为分析对象，不作为独立报表。"""
    where, params = filters.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"SELECT p.plan_id, MAX(p.plan_name) AS plan_name, "
        f"       MAX(p.scene_l1) AS scene, "
        f"       COUNT(DISTINCT p.item_id) AS item_count, "
        f"       ROUND(SUM(p.cost), 2) AS cost, "
        f"       ROUND(SUM(p.total_gmv), 2) AS gmv, "
        f"       COALESCE(SUM(p.total_orders), 0) AS orders, "
        f"       COALESCE(SUM(p.clicks), 0) AS clicks, "
        f"       COALESCE(SUM(p.impressions), 0) AS impressions "
        f"FROM fact_ad_plan_daily p "
        f"JOIN fact_wide_daily w ON p.stat_date = w.stat_date "
        f"  AND p.shop_id = w.shop_id AND p.item_id = w.item_id "
        f"WHERE {where} GROUP BY p.plan_id ORDER BY cost DESC", params)
    df["roi"] = df.apply(
        lambda r: round(r["gmv"] / r["cost"], 2) if r["cost"] else None, axis=1)
    df["ctr"] = df.apply(
        lambda r: r["clicks"] / r["impressions"] if r["impressions"] else None, axis=1)
    df["click_cvr"] = df.apply(
        lambda r: r["orders"] / r["clicks"] if r["clicks"] else None, axis=1)
    return df


# roi_distribution
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def roi_distribution(plans: pd.DataFrame) -> pd.DataFrame:
    bins = [0, 0.5, 1.0, 1.5, 2.0, 3.0, float("inf")]
    labels = ["< 0.5", "0.5 ~ 1.0", "1.0 ~ 1.5", "1.5 ~ 2.0", "2.0 ~ 3.0", "≥ 3.0"]
    frame = plans.copy()
    frame["band"] = pd.cut(frame["roi"].fillna(0), bins=bins, labels=labels, right=False)
    return frame.groupby("band", observed=False).size().reset_index(name="plan_count")


# =====================================================================
# 单链接详情 / 数据明细
# =====================================================================

# item_mapping
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def item_mapping(conn, item_id: str) -> dict | None:
    row = dbmod.query_one(
        conn,
        "SELECT * FROM dim_item_mapping WHERE item_id = ? ORDER BY shop_id LIMIT 1",
        (item_id,))
    return dict(row) if row else None


# item_detail
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def item_detail(conn, item_id: str, filters: Filters) -> dict:
    # ① 准备输入与上下文
    mapping = item_mapping(conn, item_id)
    shop_id = mapping["shop_id"] if mapping else ""
    where, params = filters.wide_where("w")
    where += " AND w.item_id = ?"
    params.append(item_id)
    kpi = dbmod.query_one(
        conn,
        f"SELECT ROUND(COALESCE(SUM(w.pay_amount), 0), 2) AS sales, "
        f"       ROUND(COALESCE(SUM(w.net_amount), 0), 2) AS net_sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.order_count), 0) AS order_count, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(COALESCE(SUM(w.refund_amount), 0), 2) AS refund_amount, "
        f"       ROUND(COALESCE(SUM(w.ad_cost), 0), 2) AS ad_cost, "
        f"       ROUND(COALESCE(SUM(w.ad_gmv), 0), 2) AS ad_gmv, "
        f"       COALESCE(SUM(w.is_active), 0) AS active_days "
        f"FROM fact_wide_daily w WHERE {where}", params)
    kpi = dict(kpi) if kpi else {}
    kpi["aov"] = round(kpi["sales"] / kpi["order_count"], 2) if kpi.get("order_count") else None
    kpi["conversion_rate"] = (kpi["pay_buyers"] / kpi["visitors"]
                              if kpi.get("visitors") else None)
    kpi["refund_rate"] = (kpi["refund_amount"] / kpi["sales"]) if kpi.get("sales") else None
    kpi["roi"] = (kpi["ad_gmv"] / kpi["ad_cost"]) if kpi.get("ad_cost") else None
    # ② 处理主体数据
    kpi["ad_spend_ratio"] = (kpi["ad_cost"] / kpi["sales"]) if kpi.get("sales") else None

    trend = dbmod.query_df(
        conn,
        f"SELECT w.stat_date, ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost "
        f"FROM fact_wide_daily w WHERE {where} GROUP BY w.stat_date "
        f"ORDER BY w.stat_date", params)

    raw_sql = ("SELECT child_order_id, stat_date, order_status, quantity, "
               "payable_goods_amount, discount_amount, payable_shipping_fee, "
               "line_pay_amount, refund_status, refund_amount, is_valid, "
               "issue_flags, raw_row_json, source_file, source_row_no "
               "FROM fact_order_line o WHERE 1 = 1")
    raw_params: list = []
    if shop_id:
        raw_sql += " AND o.shop_id = ?"
        raw_params.append(shop_id)
    if filters.tags:
        marks = ",".join(["?"] * len(filters.tags))
        raw_sql += (" AND EXISTS (SELECT 1 FROM link_tags lt WHERE lt.shop_id = o.shop_id "
                    "AND lt.item_id = o.item_id AND lt.tag IN (" + marks + "))")
        raw_params.extend(filters.tags)
    if filters.owner:
        raw_sql += (" AND EXISTS (SELECT 1 FROM link_tags lt WHERE lt.shop_id = o.shop_id "
                    "AND lt.item_id = o.item_id AND lt.owner = ?)")
        raw_params.append(filters.owner)
    raw_sql += " AND o.item_id = ? ORDER BY o.stat_date DESC, o.child_order_id LIMIT 50"
    raw_params.append(item_id)
    raw_rows = dbmod.query_df(conn, raw_sql, raw_params)

    anomalies_df = pd.DataFrame()
    # ③ 整理并返回结果
    return {
        "mapping": mapping, "kpi": kpi, "trend": trend,
        "raw_rows": raw_rows, "anomalies": anomalies_df,
        "shop_id": shop_id,
    }


DATA_SORT_COLUMNS = {
    "stat_date": "w.stat_date",
    "shop_id": "w.shop_id",
    "item_id": "w.item_id",
    "style_code": "w.style_code",
    "category_l2": "w.category_l2",
    "pay_amount": "w.pay_amount",
    "units": "w.units",
    "order_count": "w.order_count",
    "visitors": "w.visitors",
    "conversion_rate": "w.conversion_rate",
    "refund_rate": "w.refund_rate",
    "aov": "w.aov",
    "ad_cost": "w.ad_cost",
    "ad_gmv": "w.ad_gmv",
    "ad_roi": "w.ad_roi",
    "ad_spend_ratio": "CASE WHEN w.pay_amount > 0 "
    "THEN w.ad_cost * 1.0 / w.pay_amount END",
}


# wide_rows
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def wide_rows(conn, filters: Filters, keyword: str = "", sort: str = "stat_date",
              order: str = "desc", page: int = 1, size: int = 50) -> dict:
    # ① 准备输入与上下文
    where, params = filters.wide_where("w")
    if keyword:
        where += (" AND (w.item_id LIKE ? OR w.style_code LIKE ? "
                  "OR w.category_l2 LIKE ? OR m.item_title LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like, like])
    join = (" LEFT JOIN dim_item_mapping m ON w.shop_id = m.shop_id "
            "AND w.item_id = m.item_id")
    total = dbmod.scalar(
        conn, f"SELECT COUNT(*) FROM fact_wide_daily w{join} WHERE {where}", params) or 0
    sort_col = DATA_SORT_COLUMNS.get(sort, "w.stat_date")
    direction = "DESC" if str(order).lower() != "asc" else "ASC"
    # ② 处理主体数据
    size = max(10, min(int(size or 50), 100000))
    pages = max(1, (total + size - 1) // size)
    page = max(1, min(int(page or 1), pages))
    offset = (page - 1) * size
    df = dbmod.query_df(
        conn,
        f"SELECT w.stat_date, w.shop_id, w.item_id, "
        f"       COALESCE(m.item_title, w.item_id) AS item_title, "
        f"       w.style_code, w.category_l2, "
        f"       w.mapping_status, w.is_primary, "
        f"       ROUND(w.pay_amount, 2) AS pay_amount, "
        f"       ROUND(w.net_amount, 2) AS net_amount, w.units, w.order_count, "
        f"       w.visitors, w.pay_buyers, w.conversion_rate, w.refund_rate, "
        f"       w.aov, w.ad_cost, w.ad_gmv, w.ad_roi, "
        f"       CASE WHEN w.pay_amount > 0 THEN w.ad_cost * 1.0 / w.pay_amount END "
        f"           AS ad_spend_ratio "
        f"FROM fact_wide_daily w{join} WHERE {where} "
        f"ORDER BY {sort_col} {direction}, w.stat_date DESC, w.item_id "
        f"LIMIT ? OFFSET ?", params + [size, offset])
    # ③ 整理并返回结果
    return {"df": df, "total": int(total), "page": page, "pages": pages,
            "size": size, "sort": sort, "order": order, "keyword": keyword}


# data_summary
# 作用：完成指标计算中的该步骤，结果交给调用方继续使用。
def data_summary(conn, filters: Filters) -> dict:
    where, params = filters.wide_where("w")
    row = dbmod.query_one(
        conn,
        f"SELECT COUNT(*) AS rows, COUNT(DISTINCT w.item_id) AS items, "
        f"       COUNT(DISTINCT w.stat_date) AS days, "
        f"       ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       ROUND(SUM(w.net_amount), 2) AS net_sales, "
        f"       COALESCE(SUM(w.units), 0) AS units "
        f"FROM fact_wide_daily w WHERE {where}", params)
    return dict(row) if row else {}
