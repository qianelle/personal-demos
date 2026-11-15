# -*- coding: utf-8 -*-
# 链接标签数据
# 作用：维护链接标签、链接池记录与标签写入记录。
""" 链接标签（单表 link_tags）。

约束：
  * 唯一新增表 link_tags(shop_id, item_id, tag, owner, updated_by, updated_at)；
  * 标签单选，五选一；不新增标签既有表，变更记录写入 output/标签变更日志.md；
  * 系统不自动判定标签，初始标签仅为模拟数据中的既有人工设置；
  * owner 字段既有保留； 页面不读取、不展示、不参与逻辑。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import config
from src.models import db as dbmod


# _link_exists_table
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def _link_exists_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'link_tags'"
    ).fetchone()
    return bool(row and row[0])


# snapshot_link_tags
# 作用：数据库重建前快照 link_tags，避免人工标签被模拟数据重建覆盖。
def snapshot_link_tags(db_path: Path) -> pd.DataFrame | None:
    """数据库重建前快照 link_tags，避免人工标签被模拟数据重建覆盖。"""
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='link_tags'"
        ).fetchone()[0]
        if not exists:
            conn.close()
            return None
        df = pd.read_sql_query("SELECT * FROM link_tags", conn)
        conn.close()
        return df
    except (sqlite3.Error, pd.errors.DatabaseError):
        return None


# _stable_hash
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def _stable_hash(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


# _owner_for
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def _owner_for(shop_id: str, item_id: str) -> str:
    pool = config.OWNER_POOL.get(shop_id) or [config.DEMO_OPERATOR]
    return pool[_stable_hash(item_id) % len(pool)]


# _collect_links
# 作用：收集全部链接（含未映射链接），并补映射属性与近 30 天表现。
def _collect_links(conn: sqlite3.Connection) -> pd.DataFrame:
    """收集全部链接（含未映射链接），并补映射属性与近 30 天表现。"""
    keys = dbmod.query_df(
        conn,
        "SELECT shop_id, item_id FROM dim_item_mapping "
        "UNION SELECT shop_id, item_id FROM fact_wide_daily",
    )
    if keys.empty:
        return keys
    window_start = (config.END_DATE - pd.Timedelta(days=config.ZERO_SALES_DAYS - 1)
                    ).strftime("%Y-%m-%d")
    window_end = config.END_DATE.strftime("%Y-%m-%d")
    perf = dbmod.query_df(
        conn,
        "SELECT shop_id, item_id, ROUND(SUM(pay_amount), 2) AS pay_30d, "
        "       COALESCE(SUM(units), 0) AS units_30d, "
        "       COALESCE(SUM(pay_buyers), 0) AS pay_buyers_30d "
        "FROM fact_wide_daily WHERE stat_date BETWEEN ? AND ? "
        "GROUP BY shop_id, item_id", (window_start, window_end))
    mapping = dbmod.query_df(
        conn,
        "SELECT shop_id, item_id, item_title, style_code, category_l2, is_primary, "
        "       item_status, launch_date FROM dim_item_mapping")
    links = keys.merge(mapping, on=["shop_id", "item_id"], how="left")
    links = links.merge(perf, on=["shop_id", "item_id"], how="left")
    for col in ("pay_30d", "units_30d", "pay_buyers_30d"):
        links[col] = pd.to_numeric(links[col], errors="coerce").fillna(0)
    links["launch_date"] = links["launch_date"].fillna("")
    links["is_primary"] = pd.to_numeric(links["is_primary"], errors="coerce").fillna(0).astype(int)
    return links


# init_management
# 作用：初始化链接管理表：不预置任何链接；只恢复运营之前手工添加的记录。
def init_management(conn: sqlite3.Connection,
                    preserved: pd.DataFrame | None = None) -> dict:
    """初始化链接管理表：不预置任何链接；只恢复运营之前手工添加的记录。

    B2 规则：220 条在售链接只是可选池，系统绝不自动灌入管理表；
    首次运行 link_tags 为空，由运营通过「添加链接」建立管理记录。
    """
    # ① 准备输入与上下文
    restored = 0
    if preserved is not None and not preserved.empty:
        rows = []
        for rec in preserved.fillna("").to_dict(orient="records"):
            shop_id = str(rec.get("shop_id") or "")
            item_id = str(rec.get("item_id") or "")
            tag = str(rec.get("tag") or "")
            if not shop_id or not item_id:
                continue
            # 演示预置数据每次重建后重新生成，不作为运营手工记录恢复
            if str(rec.get("updated_by") or "") == "演示预置":
                continue
            if tag and tag not in config.MANAGEMENT_TAG_OPTIONS:
                tag = ""
            pool = conn.execute(
                "SELECT 1 FROM dim_item_mapping WHERE shop_id = ? AND item_id = ?",
                (shop_id, item_id)).fetchone()
            if not pool:
                continue
            rows.append((shop_id, item_id, tag or None,
                         str(rec.get("owner") or config.DEMO_OPERATOR),
                         str(rec.get("updated_by") or config.DEMO_OPERATOR),
                         str(rec.get("updated_at") or "")))
            restored += 1
        if rows:
            conn.executemany(
                "INSERT OR REPLACE INTO link_tags "
                "(shop_id, item_id, tag, owner, updated_by, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)", rows)
            conn.commit()
    # ② 处理主体数据
    total = conn.execute("SELECT COUNT(*) FROM link_tags").fetchone()[0]
    tagged = conn.execute("SELECT COUNT(*) FROM link_tags WHERE tag IS NOT NULL "
                          "AND tag <> ''").fetchone()[0]
    # ③ 整理并返回结果
    return {"rows": int(total), "tagged": int(tagged), "restored": restored,
            "owner_count": len(owner_options(conn))}


# owner_options
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def owner_options(conn: sqlite3.Connection) -> list[str]:
    try:
        rows = conn.execute(
            "SELECT DISTINCT owner FROM dim_item_mapping WHERE owner IS NOT NULL "
            "AND owner <> '' ORDER BY owner").fetchall()
        return [row[0] for row in rows]
    except sqlite3.Error:
        return []


# tag_counts
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def tag_counts(conn: sqlite3.Connection, shop_id: str = "", owner: str = "") -> dict:
    clauses = ["1 = 1"]
    params: list = []
    if shop_id:
        clauses.append("shop_id = ?")
        params.append(shop_id)
    if owner:
        clauses.append("owner = ?")
        params.append(owner)
    rows = conn.execute(
        "SELECT tag, COUNT(*) AS n FROM link_tags WHERE " + " AND ".join(clauses) +
        " GROUP BY tag", params).fetchall()
    counts = {tag: 0 for tag in config.TAG_OPTIONS}
    counts["未设置"] = 0
    for row in rows:
        tag = row[0] or "未设置"
        counts[tag] = counts.get(tag, 0) + row[1]
    return counts


# _append_change_log
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def _append_change_log(operator: str, tag: str, ok_items: list[str],
                       skipped_items: list[str]) -> Path:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUT_DIR / "标签变更日志.md"
    if not path.exists():
        path.write_text(
            "# 标签变更日志\n\n"
            "本文件由「我的链接 · 标签管理」批量设置写入，记录每次标签变更的操作人、"
            "标签、命中与未命中链接。当前标签为单选；标签既有仅记录在本文件，不新增数据库表。\n\n",
            encoding="utf-8")
    lines = [f"## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 批量设置标签", "",
             f"- 操作人：{operator}",
             f"- 目标标签：{tag}",
             f"- 命中并写入：{len(ok_items)} 条",
             f"- 未命中跳过：{len(skipped_items)} 条",
             f"- 命中链接：{', '.join(ok_items) if ok_items else '无'}",
             f"- 未命中链接：{', '.join(skipped_items) if skipped_items else '无'}",
             ""]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


# _append_change_rows
# 作用：rows: (item_id, old_tag, new_tag)。
def _append_change_rows(action: str, operator: str,
                        rows: list[tuple[str, str, str]]) -> Path:
    """rows: (item_id, old_tag, new_tag)"""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUT_DIR / "标签变更日志.md"
    if not path.exists():
        path.write_text(
            "# 标签变更日志\n\n"
            "本文件记录「链接管理」的标签变更与添加/移除操作；标签为单选、人工写入，"
            "系统不自动判定任何标签。字段：时间 / 操作人 / 链接ID / 旧标签 / 新标签。\n\n",
            encoding="utf-8")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"## {stamp} {action}", "",
             "| 时间 | 操作人 | 链接ID | 旧标签 | 新标签 |",
             "| --- | --- | --- | --- | --- |"]
    for item_id, old_tag, new_tag in rows:
        lines.append(f"| {stamp} | {operator} | {item_id} | "
                     f"{old_tag or '未打标'} | {new_tag or '未打标'} |")
    lines.append("")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


# update_tags
# 作用：批量设置标签：只更新管理表中已存在的链接；记录旧标签与新标签。
def update_tags(conn: sqlite3.Connection, item_ids: list[str], tag: str,
                operator: str | None = None) -> dict:
    """批量设置标签：只更新管理表中已存在的链接；记录旧标签与新标签。"""
    # ① 准备输入与上下文
    operator = operator or config.DEMO_OPERATOR
    if tag not in config.MANAGEMENT_TAG_OPTIONS:
        return {"ok": 0, "skipped": len(item_ids), "ok_items": [],
                "skipped_items": item_ids, "error": "标签不在允许范围内"}
    cleaned = []
    seen = set()
    for item in item_ids:
        item = (item or "").strip()
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    if not cleaned:
        return {"ok": 0, "skipped": 0, "ok_items": [], "skipped_items": [],
                "error": "未提供链接 ID"}
    placeholders = ",".join(["?"] * len(cleaned))
    rows = conn.execute(
        f"SELECT shop_id, item_id, COALESCE(tag, '') AS tag FROM link_tags "
        f"WHERE item_id IN ({placeholders})", cleaned).fetchall()
    # ② 处理主体数据
    old_tags = {row["item_id"]: row["tag"] for row in rows}
    ok_items = [item for item in cleaned if item in old_tags]
    skipped_items = [item for item in cleaned if item not in old_tags]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if ok_items:
        marks = ",".join(["?"] * len(ok_items))
        conn.execute(
            f"UPDATE link_tags SET tag = ?, updated_by = ?, updated_at = ? "
            f"WHERE item_id IN ({marks})", [tag, operator, now] + ok_items)
        conn.commit()
    log_rows = [(item, old_tags[item], tag) for item in ok_items]
    log_path = _append_change_rows("批量设置标签", operator, log_rows)
    # ③ 整理并返回结果
    return {"ok": len(ok_items), "skipped": len(skipped_items),
            "ok_items": ok_items, "skipped_items": skipped_items,
            "error": "", "log_path": str(log_path), "log_rows": log_rows}


# add_links
# 作用：运营主动添加链接：只能在在售可选池中选择，不预填、不自动打标。
def add_links(conn: sqlite3.Connection, item_ids: list[str],
              operator: str | None = None) -> dict:
    """运营主动添加链接：只能在在售可选池中选择，不预填、不自动打标。"""
    # ① 准备输入与上下文
    operator = operator or config.DEMO_OPERATOR
    cleaned = []
    seen = set()
    for item in item_ids:
        item = (item or "").strip()
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    if not cleaned:
        return {"added": 0, "missing": [], "existing": [], "operator": operator}
    placeholders = ",".join(["?"] * len(cleaned))
    pool_rows = conn.execute(
        f"SELECT shop_id, item_id FROM dim_item_mapping "
        f"WHERE item_status = '在售' AND item_id IN ({placeholders})",
        cleaned).fetchall()
    pool = {row["item_id"]: row["shop_id"] for row in pool_rows}
    # ② 处理主体数据
    existing_rows = conn.execute(
        f"SELECT item_id FROM link_tags WHERE item_id IN ({placeholders})",
        cleaned).fetchall()
    existing = {row["item_id"] for row in existing_rows}
    added, missing, already = [], [], []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in cleaned:
        if item not in pool:
            missing.append(item)
        elif item in existing:
            already.append(item)
        else:
            conn.execute(
                "INSERT INTO link_tags (shop_id, item_id, tag, owner, updated_by, updated_at) "
                "VALUES (?, ?, NULL, ?, ?, ?)",
                (pool[item], item, operator, operator, now))
            added.append(item)
    conn.commit()
    if added:
        _append_change_rows("添加链接到管理表", operator,
                            [(item, "", "") for item in added])
    # ③ 整理并返回结果
    return {"added": len(added), "missing": missing, "existing": already,
            "operator": operator, "added_items": added}


# remove_links
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def remove_links(conn: sqlite3.Connection, item_ids: list[str],
                 operator: str | None = None) -> dict:
    operator = operator or config.DEMO_OPERATOR
    cleaned = []
    seen = set()
    for item in item_ids:
        item = (item or "").strip()
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    if not cleaned:
        return {"removed": 0, "missing": []}
    placeholders = ",".join(["?"] * len(cleaned))
    rows = conn.execute(
        f"SELECT item_id, COALESCE(tag, '') AS tag FROM link_tags "
        f"WHERE item_id IN ({placeholders})", cleaned).fetchall()
    existing = {row["item_id"]: row["tag"] for row in rows}
    removed_items = [item for item in cleaned if item in existing]
    missing = [item for item in cleaned if item not in existing]
    if removed_items:
        marks = ",".join(["?"] * len(removed_items))
        conn.execute(f"DELETE FROM link_tags WHERE item_id IN ({marks})",
                     removed_items)
        conn.commit()
        _append_change_rows("从管理表移除链接", operator,
                            [(item, existing[item], "") for item in removed_items])
    return {"removed": len(removed_items), "missing": missing,
            "removed_items": removed_items}



# seed_demo_tags
# 作用：演示标签种子：在链接池内预置五类合理标签，其余链接保持未打标。
def seed_demo_tags(conn: sqlite3.Connection) -> dict:
    """ 演示标签种子：在链接池内预置五类合理标签，其余链接保持未打标。

    这是模拟的「既有人工打标结果」，只写入一次；运行期系统仍不自动判定标签。
    """
    # ① 准备输入与上下文
    existing = conn.execute("SELECT COUNT(*) FROM link_tags").fetchone()[0]
    if existing:
        return {"rows": int(existing), "seeded": 0, "tagged": 0}
    start_30 = (config.END_DATE - pd.Timedelta(days=29)).strftime("%Y-%m-%d")
    end = config.END_DATE.strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT m.shop_id, m.item_id, m.item_title, m.style_code, m.launch_date, "
        "       m.item_status, m.owner, "
        "       COALESCE(SUM(CASE WHEN w.stat_date BETWEEN ? AND ? "
        "                         THEN w.pay_amount ELSE 0 END), 0) AS sales30, "
        "       COALESCE(SUM(CASE WHEN w.stat_date BETWEEN ? AND ? "
        "                         THEN w.pay_buyers ELSE 0 END), 0) AS buyers30 "
        "FROM dim_item_mapping m "
        "LEFT JOIN fact_wide_daily w ON m.shop_id = w.shop_id AND m.item_id = w.item_id "
        "WHERE m.item_status = '在售' "
        "GROUP BY m.shop_id, m.item_id, m.item_title, m.style_code, m.launch_date, "
        "         m.item_status, m.owner",
        (start_30, end, start_30, end)).fetchall()
    links = [dict(r) for r in rows]
    links.sort(key=lambda r: (-float(r["sales30"] or 0), r["item_id"]))
    chosen: list[tuple[dict, str | None]] = []
    used: set[str] = set()

    # take
    # 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
    def take(candidates, tag, limit):
        count = 0
        for rec in candidates:
            if count >= limit:
                break
            if rec["item_id"] in used:
                continue
            used.add(rec["item_id"])
            chosen.append((rec, tag))
            count += 1
        return count

    # 主推 2：近 30 天销售额最高、款号不同
    main_used_styles = set()
    for rec in links:
        if len(main_used_styles) >= 2:
            break
        if rec["style_code"] in main_used_styles:
            continue
        main_used_styles.add(rec["style_code"])
        used.add(rec["item_id"])
        chosen.append((rec, "主推款"))
    # 动销 8：接下来销售额靠前的 8 条
    take([r for r in links if r["item_id"] not in used], "动销款", 8)

    # age
    # 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
    def age(rec) -> int:
        try:
            return (config.END_DATE - date.fromisoformat(str(rec["launch_date"]))).days + 1
        except (TypeError, ValueError):
            return 999

    # ② 处理主体数据
    potential = [r for r in links if age(r) <= 30 and float(r["buyers30"] or 0) >= 20]
    take(potential, "潜力款", 5)
    testing = [r for r in links if age(r) <= 30]
    test_added = take(testing, "测试款", 4)
    if test_added < 4:
        take([r for r in links if r["item_id"] not in used], "测试款", 4 - test_added)
    slow = [r for r in links if 30 <= age(r) <= 180]
    slow.sort(key=lambda r: (float(r["sales30"] or 0), r["item_id"]))
    take(slow, "滞销款", 10)
    now = f"{config.END_DATE.strftime('%Y-%m-%d')} 18:00:00"
    records = []
    for rec, tag in chosen:
        if not tag:
            continue
        records.append((rec["shop_id"], rec["item_id"], tag,
                        "演示环境", "演示预置", now))
    if records:
        conn.executemany(
            "INSERT OR REPLACE INTO link_tags "
            "(shop_id, item_id, tag, owner, updated_by, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            records)
        conn.commit()
    counts = {row[0] or "未打标": row[1] for row in conn.execute(
        "SELECT COALESCE(tag, ''), COUNT(*) FROM link_tags GROUP BY COALESCE(tag, '')")}
    # ③ 整理并返回结果
    return {"rows": len(records), "seeded": len(records),
            "tagged": len([1 for _, tag in chosen if tag]),
            "counts": counts}


# resolve_owner_scope
# 作用：解析数据范围参数：all / mine / owner:<运营>。返回空字符串表示全店。
def resolve_owner_scope(scope: str, owner: str = "") -> str:
    """解析数据范围参数：all / mine / owner:<运营>。返回空字符串表示全店。"""
    if not scope or scope == config.DATA_SCOPE_ALL:
        return ""
    if scope == config.DATA_SCOPE_MINE:
        return config.DEMO_OPERATOR
    if scope.startswith(config.DATA_SCOPE_OWNER_PREFIX):
        return scope[len(config.DATA_SCOPE_OWNER_PREFIX):] or owner
    return owner or ""


# link_owner
# 作用：完成链接标签数据中的该步骤，结果交给调用方继续使用。
def link_owner(conn: sqlite3.Connection, shop_id: str, item_id: str) -> str:
    row = conn.execute(
        "SELECT owner FROM link_tags WHERE shop_id = ? AND item_id = ?",
        (shop_id, item_id)).fetchone()
    return row[0] if row and row[0] else ""
