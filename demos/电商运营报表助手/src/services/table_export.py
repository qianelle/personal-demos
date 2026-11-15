# -*- coding: utf-8 -*-
# 表格导出
# 作用：把当前筛选结果写成 xlsx 表格。
"""当前筛选结果的表格导出（xlsx）。"""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

import config


# _plan_value
# 作用：完成表格导出中的该步骤，结果交给调用方继续使用。
def _plan_value(row, col):
    value = row.get(col["key"])
    if value is None:
        return ""
    kind = col.get("kind", "text")
    if kind == "money":
        return round(float(value), 2)
    if kind == "int":
        return int(float(value))
    if kind == "ratio":
        return round(float(value), 4)
    if kind == "pct":
        return f"{float(value) * 100:.2f}%"
    return str(value)


# build_plan_workbook
# 作用：完成表格导出中的该步骤，结果交给调用方继续使用。
def build_plan_workbook(rows: list[dict], columns: list[dict]) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "推广计划"
    ws.append([col["label"] for col in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([_plan_value(row, col) for col in columns])
    for idx, col in enumerate(columns, start=1):
        ws.column_dimensions[chr(64 + idx) if idx <= 26 else "A"].width = 16
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


# build_link_workbook
# 作用：完成表格导出中的该步骤，结果交给调用方继续使用。
def build_link_workbook(rows: list[dict], columns: list[dict]) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "链接管理"
    ws.append([col["label"] for col in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    money = {"sales", "ad_cost"}
    integer = {"serial", "units", "pay_buyers", "launch_days", "launch_buyers_30"}
    for row in rows:
        values = []
        for col in columns:
            key = col["key"]
            value = row.get(key)
            if value is None:
                values.append("")
            elif key in money:
                values.append(round(float(value), 2))
            elif key in integer:
                values.append(int(float(value)))
            elif key == "ad_spend_ratio":
                values.append(f"{float(value) * 100:.2f}%")
            else:
                values.append(str(value))
        ws.append(values)
    for idx, _ in enumerate(columns, start=1):
        ws.column_dimensions[chr(64 + idx) if idx <= 26 else "A"].width = 16
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


# range_name
# 作用：完成表格导出中的该步骤，结果交给调用方继续使用。
def range_name(filters=None) -> str:
    start = getattr(filters, "start", None) or config.START_DATE.strftime("%Y-%m-%d")
    end = getattr(filters, "end", None) or config.END_DATE.strftime("%Y-%m-%d")
    return f"{start.replace('-', '')}-{end.replace('-', '')}"
