# -*- coding: utf-8 -*-
"""
千牛 / 淘宝 商家评价管理后台 —— 仿真环境 V1
==================================================================
用途：为影刀 RPA 浏览器自动化提供本地仿真靶站，用于演示与测试
      「电商 VOC 评价数据采集」流程（登录 → 筛选 → 查询 → 导出）。

边界声明（重要）：
  · 本项目不复制任何真实平台源码，不使用任何平台商标资源；
  · 不接入真实淘宝 / 千牛接口，不做登录绕过、不做验证码绕过、不做爬虫；
  · 全部数据为本地虚构仿真数据，不含真实消费者、真实店铺、真实订单信息；
  · 仅实现「评价管理 + CSV 导出」，其余菜单为界面占位。

启动：python app.py   →   http://localhost:5000
"""

import io
import csv
import os
import math
from datetime import datetime, timedelta

from flask import (Flask, Response, jsonify, redirect, render_template,
                   request, session, url_for)

from mock_data import (REVIEWS, SHOPS, SHOP_NAMES, CSV_FIELDS,
                       SIM_BASE_DATE)


# ================================================================ 增量巡检
# 运营不是按「首评时间」巡检的，而是按「这条线程最后一次动过是什么时候」。
# 老评价一旦被追评，就必须重新回到列表顶部、并被「今天 / 昨天 / 近7天」命中，
# 否则运营永远看不到消费者补充的关键信息（尤其是差评后续恶化）。
#
# last_activity_time = append_review_time or review_time
#   - 只用于：列表默认排序、日期区间筛选
#   - 不用于：CSV 导出（CSV 仍是冻结的 15 字段）
#   - 不改变：PostgreSQL Source Schema
QUICK_RANGES = [
    ("today", "今天"),
    ("yesterday", "昨天"),
    ("last7", "近7天"),
]
QUICK_RANGE_KEYS = {k for k, _ in QUICK_RANGES}


def compute_last_activity(row):
    """线程最后活动时间：有追评取追评时间，否则取首评时间。"""
    return row.get("append_review_time") or row.get("review_time") or ""


def _ensure_last_activity(rows):
    """为每行补齐内部计算字段（数据源未提供时兜底计算）。"""
    for r in rows:
        r["last_activity_time"] = compute_last_activity(r)
    return rows


def quick_range_bounds(key):
    """
    快捷区间 -> (date_start, date_end)，基于「今天」实时计算。
    last7 = 含今天在内的 7 个自然日（今天 - 6 天 ~ 今天）。
    """
    # 用 Demo 时钟（SIM_BASE_DATE）而不是 datetime.now()：
    # 仿真后台的「今天」必须可重复，否则演示验收日期会随运行日期漂移，
    # 「昨日完整补采 / 当天滚动增量」这两条用例没法稳定复现。
    today = SIM_BASE_DATE.date()
    if key == "today":
        d = today.strftime("%Y-%m-%d")
        return d, d
    if key == "yesterday":
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return d, d
    if key == "last7":
        return (today - timedelta(days=6)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    return "", ""


_ensure_last_activity(REVIEWS)

app = Flask(__name__)
app.secret_key = "qianniu-review-demo-v1-local-only"

# ------------------------------------------------------------------ 常量
DEMO_USERNAME = "demo_admin"
DEMO_PASSWORD = "123456"

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_OPTIONS = [20, 50, 100]

MENUS = [
    {"key": "dashboard", "name": "首页", "endpoint": "dashboard"},
    {"key": "products", "name": "商品管理", "endpoint": "placeholder_products"},
    {"key": "orders", "name": "交易管理", "endpoint": "placeholder_orders"},
    {"key": "reviews", "name": "评价管理", "endpoint": "reviews_page"},
    {"key": "data", "name": "数据中心", "endpoint": "placeholder_data"},
]

RATING_OPTIONS = [("", "全部"), ("1", "1星"), ("2", "2星"), ("3", "3星"),
                  ("4", "4星"), ("5", "5星")]
# Source Schema v1 冻结后：一行 = 一个主评价线程，追评不再单独成行。
# 因此「评价类型」按该线程是否含追评内容划分（value 保持不变，避免影响 RPA 脚本）。
TYPE_OPTIONS = [("", "全部"), ("初评", "初评（仅主评价）"), ("追评", "追评（含追评内容）")]
APPEND_OPTIONS = [("", "全部"), ("是", "是"), ("否", "否")]


@app.context_processor
def inject_common():
    """全局注入左侧菜单，所有后台页面共用。"""
    return {"menus": MENUS}


# ------------------------------------------------------------------ 登录守卫
@app.before_request
def require_login():
    ep = request.endpoint
    if ep in (None, "static", "login"):
        return None
    if not session.get("user"):
        return redirect(url_for("login"))
    return None


@app.route("/favicon.ico")
def favicon():
    # 避免浏览器控制台出现 404 噪音（不使用任何平台图标资源）
    return Response(status=204)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user"):
            return redirect(url_for("reviews_page"))
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if username == DEMO_USERNAME and password == DEMO_PASSWORD:
        session.clear()
        session["user"] = username
        session["login_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return redirect(url_for("reviews_page"))

    return render_template(
        "login.html",
        error="账号或密码错误。Demo 账号：demo_admin / 123456",
        username=username,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/session/expire", methods=["POST"])
def session_expire():
    """异常场景2：模拟登录失效（清除 Session），供 RPA 测试 LOGIN_REQUIRED 分支。"""
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("login")})


# ------------------------------------------------------------------ 页面
@app.route("/")
def index():
    return redirect(url_for("reviews_page"))


@app.route("/dashboard")
def dashboard():
    total = len(REVIEWS)
    bad = sum(1 for r in REVIEWS if isinstance(r["rating"], int) and r["rating"] <= 2)
    append_cnt = sum(1 for r in REVIEWS if r["has_append"] == "是")
    risk = sum(1 for r in REVIEWS if r["category"] == "疑似身体不适反馈")
    return render_template(
        "placeholder.html",
        active="dashboard",
        title="首页",
        guide=True,
        stats={"total": total, "bad": bad, "append": append_cnt, "risk": risk},
    )


def _placeholder(active, title):
    return render_template("placeholder.html", active=active, title=title)


@app.route("/products")
def placeholder_products():
    return _placeholder("products", "商品管理")


@app.route("/orders")
def placeholder_orders():
    return _placeholder("orders", "交易管理")


@app.route("/data")
def placeholder_data():
    return _placeholder("data", "数据中心")


# ------------------------------------------------------------------ 筛选
def parse_filters(args):
    f = {
        "date_start": (args.get("date_start") or "").strip(),
        "date_end": (args.get("date_end") or "").strip(),
        "shop": (args.get("shop") or "").strip(),
        "q": (args.get("q") or "").strip(),
        "type": (args.get("type") or "").strip(),
        "rating": (args.get("rating") or "").strip(),
        "has_append": (args.get("has_append") or "").strip(),
        "range": (args.get("range") or "").strip(),
    }
    # 快捷区间只在用户没有手填起止日期时生效，避免覆盖自定义区间。
    # 区间一旦展开就写回 date_start / date_end，页面上的日期框会同步显示，
    # 导出时也能原样带上，保证「导出 = 当前筛选结果」。
    if f["range"] in QUICK_RANGE_KEYS and not (f["date_start"] or f["date_end"]):
        f["date_start"], f["date_end"] = quick_range_bounds(f["range"])
    return f


def filter_reviews(f):
    rows = REVIEWS
    # 日期区间按「最后活动时间」过滤：老首评 + 新追评 的线程也要能被增量巡检命中
    if f["date_start"]:
        rows = [r for r in rows if r["last_activity_time"][:10] >= f["date_start"]]
    if f["date_end"]:
        rows = [r for r in rows if r["last_activity_time"][:10] <= f["date_end"]]
    if f["shop"]:
        rows = [r for r in rows if r["shop_name"] == f["shop"]]
    if f["q"]:
        kw = f["q"].lower()
        rows = [r for r in rows
                if kw in r["item_id"].lower() or kw in r["item_name"].lower()]
    if f["type"]:
        rows = [r for r in rows if r["review_type"] == f["type"]]
    if f["rating"]:
        rows = [r for r in rows if str(r["rating"]) == f["rating"]]
    if f["has_append"]:
        rows = [r for r in rows if r["has_append"] == f["has_append"]]
    # 默认排序：最后活动时间倒序（发生新追评的老线程重新回到顶部）
    return sorted(rows, key=lambda r: r["last_activity_time"], reverse=True)


@app.route("/reviews")
def reviews_page():
    f = parse_filters(request.args)
    rows = filter_reviews(f)

    try:
        size = int(request.args.get("size", PAGE_SIZE_DEFAULT))
    except ValueError:
        size = PAGE_SIZE_DEFAULT
    if size not in PAGE_SIZE_OPTIONS:
        size = PAGE_SIZE_DEFAULT

    total = len(rows)
    pages = max(1, math.ceil(total / size)) if total else 1
    try:
        page = int(request.args.get("page", 1) or 1)
    except ValueError:
        page = 1
    page = min(max(page, 1), pages)

    start = (page - 1) * size
    page_rows = rows[start:start + size]

    # 分页链接：保留当前筛选条件
    def page_url(p):
        args = {k: v for k, v in request.args.items() if k != "page"}
        args["page"] = p
        args["size"] = size
        return url_for("reviews_page", **args)

    return render_template(
        "reviews.html",
        active="reviews",
        rows=page_rows,
        total=total,
        page=page,
        pages=pages,
        size=size,
        filters=f,
        quick_ranges=QUICK_RANGES,
        quick_active=f["range"],
        # 统计口径必须与筛选口径一致：这里统计的是「当前筛选结果」里的含追评数
        append_total=sum(1 for r in rows if r["has_append"] == "是"),
        shops=SHOP_NAMES,
        rating_options=RATING_OPTIONS,
        type_options=TYPE_OPTIONS,
        append_options=APPEND_OPTIONS,
        size_options=PAGE_SIZE_OPTIONS,
        page_url=page_url,
        total_all=len(REVIEWS),
    )


# ------------------------------------------------------------------ 导出
@app.route("/export")
def export_csv():
    f = parse_filters(request.args)
    rows = filter_reviews(f)

    if not rows:
        return Response(
            "暂无可导出数据：当前筛选条件下没有符合条件的评价。",
            mimetype="text/plain; charset=utf-8",
        )

    filename = "reviews_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_FIELDS)
    for r in rows:
        writer.writerow([r.get(k, "") for k in CSV_FIELDS])

    # UTF-8 with BOM：确保 Excel 直接打开中文不乱码
    data = "\ufeff" + buf.getvalue()

    return Response(
        data.encode("utf-8"),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename={}".format(filename),
            "X-Filename": filename,
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print(" 商家评价管理后台 仿真环境 V1")
    print(" 访问地址： http://localhost:{}".format(port))
    print(" 测试账号： {} / {}".format(DEMO_USERNAME, DEMO_PASSWORD))
    print(" 仿真评价数据：{} 条（全部虚构）".format(len(REVIEWS)))
    print("=" * 60)
    app.run(host="127.0.0.1", port=port, debug=False)
