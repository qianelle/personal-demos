# -*- coding: utf-8 -*-
# 源文件探测
# 作用：查看源文件编码、行列数、表头和首行样例。
"""源文件探测。

读入前先探测：真实编码、BOM、换行、行列数、表头、首行样例、sheet 名称。
探测结果与表头依据文件（docs/source_schema/）逐列比对，不一致直接报错，
不采用任何硬编码假设。
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from src.etl import field_spec


# _detect_encoding
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def _detect_encoding(path: Path) -> tuple[str, bool, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", True, "检测到 UTF-8 BOM"
    try:
        raw.decode("utf-8", errors="strict")
        return "utf-8", False, "UTF-8 严格解码通过"
    except UnicodeDecodeError:
        pass
    try:
        raw.decode("gbk", errors="strict")
        return "gbk", False, "GBK 严格解码通过（GB18030 子集）"
    except UnicodeDecodeError:
        return "gb18030", False, "GBK 解码失败，按 GB18030 读取"


# _detect_line_ending
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def _detect_line_ending(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and not lf:
        return "CRLF"
    if lf and not crlf:
        return "LF"
    if crlf and lf:
        return f"混合（CRLF={crlf} / LF={lf}）"
    return "未知"


# probe_csv
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def probe_csv(path: Path, table_id: str, shop_id: str) -> dict:
    # ① 准备输入与上下文
    encoding, has_bom, note = _detect_encoding(path)
    raw = path.read_bytes()
    text = raw.decode(encoding)
    with open(path, "r", encoding=encoding, newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        first_row = next(reader, [])
        row_count = 1  # 数据行（不含表头）
        for _ in reader:
            row_count += 1
    # ② 处理主体数据
    expected = [f["cn"] for f in field_spec.T1_FIELDS]
    if header != expected:
        raise ValueError(
            f"T1 表头与依据不一致：{path}\n实际：{header}\n依据：{expected}")
    if len(first_row) != len(header):
        raise ValueError(f"T1 首行列数与表头不一致：{path}")
    # ③ 整理并返回结果
    return {
        "shop_id": shop_id,
        "table_id": table_id,
        "file_path": str(path),
        "file_type": "csv",
        "encoding": encoding,
        "has_bom": int(has_bom),
        "line_ending": _detect_line_ending(raw),
        "row_count": row_count,
        "column_count": len(header),
        "sheet_names": "",
        "header_json": json.dumps(header, ensure_ascii=False),
        "first_row_json": json.dumps(first_row, ensure_ascii=False),
        "note": note,
    }


# probe_xlsx
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def probe_xlsx(path: Path, table_id: str, shop_id: str,
               sheet_name: str | None, expected_headers: list[str]) -> dict:
    # ① 准备输入与上下文
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    sheet_names = wb.sheetnames
    if sheet_name is not None and sheet_name in sheet_names:
        ws = wb[sheet_name]
    else:
        ws = wb[sheet_names[0]]
    rows_iter = ws.iter_rows(values_only=True)
    header = list(next(rows_iter))
    first_row = list(next(rows_iter, []))
    # ② 处理主体数据
    row_count = 0
    for _ in rows_iter:
        row_count += 1
    row_count += 1  # 首行数据已被单独取出
    wb.close()
    if header != expected_headers:
        raise ValueError(
            f"{table_id} 表头与依据不一致：{path}\n实际：{header}\n依据：{expected_headers}")
    first_row_view = [str(v) if v is not None else "" for v in first_row]
    # ③ 整理并返回结果
    return {
        "shop_id": shop_id,
        "table_id": table_id,
        "file_path": str(path),
        "file_type": "xlsx",
        "encoding": "xlsx（OLE/XML 容器，无文本编码）",
        "has_bom": 0,
        "line_ending": "—",
        "row_count": row_count,
        "column_count": len(header),
        "sheet_names": json.dumps(sheet_names, ensure_ascii=False),
        "header_json": json.dumps(header, ensure_ascii=False),
        "first_row_json": json.dumps(first_row_view, ensure_ascii=False),
        "note": f"读取 sheet：{ws.title}",
    }


# probe_all
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def probe_all(data_dir: Path, shops: list[str]) -> list[dict]:
    records: list[dict] = []
    t2_headers = [f["cn"] for f in field_spec.T2_FIELDS]
    t3_headers = [f["cn"] for f in field_spec.T3_FIELDS]
    for shop in shops:
        shop_dir = data_dir / shop
        t1_files = sorted(shop_dir.glob("订单导出_*.csv"))
        t2_files = sorted(shop_dir.glob("商品效果_*.xlsx"))
        t3_files = sorted(shop_dir.glob("商品推广报表_*.xlsx"))
        if not t1_files or not t2_files or not t3_files:
            raise FileNotFoundError(f"{shop_dir} 缺少源文件：T1={len(t1_files)} "
                                    f"T2={len(t2_files)} T3={len(t3_files)}")
        records.append(probe_csv(t1_files[-1], "T1_千牛订单", shop))
        records.append(probe_xlsx(t2_files[-1], "T2_商品效果", shop, None, t2_headers))
        records.append(probe_xlsx(t3_files[-1], "T3_商品推广", shop,
                                  field_spec.T3_SHEET_NAME, t3_headers))
    return records


# probe_mapping
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def probe_mapping(path: Path) -> dict:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows_iter = ws.iter_rows(values_only=True)
    header = [str(v) for v in next(rows_iter)]
    first_row = [str(v) if v is not None else "" for v in next(rows_iter, [])]
    row_count = 0
    for _ in rows_iter:
        row_count += 1
    row_count += 1  # 首行数据已被单独取出
    wb.close()
    expected = [name for name, _ in field_spec.MAPPING_FIELDS]
    if header != expected:
        raise ValueError(f"主数据映射表表头不一致：{header} / 期望 {expected}")
    return {
        "shop_id": "全部",
        "table_id": "商品主数据映射表",
        "file_path": str(path),
        "file_type": "xlsx",
        "encoding": "xlsx（OLE/XML 容器，无文本编码）",
        "has_bom": 0,
        "line_ending": "—",
        "row_count": row_count,
        "column_count": len(header),
        "sheet_names": json.dumps(wb.sheetnames, ensure_ascii=False),
        "header_json": json.dumps(header, ensure_ascii=False),
        "first_row_json": json.dumps(first_row, ensure_ascii=False),
        "note": "主数据映射表，粒度 shop_id + item_id",
    }


# format_probe_report
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def format_probe_report(records: list[dict]) -> str:
    lines = ["# 源文件探测报告", "",
             f"探测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "",
             "读入前对每个文件逐一探测编码、行列数、表头与首行样例；"
             "表头与 docs/source_schema/ 依据文件逐字比对，不一致即中止。", ""]
    for rec in records:
        lines.append(f"## {rec['table_id']} · {rec['shop_id']}")
        lines.append("")
        lines.append(f"- 文件：`{Path(rec['file_path']).name}`")
        lines.append(f"- 文件类型：{rec['file_type']}")
        lines.append(f"- 实际编码：{rec['encoding']}；BOM：{'有' if rec['has_bom'] else '无'}；"
                     f"换行：{rec['line_ending']}")
        if rec["sheet_names"]:
            lines.append(f"- sheet：{rec['sheet_names']}")
        lines.append(f"- 数据行数：{rec['row_count']}；列数：{rec['column_count']}")
        header = json.loads(rec["header_json"])
        lines.append(f"- 表头（{len(header)} 列）：{ ' | '.join(header) }")
        first = json.loads(rec["first_row_json"])
        sample = " | ".join(str(v)[:30] for v in first[:12])
        lines.append(f"- 首行样例（前 12 列）：{sample}")
        lines.append(f"- 说明：{rec['note']}")
        lines.append("")
    return "\n".join(lines)


# print_probe
# 作用：完成源文件探测中的该步骤，结果交给调用方继续使用。
def print_probe(records: list[dict]) -> None:
    print("[文件探测] 开始逐个探测源文件（编码 / 行列数 / 表头 / 首行样例）")
    for rec in records:
        header = json.loads(rec["header_json"])
        print("[文件探测] %-18s %-6s 编码=%-10s BOM=%s 行=%6d 列=%2d 文件=%s"
              % (rec["table_id"], rec["shop_id"], rec["encoding"],
                 "有" if rec["has_bom"] else "无", rec["row_count"],
                 rec["column_count"], Path(rec["file_path"]).name))
        print("[文件探测]   表头：%s" % " | ".join(header))
        first = json.loads(rec["first_row_json"])
        print("[文件探测]   首行：%s" % (" | ".join(str(v)[:24] for v in first[:8])))
