# -*- coding: utf-8 -*-
# 数据库访问
# 作用：建立 SQLite 连接、建表、写入数据与执行查询。
"""SQLite 数据层：建表、装载、日志、校验结果。

数据库为单文件 SQLite（data/warehouse.db），字段一律英文。
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

import config

SCHEMA_STATEMENTS = [
    # 建表：链接主数据映射表
    """
    CREATE TABLE IF NOT EXISTS dim_item_mapping (
        shop_id TEXT NOT NULL,
        owner TEXT,
        item_id TEXT NOT NULL,
        item_title TEXT,
        category_l1 TEXT,
        category_l2 TEXT,
        style_code TEXT,
        style_name TEXT,
        asset_lib_id TEXT,
        season_asset_version TEXT,
        main_image_copy_version TEXT,
        similar_group_id TEXT,
        item_status TEXT,
        mapping_source TEXT,
        frozen_flag INTEGER DEFAULT 0,
        is_primary INTEGER DEFAULT 0,
        launch_date TEXT,
        remark TEXT,
        PRIMARY KEY (shop_id, item_id)
    )
    """,
    # 建表：链接标签表
    """
    CREATE TABLE IF NOT EXISTS link_tags (
        shop_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        tag TEXT DEFAULT '',
        owner TEXT,
        updated_by TEXT,
        updated_at TEXT,
        PRIMARY KEY (shop_id, item_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_link_tags_owner ON link_tags(owner)",
    "CREATE INDEX IF NOT EXISTS ix_link_tags_tag ON link_tags(tag)",
    # 建表：订单行表
    """
    CREATE TABLE IF NOT EXISTS fact_order_line (
        line_id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id TEXT NOT NULL,
        source_file TEXT,
        source_row_no INTEGER,
        child_order_id TEXT NOT NULL,
        item_id TEXT,
        item_title TEXT,
        merchant_code TEXT,
        quantity INTEGER,
        payable_goods_amount REAL,
        discount_amount REAL,
        payable_shipping_fee REAL,
        order_status TEXT,
        paid_at TEXT,
        stat_date TEXT,
        refund_status TEXT,
        refund_amount REAL,
        line_pay_amount REAL,
        is_refund_completed INTEGER DEFAULT 0,
        is_valid INTEGER DEFAULT 0,
        issue_flags TEXT,
        raw_row_json TEXT
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_order_child ON fact_order_line(child_order_id)",
    "CREATE INDEX IF NOT EXISTS ix_order_item_date ON fact_order_line(shop_id, item_id, stat_date)",
    # 建表：商品效果日表
    """
    CREATE TABLE IF NOT EXISTS fact_item_traffic_daily (
        shop_id TEXT NOT NULL,
        stat_date TEXT NOT NULL,
        item_id TEXT NOT NULL,
        visitors INTEGER,
        page_views INTEGER,
        avg_stay_seconds REAL,
        detail_bounce_rate REAL,
        favorite_users INTEGER,
        cart_units INTEGER,
        cart_users INTEGER,
        order_buyers INTEGER,
        order_units INTEGER,
        order_amount REAL,
        order_cvr REAL,
        pay_buyers INTEGER,
        pay_units INTEGER,
        pay_amount REAL,
        pay_cvr REAL,
        new_buyers INTEGER,
        old_buyers INTEGER,
        old_buyer_pay_amount REAL,
        juhuasuan_pay_amount REAL,
        visitor_avg_value REAL,
        success_refund_amount REAL,
        competitiveness_score REAL,
        year_cum_pay_amount REAL,
        month_cum_pay_amount REAL,
        month_cum_pay_units INTEGER,
        search_pay_cvr REAL,
        search_visitors INTEGER,
        search_pay_buyers INTEGER,
        structured_detail_cvr REAL,
        structured_detail_gmv_ratio REAL,
        PRIMARY KEY (stat_date, shop_id, item_id)
    )
    """,
    # 建表：推广计划日表
    """
    CREATE TABLE IF NOT EXISTS fact_ad_plan_daily (
        shop_id TEXT NOT NULL,
        stat_date TEXT NOT NULL,
        item_id TEXT NOT NULL,
        scene_l1 TEXT,
        scene_l2 TEXT,
        subject_type TEXT,
        subject_id TEXT,
        subject_name TEXT,
        item_name TEXT,
        plan_id TEXT NOT NULL,
        plan_name TEXT,
        impressions INTEGER,
        clicks INTEGER,
        cost REAL,
        ctr REAL,
        cpc REAL,
        cpm REAL,
        direct_gmv REAL,
        indirect_gmv REAL,
        total_gmv REAL,
        total_orders INTEGER,
        direct_orders INTEGER,
        indirect_orders INTEGER,
        click_cvr REAL,
        cart_users_click INTEGER,
        click_cart_rate REAL,
        roi REAL,
        total_carts INTEGER,
        direct_carts INTEGER,
        indirect_carts INTEGER,
        cart_rate REAL,
        favorite_count INTEGER,
        total_fav_cart INTEGER,
        PRIMARY KEY (stat_date, shop_id, plan_id, item_id)
    )
    """,
    # 建表：推广商品日表
    """
    CREATE TABLE IF NOT EXISTS fact_ad_item_daily (
        shop_id TEXT NOT NULL,
        stat_date TEXT NOT NULL,
        item_id TEXT NOT NULL,
        impressions INTEGER,
        clicks INTEGER,
        cost REAL,
        direct_gmv REAL,
        indirect_gmv REAL,
        total_gmv REAL,
        total_orders INTEGER,
        direct_orders INTEGER,
        indirect_orders INTEGER,
        total_carts INTEGER,
        direct_carts INTEGER,
        indirect_carts INTEGER,
        favorite_count INTEGER,
        total_fav_cart INTEGER,
        plan_count INTEGER,
        ctr REAL,
        click_cvr REAL,
        roi REAL,
        cart_rate REAL,
        cpc REAL,
        cpm REAL,
        PRIMARY KEY (stat_date, shop_id, item_id)
    )
    """,
    # 建表：经营日报宽表
    """
    CREATE TABLE IF NOT EXISTS fact_wide_daily (
        stat_date TEXT NOT NULL,
        shop_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        style_code TEXT,
        style_name TEXT,
        category_l1 TEXT,
        category_l2 TEXT,
        asset_lib_id TEXT,
        season_asset_version TEXT,
        main_image_copy_version TEXT,
        similar_group_id TEXT,
        item_status TEXT,
        mapping_source TEXT,
        frozen_flag INTEGER,
        is_primary INTEGER,
        mapping_status TEXT,
        pay_amount REAL,
        net_amount REAL,
        units INTEGER,
        order_count INTEGER,
        refund_amount REAL,
        refund_order_count INTEGER,
        visitors INTEGER,
        page_views INTEGER,
        pay_buyers INTEGER,
        t2_pay_amount REAL,
        t2_refund_amount REAL,
        cart_units INTEGER,
        cart_users INTEGER,
        favorite_users INTEGER,
        avg_stay_seconds REAL,
        ad_cost REAL,
        ad_gmv REAL,
        ad_orders INTEGER,
        ad_clicks INTEGER,
        ad_impressions INTEGER,
        ad_carts INTEGER,
        ad_plan_count INTEGER,
        ad_roi REAL,
        conversion_rate REAL,
        refund_rate REAL,
        aov REAL,
        is_active INTEGER,
        year_month TEXT,
        week_start TEXT,
        PRIMARY KEY (stat_date, shop_id, item_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_wide_shop ON fact_wide_daily(shop_id, stat_date)",
    "CREATE INDEX IF NOT EXISTS ix_wide_style ON fact_wide_daily(style_code)",
    # 建表：数据管线日志表
    """
    CREATE TABLE IF NOT EXISTS etl_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        step TEXT,
        level TEXT,
        message TEXT,
        row_count INTEGER,
        created_at TEXT
    )
    """,
    # 建表：报表目标表
    """
    CREATE TABLE IF NOT EXISTS report_goals (
        goals_id INTEGER PRIMARY KEY CHECK (goals_id = 1),
        daily_sales_wan REAL,
        weekly_sales_wan REAL,
        monthly_sales_wan REAL,
        paid_ratio_limit REAL,
        updated_by TEXT,
        updated_at TEXT
    )
    """,
    # 建表：源文件探测表
    """
    CREATE TABLE IF NOT EXISTS source_file_probe (
        probe_id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id TEXT,
        table_id TEXT,
        file_path TEXT,
        file_type TEXT,
        encoding TEXT,
        has_bom INTEGER,
        line_ending TEXT,
        row_count INTEGER,
        column_count INTEGER,
        sheet_names TEXT,
        header_json TEXT,
        first_row_json TEXT,
        note TEXT,
        probed_at TEXT
    )
    """,
]


# _to_python
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def _to_python(value):
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, bool):
        return int(value)
    return value


# connect
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def connect(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# init_db
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def init_db(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()


# insert_dataframe
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def insert_dataframe(conn: sqlite3.Connection, table: str, df: pd.DataFrame,
                     columns: Iterable[str] | None = None) -> int:
    if df is None or len(df) == 0:
        return 0
    cols = list(columns) if columns is not None else list(df.columns)
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    rows = [tuple(_to_python(v) for v in rec) for rec in df[cols].itertuples(index=False, name=None)]
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# query_df
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def query_df(conn: sqlite3.Connection, sql: str, params: tuple | list = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=tuple(params))


# query_one
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def query_one(conn: sqlite3.Connection, sql: str, params: tuple | list = ()):
    cur = conn.execute(sql, tuple(params))
    return cur.fetchone()


# scalar
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def scalar(conn: sqlite3.Connection, sql: str, params: tuple | list = ()):
    row = query_one(conn, sql, params)
    if row is None:
        return None
    return row[0]


# write_etl_log
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def write_etl_log(conn: sqlite3.Connection, run_id: str, step: str, message: str,
                  level: str = "INFO", row_count: int | None = None) -> None:
    conn.execute(
        "INSERT INTO etl_log (run_id, step, level, message, row_count, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, step, level, message, row_count,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()


# save_probe
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def save_probe(conn: sqlite3.Connection, records: list[dict]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.executemany(
        "INSERT INTO source_file_probe "
        "(shop_id, table_id, file_path, file_type, encoding, has_bom, line_ending, "
        " row_count, column_count, sheet_names, header_json, first_row_json, note, probed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(r["shop_id"], r["table_id"], r["file_path"], r["file_type"], r["encoding"],
          r["has_bom"], r["line_ending"], r["row_count"], r["column_count"],
          r["sheet_names"], r["header_json"], r["first_row_json"], r["note"], now)
         for r in records],
    )
    conn.commit()


# table_counts
# 作用：完成数据库访问中的该步骤，结果交给调用方继续使用。
def table_counts(conn: sqlite3.Connection) -> dict:
    tables = ["dim_item_mapping", "fact_order_line", "fact_item_traffic_daily",
              "fact_ad_plan_daily", "fact_ad_item_daily", "fact_wide_daily",
              "link_tags", "report_goals", "etl_log", "source_file_probe"]
    return {t: int(scalar(conn, f"SELECT COUNT(*) FROM {t}") or 0) for t in tables}
