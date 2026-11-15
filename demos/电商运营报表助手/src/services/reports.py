# -*- coding: utf-8 -*-
# 报表数据与导出
# 作用：生成日报、周报、月报的数据、图表与自包含 HTML。
""" 数据报表：日报 / 周报 / 月报固定模板、目标达成、快照与导出。"""

from __future__ import annotations

import html as html_lib
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import config
from src.models import db as dbmod
from src.services import analysis as chart_helpers, goals, metrics
from src.services.filters import Filters

TAB_LABELS = {item["key"]: item["label"] for item in config.REPORT_TABS}


# _filters_on
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _filters_on(filters: Filters, start: date, end: date) -> Filters:
    return Filters(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"),
                   shop_id=filters.shop_id, category_l2=filters.category_l2,
                   style_code=filters.style_code, item_ids=list(filters.item_ids),
                   primary_only=filters.primary_only, tags=list(filters.tags),
                   scope=filters.scope, owner=filters.owner)


# _last_full_week_end
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _last_full_week_end(anchor: date) -> date:
    # ISO 周一=0；数据截止日若为周日，则它就是上一自然周的最后一天。
    if anchor.weekday() == 6:
        return anchor
    return anchor - timedelta(days=anchor.weekday() + 1)


# report_period
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def report_period(tab: str, anchor: date | None = None) -> dict:
    # ① 准备输入与上下文
    anchor = anchor or config.END_DATE
    if tab == "daily":
        start = end = anchor
        prev_start = prev_end = anchor - timedelta(days=1)
        label = "日报"
        note = "昨日 vs 前日"
    elif tab == "monthly":
        start = anchor.replace(day=1)
        end = anchor
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        # 本月至今 vs 上月同期（同一自然日跨度）
        span = (end - start).days
        prev_end = min(prev_start + timedelta(days=span), prev_end)
        label = "月报"
        note = "本月至今 vs 上月同期"
    else:
        tab = "weekly"
        end = _last_full_week_end(anchor)
        start = end - timedelta(days=6)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=6)
        label = "周报"
        note = "上一自然周 vs 前一自然周"
    # ② 处理主体数据
    if tab == "daily":
        range_label = f"{start.strftime('%m/%d')}（昨日）"
    elif tab == "weekly":
        range_label = (f"{start.strftime('%m/%d')}-{end.strftime('%m/%d')}"
                       f"（上一自然周 周一至周日）")
    else:
        range_label = (f"{start.strftime('%m/%d')}-{end.strftime('%m/%d')}"
                       f"（本月至今 {(end - start).days + 1} 天）")
    # ③ 整理并返回结果
    return {"tab": tab, "label": label, "note": note,
            "start": start, "end": end,
            "prev_start": prev_start, "prev_end": prev_end,
            "range_label": range_label,
            "prev_label": f"{prev_start.strftime('%m/%d')}~{prev_end.strftime('%m/%d')}",
            "file_range": f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"}


# _aggregate
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _aggregate(conn, flt: Filters) -> pd.DataFrame:
    where, params = flt.wide_where("w")
    return dbmod.query_df(
        conn,
        f"SELECT w.shop_id, w.item_id, COALESCE(m.item_title, w.item_id) AS item_title, "
        f"       COALESCE(m.style_code, w.style_code, '') AS style_code, "
        f"       COALESCE(lt.tag, '') AS tag, "
        f"       ROUND(SUM(w.pay_amount), 2) AS sales, "
        f"       ROUND(SUM(w.net_amount), 2) AS net_sales, "
        f"       COALESCE(SUM(w.units), 0) AS units, "
        f"       COALESCE(SUM(w.visitors), 0) AS visitors, "
        f"       COALESCE(SUM(w.pay_buyers), 0) AS pay_buyers, "
        f"       ROUND(SUM(w.refund_amount), 2) AS refund_amount, "
        f"       ROUND(SUM(w.ad_cost), 2) AS ad_cost, "
        f"       ROUND(SUM(w.ad_gmv), 2) AS ad_gmv "
        f"FROM fact_wide_daily w "
        f"LEFT JOIN dim_item_mapping m ON w.shop_id = m.shop_id AND w.item_id = m.item_id "
        f"LEFT JOIN link_tags lt ON w.shop_id = lt.shop_id AND w.item_id = lt.item_id "
        f"WHERE {where} GROUP BY w.shop_id, w.item_id "
        f"ORDER BY sales DESC", params)


# report_rows
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def report_rows(conn, filters: Filters, period: dict) -> pd.DataFrame:
    cur = _aggregate(conn, _filters_on(filters, period["start"], period["end"]))
    prev = _aggregate(conn, _filters_on(filters, period["prev_start"], period["prev_end"]))
    prev_map = {(r["shop_id"], r["item_id"]): r["sales"] for _, r in prev.iterrows()}
    frame = cur.copy()
    if frame.empty:
        return frame
    frame["prev_value"] = frame.apply(
        lambda r: prev_map.get((r["shop_id"], r["item_id"]), 0.0), axis=1)
    frame["wow"] = frame.apply(
        lambda r: ((r["sales"] - r["prev_value"]) / r["prev_value"])
        if r["prev_value"] else None, axis=1)
    frame["conversion_rate"] = frame.apply(
        lambda r: r["pay_buyers"] / r["visitors"] if r["visitors"] else None, axis=1)
    frame["refund_rate"] = frame.apply(
        lambda r: r["refund_amount"] / r["sales"] if r["sales"] else None, axis=1)
    frame["roi"] = frame.apply(
        lambda r: r["ad_gmv"] / r["ad_cost"] if r["ad_cost"] else None, axis=1)
    frame["paid_ratio"] = frame.apply(
        lambda r: r["ad_cost"] / r["sales"] if r["sales"] else None, axis=1)

    frame["period_label"] = f"{period['start']}~{period['end']}"
    frame["shop_name"] = frame["shop_id"].map(config.shop_display)
    frame["tag"] = frame["tag"].fillna("").replace("", "未打标")
    frame["item_title"] = frame["item_title"].fillna("")
    frame["action"] = ""
    frame["caliber_note"] = "支付口径；净销售额=实付−已完结退款；归因7日"
    return frame


# report_kpis
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def report_kpis(conn, filters: Filters, period: dict) -> dict:
    cur = metrics.period_kpis(conn, _filters_on(filters, period["start"], period["end"]))
    prev = metrics.period_kpis(conn, _filters_on(filters, period["prev_start"],
                                                period["prev_end"]))
    cur["prev"] = prev
    return cur


# goal_attainment
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def goal_attainment(conn, filters: Filters, period: dict) -> dict:
    # ① 准备输入与上下文
    settings = goals.get_goals(conn)
    month_start = config.END_DATE.replace(day=1)
    month_flt = _filters_on(filters, month_start, config.END_DATE)
    month_kpis = metrics.period_kpis(conn, month_flt)
    target_wan = settings.get("monthly_sales_wan")
    target_amount = round(float(target_wan) * 10000, 2) if target_wan is not None else None
    actual = round(float(month_kpis.get("net_sales") or 0), 2)
    # ② 处理主体数据
    if target_amount:
        rate = actual / target_amount
        diff = actual - target_amount
        judgment = "达成" if actual >= target_amount else "未达成"
    else:
        rate = diff = None
        judgment = "未设置目标"
    kpis = metrics.period_kpis(conn, _filters_on(filters, month_start, config.END_DATE))
    paid_ratio = kpis.get("ad_spend_ratio")
    limit_pct = settings.get("paid_ratio_limit")
    limit = (float(limit_pct) / 100.0) if limit_pct is not None else None
    if limit is not None and paid_ratio is not None:
        paid_ok = paid_ratio <= limit
        paid_judgment = "达成" if paid_ok else "未达成"
        excess_pp = max(0.0, (paid_ratio - limit) * 100)
        paid_note = (f"超出上限 {excess_pp:.2f} pp" if not paid_ok
                     else f"低于上限 {max(0.0, (limit - paid_ratio) * 100):.2f} pp")
    else:
        paid_judgment = "未设置上限"
        excess_pp = None
        paid_note = "未设置月度付费占比上限"
    rows = [
        {"item": "净销售额", "target": target_amount,
         "target_text": f"{target_wan} 万元" if target_wan is not None else "未设置",
         "actual": actual, "rate": rate, "diff": diff, "judgment": judgment},
        {"item": "付费占比", "target": limit,
         "target_text": f"≤ {limit_pct}%" if limit_pct is not None else "未设置",
         "actual": paid_ratio, "rate": None,
         "diff": (paid_ratio - limit) if (paid_ratio is not None and limit is not None) else None,
         "judgment": paid_judgment},
    ]
    # ③ 整理并返回结果
    return {"settings": settings, "rows": rows, "paid_ratio": paid_ratio,
            "paid_limit": limit, "paid_excess_pp": excess_pp,
            "paid_ok": (paid_ratio <= limit) if (paid_ratio is not None and limit is not None) else None,
            "paid_note": paid_note,
            "target_wan": target_wan, "target_amount": target_amount,
            "actual": actual, "kpis": kpis}


# _snapshot_path
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _snapshot_path(period: dict, filters: Filters) -> Path:
    config.REPORT_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scope = "我的链接" if filters.my_links_only else (filters.owner or "全部链接")
    return config.REPORT_SAVE_DIR / f"{period['tab']}_{scope}_{stamp}.json"


# latest_snapshot
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def latest_snapshot(tab: str) -> dict | None:
    if not config.REPORT_SAVE_DIR.exists():
        return None
    files = sorted(config.REPORT_SAVE_DIR.glob(f"{tab}_*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# snapshot_compare
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def snapshot_compare(period: dict, filters: Filters) -> str:
    last = latest_snapshot(period["tab"])
    if not last:
        return "首次生成，暂无上版"
    parts = []
    old_period = last.get("period", {})
    old_label = f"{old_period.get('start')}~{old_period.get('end')}"
    new_label = f"{period['start']}~{period['end']}"
    if old_label != new_label:
        parts.append(f"日期：{old_label} → {new_label}")
    old_scope = last.get("scope", "全店")
    new_scope = filters.scope_label
    if old_scope != new_scope:
        parts.append(f"范围：{old_scope} → {new_scope}")
    if not parts:
        return "与上版一致"
    return "；".join(parts)


# save_snapshot
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def save_snapshot(period: dict, filters: Filters, rows: int) -> Path:
    path = _snapshot_path(period, filters)
    payload = {
        "tab": period["tab"], "title": period["label"],
        "period": {"start": str(period["start"]), "end": str(period["end"]),
                   "prev_start": str(period["prev_start"]),
                   "prev_end": str(period["prev_end"])},
        "scope": filters.scope_label, "shop_count": 1 if filters.shop_id else 2,
        "includes_refund": True, "attribution_days": config.ATTRIBUTION_WINDOW_DAYS,
        "rows": rows, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": "交出去快照：仅记录口径与范围，不含自动发送与自动改数",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# _fmt_ratio
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _fmt_ratio(value):
    return round(float(value), 6) if value is not None else None


# export_report
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def export_report(conn, filters: Filters, tab: str, args=None) -> tuple[str, io.BytesIO]:
    # ① 准备输入与上下文
    period = report_period(tab)
    rows = report_rows(conn, filters, period)
    attain = goal_attainment(conn, filters, period)
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("固定模板")
    headers = [label for _, label in config.REPORT_COLUMNS]
    ws.append(headers)
    head_fill = PatternFill("solid", fgColor="1F4E79")
    for cell in ws[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    red_fill = PatternFill("solid", fgColor="FDE9E7")
    yellow_fill = PatternFill("solid", fgColor="FFF2CC")
    green_fill = PatternFill("solid", fgColor="E8F5EC")
    for rec in rows.to_dict(orient="records"):
        values = []
        for key, _ in config.REPORT_COLUMNS:
            value = rec.get(key)
            if key in ("sales", "net_sales", "ad_cost", "prev_value"):
                value = round(float(value or 0), 2)
            elif key in ("conversion_rate", "refund_rate", "paid_ratio", "wow"):
                value = _fmt_ratio(value)
            values.append(value if value is not None else "")
        ws.append(values)
        row_idx = ws.max_row
        if rec.get("wow") is not None:
            ws.cell(row=row_idx, column=17).fill = (green_fill if rec["wow"] >= 0
                                                    else red_fill)
        if (attain["paid_limit"] is not None and rec.get("paid_ratio") is not None
                and rec["paid_ratio"] > attain["paid_limit"]):
            ws.cell(row=row_idx, column=15).fill = yellow_fill
    # 表尾固定行
    tail = [
        ["合计", "", "", "", "", "", round(float(rows["sales"].sum()), 2) if not rows.empty else 0,
         round(float(rows["net_sales"].sum()), 2) if not rows.empty else 0,
         int(rows["units"].sum()) if not rows.empty else 0,
         int(rows["visitors"].sum()) if not rows.empty else 0, "", "",
         round(float(rows["ad_cost"].sum()), 2) if not rows.empty else 0, "", "", "", "", "", "", ""],
    ]
    for rec in tail:
        ws.append(rec)
    ws.append(["目标达成", f"净销售额 {attain['rows'][0]['judgment']}；"
                          f"付费占比 {attain['rows'][1]['judgment']}",
               "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    ws.append(["付费占比合规", attain["paid_note"], "", "", "", "", "", "", "", "", "", "",
               "", "", "", "", "", "", "", ""])
    ws.append(["口径注脚", "；".join(config.REPORT_CALIBER_NOTES), "", "", "", "", "", "",
               "", "", "", "", "", "", "", "", "", "", "", ""])
    # ② 处理主体数据
    ws.freeze_panes = "A2"
    for idx, _ in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = 14 if idx != 5 else 34
    # 目标达成 sheet
    ws2 = wb.create_sheet("目标达成")
    ws2.append(["项目", "目标", "实际", "达成率", "差额", "判定"])
    for cell in ws2[1]:
        cell.font = Font(bold=True)
    for rec in attain["rows"]:
        ws2.append([rec["item"], rec["target_text"], rec["actual"], rec["rate"],
                    rec["diff"], rec["judgment"]])
    ws2.append([])
    ws2.append(["说明", "目标只用于报表达成判定；薪酬相关金额不在系统计算范围。"])
    # 口径说明 sheet
    ws3 = wb.create_sheet("口径说明")
    ws3.append(["项目", "说明"])
    for note in config.REPORT_CALIBER_NOTES:
        ws3.append(["口径", note])
    ws3.append(["快照", snapshot_compare(period, filters)])
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    save_snapshot(period, filters, len(rows))
    scope_part = "我的链接" if filters.my_links_only else "全部链接"
    filename = (f"{period['label']}_{scope_part}_{period['file_range']}_"
                f"截止{config.END_DATE.strftime('%m%d')}.xlsx")
    # ③ 整理并返回结果
    return filename, buffer


# weekly_trend
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def weekly_trend(conn, filters: Filters, period: dict, weeks: int = 8) -> pd.DataFrame:
    end = period["end"]
    start = end - timedelta(days=weeks * 7 - 1)
    flt = _filters_on(filters, start, end)
    df = metrics.weekly_metrics(conn, flt)
    if df.empty:
        return df
    return df.tail(weeks)


# structure_change
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def structure_change(conn, filters: Filters, period: dict) -> pd.DataFrame:
    cur = metrics.category_structure(
        conn, _filters_on(filters, period["start"], period["end"]))
    prev = metrics.category_structure(
        conn, _filters_on(filters, period["prev_start"], period["prev_end"]))
    cur = cur.rename(columns={"sales": "cur_sales"})[["category_l2", "cur_sales"]]
    prev = prev.rename(columns={"sales": "prev_sales"})[["category_l2", "prev_sales"]]
    merged = cur.merge(prev, on="category_l2", how="outer").fillna(0)
    total_cur = float(merged["cur_sales"].sum()) or 1.0
    total_prev = float(merged["prev_sales"].sum()) or 1.0
    merged["cur_share"] = merged["cur_sales"] / total_cur
    merged["prev_share"] = merged["prev_sales"] / total_prev
    merged["share_change"] = merged["cur_share"] - merged["prev_share"]
    return merged.sort_values("cur_sales", ascending=False)


# declining_links
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def declining_links(conn, filters: Filters, period: dict, limit: int = 10) -> pd.DataFrame:
    weeks = []
    end = period["end"]
    for offset in range(3):
        w_end = end - timedelta(days=7 * offset)
        w_start = w_end - timedelta(days=6)
        df = metrics.item_ranking(
            conn, _filters_on(filters, w_start, w_end), limit=10000)
        df = df[["shop_id", "item_id", "style_code", "item_title", "sales"]].copy()
        df["week"] = offset
        weeks.append(df)
    if not weeks:
        return pd.DataFrame()
    frame = pd.concat(weeks, ignore_index=True)
    pivot = frame.pivot_table(index=["shop_id", "item_id", "style_code", "item_title"],
                              columns="week", values="sales", aggfunc="sum").fillna(0)
    if 0 not in pivot.columns or 1 not in pivot.columns or 2 not in pivot.columns:
        return pd.DataFrame()
    pivot["d0"] = pivot[0] - pivot[1]
    pivot["d1"] = pivot[1] - pivot[2]
    down = pivot[(pivot["d0"] < 0) & (pivot["d1"] < 0)].reset_index()
    down["decline"] = down["d0"] + down["d1"]
    return down.sort_values("decline").head(limit).reset_index(drop=True)


# report_sections
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def report_sections(conn, filters: Filters, period: dict) -> dict:
    return {"kpis": report_kpis(conn, filters, period),
            "attainment": goal_attainment(conn, filters, period),
            "caliber_notes": config.REPORT_CALIBER_NOTES}


# monthly_target
# 作用：当月累计净销售额 / 月度目标；按数据截止日计算，不用系统当前日期。
def monthly_target(conn, filters: Filters) -> dict:
    """当月累计净销售额 / 月度目标；按数据截止日计算，不用系统当前日期。"""
    import calendar
    month_start = config.END_DATE.replace(day=1)
    month_days = calendar.monthrange(config.END_DATE.year, config.END_DATE.month)[1]
    elapsed_days = config.END_DATE.day
    month_flt = _filters_on(filters, month_start, config.END_DATE)
    month_kpis = metrics.period_kpis(conn, month_flt)
    actual = round(float(month_kpis.get("net_sales") or 0), 2)
    settings = goals.get_goals(conn)
    target_wan = settings.get("monthly_sales_wan")
    target = round(float(target_wan) * 10000, 2) if target_wan is not None else None
    rate = (actual / target) if target else None
    diff = (actual - target) if target is not None else None
    time_progress = elapsed_days / month_days if month_days else None
    if target is None:
        judgment = "未设置月度目标"
        note = "未设置月度销售目标"
    else:
        judgment = "达成" if actual >= target else "未达成"
        if actual >= target:
            note = f"超过目标 {actual - target:,.2f} 元"
        else:
            note = f"还差 {target - actual:,.2f} 元"
    return {"month_start": month_start, "month_days": month_days,
            "elapsed_days": elapsed_days, "time_progress": time_progress,
            "actual": actual, "target": target, "target_wan": target_wan,
            "rate": rate, "rate_pct": min(100.0, max(0.0, (rate or 0) * 100)),
            "diff": diff, "judgment": judgment, "note": note}


# paid_ratio_block
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def paid_ratio_block(conn, filters: Filters, period: dict) -> dict:
    # 当前付费占比取当月累计（与月度上限同一观察窗），分母仍为订单实付销售额
    month_start = config.END_DATE.replace(day=1)
    kpis = metrics.period_kpis(conn, _filters_on(filters, month_start, config.END_DATE))
    settings = goals.get_goals(conn)
    actual = kpis.get("ad_spend_ratio")
    limit_pct = settings.get("paid_ratio_limit")
    limit = (float(limit_pct) / 100.0) if limit_pct is not None else None
    if actual is not None and limit is not None:
        pp = (actual - limit) * 100
        ok = actual <= limit
        note = f"超出上限 {pp:.2f} pp" if pp > 0 else f"低于上限 {abs(pp):.2f} pp"
        gauge_pct = min(100.0, max(0.0, actual / limit * 100)) if limit else 0.0
    else:
        pp = None
        ok = None
        note = "未设置月度付费占比上限"
        gauge_pct = 0.0
    return {"actual": actual, "limit": limit, "limit_pct": limit_pct,
            "pp": pp, "ok": ok, "note": note, "gauge_pct": round(gauge_pct, 1)}


# target_dashboard
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def target_dashboard(conn, filters: Filters, period: dict) -> dict:
    monthly = monthly_target(conn, filters)
    paid = paid_ratio_block(conn, filters, period)
    return {"monthly": monthly, "paid": paid}


# scene_spend_block
# 作用：当前报表区间 + 链接池过滤下的一级场景花费占比（合计相除，不取平均）。
def scene_spend_block(conn, filters: Filters, period: dict) -> dict:
    """当前报表区间 + 链接池过滤下的一级场景花费占比（合计相除，不取平均）。"""
    ids = list(getattr(filters, "my_links_ids", []) or [])
    cost_map = {scene: 0.0 for scene in config.SCENE_L1_OPTIONS}
    if ids:
        marks = ",".join("?" * len(ids))
        rows = conn.execute(
            "SELECT scene_l1, ROUND(SUM(cost), 2) FROM fact_ad_plan_daily "
            f"WHERE stat_date BETWEEN ? AND ? AND item_id IN ({marks}) "
            "GROUP BY scene_l1", (str(period["start"]), str(period["end"]), *ids)
        ).fetchall()
        for scene, cost in rows:
            if scene in cost_map:
                cost_map[scene] = round(float(cost or 0), 2)
    total = round(sum(cost_map.values()), 2)
    result = []
    for idx, scene in enumerate(config.SCENE_L1_OPTIONS):
        cost = cost_map[scene]
        if idx == len(config.SCENE_L1_OPTIONS) - 1:
            ratio = round(100.0 - sum(item["ratio"] for item in result), 2)
        else:
            ratio = round(cost / total * 100, 2) if total else 0.0
        result.append({"scene": scene, "cost": cost,
                       "ratio": max(0.0, ratio)})
    return {"rows": result, "total": total, "range_label": period["range_label"],
            "colors": ["#1B4F8C", "#2E9E9B", "#E8944A"]}
# weekly_series
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def weekly_series(conn, filters: Filters, weeks: int = 8) -> list[dict]:
    end = _last_full_week_end(config.END_DATE)
    result = []
    for offset in range(weeks - 1, -1, -1):
        w_end = end - timedelta(days=7 * offset)
        w_start = w_end - timedelta(days=6)
        vals = metrics.period_kpis(conn, _filters_on(filters, w_start, w_end))
        result.append({"label": f"{w_start.strftime('%m/%d')}-{w_end.strftime('%m/%d')}",
                        "net_sales": round(float(vals.get("net_sales") or 0), 2),
                        "paid_ratio": vals.get("ad_spend_ratio")})
    return result


# daily_series_7
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def daily_series_7(conn, filters: Filters) -> list[dict]:
    result = []
    for offset in range(6, -1, -1):
        day = config.END_DATE - timedelta(days=offset)
        vals = metrics.period_kpis(conn, _filters_on(filters, day, day))
        result.append({"label": day.strftime("%m/%d"),
                        "net_sales": round(float(vals.get("net_sales") or 0), 2),
                        "paid_ratio": vals.get("ad_spend_ratio")})
    return result


# monthly_series
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def monthly_series(conn, filters: Filters, months: int = 12) -> list[dict]:
    import calendar
    result = []
    anchor = config.END_DATE.replace(day=1)
    for offset in range(months - 1, -1, -1):
        year = anchor.year
        month = anchor.month - offset
        while month <= 0:
            month += 12
            year -= 1
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = min(date(year, month, last_day), config.END_DATE)
        vals = metrics.period_kpis(conn, _filters_on(filters, start, end))
        result.append({"label": f"{year}-{month:02d}",
                        "net_sales": round(float(vals.get("net_sales") or 0), 2),
                        "paid_ratio": vals.get("ad_spend_ratio")})
    return result


# gauge_option
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def gauge_option(rate, label="本月目标达成"):
    value = round(max(0.0, min(1.0, float(rate or 0))) * 100, 1)
    return {
        "series": [{
            "type": "gauge", "startAngle": 180, "endAngle": 0,
            "min": 0, "max": 100, "center": ["50%", "72%"], "radius": "95%",
            "pointer": {"show": False},
            "progress": {"show": True, "width": 16,
                         "itemStyle": {"color": "#1f4e79"}},
            "axisLine": {"lineStyle": {"width": 16, "color": [[1, "#e8eff7"]]}},
            "axisTick": {"show": False}, "splitLine": {"show": False},
            "axisLabel": {"show": False},
            "detail": {"valueAnimation": True, "offsetCenter": [0, "-12%"],
                       "formatter": f"{label}\n{{value}}%",
                       "fontSize": 24, "fontWeight": "bold", "color": "#1f2937"},
            "title": {"show": False},
            "data": [{"value": value}],
        }]
    }


# net_ratio_combo
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def net_ratio_combo(series: list[dict], limit: float | None, endpoint_tag: str = "本周"):
    x = [item["label"] for item in series]
    bars = [{"name": "净销售额", "data": [item["net_sales"] for item in series]}]
    line_values = [round(item["paid_ratio"] * 100, 2) if item.get("paid_ratio") is not None
                   else None for item in series]
    lines = [{"name": "付费占比（%）", "data": line_values}]
    option = chart_helpers._combo_option(x, bars, lines, y_name="净销售额（元）",
                                         y2_name="付费占比（%）")
    if limit is not None:
        option["series"].append({
            "name": "付费占比上限", "type": "line", "data": [round(limit * 100, 2)] * len(x),
            "yAxisIndex": 1, "symbol": "none", "lineStyle": {"type": "dashed"},
            "itemStyle": {"color": "#E8A33D"},
        })
    option["series"][0]["name"] = "净销售额"
    option["grid"]["bottom"] = 38
    last_label = x[-1] if x else ""
    option["graphic"] = [{
        "type": "text", "right": 24, "bottom": 2,
        "style": {"text": f"{endpoint_tag}\n{last_label}", "fill": "#E8944A",
                  "fontSize": 11, "fontWeight": "bold", "lineHeight": 15,
                  "textAlign": "right"},
    }]
    return option


# _channel_top
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _channel_top(conn, filters: Filters, period: dict, limit: int = 5) -> pd.DataFrame:
    # 以推广场景作为渠道粒度展示（模拟数据暂无独立后台字段）
    from src.services import tag_center
    scenes = tag_center.scene_summary(conn, _filters_on(
        filters, period["start"], period["end"]))
    if scenes.empty:
        return scenes
    return scenes[["scene", "cost"]].rename(columns={"cost": "ad_cost"}).head(limit)


# fixed_columns
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def fixed_columns() -> list[dict]:
    return [{"key": key, "label": label} for key, label in config.REPORT_COLUMNS]


# =====================================================================
#  自包含 HTML 可视化报表（不引外部库、不产出 xlsx）
# =====================================================================

# _svg_gauge
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _svg_gauge(rate) -> str:
    pct = max(0.0, min(1.0, float(rate or 0))) * 100
    return f"""
    <svg viewBox="0 0 360 210" width="100%" height="210" role="img" aria-label="本月目标达成">
      <path d="M45 160 A135 135 0 0 1 315 160" fill="none" stroke="#e8eff7" stroke-width="18" pathLength="100"/>
      <path d="M45 160 A135 135 0 0 1 315 160" fill="none" stroke="#1f4e79" stroke-width="18"
            pathLength="100" stroke-dasharray="{pct:.1f} 100" stroke-linecap="round"/>
      <text x="180" y="138" text-anchor="middle" fill="#6b7280" font-size="13">本月目标达成</text>
      <text x="180" y="176" text-anchor="middle" fill="#12324a" font-size="34" font-weight="700">{pct:.1f}%</text>
    </svg>"""


# _svg_paid
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _svg_paid(actual, limit, note, ok) -> str:
    if actual is None:
        actual_text = "—"
    else:
        actual_text = f"{actual * 100:.2f}%"
    limit_text = "未设置" if limit is None else f"{limit * 100:.2f}%"
    width = 0 if not limit else max(0, min(100, (actual or 0) / limit * 100))
    color = "#c0392b" if ok is False else "#1e8449"
    return f"""
    <div class="paid">
      <div class="paid-value" style="color:{color}">{actual_text}</div>
      <div class="bar"><span style="width:{width:.1f}%;background:{color}"></span></div>
      <div class="muted">上限 {limit_text} · {note}</div>
    </div>"""


# _svg_combo
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _svg_combo(series: list[dict], limit: float | None, endpoint_tag: str = "本周") -> str:
    # ① 准备输入与上下文
    width, height = 960, 360
    left, right, top, bottom = 64, 64, 32, 48
    plot_w = width - left - right
    plot_h = height - top - bottom
    nets = [float(x.get("net_sales") or 0) for x in series]
    ratios = [x.get("paid_ratio") for x in series]
    max_net = max(nets + [1.0])
    ratio_values = [r * 100 for r in ratios if r is not None]
    if limit is not None:
        ratio_values.append(limit * 100)
    max_ratio = max(ratio_values + [1.0])
    max_ratio = max(max_ratio * 1.15, 1.0)
    step = plot_w / max(len(series), 1)
    # ② 处理主体数据
    bars = []
    points = []
    labels = []
    for i, item in enumerate(series):
        x = left + step * i + step * 0.5
        h = plot_h * (float(item.get("net_sales") or 0) / max_net)
        y = top + plot_h - h
        bars.append(f'<rect x="{x - step * 0.28:.1f}" y="{y:.1f}" width="{step * 0.56:.1f}" '
                    f'height="{h:.1f}" fill="#1f4e79" rx="2"/>')
        ratio = item.get("paid_ratio")
        line_y = top + plot_h - (plot_h * ((ratio * 100) / max_ratio) if ratio is not None else 0)
        points.append(f"{x:.1f},{line_y:.1f}")
        labels.append(f'<text x="{x:.1f}" y="{height - 16}" text-anchor="middle" '
                      f'font-size="11" fill="#6b7280">{html_lib.escape(str(item.get("label", "")))}</text>')
    line = (f'<polyline points="{" ".join(points)}" fill="none" stroke="#b9770e" '
            f'stroke-width="2.5"/>')
    dots = "".join(
        f'<circle cx="{point.split(",")[0]}" cy="{point.split(",")[1]}" r="3" fill="#b9770e"/>'
        for point in points)
    limit_line = ""
    if limit is not None:
        ly = top + plot_h - plot_h * ((limit * 100) / max_ratio)
        limit_line = (f'<line x1="{left}" y1="{ly:.1f}" x2="{left + plot_w}" y2="{ly:.1f}" '
                      f'stroke="#c0392b" stroke-width="1.5" stroke-dasharray="6 5"/>'
                      f'<text x="{left + plot_w - 2}" y="{ly - 6:.1f}" text-anchor="end" '
                      f'font-size="11" fill="#c0392b">付费占比上限 {limit * 100:.2f}%</text>')
    # 左侧金额轴简标 + 右侧百分比轴简标
    axis = []
    for k in range(5):
        value = max_net * k / 4
        y = top + plot_h - plot_h * k / 4
        axis.append(f'<line x1="{left - 5}" y1="{y:.1f}" x2="{left}" y2="{y:.1f}" stroke="#cbd4e1"/>'
                    f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10" '
                    f'fill="#6b7280">{value:,.0f}</text>')
        ratio_v = max_ratio * k / 4
        axis.append(f'<text x="{left + plot_w + 8}" y="{y + 4:.1f}" font-size="10" '
                    f'fill="#6b7280">{ratio_v:.1f}%</text>')
    endpoint = ""
    if series:
        last_x = left + step * (len(series) - 1) + step * 0.5
        endpoint = (f'<text x="{last_x:.1f}" y="{height - 2}" text-anchor="middle" '
                    f'font-size="11" font-weight="bold" fill="#E8944A">'
                    f'{html_lib.escape(endpoint_tag)}</text>')
    # ③ 整理并返回结果
    return f"""
    <svg viewBox="0 0 {width} {height}" width="100%" height="340" role="img" aria-label="净销售额与付费占比">
      <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#fbfcfe" stroke="#e1e6ee"/>
      {"".join(axis)}
      {"".join(bars)}
      {"".join(labels)}
      {line}{dots}{limit_line}{endpoint}
    </svg>
    <div class="legend"><span class="lg-bar"></span>净销售额（元）
      <span class="lg-line"></span>付费占比（%）
      <span class="lg-limit"></span>付费占比上限</div>"""


# _svg_scene_stack
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _svg_scene_stack(scene: dict) -> str:
    x = 0.0
    parts = []
    for idx, item in enumerate(scene.get("rows", [])):
        width = max(0.0, min(100.0, float(item.get("ratio") or 0))) * 3.2
        color = scene.get("colors", ["#1B4F8C", "#2E9E9B", "#E8944A"])[idx]
        parts.append(f'<rect x="{x:.1f}" y="0" width="{width:.1f}" height="14" fill="{color}"/>')
        x += width
    return ('<svg class="scene-stack-svg" viewBox="0 0 320 14" width="100%" height="14" '
            'preserveAspectRatio="none" role="img" aria-label="推广场景花费占比">'
            + "".join(parts) + '</svg>')


# _fmt_html_value
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _fmt_html_value(key, value):
    if key in ("sales", "net_sales", "ad_cost", "prev_value"):
        return f"{float(value or 0):,.2f}"
    if key in ("conversion_rate", "refund_rate", "paid_ratio", "wow"):
        return "" if value is None else f"{float(value) * 100:.2f}%"
    if key == "roi":
        return "" if value is None else f"{float(value):,.2f}"
    if key in ("units", "visitors"):
        return f"{int(float(value or 0)):,}"
    return html_lib.escape(str(value if value is not None else ""))


REPORT_TEXT_TITLES = {
    "daily": ["一、经营结论和目标进度", "二、当日工作回顾", "三、明日工作安排",
              "四、遇到的问题&解决方案"],
    "weekly": ["一、经营结论和目标进度", "二、本周重点工作回顾", "三、数据复盘与问题归因",
               "四、下周工作计划"],
    "monthly": ["一、经营结论和目标进度", "二、本月经营复盘", "三、目标达成与偏差分析",
                "四、下月目标与策略"],
}


# _pct
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def _pct(value):
    return "—" if value is None else f"{value * 100:.1f}%"


# build_text_modules
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def build_text_modules(conn, filters: Filters, period: dict, tab: str) -> list[dict]:
    # ① 准备输入与上下文
    kpis = report_kpis(conn, filters, period)
    prev = report_kpis(conn, filters, period | {"start": period["prev_start"],
                                                 "end": period["prev_end"]})
    targets = target_dashboard(conn, filters, period)
    monthly = targets["monthly"]
    paid = targets["paid"]
    rate = monthly.get("rate")
    time_progress = monthly.get("time_progress") or 0
    if rate is None or monthly.get("target") is None:
        target_text = "未设置月度目标"
        progress_text = "目标未设置，暂无法计算达成率与时间进度差"
    else:
        diff = (rate - time_progress) * 100
        compare_word = "高于" if diff >= 0 else "低于"
        pace = "跑赢时间进度" if diff >= 0 else "月内节奏承压但可控"
        target_text = (f"对应月度目标 {monthly['target_wan']} 万元，达成 {_pct(rate)}，"
                       f"{compare_word}时间进度 {_pct(time_progress)} {abs(diff):.1f} 个百分点；{pace}")
        progress_text = target_text
    if paid.get("actual") is None or paid.get("limit") is None:
        paid_text = "付费占比上限未设置"
        action_text = "目标未设置，暂不做投放结构调整结论"
    else:
        pp = (paid["actual"] - paid["limit"]) * 100
        rel = "高于" if pp > 0 else "低于"
        paid_text = f"当期付费占比 {_pct(paid['actual'])}，{rel} {_pct(paid['limit'])} 的控制上限 {abs(pp):.1f} pp"
        action_text = ("先压降全站推广与精准人群推广单日花费"
                       if pp > 0 else "维持当前投放结构")
    # growth
    # 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
    def growth(cur, before):
        if before in (None, 0) or cur is None:
            return "变化—"
        value = (cur - before) / abs(before) * 100
        return f"{'上升' if value >= 0 else '下降'}{abs(value):.1f}%"
    net_growth = growth(kpis.get("net_sales"), prev.get("net_sales"))
    # ② 处理主体数据
    ad_growth = growth(kpis.get("ad_cost"), prev.get("ad_cost"))
    visitor_growth = growth(kpis.get("visitors"), prev.get("visitors"))
    cvr_now = kpis.get("conversion_rate")
    cvr_prev = prev.get("conversion_rate")
    cvr_text = "转化率变化—"
    if cvr_now is not None and cvr_prev is not None:
        cvr_text = f"转化率{'上升' if cvr_now >= cvr_prev else '下降'}{abs(cvr_now - cvr_prev) * 100:.1f} pp"
    main = (f"截至 {config.DATA_END_LABEL}，本月累计净销售额 {monthly.get('actual', 0):,.2f} 元，"
            f"{progress_text}。{paid_text}。"
            f"近 {period['range_label']} 净销售额较 {period['prev_label']} {net_growth}，"
            f"推广花费较上期{ad_growth}，访客数较上期{visitor_growth}，{cvr_text}。")
    # 业务动作句放在结论之后，避免模板出现数据状态类措辞。
    main = main + f" 下阶段投放：{action_text}。"
    modules = []
    for idx, title in enumerate(REPORT_TEXT_TITLES[tab]):
        modules.append({"title": title,
                        "default": main if idx == 0 else "",
                        "placeholder": "可在此补充本周工作内容" if idx else "默认正文"})
    # ③ 整理并返回结果
    return modules


# html_export
# 作用：完成报表数据与导出中的该步骤，结果交给调用方继续使用。
def html_export(conn, filters: Filters, tab: str,
                text_sections: list[str] | None = None) -> tuple[str, str]:
    # ① 准备输入与上下文
    period = report_period(tab)
    kpis = report_kpis(conn, filters, period)
    targets = target_dashboard(conn, filters, period)
    monthly = targets["monthly"]
    paid = targets["paid"]
    scene = scene_spend_block(conn, filters, period)
    if tab == "daily":
        series = daily_series_7(conn, filters)
        chart_title = "近 7 个自然日 · 净销售额与付费占比"
        chart_range_label = (f"{(config.END_DATE - timedelta(days=6)).strftime('%m/%d')}-"
                             f"{config.END_DATE.strftime('%m/%d')}（7天）")
        endpoint = "昨日"
    elif tab == "weekly":
        series = weekly_series(conn, filters, 8)
        chart_title = "近 8 个自然周 · 净销售额与付费占比"
        chart_range_label = period["range_label"]
        endpoint = "本周"
    else:
        series = monthly_series(conn, filters, 12)
        chart_title = "近 12 个自然月 · 净销售额与付费占比"
        chart_range_label = period["range_label"]
        endpoint = "本月"
    modules = build_text_modules(conn, filters, period, tab)
    if text_sections and any(x.strip() for x in text_sections):
        for idx, module in enumerate(modules):
            module["value"] = text_sections[idx] if idx < len(text_sections) else module["default"]
    else:
        for module in modules:
            module["value"] = module["default"]
    # ② 处理主体数据
    scope = filters.scope_label
    kpi_rows = [
        ("销售额", kpis.get("sales"), "元"), ("净销售额", kpis.get("net_sales"), "元"),
        ("销量", kpis.get("units"), "件"), ("访客数", kpis.get("visitors"), "人"),
        ("转化率", kpis.get("conversion_rate"), ""), ("退款率", kpis.get("refund_rate"), ""),
        ("推广花费", kpis.get("ad_cost"), "元"), ("付费占比", kpis.get("ad_spend_ratio"), ""),
    ]
    cards = []
    for label, value, unit in kpi_rows:
        if label in ("转化率", "退款率", "付费占比"):
            shown = "—" if value is None else f"{float(value) * 100:.2f}%"
            unit_text = ""
        elif unit == "元":
            shown = f"{float(value or 0):,.2f}"
            unit_text = "元"
        else:
            shown = f"{int(float(value or 0)):,}"
            unit_text = unit
        unit_html = f"<div class='kpi-unit'>{html_lib.escape(unit_text)}</div>" if unit_text else "<div class='kpi-unit'></div>"
        cards.append(f"<div class='kpi'><div class='kpi-label'>{html_lib.escape(label)}</div>"
                     f"<div class='kpi-value'>{shown}</div>{unit_html}"
                     f"<div class='kpi-prev'>上期 {html_lib.escape(period['prev_label'])}</div></div>")
    text_html = []
    for module in modules:
        body = html_lib.escape(module.get("value") or "")
        if not body.strip():
            body = "<div class='write-line'></div>"
        else:
            body = f"<div class='text-body'>{body}</div>"
        text_html.append(f"<section class='text-module'><h2>{html_lib.escape(module['title'])}</h2>"
                         f"{body}</section>")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>报表 · {html_lib.escape(period['label'])}</title>
<style>
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:22px; background:#F4F7FB; color:#22303F;
  font-family:"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif; font-size:14px; line-height:1.7; }}
.wrap {{ max-width:1180px; margin:0 auto; background:#fff; border:1px solid #DDE5EE; border-radius:10px; padding:24px 28px; }}
h1 {{ margin:0 0 4px; font-size:24px; color:#1B4F8C; }}
h2 {{ font-size:17px; color:#1B4F8C; margin:20px 0 10px; }}
.meta {{ color:#6B7A8C; font-size:13px; }}
.print-btn {{ float:right; border:1px solid #1B4F8C; background:#1B4F8C; color:#fff; border-radius:6px; padding:8px 16px; cursor:pointer; font-size:14px; }}
.kpis {{ display:grid; grid-template-columns:repeat(8,minmax(0,1fr)); gap:8px; }}
.kpi {{ border:1px solid #DDE5EE; border-radius:8px; padding:16px; background:#FBFCFE; min-width:0; overflow:hidden; }}
.kpi-label {{ color:#6B7A8C; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.kpi-value {{ font-size:clamp(18px,1.25vw,22px); font-weight:700; color:#1B4F8C; margin:4px 0; font-variant-numeric:tabular-nums; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }}
.kpi-unit {{ color:#6B7A8C; font-size:12px; min-height:16px; line-height:16px; }}
.kpi-prev {{ color:#6B7A8C; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.dash {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; align-items:stretch; }}
.card {{ border:1px solid #DDE5EE; border-radius:8px; padding:14px 16px; margin-top:12px; background:#fff; }}
.gauge-wrap {{ text-align:center; }}
.paid-value {{ font-size:38px; font-weight:700; color:#D9534F; margin:18px 0 12px; }}
.bar {{ height:14px; background:#EAF2FB; border-radius:8px; overflow:hidden; }}
.bar span {{ display:block; height:100%; border-radius:8px; }}
.muted {{ color:#6B7A8C; font-size:13px; margin-top:8px; }}
.text-module {{ border-top:1px solid #E6ECF3; margin-top:16px; padding-top:6px; break-inside:avoid; }}
.text-body {{ white-space:pre-wrap; color:#22303F; font-size:14px; line-height:1.8; }}
.write-line {{ border-bottom:1px solid #DDE5EE; height:24px; margin-top:8px; }}
.caliber-line {{ margin-top:20px; padding-top:10px; border-top:1px solid #E6ECF3; color:#6B7A8C; font-size:12px; line-height:1.6; }}
.scene-card {{ min-width:0; }}
.scene-stack-svg {{ display:block; margin:12px 0 12px; border-radius:7px; overflow:hidden; }}
.scene-list {{ display:flex; flex-direction:column; gap:8px; }}
.scene-line {{ display:grid; grid-template-columns:minmax(0,1.35fr) minmax(0,1fr) auto; gap:8px; align-items:center; font-size:13px; }}
.scene-name {{ display:flex; align-items:center; gap:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.scene-name i {{ width:8px; height:8px; border-radius:2px; display:inline-block; }}
.scene-cost, .scene-ratio {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
.scene-total {{ margin-top:auto; padding-top:9px; border-top:1px dashed #E6ECF3; color:#6B7A8C; font-size:12px; }}
@media (max-width:1100px) {{ .dash {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
@media print {{
  body {{ background:#fff; padding:0; }}
  .wrap {{ border:0; padding:0; max-width:none; }}
  .print-btn {{ display:none; }}
  @page {{ size:A4 portrait; margin:12mm; }}
  .card, .kpis, .dash, h2, .text-module {{ break-inside:avoid; }}
}}
</style></head><body><div class="wrap">
<button class="print-btn" onclick="window.print()">打印 / 另存 PDF</button>
<h1>报表 · {html_lib.escape(period['label'])} · {html_lib.escape(str(period['start']))} ~ {html_lib.escape(str(period['end']))}</h1>
<div class="meta">统计区间 {period['start']} ~ {period['end']}｜对比 {period['prev_start']} ~ {period['prev_end']}｜范围 {html_lib.escape(scope)}｜数据截止 {html_lib.escape(config.DATA_END_LABEL)}</div>
<h2>关键指标</h2><div class="kpis">{''.join(cards)}</div>
<div class="dash">
  <div class="card gauge-wrap"><h2>本月目标达成</h2>{_svg_gauge(monthly.get('rate'))}
    <div class="muted">本月累计净销售额 {monthly.get('actual', 0):,.2f} 元 · 目标
      {monthly.get('target_wan') if monthly.get('target_wan') is not None else '未设置'} 万元
      · 时间进度 {monthly.get('elapsed_days')}/{monthly.get('month_days')} 天</div></div>
  <div class="card"><h2>当前付费占比</h2>{_svg_paid(paid.get('actual'), paid.get('limit'), paid.get('note'), paid.get('ok'))}</div>
  <div class="card scene-card"><h2>推广场景花费占比</h2>{_svg_scene_stack(scene)}
    <div class="scene-list">{''.join(f'<div class="scene-line"><span class="scene-name"><i style="background:{scene["colors"][idx]}"></i>{html_lib.escape(item["scene"])}</span><span class="scene-cost">{item["cost"]:,.2f} 元</span><span class="scene-ratio">{item["ratio"]:.2f}%</span></div>' for idx, item in enumerate(scene["rows"]))}</div>
    <div class="scene-total">合计花费 {scene["total"]:,.2f} 元</div></div>
</div>
<div class="card"><h2>{html_lib.escape(chart_title)}｜{html_lib.escape(chart_range_label)}</h2>
{_svg_combo(series, paid.get('limit'), endpoint)}</div>
{''.join(text_html)}
<div class="caliber-line">数据来源：订单明细 / 商品效果 / 商品推广（模拟数据）｜统计区间：{period['start']}~{period['end']}｜净销售额 = 实付金额 − 当期退款｜付费占比 = 推广花费 / 实付销售额｜个人练习项目 · 模拟脱敏数据 · 未接生产</div>
</div></body></html>"""
    filename = (f"{period['label']}_我的链接池_{period['file_range']}_"
                f"截止{config.END_DATE.strftime('%m%d')}.html")
    # ③ 整理并返回结果
    return filename, html
