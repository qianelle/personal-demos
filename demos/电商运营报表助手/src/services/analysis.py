# -*- coding: utf-8 -*-
# 单链接分析数据
# 作用：为单链接明细页提供趋势、结构图与链接基础信息。
"""经营分析与单链接明细的图表/页面数据组装。"""
from __future__ import annotations

import config
from src.models import db as dbmod
from src.services import metrics
from src.services.filters import Filters

PRIMARY = "#1B4F8C"
SECONDARY = "#2563A6"
TEAL = "#2E9E9B"
ORANGE = "#E8944A"
PURPLE = "#7A6BB5"
GREEN = "#3E9B6B"
AMBER = "#E8A33D"
RED = "#D9534F"
GRAY = "#6B7A8C"
PALETTE = [PRIMARY, TEAL, ORANGE, PURPLE, GREEN, AMBER, RED, SECONDARY,
           "#8FC7C4", "#C7B9E8"]


# _donut
# 作用：完成单链接分析数据中的该步骤，结果交给调用方继续使用。
def _donut(data, unit="元"):
    return {
        "color": PALETTE,
        "tooltip": {"trigger": "item"},
        "legend": {"type": "scroll", "bottom": 0},
        "series": [{"type": "pie", "radius": ["40%", "66%"], "center": ["50%", "44%"],
                    "avoidLabelOverlap": True,
                    "label": {"formatter": "{b}\n{d}%"},
                    "itemStyle": {"borderColor": "#fff", "borderWidth": 2},
                    "data": [{"name": name, "value": value} for name, value in data]}],
        "unit": unit,
    }


# _combo_option
# 作用：完成单链接分析数据中的该步骤，结果交给调用方继续使用。
def _combo_option(x, bar_series, line_series, y_name="元", y2_name=""):
    y_axis = [{"type": "value", "name": y_name, "scale": True,
               "axisLabel": {"color": PRIMARY}, "nameTextStyle": {"color": PRIMARY}}]
    if y2_name:
        y_axis.append({"type": "value", "name": y2_name, "scale": True,
                       "axisLabel": {"color": TEAL}, "nameTextStyle": {"color": TEAL},
                       "splitLine": {"show": False}})
    series = []
    for item in bar_series:
        series.append(dict(item, type="bar", barMaxWidth=22, yAxisIndex=0,
                           label={"show": True, "position": "top", "fontSize": 10,
                                  "color": PRIMARY}))
    for item in line_series:
        series.append(dict(item, type="line", smooth=True, symbolSize=4,
                           yAxisIndex=1 if y2_name else 0))
    return {
        "color": [PRIMARY, ORANGE, TEAL, PURPLE, GREEN, AMBER, RED],
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0, "type": "scroll"},
        "grid": {"left": 12, "right": 40, "top": 42, "bottom": 12, "containLabel": True},
        "xAxis": {"type": "category", "data": list(x),
                  "axisLabel": {"hideOverlap": True, "color": GRAY}},
        "yAxis": y_axis,
        "series": series,
    }


# page_item_detail
# 作用：完成单链接分析数据中的该步骤，结果交给调用方继续使用。
def page_item_detail(conn, filters: Filters, item_id: str) -> dict:
    # ① 准备输入与上下文
    detail = metrics.item_detail(conn, item_id, filters)
    mapping = detail["mapping"]
    if mapping is not None:
        mapping["shop_name"] = config.shop_display(mapping.get("shop_id", ""))
        tag = conn.execute(
            "SELECT tag FROM link_tags WHERE shop_id = ? AND item_id = ?",
            (mapping.get("shop_id", ""), item_id)).fetchone()
        mapping["current_tag"] = (tag["tag"] if tag and tag["tag"] else "未打标")
    kpi = detail["kpi"]
    # ② 处理主体数据
    kpi_cards = [
        {"label": "销售额", "value": kpi.get("sales"), "fmt": "money", "tip": "订单行级实付合计"},
        {"label": "净销售额", "value": kpi.get("net_sales"), "fmt": "money", "tip": "实付 − 当期退款"},
        {"label": "销量", "value": kpi.get("units"), "fmt": "int", "tip": "购买数量合计"},
        {"label": "订单数", "value": kpi.get("order_count"), "fmt": "int", "tip": "去重子订单数"},
        {"label": "客单价", "value": kpi.get("aov"), "fmt": "money", "tip": "销售额 / 订单数"},
        {"label": "访客数", "value": kpi.get("visitors"), "fmt": "int", "tip": "商品访客数"},
        {"label": "转化率", "value": kpi.get("conversion_rate"), "fmt": "pct", "tip": "支付买家数 / 访客数"},
        {"label": "退款率", "value": kpi.get("refund_rate"), "fmt": "pct", "tip": "退款金额 / 实付金额"},
    ]
    trend = detail["trend"]
    chart_trend = _combo_option(
        trend["stat_date"].tolist() if not trend.empty else [],
        [{"name": "销售额", "data": trend["sales"].round(2).tolist() if not trend.empty else []}],
        [{"name": "访客数", "data": trend["visitors"].tolist() if not trend.empty else []}],
        y_name="元", y2_name="访客数")
    # ③ 整理并返回结果
    return {
        "title": "单链接明细", "active": "items",
        "subtitle": f"链接 {item_id} · 统计区间 {filters.label}",
        "item_id": item_id, "mapping": mapping, "shop_id": detail["shop_id"],
        "kpi_cards": kpi_cards,
        "charts": {"chart_trend": chart_trend},
        "chart_layout": [{"id": "chart_trend", "title": "单链接销售额与访客数趋势",
                          "span": 2, "height": 340}],
        "tables": [], "charts_note": "", "raw_json_rows": [],
        "extra": {},
    }
