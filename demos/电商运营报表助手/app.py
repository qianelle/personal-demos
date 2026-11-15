# -*- coding: utf-8 -*-
# 页面路由入口
# 作用：组织三个模块页面、数据接口与导出入口，把请求交给对应的数据服务。
""" Flask 应用：数据分析 / 链接管理 / 数据报表（含目标设置、单链接明细）。"""

from __future__ import annotations

import io
import math
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask import Flask, abort, g, redirect, render_template, request, send_file

import config
from src.models import db as dbmod
from src.services import goals, link_management, my_links, reports, table_export, pages
from src.services.filters import Filters, parse_item_ids


# _is_empty
# 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return True
    return value == ""


# fmtv
# 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
def fmtv(value, kind: str = "text"):
    if _is_empty(value):
        return "—"
    try:
        if kind == "money":
            return f"{float(value):,.2f}"
        if kind == "int":
            return f"{int(round(float(value))):,}"
        if kind == "pct":
            return f"{float(value) * 100:.2f}%"
        if kind == "pp":
            return f"{float(value) * 100:+.2f} pp"
        if kind == "ratio":
            return f"{float(value):,.2f}"
        if kind == "num":
            return f"{float(value):,.2f}"
        if kind == "num1":
            return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return str(value)
    return str(value)


# delta_text
# 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
def delta_text(delta, kind: str = "pct"):
    if delta is None:
        return "—"
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        return "—"
    if kind == "pp":
        return f"{abs(delta) * 100:.2f} pp"
    return f"{abs(delta) * 100:.2f}%"


# delta_cls
# 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
def delta_cls(delta) -> str:
    if delta is None:
        return "flat"
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        return "flat"
    return "up" if delta > 0 else ("down" if delta < 0 else "flat")


# delta_arrow
# 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
def delta_arrow(delta) -> str:
    return {"up": "▲", "down": "▼", "flat": "—"}[delta_cls(delta)]


# shopname
# 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
def shopname(value) -> str:
    return config.shop_display(str(value or ""))


# create_app
# 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
def create_app() -> Flask:
    # ① 准备输入与上下文
    app = Flask(
        __name__,
        template_folder=str(config.TEMPLATES_DIR),
        static_folder=str(config.STATIC_DIR),
    )
    app.config["JSON_AS_ASCII"] = False
    app.jinja_env.filters["fmtv"] = fmtv
    app.jinja_env.filters["delta_text"] = delta_text
    app.jinja_env.filters["delta_cls"] = delta_cls
    app.jinja_env.filters["delta_arrow"] = delta_arrow
    app.jinja_env.filters["shopname"] = shopname

    # get_conn
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    def get_conn():
        if "conn" not in g:
            if not config.DB_PATH.exists():
                raise RuntimeError(
                    f"数据库不存在：{config.DB_PATH}。请先运行 python run.py --data-only")
            g.conn = dbmod.connect()
            goals.ensure_table(g.conn)
            my_links.ensure_seeded(g.conn)
        return g.conn

    # close_conn
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.teardown_appcontext
    def close_conn(_exception=None):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    # filter_options
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    def filter_options(conn) -> dict:
        shops = [{"value": s, "label": config.shop_display(s)} for s in config.SHOPS]
        styles = [r["style_code"] for r in conn.execute(
            "SELECT DISTINCT style_code FROM dim_item_mapping "
            "WHERE style_code <> '' ORDER BY style_code").fetchall()]
        categories = []
        for row in conn.execute(
                "SELECT category_l2, COUNT(*) AS n FROM dim_item_mapping "
                "GROUP BY category_l2 ORDER BY n DESC").fetchall():
            categories.append({"value": row["category_l2"],
                               "label": f"{row['category_l2']}（{row['n']} 个链接）"})
        item_options = [r["item_id"] for r in conn.execute(
            "SELECT item_id, SUM(pay_amount) AS pay FROM fact_wide_daily "
            "GROUP BY item_id ORDER BY pay DESC LIMIT 40").fetchall()]
        return {"shops": shops, "styles": styles, "categories": categories,
                "item_ids": item_options, "tags": config.ANALYSIS_TAG_OPTIONS}

    # base_context
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    def base_context(conn, filters: Filters, page: dict, page_key: str) -> dict:
        # ① 准备输入与上下文
        nav = []
        for item in config.NAV_ITEMS:
            nav.append({"key": item["key"], "title": item["title"],
                        "href": item["path"],
                        "active": item["key"] == page.get("active", page_key)})
        ranges = [("昨日", 1, 1), ("近7天", 6, 0), ("近30天", 29, 0),
                  ("近60天", 59, 0)]
        quick_ranges = []
        for label, start_offset, end_offset in ranges:
            start = (config.END_DATE - timedelta(days=start_offset)).strftime("%Y-%m-%d")
            end = (config.END_DATE - timedelta(days=end_offset)).strftime("%Y-%m-%d")
            href = filters.with_query(request.path, start=start, end=end)
            metric = request.args.get("metric")
            if metric and request.path == "/":
                href += ("&" if "?" in href else "?") + "metric=" + metric
            quick_ranges.append({
                "label": label,
                "href": href,
                "active": filters.start == start and filters.end == end,
            })
        # ② 处理主体数据
        default_start = (config.END_DATE - timedelta(
            days=config.DEFAULT_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")
        date_switched = page.get("date_switched", (
            filters.start != default_start
            or filters.end != config.END_DATE.strftime("%Y-%m-%d")))
        top_range = page.get("top_range") or (
            f"当前区间 {filters.start} ~ {filters.end}（{filters.days} 天）"
            f"｜对比 {filters.compare_label}"
            f"｜取数时点 {config.DATA_CUTOFF_LABEL}"
            f"｜范围 {filters.scope_label}")
        my_count = my_links.count()
        all_ids = my_links.all_on_sale_ids(conn)
        # ③ 整理并返回结果
        return {
            "nav": nav, "filters": filters,
            "filter_options": filter_options(conn),
            "quick_ranges": quick_ranges,
            "page": page, "page_key": page_key,
            "chart_data": page.get("charts", {}),
            "chart_layout": page.get("chart_layout", []),
            "my_links_count": my_count,
            "my_links_ids_text": "\n".join(my_links.get_ids()),
            "all_on_sale_ids_json": all_ids,
            "pool_notice": {
                "open": bool(request.args.get("pool")),
                "ok": request.args.get("pool_ok"),
                "missing": request.args.get("pool_missing"),
                "missing_ids": [x for x in (request.args.get("pool_missing_ids") or "").split(",") if x],
            },
            "top_range": top_range,
            "date_switched": date_switched,
            "project_name": config.SYSTEM_NAME,
            "browser_title": config.BROWSER_TITLE,
            "brand_mark": config.BRAND_MARK,
            "brand_subtitle": config.BRAND_SUBTITLE,
            "footer_note": config.FOOTER_NOTE,
            "snapshot_note": config.DATA_SNAPSHOT_NOTE,
            "today": datetime.now().strftime("%Y-%m-%d"),
            "start_date": config.START_DATE.strftime("%Y-%m-%d"),
            "end_date": config.END_DATE.strftime("%Y-%m-%d"),
            "query_string": filters.to_query(),
        }

    # render_page
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    def render_page(page_key: str, template: str, page: dict,
                    filters: Filters, conn) -> str:
        return render_template(template, **base_context(conn, filters, page, page_key))

    # _links_redirect
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    def _links_redirect(params: dict) -> str:
        query = urlencode({k: v for k, v in params.items() if v not in ("", None)})
        return f"/links?{query}" if query else "/links"

    # analysis_index
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.get("/")
    def analysis_index():
        conn = get_conn()
        filters = Filters.from_request_args(request.args)
        page = pages.page_analysis(conn, filters, request.args)
        return render_page("analysis", "analysis.html", page, filters, conn)

    # links_page
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.get("/links")
    # ② 处理主体数据
    def links_page():
        conn = get_conn()
        filters = Filters()
        page = pages.page_links(conn, filters, request.args)
        return render_page("links", "my_links.html", page, filters, conn)

    # reports_page
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.get("/reports")
    def reports_page():
        conn = get_conn()
        filters = Filters()
        page = pages.page_reports(conn, filters, request.args)
        page["hide_date_filter"] = True
        return render_page("reports", "reports.html", page, filters, conn)

    # save_goals_page
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.post("/reports/save-goals")
    def save_goals_page():
        conn = get_conn()
        goals.save_goals(conn, request.form, operator="演示环境")
        tab = request.form.get("tab", "weekly")
        if tab not in ("daily", "weekly", "monthly"):
            tab = "weekly"
        return redirect(f"/reports?tab={tab}")

    # item_detail
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.get("/item/<item_id>")
    def item_detail(item_id: str):
        conn = get_conn()
        filters = Filters.from_request_args(request.args)
        page = pages.page_item_detail(conn, filters, item_id)
        page["hide_date_filter"] = False
        return render_page("analysis", "item_detail.html", page, filters, conn)

    # update_link_tags
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.post("/links/tag")
    def update_link_tags():
        conn = get_conn()
        selected = request.form.getlist("selected")
        item_ids = list(dict.fromkeys(selected))
        tag = (request.form.get("tag", "") or "").strip()
        result = link_management.update_tags(conn, item_ids, tag)
        back = request.form.get("return_url") or "/links"
        sep = "&" if "?" in back else "?"
        return redirect(f"{back}{sep}write_ok={result.get('ok', 0)}"
                        f"&write_tag={tag}")

    # update_my_links
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.post("/links/my-links")
    def update_my_links():
        conn = get_conn()
        pasted = parse_item_ids(request.form.get("item_ids", ""))
        result = my_links.replace_items(conn, pasted)
        from urllib.parse import quote
        missing = quote(",".join(result["missing"][:100]), safe=",")
        next_url = request.form.get("next") or "/"
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = "/"
        sep = "&" if "?" in next_url else "?"
        return redirect(next_url + sep + "pool=1&pool_ok=" + str(result["ok"]) +
                        "&pool_missing=" + str(len(result["missing"])) +
                        "&pool_missing_ids=" + missing)

    # remove_managed_links
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.post("/links/remove")
    def remove_managed_links():
        conn = get_conn()
        item_ids = list(dict.fromkeys(request.form.getlist("selected")))
        result = link_management.remove_tag_records(conn, item_ids)
        back = request.form.get("return_url") or "/links"
        sep = "&" if "?" in back else "?"
        return redirect(f"{back}{sep}remove_ok={result.get('removed', 0)}")

    # export_report_html
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.route("/export/reports/html", methods=["GET", "POST"])
    def export_report_html():
        conn = get_conn()
        filters = Filters()
        source = request.form if request.method == "POST" else request.args
        tab = source.get("tab") if source.get("tab") in {
            "daily", "weekly", "monthly"} else "weekly"
        text_sections = [source.get(f"section_{idx}", "") for idx in range(1, 5)]
        filename, content = reports.html_export(conn, filters, tab, text_sections)
        return send_file(io.BytesIO(content.encode("utf-8")),
                         mimetype="text/html", as_attachment=True,
                         download_name=filename)

    # export_plan_table
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.get("/export/table/plan")
    def export_plan_table():
        conn = get_conn()
        filters = Filters.from_request_args(request.args)
        page = pages._plan_page(conn, filters, request.args)
        stream = table_export.build_plan_workbook(page["all_rows"], page["columns"])
        return send_file(
            stream, as_attachment=True,
            download_name=f"推广计划_{table_export.range_name(filters)}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # export_link_table
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.get("/export/table/links")
    def export_link_table():
        conn = get_conn()
        filters = Filters()
        view = link_management.table_view(conn, filters, request.args)
        stream = table_export.build_link_workbook(view["all_rows"], view["columns"])
        suffix = ""
        if view.get("card") and view["card"] != "all":
            suffix = "_" + view.get("card_label", "")
        return send_file(
            stream, as_attachment=True,
            download_name=f"链接管理_{table_export.range_name(filters)}{suffix}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # healthz
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.get("/healthz")
    def healthz():
        conn = get_conn()
        return {"status": "ok", "tables": dbmod.table_counts(conn)}

    # not_found
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.errorhandler(404)
    def not_found(_error):
        conn = get_conn()
        filters = Filters.from_request_args(request.args)
        page = {"title": "页面不存在", "subtitle": "请求的页面或链接不存在",
                "charts": {}, "chart_layout": [], "tables": []}
        return render_template("error.html", code=404,
                               message="请求的页面或链接不存在。",
                               **base_context(conn, filters, page, "")), 404

    # server_error
    # 作用：完成页面路由入口中的该步骤，结果交给调用方继续使用。
    @app.errorhandler(500)
    def server_error(_error):
        conn = get_conn()
        filters = Filters.from_request_args(request.args)
        page = {"title": "服务异常", "subtitle": "请查看控制台日志",
                "charts": {}, "chart_layout": [], "tables": []}
        return render_template("error.html", code=500,
                               message="服务端处理异常，请查看控制台日志。",
                               **base_context(conn, filters, page, "")), 500

    # ③ 整理并返回结果
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
