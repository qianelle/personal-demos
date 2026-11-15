# -*- coding: utf-8 -*-
# 标签统计
# 作用：统计各标签链接数、主推清单与推广场景汇总。
""" 标签管理、数据范围辅助查询与推广场景归类。

标签为单选，系统不自动判定；本模块只提供查询与批量写入能力。
推广场景按计划名称前缀归类，映射字典在 config.SCENE_MAPPING 中维护。
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

import config
from src.etl import link_tags as link_tag_store
from src.models import db as dbmod
from src.services.filters import Filters


# update_tags
# 作用：批量设置标签：委托 link_tags 数据模块写入，并记录变更日志。
def update_tags(conn, item_ids: list[str], tag: str,
                operator: str | None = None) -> dict:
    """批量设置标签：委托 link_tags 数据模块写入，并记录变更日志。"""
    return link_tag_store.update_tags(conn, item_ids, tag, operator=operator)


# where_without_tags
# 作用：标签管理页的标签汇总与主推清单忽略全局标签筛选，避免自相矛盾。
def where_without_tags(filters: Filters, **overrides) -> Filters:
    """标签管理页的标签汇总与主推清单忽略全局标签筛选，避免自相矛盾。"""
    base = replace(filters, tags=[])
    if overrides:
        base = replace(base, **overrides)
    return base


# owner_options
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def owner_options(conn) -> list[str]:
    try:
        rows = conn.execute(
            "SELECT DISTINCT owner FROM dim_item_mapping WHERE owner IS NOT NULL "
            "AND owner <> '' ORDER BY owner").fetchall()
        return [row[0] for row in rows]
    except Exception:
        return []


# _dim_scope_sql
# 作用：在 link_tags 上应用店铺/品类/款/主推/链接条件（无标签条件）。
def _dim_scope_sql(filters: Filters, alias: str = "lt") -> tuple[list[str], list]:
    """在 link_tags 上应用店铺/品类/款/主推/链接条件（无标签条件）。"""
    clauses, params = [], []
    if filters.shop_id:
        clauses.append(f"{alias}.shop_id = ?")
        params.append(filters.shop_id)
    if filters.owner:
        clauses.append(
            f"EXISTS (SELECT 1 FROM dim_item_mapping dm WHERE dm.shop_id = {alias}.shop_id "
            f"AND dm.item_id = {alias}.item_id AND dm.owner = ?)")
        params.append(filters.owner)
    if filters.category_l2 or filters.style_code or filters.primary_only or filters.item_ids:
        dim_clauses = [f"m.shop_id = {alias}.shop_id", f"m.item_id = {alias}.item_id"]
        if filters.category_l2:
            dim_clauses.append("m.category_l2 = ?")
            params.append(filters.category_l2)
        if filters.style_code:
            dim_clauses.append("m.style_code = ?")
            params.append(filters.style_code)
        if filters.primary_only:
            dim_clauses.append("m.is_primary = 1")
        if filters.item_ids:
            marks = ",".join(["?"] * len(filters.item_ids))
            dim_clauses.append(f"m.item_id IN ({marks})")
            params.extend(filters.item_ids)
        clauses.append("EXISTS (SELECT 1 FROM dim_item_mapping m WHERE "
                       + " AND ".join(dim_clauses) + ")")
    return clauses, params


# tag_counts
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def tag_counts(conn, filters: Filters) -> dict:
    clauses, params = _dim_scope_sql(filters)
    sql = "SELECT tag, COUNT(*) AS n FROM link_tags lt"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " GROUP BY tag"
    rows = conn.execute(sql, params).fetchall()
    counts = {tag: 0 for tag in config.TAG_OPTIONS}
    counts["未设置"] = 0
    for row in rows:
        tag = row[0] or "未设置"
        counts[tag] = counts.get(tag, 0) + row[1]
    return counts


# tagged_links
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def tagged_links(conn, filters: Filters, tag: str, limit: int | None = None) -> pd.DataFrame:
    base = where_without_tags(filters)
    where, params = base.wide_where("w")
    limit_sql = ""
    query_params = list(params) + [tag]
    if limit:
        limit_sql = " LIMIT ?"
        query_params.append(limit)
    df = dbmod.query_df(
        conn,
        f"SELECT w.shop_id, w.item_id, COALESCE(m.item_title, w.item_id) AS item_title, "
        f"       m.style_code, w.category_l2, lt.tag, lt.owner, "
        f"       ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost "
        f"FROM fact_wide_daily w "
        f"LEFT JOIN dim_item_mapping m ON w.shop_id = m.shop_id AND w.item_id = m.item_id "
        f"JOIN link_tags lt ON w.shop_id = lt.shop_id AND w.item_id = lt.item_id "
        f"WHERE {where} AND lt.tag = ? "
        f"GROUP BY w.shop_id, w.item_id ORDER BY sales DESC{limit_sql}",
        query_params)
    df["ad_spend_ratio"] = df.apply(
        lambda r: r["ad_cost"] / r["sales"] if r["sales"] else None, axis=1)
    return df


# tag_summary
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def tag_summary(conn, filters: Filters) -> dict:
    counts = tag_counts(conn, filters)
    main_links = tagged_links(conn, filters, "主推款")
    total_sales = float(main_links["sales"].sum()) if len(main_links) else 0.0
    total_cost = float(main_links["ad_cost"].sum()) if len(main_links) else 0.0
    return {
        "counts": counts,
        "main_link_count": int(len(main_links)),
        "main_sales": round(total_sales, 2),
        "main_ad_cost": round(total_cost, 2),
        "main_ad_spend_ratio": (total_cost / total_sales) if total_sales else None,
        "main_links": main_links,
    }


# zero_sales_candidates
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def zero_sales_candidates(conn, filters: Filters) -> pd.DataFrame:
    base = where_without_tags(filters)
    date_start = (config.END_DATE - pd.Timedelta(days=config.ZERO_SALES_DAYS - 1)
                  ).strftime("%Y-%m-%d")
    date_end = config.END_DATE.strftime("%Y-%m-%d")
    mapping_where, mapping_params = base.mapping_where("m")
    end_date = config.END_DATE.strftime("%Y-%m-%d")
    df = dbmod.query_df(
        conn,
        f"WITH agg AS ("
        f"  SELECT w.shop_id, w.item_id, SUM(w.units) AS units, "
        f"         SUM(w.pay_amount) AS sales, SUM(w.visitors) AS visitors "
        f"  FROM fact_wide_daily w WHERE w.stat_date BETWEEN ? AND ? "
        f"  GROUP BY w.shop_id, w.item_id) "
        f"SELECT m.shop_id, m.item_id, m.item_title, m.style_code, m.launch_date, "
        f"       lt.owner, COALESCE(lt.tag, '') AS tag, "
        f"       COALESCE(a.units, 0) AS units, "
        f"       COALESCE(a.sales, 0) AS sales, "
        f"       COALESCE(a.visitors, 0) AS visitors, "
        f"       CAST(julianday(?) - julianday(m.launch_date) + 1 AS INTEGER) AS launch_days "
        f"FROM dim_item_mapping m "
        f"LEFT JOIN link_tags lt ON m.shop_id = lt.shop_id AND m.item_id = lt.item_id "
        f"LEFT JOIN agg a ON m.shop_id = a.shop_id AND m.item_id = a.item_id "
        f"WHERE {mapping_where} AND m.item_status = '在售' "
        f"  AND COALESCE(a.units, 0) = 0 "
        f"ORDER BY m.launch_date DESC, m.item_id LIMIT 100",
        [date_start, date_end, end_date] + mapping_params)
    return df


# new_launch_observation
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def new_launch_observation(conn, filters: Filters) -> pd.DataFrame:
    base = where_without_tags(filters)
    mapping_where, mapping_params = base.mapping_where("m")
    cutoff = (config.END_DATE - pd.Timedelta(days=config.NEW_LAUNCH_DAYS - 1)
              ).strftime("%Y-%m-%d")
    end_date = config.END_DATE.strftime("%Y-%m-%d")
    where, params = base.wide_where("w")
    df = dbmod.query_df(
        conn,
        f"WITH agg AS ("
        f"  SELECT w.shop_id, w.item_id, COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"         COALESCE(SUM(w.pay_amount), 0) AS sales "
        f"  FROM fact_wide_daily w WHERE {where} GROUP BY w.shop_id, w.item_id) "
        f"SELECT m.shop_id, m.item_id, m.item_title, m.style_code, m.launch_date, "
        f"       lt.owner, COALESCE(lt.tag, '') AS tag, "
        f"       CAST(julianday(?) - julianday(m.launch_date) + 1 AS INTEGER) AS launch_days, "
        f"       COALESCE(a.pay_buyers, 0) AS pay_buyers, "
        f"       ROUND(COALESCE(a.sales, 0), 2) AS sales "
        f"FROM dim_item_mapping m "
        f"LEFT JOIN link_tags lt ON m.shop_id = lt.shop_id AND m.item_id = lt.item_id "
        f"LEFT JOIN agg a ON m.shop_id = a.shop_id AND m.item_id = a.item_id "
        f"WHERE {mapping_where} AND m.launch_date >= ? AND m.launch_date <= ? "
        f"ORDER BY m.launch_date DESC, pay_buyers DESC LIMIT 100",
        params + [end_date] + mapping_params + [cutoff, end_date])
    df["achieved"] = df["pay_buyers"] >= config.NEW_LAUNCH_PAY_BUYERS_TARGET
    return df


# tag_link_rows_for_batch
# 作用：主推清单表格：当前筛选下标签为主推款的链接。
def tag_link_rows_for_batch(conn, filters: Filters, limit: int = 100) -> pd.DataFrame:
    """主推清单表格：当前筛选下标签为主推款的链接。"""
    return tagged_links(conn, filters, "主推款", limit=limit)


# =====================================================================
# 推广场景
# =====================================================================

# scene_of_plan
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def scene_of_plan(plan_name: str) -> str:
    name = plan_name or ""
    for prefix in sorted(config.SCENE_MAPPING, key=len, reverse=True):
        if name.startswith(prefix):
            return config.SCENE_MAPPING[prefix]
    return config.DEFAULT_SCENE


# add_scene_column
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def add_scene_column(plans: pd.DataFrame) -> pd.DataFrame:
    frame = plans.copy()
    frame["scene"] = frame["plan_name"].map(scene_of_plan)
    return frame


# scene_summary
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def scene_summary(conn, filters: Filters) -> pd.DataFrame:
    from src.services import metrics
    plans = metrics.plan_efficiency(conn, filters)
    if plans.empty:
        return pd.DataFrame(columns=["scene", "cost", "gmv", "roi", "plan_count",
                                     "item_count", "cost_share"])
    plans = add_scene_column(plans)
    grouped = plans.groupby("scene", as_index=False).agg(
        cost=("cost", "sum"), gmv=("gmv", "sum"),
        plan_count=("plan_id", "nunique"), item_count=("item_count", "sum"))
    total_cost = float(grouped["cost"].sum()) or 1.0
    grouped["roi"] = grouped.apply(
        lambda r: round(r["gmv"] / r["cost"], 2) if r["cost"] else None, axis=1)
    grouped["cost_share"] = grouped["cost"] / total_cost
    order = {name: index for index, name in enumerate(config.SCENE_ORDER)}
    grouped["_order"] = grouped["scene"].map(order).fillna(len(order))
    grouped = grouped.sort_values(["_order", "cost"], ascending=[True, False])
    return grouped.drop(columns=["_order"]).reset_index(drop=True)


# plan_filter_rows
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def plan_filter_rows(conn, filters: Filters, roi_below: float | None,
                     plan_ids: list[str], scene: str = "") -> pd.DataFrame:
    from src.services import metrics
    plans = metrics.plan_efficiency(conn, filters)
    if plans.empty:
        return plans
    plans = add_scene_column(plans)
    frame = plans.copy()
    if scene:
        frame = frame[frame["scene"] == scene]
    if plan_ids:
        frame = frame[frame["plan_id"].isin(plan_ids)]
    if roi_below is not None:
        frame = frame[frame["roi"].notna() & (frame["roi"] < roi_below)]
    return frame.sort_values("cost", ascending=False).reset_index(drop=True)


# check_link_hits
# 作用：完成标签统计中的该步骤，结果交给调用方继续使用。
def check_link_hits(conn, item_ids: list[str]) -> dict:
    if not item_ids:
        return {"hits": [], "misses": [], "hit_count": 0, "miss_count": 0}
    marks = ",".join(["?"] * len(item_ids))
    rows = conn.execute(
        f"SELECT DISTINCT item_id FROM fact_wide_daily WHERE item_id IN ({marks}) "
        f"UNION SELECT DISTINCT item_id FROM dim_item_mapping WHERE item_id IN ({marks})",
        list(item_ids) + list(item_ids)).fetchall()
    hits_set = {row[0] for row in rows}
    hits = [item for item in item_ids if item in hits_set]
    misses = [item for item in item_ids if item not in hits_set]
    return {"hits": hits, "misses": misses,
            "hit_count": len(hits), "miss_count": len(misses)}
