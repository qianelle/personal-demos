# -*- coding: utf-8 -*-
# 数据管线
# 作用：依次完成源文件探测、建库、清洗入库、宽表构建与数据规模打印。
"""数据管线：读取现有模拟源文件 → 探测 → 清洗 → SQLite → 宽表 → 静默合计校验。"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

import config
from src.etl import clean, link_tags, probe
from src.etl.build_wide import build_wide
from src.models import db as dbmod
from src.services import goals


# _merge_counters
# 作用：完成数据管线中的该步骤，结果交给调用方继续使用。
def _merge_counters(target: Counter, source: dict) -> None:
    target.update(source)


# _clean_db_files
# 作用：完成数据管线中的该步骤，结果交给调用方继续使用。
def _clean_db_files() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = config.DB_PATH.with_name(config.DB_PATH.name + suffix)
        if path.exists():
            path.unlink()


# run_data_pipeline
# 作用：完成数据管线中的该步骤，结果交给调用方继续使用。
def run_data_pipeline(verbose: bool = True) -> dict:
    # ① 准备输入与上下文
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    started = datetime.now()
    if verbose:
        print("=" * 78)
        print(f"[数据管线] 开始运行 run_id={run_id}")
        print("=" * 78)

    # 源文件探测阶段：读取文件信息，后续按店铺逐个处理。
    # 1) 现有源文件探测（不重造模拟数据）
    probe_records = probe.probe_all(config.DATA_DIR, config.SHOPS)
    probe_records.append(probe.probe_mapping(config.MAPPING_FILE))
    if verbose:
        probe.print_probe(probe_records)

    # 建库与保留设置阶段：重建数据表，保留人工标签与月度目标。
    # 2) 建库，保留人工标签与目标
    preserved_tags = link_tags.snapshot_link_tags(config.DB_PATH)
    preserved_goals = goals.snapshot_goals(config.DB_PATH)
    _clean_db_files()
    conn = dbmod.connect()
    dbmod.init_db(conn)
    goals.ensure_table(conn)
    dbmod.save_probe(conn, probe_records)
    goals.restore_goals(conn, preserved_goals)
    dbmod.write_etl_log(conn, run_id, "建库", "SQLite 表结构初始化完成", row_count=0)

    # 链接主数据阶段：读入映射表并写入主数据表。
    # 3) 主数据
    mapping_df, mapping_stats, _ = clean.load_mapping(config.MAPPING_FILE)
    dbmod.insert_dataframe(conn, "dim_item_mapping", mapping_df, list(mapping_df.columns))
    dbmod.write_etl_log(conn, run_id, "映射表载入",
                        f"映射 {mapping_stats['mapping_rows']} 行，"
                        f"款 {mapping_stats['style_count']} 个",
                        row_count=mapping_stats["mapping_rows"])
    if verbose:
        print(f"[映射表] {mapping_stats['mapping_rows']} 行链接映射，"
              f"{mapping_stats['style_count']} 个款")

    # 三张源表清洗入库阶段：订单、商品效果、推广分别整理并写库。
    # 4) T1/T2/T3 清洗入库
    t1_stats_total: dict = {"read_rows": 0, "stored_rows": 0, "valid_rows": 0,
                            "invalid_rows": 0, "duplicate_rows": 0,
                            "valid_pay_amount": 0.0,
                            "refund_completed_amount": 0.0}
    # ② 处理主体数据
    t2_stats_total = {"read_rows": 0, "t2_rows": 0, "duplicate_keys": 0,
                      "invalid_date_rows": 0, "t2_pay_amount": 0.0}
    t3_stats_total = {"read_rows": 0, "t3_plan_rows": 0, "t3_item_rows": 0,
                      "t3_cost": 0.0, "t3_gmv": 0.0,
                      "multi_plan_item_days": 0}
    issue_counter: Counter = Counter()
    for shop in config.SHOPS:
        shop_dir = config.DATA_DIR / shop
        t1_file = sorted(shop_dir.glob("订单导出_*.csv"))[-1]
        t2_file = sorted(shop_dir.glob("商品效果_*.xlsx"))[-1]
        t3_file = sorted(shop_dir.glob("商品推广报表_*.xlsx"))[-1]

        order_df, order_stats, _ = clean.clean_t1(t1_file, shop)
        dbmod.insert_dataframe(conn, "fact_order_line", order_df, list(order_df.columns))
        for key in ("read_rows", "stored_rows", "valid_rows", "invalid_rows",
                    "duplicate_rows"):
            t1_stats_total[key] += order_stats[key]
        t1_stats_total["valid_pay_amount"] += order_stats["valid_pay_amount"]
        t1_stats_total["refund_completed_amount"] += order_stats["refund_completed_amount"]
        _merge_counters(issue_counter, order_stats["issue_counter"])
        dbmod.write_etl_log(
            conn, run_id, "T1 订单清洗",
            f"{shop}：读入 {order_stats['read_rows']} 行，有效 "
            f"{order_stats['valid_rows']} 行，实付合计 "
            f"{order_stats['valid_pay_amount']:.2f}",
            row_count=order_stats["valid_rows"])

        t2_df, t2_stats = clean.clean_t2(t2_file, shop)
        dbmod.insert_dataframe(conn, "fact_item_traffic_daily", t2_df,
                               ["shop_id"] + clean.T2_EN)
        for key in ("read_rows", "t2_rows", "duplicate_keys", "invalid_date_rows"):
            t2_stats_total[key] += t2_stats[key]
        t2_stats_total["t2_pay_amount"] += t2_stats["t2_pay_amount"]
        dbmod.write_etl_log(conn, run_id, "T2 商品效果清洗",
                            f"{shop}：入库 {t2_stats['t2_rows']} 行",
                            row_count=t2_stats["t2_rows"])

        t3_plan_df, t3_item_df, t3_stats, _ = clean.clean_t3(t3_file, shop)
        dbmod.insert_dataframe(conn, "fact_ad_plan_daily", t3_plan_df,
                               list(t3_plan_df.columns))
        dbmod.insert_dataframe(conn, "fact_ad_item_daily", t3_item_df,
                               list(t3_item_df.columns))
        for key in ("read_rows", "t3_plan_rows", "t3_item_rows", "multi_plan_item_days"):
            t3_stats_total[key] += t3_stats[key]
        t3_stats_total["t3_cost"] += t3_stats["t3_cost"]
        t3_stats_total["t3_gmv"] += t3_stats["t3_gmv"]
        dbmod.write_etl_log(conn, run_id, "T3 商品推广清洗",
                            f"{shop}：计划日 {t3_stats['t3_plan_rows']} 行，"
                            f"商品日 {t3_stats['t3_item_rows']} 行",
                            row_count=t3_stats["t3_plan_rows"])

    # 宽表阶段：汇总三张源表，生成按日期和链接的经营数据。
    # 5) 宽表与静默合计校验
    _, _, wide_meta = build_wide(conn, run_id)
    dbmod.write_etl_log(conn, run_id, "宽表构建",
                        f"宽表 {wide_meta['wide_rows']} 行，实付合计 "
                        f"{wide_meta['wide_pay']:.2f}", row_count=wide_meta["wide_rows"])
    data_ok = abs(wide_meta["diff"]) < 0.005
    if verbose:
        print(f"[宽表] {wide_meta['wide_rows']} 行；金额合计 {wide_meta['wide_pay']:,.2f} 元")

    # 6) 链接管理标签
    tag_stats = link_tags.init_management(conn, preserved_tags)
    seed_stats = link_tags.seed_demo_tags(conn)
    tag_stats["rows"] = seed_stats.get("rows", tag_stats["rows"])
    tag_stats["tagged"] = seed_stats.get("tagged", tag_stats["tagged"])
    tag_stats["seeded"] = seed_stats.get("seeded", 0)
    dbmod.write_etl_log(conn, run_id, "链接管理",
                        f"link_tags {tag_stats['rows']} 条", row_count=tag_stats["rows"])
    if verbose:
        print(f"[链接管理] link_tags {tag_stats['rows']} 条")

    elapsed = (datetime.now() - started).total_seconds()
    dbmod.write_etl_log(conn, run_id, "完成", f"数据管线耗时 {elapsed:.1f} 秒")
    if verbose:
        print(f"[数据就绪] 数据就绪：{t1_stats_total['valid_rows']} 行")
        print(f"[数据管线] 完成，耗时 {elapsed:.1f} 秒；"
              f"数据库 {config.DB_PATH.relative_to(config.BASE_DIR)}")

    context = {
        "run_id": run_id,
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "mapping": mapping_stats,
        "t1": t1_stats_total,
        "t1_issue_counter": dict(issue_counter.most_common()),
        "t2": t2_stats_total,
        "t3": t3_stats_total,
        "wide": wide_meta,
        "data_ok": data_ok,
        "link_tags": tag_stats,
        "goals": goals.get_goals(conn),
        "table_counts": dbmod.table_counts(conn),
        "db_path": str(config.DB_PATH),
    }
    conn.close()
    # ③ 整理并返回结果
    return context
