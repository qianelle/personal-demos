# -*- coding: utf-8 -*-
# 链接管理数据
# 作用：按标签、快捷查询、高级筛选和排序整理链接表数据。
""" 链接管理：全量在售链接表 + 我的链接集合 + 分页/排序/筛选。

约束：
  * 链接管理页底层含全量在售链接；默认视图为「我的链接」。
  * 「我的链接」是全站共享集合，由链接管理页弹窗覆盖/追加；分析、报表锁死在该集合。
  * 系统运行期不自动判定标签、不自动下架、不自动修改 item_status。
"""

from __future__ import annotations

import math
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd

import config
from src.etl import link_tags as link_tag_store
from src.models import db as dbmod
from src.services import my_links as my_links_store
from src.services.filters import Filters, parse_item_ids

SORT_COLUMNS = {
    "style_code": "style_code", "category_l2": "category_l2",
    "launch_date": "launch_date", "launch_days": "launch_days",
    "launch_buyers_30": "launch_buyers_30", "sales": "sales", "units": "units",
    "pay_buyers": "pay_buyers", "ad_cost": "ad_cost",
    "ad_spend_ratio": "ad_spend_ratio", "tag": "tag",
}

CARD_KEYS = ([{"key": "all", "label": "全部链接"}]
             + [{"key": tag, "label": tag} for tag in
                ("主推款", "动销款", "潜力款", "测试款", "滞销款")]
             + [{"key": "untagged", "label": "未打标"}])

NUMERIC_FILTERS = ["launch_days", "launch_buyers_30", "sales", "units",
                   "pay_buyers", "ad_cost", "ad_spend_ratio"]
ENUM_FILTERS = []
QUICK_FIELDS = {"item_id": "商品ID", "style_code": "款号",
                "category_l2": "二级品类"}

TABLE_COLUMNS = [
    {"key": "serial", "label": "序号", "align": "right", "sortable": False,
     "filter": False},
    {"key": "item_id", "label": "商品ID", "align": "left", "sortable": False,
     "filter": False},
    {"key": "item_title", "label": "商品标题", "align": "left", "sortable": False,
     "filter": False},
    {"key": "style_code", "label": "款号", "align": "left", "sortable": True,
     "filter": False},
    {"key": "category_l2", "label": "二级品类", "align": "left", "sortable": True,
     "filter": False},
    {"key": "launch_date", "label": "上架日期", "align": "left", "sortable": True,
     "filter": "date"},
    {"key": "launch_days", "label": "上架天数", "align": "right", "sortable": True,
     "filter": "range"},
    {"key": "launch_buyers_30", "label": "上架30天支付买家数", "align": "right",
     "sortable": True, "filter": "range"},
    {"key": "sales", "label": "区间销售额", "align": "right", "sortable": True,
     "filter": "range"},
    {"key": "units", "label": "销量", "align": "right", "sortable": True,
     "filter": "range"},
    {"key": "pay_buyers", "label": "支付买家数", "align": "right", "sortable": True,
     "filter": "range"},
    {"key": "ad_cost", "label": "推广花费", "align": "right", "sortable": True,
     "filter": "range"},
    {"key": "ad_spend_ratio", "label": "付费占比", "align": "right", "sortable": True,
     "filter": "range"},
    {"key": "tag", "label": "当前标签", "align": "left", "sortable": True,
     "filter": False},
]
LINK_COLUMN_WIDTHS = {"serial": 60, "item_id": 130, "item_title": 280,
                      "style_code": 100, "category_l2": 100, "launch_date": 110,
                      "launch_days": 90, "launch_buyers_30": 120, "sales": 110,
                      "units": 80, "pay_buyers": 100, "ad_cost": 100,
                      "ad_spend_ratio": 90, "tag": 90}
for _col in TABLE_COLUMNS:
    _col["width"] = LINK_COLUMN_WIDTHS.get(_col["key"], 100)


# normalize_card
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def normalize_card(card: str | None) -> str:
    if not card or card == "all":
        return "all"
    if card == "untagged" or card in config.MANAGEMENT_TAG_OPTIONS:
        return card
    return "all"


# _arg
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def _arg(args, key: str, default: str = "") -> str:
    try:
        return (args.get(key) or default).strip()
    except AttributeError:
        return default


# _float
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def _float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# _unlocked
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def _unlocked(filters: Filters) -> Filters:
    return Filters(start=filters.start, end=filters.end, shop_id=filters.shop_id,
                   category_l2=filters.category_l2, style_code=filters.style_code,
                   item_ids=list(filters.item_ids), primary_only=filters.primary_only,
                   tags=list(filters.tags), scope=filters.scope, owner=filters.owner,
                   my_links_only=False)


# _base_rows
# 作用：全量在售链接 + 当期指标 + 人工标签 + 我的链接归属。
def _base_rows(conn, filters: Filters) -> list[dict]:
    """全量在售链接 + 当期指标 + 人工标签 + 我的链接归属。"""
    # ① 准备输入与上下文
    filters = _unlocked(filters)
    where, params = filters.wide_where("w")
    agg = dbmod.query_df(
        conn,
        f"SELECT w.shop_id, w.item_id, ROUND(SUM(w.pay_amount),2) AS sales, "
        f"       COALESCE(SUM(w.units),0) AS units, "
        f"       COALESCE(SUM(w.pay_buyers),0) AS pay_buyers, "
        f"       ROUND(SUM(w.ad_cost),2) AS ad_cost "
        f"FROM fact_wide_daily w WHERE {where} GROUP BY w.shop_id, w.item_id", params)
    agg_map = {(r["shop_id"], r["item_id"]): r for _, r in agg.iterrows()}
    lb_map = {row[0]: int(row[1] or 0) for row in conn.execute(
        "SELECT m.item_id, COALESCE(SUM(w.pay_buyers),0) "
        "FROM dim_item_mapping m JOIN fact_wide_daily w "
        "  ON m.shop_id=w.shop_id AND m.item_id=w.item_id "
        " AND w.stat_date BETWEEN m.launch_date AND date(m.launch_date, '+29 day') "
        "GROUP BY m.item_id")}
    # ② 处理主体数据
    tag_map = {row[0]: (row[1] or "") for row in conn.execute(
        "SELECT item_id, tag FROM link_tags WHERE tag IS NOT NULL AND tag <> ''")}
    mine = {item["item_id"]: item.get("owner") for item in my_links_store.load_items()}
    rows = []
    for rec in conn.execute(
            "SELECT shop_id, item_id, item_title, style_code, category_l2, "
            "launch_date, owner, item_status FROM dim_item_mapping "
            "WHERE item_status='在售' ORDER BY item_id").fetchall():
        row = dict(rec)
        metrics = agg_map.get((row["shop_id"], row["item_id"]))
        row["sales"] = round(float(metrics["sales"] or 0), 2) if metrics is not None else 0.0
        row["units"] = int(metrics["units"] or 0) if metrics is not None else 0
        row["pay_buyers"] = int(metrics["pay_buyers"] or 0) if metrics is not None else 0
        row["ad_cost"] = round(float(metrics["ad_cost"] or 0), 2) if metrics is not None else 0.0
        row["ad_spend_ratio"] = (row["ad_cost"] / row["sales"]) if row["sales"] else None
        try:
            launch = datetime.strptime(str(row.get("launch_date")), "%Y-%m-%d").date()
            row["launch_days"] = max(0, (config.END_DATE - launch).days + 1)
        except (TypeError, ValueError):
            row["launch_days"] = None
        row["launch_buyers_30"] = lb_map.get(row["item_id"], 0)
        row["raw_tag"] = tag_map.get(row["item_id"], "")
        row["tag"] = row["raw_tag"] or "未打标"
        if row["item_id"] not in mine:
            continue
        rows.append(row)
    # ③ 整理并返回结果
    return rows


# _passes_column_filters
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def _passes_column_filters(row: dict, args) -> bool:
    if _arg(args, "f_launch_from") and str(row.get("launch_date") or "") < _arg(args, "f_launch_from"):
        return False
    if _arg(args, "f_launch_to") and str(row.get("launch_date") or "") > _arg(args, "f_launch_to"):
        return False
    for key in NUMERIC_FILTERS:
        value = row.get(key)
        low = _float(_arg(args, f"f_{key}_min"))
        high = _float(_arg(args, f"f_{key}_max"))
        if low is not None:
            if value is None or float(value) < low:
                return False
        if high is not None:
            if value is None or float(value) > high:
                return False
    for key in ENUM_FILTERS:
        selected = [v for v in (_arg(args, f"f_{key}") and
                                [_arg(args, f"f_{key}")]) if v]
        # 兼容重复参数：直接读取 getlist
        try:
            selected = [str(v) for v in args.getlist(f"f_{key}") if str(v)]
        except AttributeError:
            selected = []
        if selected and str(row.get(key)) not in selected:
            return False
    return True


# _sort_rows
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def _sort_rows(rows: list[dict], sort: str, order: str) -> list[dict]:
    sort = sort if sort in SORT_COLUMNS else "launch_date"
    reverse = str(order).lower() != "asc"

    # key
    # 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
    def key(row):
        value = row.get(sort)
        if value is None:
            return (1, "")
        if sort in NUMERIC_FILTERS:
            return (0, float(value))
        return (0, str(value))

    return sorted(rows, key=key, reverse=reverse)


# _url
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def _url(query: dict, **overrides) -> str:
    merged = {k: v for k, v in query.items() if v not in (None, "", [])}
    for key, value in overrides.items():
        if value in (None, ""):
            merged.pop(key, None)
        else:
            merged[key] = value
    pairs = []
    for key, value in merged.items():
        if isinstance(value, (list, tuple)):
            for item in value:
                pairs.append((key, item))
        else:
            pairs.append((key, value))
    return "/links" + ("?" + urlencode(pairs, doseq=True) if pairs else "")


# _allowed_args
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def _allowed_args(args) -> dict:
    allowed = {"card", "quick_field", "quick_value", "qfield", "qvalue", "sort", "order", "size", "page"}
    if hasattr(args, "lists"):
        result = {}
        for key, values in args.lists():
            if key in allowed or key.startswith("f_"):
                result[key] = values[0] if len(values) == 1 else list(values)
        return result
    return {key: value for key, value in args.items()
            if key in allowed or key.startswith("f_")}


# table_view
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def table_view(conn, filters: Filters, args=None) -> dict:
    # ① 准备输入与上下文
    args = args or {}
    clean_args = _allowed_args(args)
    all_rows = _base_rows(conn, filters)
    context = list(all_rows)
    card = normalize_card(_arg(args, "card", "all"))
    quick_field = _arg(args, "qfield", "item_id")
    if quick_field not in QUICK_FIELDS:
        quick_field = "item_id"
    quick_values = parse_item_ids(_arg(args, "qvalue"))
    query_hits, query_miss = [], []
    if quick_values:
        # quick_match
        # 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
        def quick_match(row, value):
            if quick_field == "item_id":
                return row["item_id"] == value
            if quick_field == "style_code":
                return str(row.get("style_code") or "") == value
            if quick_field == "category_l2":
                return str(row.get("category_l2") or "") == value
            return False
        hit_ids = []
        for value in quick_values:
            matched = [row for row in context if quick_match(row, value)]
            if matched:
                hit_ids.append(value)
            else:
                query_miss.append(value)
        query_hits = hit_ids
        # 任一字段值命中即保留；支持多值
        context = [row for row in context
                   if any(quick_match(row, value) for value in quick_values)]
    context = [row for row in context if _passes_column_filters(row, args)]
    # 卡片计数：仅按人工标签统计未打标
    counts = {item["key"]: 0 for item in CARD_KEYS}
    counts["all"] = len(context)
    for row in context:
        if not row["raw_tag"]:
            counts["untagged"] += 1
        if row["raw_tag"] in counts:
            counts[row["raw_tag"]] += 1
    cards = []
    for item in CARD_KEYS:
        cards.append({"key": item["key"], "label": item["label"],
                      "count": counts.get(item["key"], 0),
                      "active": item["key"] == card,
                      "url": _url(clean_args, card=item["key"], page=1)})
    rows = context
    if card == "untagged":
        rows = [row for row in rows if not row["raw_tag"]]
    elif card != "all":
        rows = [row for row in rows if row["raw_tag"] == card]
    sort = _arg(args, "sort", "launch_date")
    order = _arg(args, "order", "desc")
    rows = _sort_rows(rows, sort, order)
    # ② 处理主体数据
    total = len(rows)
    try:
        size = int(_arg(args, "size", str(config.MANAGEMENT_PAGE_SIZE)))
    except ValueError:
        size = config.MANAGEMENT_PAGE_SIZE
    size = size if size in config.MANAGEMENT_PAGE_SIZE_OPTIONS else config.MANAGEMENT_PAGE_SIZE
    pages = max(1, math.ceil(total / size))
    try:
        page = max(1, min(int(_arg(args, "page", "1")), pages))
    except ValueError:
        page = 1
    offset = (page - 1) * size
    page_rows = rows[offset:offset + size]
    display = []
    for idx, row in enumerate(page_rows, start=offset + 1):
        rec = dict(row)
        rec["serial"] = idx
        rec["item_id_url"] = filters.with_query(f"/item/{row['item_id']}",
                                                item=row["item_id"])
        display.append(rec)
    all_display = []
    for idx, row in enumerate(rows, start=1):
        rec = dict(row)
        rec["serial"] = idx
        rec["item_id_url"] = filters.with_query(f"/item/{row['item_id']}",
                                                item=row["item_id"])
        all_display.append(rec)
    query = {key: value for key, value in clean_args.items() if key != "page"}
    pagination = {
        "page": page, "pages": pages, "total": total, "size": size,
        "size_options": config.MANAGEMENT_PAGE_SIZE_OPTIONS,
        "prev_url": _url(query, page=page - 1) if page > 1 else "",
        "next_url": _url(query, page=page + 1) if page < pages else "",
        "first_url": _url(query, page=1), "last_url": _url(query, page=pages),
    }
    # 筛选项候选来自当前归属范围（不含标签卡片与列筛选前的全量）
    option_rows = list(all_rows)
    options = {}
    for key in ENUM_FILTERS:
        values = sorted({str(row.get(key)) for row in option_rows
                         if row.get(key) not in (None, "")})
        options[key] = values

    total_pool = conn.execute(
        "SELECT COUNT(*) FROM dim_item_mapping WHERE item_status='在售'").fetchone()[0]
    for column in TABLE_COLUMNS:
        if column["sortable"]:
            next_order = "asc" if sort == column["key"] and order == "desc" else "desc"
            column["sort_url"] = _url(query, sort=column["key"], order=next_order, page=1)
        else:
            column["sort_url"] = ""
    selected_filters = {}
    for key in ENUM_FILTERS:
        values = list(args.getlist(f"f_{key}")) if hasattr(args, "getlist") else []
        selected_filters[key] = values
    # ③ 整理并返回结果
    return {
        "cards": cards, "card": card, "card_label": next(
            (item["label"] for item in CARD_KEYS if item["key"] == card), "未打标"),
        "rows": display, "all_rows": all_display, "pagination": pagination,
        "columns": TABLE_COLUMNS, "filter_options": options,
        "sort": sort, "order": order,
        "query_result": {"hits": query_hits, "misses": query_miss,
                         "hit_count": len(query_hits), "miss_count": len(query_miss),
                         "input": _arg(args, "qvalue")},
        "quick_field": quick_field,
        "quick_fields": QUICK_FIELDS,
        "quick_value": _arg(args, "qvalue"),
        "pool": {"pool": len(my_links_store.get_ids()),
                 "my_count": len(my_links_store.get_ids())},
        "my_links": my_links_store.load_items(),
        "my_links_ids_text": "\n".join(my_links_store.get_ids()),
        "tag_options": config.MANAGEMENT_TAG_OPTIONS,
        "tag_definitions": config.TAG_DEFINITIONS,
        "current_query": query,
        "return_url": _url(clean_args),
        "selected_filters": selected_filters,
        "has_filters": any(selected_filters.values()),
        "clear_url": _url({"card": card}),
        "export_url": _url(query),
    }


# add_my_links
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def add_my_links(conn, item_ids: list[str], mode: str) -> dict:
    return my_links_store.replace_items(conn, item_ids, mode)


# remove_my_links
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def remove_my_links(item_ids: list[str]) -> dict:
    return my_links_store.remove_items(item_ids)


# update_tags
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def update_tags(conn, item_ids: list[str], tag: str) -> dict:
    item_ids = [item for item in dict.fromkeys(item_ids or []) if item]
    if not item_ids:
        return {"ok": 0, "skipped": 0, "tag": tag}
    # 全量链接也可能尚未进入 link_tags；补记录时不写归属人
    for item_id in item_ids:
        exists = conn.execute(
            "SELECT 1 FROM link_tags WHERE item_id = ?", (item_id,)).fetchone()
        if exists:
            continue
        row = conn.execute(
            "SELECT shop_id FROM dim_item_mapping WHERE item_id = ? LIMIT 1",
            (item_id,)).fetchone()
        if row:
            conn.execute(
                "INSERT OR IGNORE INTO link_tags "
                "(shop_id, item_id, tag, owner, updated_by, updated_at) "
                "VALUES (?, ?, NULL, NULL, ?, ?)",
                (row["shop_id"], item_id, config.DEMO_OPERATOR,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return link_tag_store.update_tags(conn, item_ids, tag,
                                      operator=config.DEMO_OPERATOR)


# pool_stats
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def pool_stats(conn) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) FROM dim_item_mapping WHERE item_status='在售'").fetchone()
    return {"pool": len(my_links_store.get_ids()),
            "managed": len(my_links_store.get_ids())}


# export_rows
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def export_rows(conn, filters: Filters, args=None) -> pd.DataFrame:
    view = table_view(conn, filters, args or {})
    return pd.DataFrame(view["rows"])


# card_counts
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def card_counts(conn, filters: Filters) -> tuple[list[dict], dict]:
    view = table_view(conn, filters, {"card": "untagged"})
    counts = {item["key"]: item["count"] for item in view["cards"]}
    return view["cards"], counts


# main_push_summary
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def main_push_summary(conn, filters: Filters) -> dict:
    return {"count": 0, "sales": 0.0, "ad_cost": 0.0,
            "ad_spend_ratio": None, "top_links": []}


# management_url
# 作用：完成链接管理数据中的该步骤，结果交给调用方继续使用。
def management_url(filters: Filters, card: str, **overrides) -> str:
    params = {"card": card}
    params.update({k: v for k, v in overrides.items() if v not in (None, "")})
    return "/links?" + urlencode(params)


# remove_tag_records
# 作用：移除所选链接的人工标签记录（不移出链接池）。
def remove_tag_records(conn, item_ids: list[str]) -> dict:
    """移除所选链接的人工标签记录（不移出链接池）。"""
    return link_tag_store.remove_links(conn, list(dict.fromkeys(item_ids or [])),
                                       operator="演示环境")
