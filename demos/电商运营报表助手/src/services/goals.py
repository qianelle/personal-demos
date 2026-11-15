# -*- coding: utf-8 -*-
# 目标设置
# 作用：读取、保存与恢复月度销售目标和付费占比上限。
""" 目标设置：唯一新增表 report_goals（单行）。

目标只作达成判定，不涉及薪酬计算。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import config
from src.models import db as dbmod

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS report_goals (
    goals_id INTEGER PRIMARY KEY CHECK (goals_id = 1),
    daily_sales_wan REAL,
    weekly_sales_wan REAL,
    monthly_sales_wan REAL,
    paid_ratio_limit REAL,
    updated_by TEXT,
    updated_at TEXT
)
"""


# ensure_table
# 作用：完成目标设置中的该步骤，结果交给调用方继续使用。
def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_SQL)
    conn.commit()


# get_goals
# 作用：完成目标设置中的该步骤，结果交给调用方继续使用。
def get_goals(conn: sqlite3.Connection) -> dict:
    ensure_table(conn)
    row = conn.execute("SELECT * FROM report_goals WHERE goals_id = 1").fetchone()
    data = {"daily_sales_wan": None, "weekly_sales_wan": None,
            "monthly_sales_wan": None, "paid_ratio_limit": None,
            "updated_by": "", "updated_at": ""}
    if row:
        data.update({key: row[key] for key in data})
    return data


# _clean_number
# 作用：完成目标设置中的该步骤，结果交给调用方继续使用。
def _clean_number(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(str(value).replace(",", "").strip()), 4)
    except (TypeError, ValueError):
        return None


# save_goals
# 作用：完成目标设置中的该步骤，结果交给调用方继续使用。
def save_goals(conn: sqlite3.Connection, form: dict,
               operator: str = config.DEMO_OPERATOR) -> dict:
    old = get_goals(conn)
    values = {key: _clean_number(form.get(key)) for key, _ in config.GOAL_FIELDS}
    #  只保留月度目标与月度付费占比上限；旧列写空，界面不再展示
    daily_value = None
    weekly_value = None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ensure_table(conn)
    conn.execute(
        "INSERT INTO report_goals (goals_id, daily_sales_wan, weekly_sales_wan, "
        "monthly_sales_wan, paid_ratio_limit, updated_by, updated_at) "
        "VALUES (1, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(goals_id) DO UPDATE SET "
        "daily_sales_wan=excluded.daily_sales_wan, "
        "weekly_sales_wan=excluded.weekly_sales_wan, "
        "monthly_sales_wan=excluded.monthly_sales_wan, "
        "paid_ratio_limit=excluded.paid_ratio_limit, "
        "updated_by=excluded.updated_by, updated_at=excluded.updated_at",
        [daily_value, weekly_value,
         values["monthly_sales_wan"], values["paid_ratio_limit"], operator, now])
    conn.commit()
    _append_log(old, values, operator, now)
    return get_goals(conn)


# _append_log
# 作用：完成目标设置中的该步骤，结果交给调用方继续使用。
def _append_log(old: dict, new: dict, operator: str, now: str) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.GOAL_LOG_FILE
    if not path.exists():
        path.write_text(
            "# 目标变更日志\n\n"
            "本文件记录目标设置变更；目标只用于报表达成判定，不涉及薪酬计算。\n\n",
            encoding="utf-8")
    labels = {key: label for key, label in config.GOAL_FIELDS}
    lines = [f"## {now} {operator}", "",
             "| 时间 | 操作人 | 目标项 | 旧值 | 新值 |",
             "| --- | --- | --- | ---: | ---: |"]
    for key, label in labels.items():
        old_value = old.get(key)
        new_value = new.get(key)
        if old_value != new_value:
            lines.append(f"| {now} | {operator} | {label} | "
                         f"{old_value if old_value is not None else '空'} | "
                         f"{new_value if new_value is not None else '空'} |")
    lines.append("")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# snapshot_goals
# 作用：完成目标设置中的该步骤，结果交给调用方继续使用。
def snapshot_goals(db_path: Path) -> dict | None:
    if not Path(db_path).exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        ensure_table(conn)
        row = conn.execute("SELECT * FROM report_goals WHERE goals_id = 1").fetchone()
        data = dict(row) if row else None
        conn.close()
        return data
    except sqlite3.Error:
        return None


# restore_goals
# 作用：完成目标设置中的该步骤，结果交给调用方继续使用。
def restore_goals(conn: sqlite3.Connection, record: dict | None) -> None:
    if not record:
        return
    ensure_table(conn)
    conn.execute(
        "INSERT OR REPLACE INTO report_goals (goals_id, daily_sales_wan, "
        "weekly_sales_wan, monthly_sales_wan, paid_ratio_limit, updated_by, updated_at) "
        "VALUES (1, ?, ?, ?, ?, ?, ?)",
        [record.get("daily_sales_wan"), record.get("weekly_sales_wan"),
         record.get("monthly_sales_wan"), record.get("paid_ratio_limit"),
         record.get("updated_by") or config.DEMO_OPERATOR,
         record.get("updated_at") or ""])
    conn.commit()
