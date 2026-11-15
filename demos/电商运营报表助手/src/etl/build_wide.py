# -*- coding: utf-8 -*-
# 经营宽表构建
# 作用：把订单、商品效果、推广三张源表按日期和链接汇总成宽表。
"""宽表构建与复算校验。

宽表主键：stat_date + shop_id + item_id。
三张源表先各自聚合到该粒度，再以键并集为基表左连接：
  * T1 子订单 → 日期 × 店铺 × 宝贝ID（行级实付、销量、订单数、当期退款）
  * T2 主商品ID × 日（访客、支付买家数、T2 支付金额、加购、收藏等）
  * T3 计划 × 商品 × 日 → 项目 × 日（多计划花费相加）
  * 主数据映射表 → 款号/品类/相似组等冗余属性
"""

from __future__ import annotations

import json

import pandas as pd

import config
from src.etl import field_spec
from src.models import db as dbmod

T2_WIDE_COLUMNS = [
    "visitors", "page_views", "pay_buyers", "t2_pay_amount", "t2_refund_amount",
    "cart_units", "cart_users", "favorite_users", "avg_stay_seconds",
]
AD_WIDE_COLUMNS = [
    "ad_cost", "ad_gmv", "ad_orders", "ad_clicks", "ad_impressions",
    "ad_carts", "ad_plan_count",
]
MAPPING_WIDE_COLUMNS = [
    "style_code", "style_name", "category_l1", "category_l2",
    "asset_lib_id", "season_asset_version",
    "main_image_copy_version", "similar_group_id", "item_status",
    "mapping_source", "frozen_flag", "is_primary",
]
ORDER_WIDE_COLUMNS = [
    "pay_amount", "net_amount", "units", "order_count", "refund_amount",
    "refund_order_count",
]


# build_wide
# 作用：完成经营宽表构建中的该步骤，结果交给调用方继续使用。
def build_wide(conn, run_id: str) -> tuple[pd.DataFrame, list[dict], dict]:
    # ---------------- T1 聚合（仅有效行，已去重）
    # ① 准备输入与上下文
    order_lines = dbmod.query_df(
        conn,
        "SELECT shop_id, item_id, stat_date, line_pay_amount, quantity, child_order_id, "
        "       refund_amount, is_refund_completed "
        "FROM fact_order_line WHERE is_valid = 1",
    )
    order_lines["refund_current"] = (
        order_lines["refund_amount"].fillna(0.0)
        * order_lines["is_refund_completed"].fillna(0).astype(int)
    )
    order_agg = order_lines.groupby(["stat_date", "shop_id", "item_id"], as_index=False).agg(
        pay_amount=("line_pay_amount", "sum"),
        units=("quantity", "sum"),
        order_count=("child_order_id", "nunique"),
        refund_amount=("refund_current", "sum"),
        refund_order_count=("is_refund_completed", "sum"),
    )
    order_agg["net_amount"] = (order_agg["pay_amount"] - order_agg["refund_amount"]).round(2)
    for col in ("pay_amount", "net_amount", "refund_amount"):
        order_agg[col] = order_agg[col].round(2)

    # ---------------- T2 日粒度
    traffic = dbmod.query_df(
        conn,
        "SELECT stat_date, shop_id, item_id, visitors, page_views, pay_buyers, "
        "       pay_amount AS t2_pay_amount, success_refund_amount AS t2_refund_amount, "
        "       cart_units, cart_users, favorite_users, avg_stay_seconds "
        "FROM fact_item_traffic_daily",
    )

    # ---------------- T3 日 × 商品聚合
    ads = dbmod.query_df(
        conn,
        "SELECT stat_date, shop_id, item_id, cost AS ad_cost, total_gmv AS ad_gmv, "
        "       total_orders AS ad_orders, clicks AS ad_clicks, "
        "       impressions AS ad_impressions, total_carts AS ad_carts, plan_count AS ad_plan_count "
        "FROM fact_ad_item_daily",
    )

    # ---------------- 映射属性
    mapping = dbmod.query_df(
        conn,
        "SELECT shop_id, item_id, " + ", ".join(MAPPING_WIDE_COLUMNS) +
        " FROM dim_item_mapping",
    )

    key_frames = [order_agg[["stat_date", "shop_id", "item_id"]],
                  traffic[["stat_date", "shop_id", "item_id"]],
                  ads[["stat_date", "shop_id", "item_id"]]]
    base = pd.concat(key_frames, ignore_index=True).drop_duplicates(
        subset=["stat_date", "shop_id", "item_id"])
    wide = base.merge(traffic, on=["stat_date", "shop_id", "item_id"], how="left")
    wide = wide.merge(order_agg, on=["stat_date", "shop_id", "item_id"], how="left")
    wide = wide.merge(ads, on=["stat_date", "shop_id", "item_id"], how="left")
    wide = wide.merge(mapping, on=["shop_id", "item_id"], how="left")

    for col in (T2_WIDE_COLUMNS + AD_WIDE_COLUMNS + ORDER_WIDE_COLUMNS):
        wide[col] = pd.to_numeric(wide[col], errors="coerce").fillna(0)
    for col in ("units", "order_count", "refund_order_count", "visitors", "page_views",
                "pay_buyers", "cart_units", "cart_users", "favorite_users",
                "ad_orders", "ad_clicks", "ad_impressions", "ad_carts", "ad_plan_count"):
        wide[col] = wide[col].astype("int64")
    wide["avg_stay_seconds"] = wide["avg_stay_seconds"].fillna(0.0)

    wide["mapping_status"] = wide["style_code"].notna().map(
        {True: "已映射", False: "未映射"})
    for col in ("mapping_source",):
        wide[col] = wide[col].fillna("")
    wide["frozen_flag"] = wide["frozen_flag"].fillna(0).astype("int64")
    wide["is_primary"] = wide["is_primary"].fillna(0).astype("int64")

    wide["ad_roi"] = (
        wide["ad_gmv"] / wide["ad_cost"].replace(0, float("nan"))).round(2)
    # ② 处理主体数据
    wide["conversion_rate"] = (
        wide["pay_buyers"] / wide["visitors"].replace(0, float("nan"))).round(5)
    wide["refund_rate"] = (
        wide["refund_amount"] / wide["pay_amount"].replace(0, float("nan"))).round(5)
    wide["aov"] = (
        wide["pay_amount"] / wide["order_count"].replace(0, float("nan"))).round(2)
    wide["is_active"] = (wide["pay_amount"] > 0).astype(int)
    wide["year_month"] = wide["stat_date"].str[:7]
    date_series = pd.to_datetime(wide["stat_date"])
    wide["week_start"] = (date_series - pd.to_timedelta(
        date_series.dt.dayofweek, unit="D")).dt.strftime("%Y-%m-%d")

    wide = wide.sort_values(["stat_date", "shop_id", "item_id"]).reset_index(drop=True)
    wide_cols = [name for name, _ in field_spec.WIDE_FIELDS]
    wide = wide[wide_cols]

    dbmod.insert_dataframe(conn, "fact_wide_daily", wide, wide_cols)

    # ---------------- 复算校验
    source_sum = float(order_lines["line_pay_amount"].fillna(0).sum())
    wide_sum = float(wide["pay_amount"].sum())
    source_sum = round(source_sum, 2)
    wide_sum = round(wide_sum, 2)
    diff = round(wide_sum - source_sum, 2)
    per_shop = dbmod.query_df(
        conn,
        "SELECT shop_id, ROUND(SUM(pay_amount), 2) AS wide_pay FROM fact_wide_daily "
        "GROUP BY shop_id ORDER BY shop_id",
    )
    src_per_shop = order_lines.groupby("shop_id")["line_pay_amount"].sum().round(2)

    dup_keys = int(wide.duplicated(subset=["stat_date", "shop_id", "item_id"]).sum())
    unmapped_rows = int((wide["mapping_status"] == "未映射").sum())
    validations = [
        {
            "check_id": "WIDE_SALES_TOTAL_EQUAL",
            "check_name": "宽表实付合计 = 源表行级实付合计（金额防翻倍）",
            "expected": "差异 = 0",
            "actual": f"宽表 {wide_sum:.2f} 元 / 源表 {source_sum:.2f} 元",
            "diff": diff,
            "passed": int(abs(diff) < 0.005),
            "detail": "源表行级实付 = 买家应付货款 − 优惠金额 + 买家应付邮费，"
                      "按子订单编号去重后按日期 + 店铺 + 宝贝ID 聚合；"
                      "主订单级「买家实付金额」不参与求和",
        },
        {
            "check_id": "WIDE_KEY_UNIQUE",
            "check_name": "宽表主键 stat_date + shop_id + item_id 唯一",
            "expected": "无重复",
            "actual": f"重复 {dup_keys} 行",
            "diff": float(dup_keys),
            "passed": int(dup_keys == 0),
            "detail": "",
        },
        {
            "check_id": "WIDE_SHOP_RECONCILIATION",
            "check_name": "分店铺实付合计复核",
            "expected": "每店差异 = 0",
            "actual": json.dumps({
                row["shop_id"]: {
                    "wide": float(row["wide_pay"]),
                    "source": float(src_per_shop.get(row["shop_id"], 0.0)),
                } for _, row in per_shop.iterrows()}, ensure_ascii=False),
            "diff": round(float(sum(per_shop["wide_pay"]) - float(src_per_shop.sum())), 2),
            "passed": int(all(abs(float(row["wide_pay"]) - float(
                src_per_shop.get(row["shop_id"], 0.0))) < 0.01
                for _, row in per_shop.iterrows())),
            "detail": "",
        },
        {
            "check_id": "WIDE_MAPPING_COVERAGE",
            "check_name": "宽表映射覆盖情况",
            "expected": "未映射链接进入问题列表，不做推断",
            "actual": f"未映射宽表行 {unmapped_rows} 行",
            "diff": float(unmapped_rows),
            "passed": 1,
            "detail": "未映射行属性留空，不按标题相似度推断",
        },
        {
            "check_id": "WIDE_DATE_COVERAGE",
            "check_name": "宽表日期覆盖",
            "expected": f"{config.DAYS} 天",
            "actual": f"{wide['stat_date'].nunique()} 天",
            "diff": float(config.DAYS - wide["stat_date"].nunique()),
            "passed": int(wide["stat_date"].nunique() == config.DAYS),
            "detail": f"{wide['stat_date'].min()} ~ {wide['stat_date'].max()}",
        },
    ]
    meta = {
        "wide_rows": len(wide),
        "wide_pay": wide_sum,
        "source_pay": source_sum,
        "diff": diff,
        "unmapped_rows": unmapped_rows,
        "dates": int(wide["stat_date"].nunique()),
        "t2_rows": len(traffic),
        "ad_rows": len(ads),
        "order_rows_valid": len(order_lines),
    }
    # ③ 整理并返回结果
    return wide, validations, meta
