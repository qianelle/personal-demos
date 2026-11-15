# -*- coding: utf-8 -*-
# 模拟数据生成
# 作用：按店铺、链接、订单、流量与推广的规则生成练习用数据。
""" 模拟脱敏数据生成。

当前重做模拟数据真实性（A 部分）：
  * A1 季节—品类—材质—标题强约束：标题按模板生成，生成后逐条扫描矛盾组合；
  * A2 季节销量结构：按 SEASON_RULES 月度权重生成日销量，夏季品类 10 月后趋零；
  * A3 主推矩阵与生命周期：TOP_TIER 头部链接、主推款号唯一、上架日期与生命周期规则；
  * 链接 ID 按店铺分段 + 不连续编号；款号结构保留 JS6628-008-36。

文件形态保持不变：
  data/shop_a|shop_b/订单导出_20261105_235900.csv   T1 28 列 / GBK / 无 BOM / CRLF
  data/shop_a|shop_b/商品效果_20261105.xlsx          T2 32 列
  data/shop_a|shop_b/商品推广报表_20261105.xlsx      T3 30 列
  data/商品主数据映射表.xlsx                         含 owner / launch_date
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from src.etl import field_spec

CN = config.CATEGORY_L2

# =====================================================================
# 款与标题
# =====================================================================

# 40 个款：品类、季节词、材质（组合均在合法矩阵内）
STYLE_BLUEPRINTS = (
    [("棉服", "加绒", "纯棉")] * 3 + [("棉服", "羊羔绒", "纯棉")] * 2
    + [("休闲裤", "加绒", "纯棉")] * 2 + [("休闲裤", "羊羔绒", "纯棉")] * 1
    + [("休闲裤", "春秋", "纯棉")] * 2
    + [("运动裤", "加绒", "纯棉")] * 3 + [("运动裤", "春秋", "纯棉")] * 2
    + [("毛呢裤", "加绒", "纯棉")] * 2 + [("毛呢裤", "春秋", "纯棉")] * 1
    + [("卫裤", "羊羔绒", "纯棉")] * 2 + [("卫裤", "加绒", "纯棉")] * 1
    + [("卫裤", "春秋", "纯棉")] * 1
    + [("卫衣", "加绒", "纯棉")] * 3 + [("卫衣", "春秋", "纯棉")] * 2
    + [("T恤", "春秋", "纯棉")] * 2 + [("T恤", "夏季", "纯棉")] * 1
    + [("T恤", "夏季", "冰丝")] * 1
    + [("短裤", "夏季", "冰丝")] * 2 + [("短裤", "夏季", "纯棉")] * 1
    + [("短袖", "夏季", "冰丝")] * 1 + [("短袖", "夏季", "纯棉")] * 1
    + [("工装裤", "春秋", "纯棉")] * 2 + [("迷彩裤", "春秋", "纯棉")] * 2
)
assert len(STYLE_BLUEPRINTS) == 40, len(STYLE_BLUEPRINTS)

SEASON_LABEL = {"春秋": "春秋", "夏季": "夏季", "加绒": "加绒加厚", "羊羔绒": "羊羔绒"}
SUFFIX = {
    "棉服": "男加厚保暖", "卫衣": "男加厚保暖", "T恤": "男宽松打底",
    "短袖": "男宽松透气", "短裤": "男宽松五分裤", "毛呢裤": "男加厚直筒",
    "休闲裤": "男宽松直筒", "运动裤": "男加厚束脚", "卫裤": "男加绒束脚",
    "工装裤": "男宽松直筒", "迷彩裤": "男宽松直筒",
}
CATEGORY_ALIAS = {"T恤": "T恤"}


# _build_styles
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _build_styles() -> list[dict]:
    # ① 准备输入与上下文
    styles = []
    color_codes = list(config.COLOR_MAP)
    # ② 处理主体数据
    for idx, (category, season, material) in enumerate(STYLE_BLUEPRINTS):
        color_code = color_codes[idx % len(color_codes)]
        color_name = config.COLOR_MAP[color_code]
        category_word = category
        if category == "T恤":
            category_word = ("长袖" if season == "春秋" else "短袖") + "T恤"
        title = config.TITLE_TEMPLATE.format(
            season_label=SEASON_LABEL[season], color_name=color_name,
            material_word=material, category=category_word, suffix=SUFFIX[category])
        style = {
            "style_idx": idx,
            "style_code": f"JS{6600 + idx}",
            "style_name": f"{season}{material}{category}",
            "category_l1": config.CATEGORY_L1,
            "category_l2": category,
            "season_key": season,
            "material": material,
            "color_code": color_code,
            "color_name": color_name,
            "asset_lib_id": f"AL{7000 + idx}",
            "season_asset_version": f"详情页{season}版V{(idx % 2) + 1}",
            "main_image_copy_version": f"主图{season}文案V{(idx % 2) + 1}",
            "similar_group_id": f"SG{(idx + 1):03d}",
            "base_price": config.BASE_PRICE[category],
            "title": title,
            "is_summer": category in ("短裤", "短袖") or season == "夏季" or material == "冰丝",
        }
        styles.append(style)
    # ③ 整理并返回结果
    return styles


# _title_is_valid
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _title_is_valid(title: str, style: dict) -> bool:
    for a, b in config.FORBIDDEN_TITLE_COMBOS:
        if a in title and b in title:
            return False
    if SEASON_LABEL[style["season_key"]] not in title:
        return False
    if style["material"] not in title:
        return False
    if style["category_l2"] not in title:
        return False
    if style["color_name"] not in title:
        return False
    if style["color_code"] not in ("",) and style["color_code"] not in title:
        # 颜色码不要求出现在标题，仅要求标题颜色词与颜色码对应
        pass
    return True


# _size_pool
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _size_pool(category_l2: str) -> list[str]:
    if category_l2 in {"T恤", "短袖", "卫衣", "棉服"}:
        return ["M", "L", "XL", "2XL", "3XL"]
    return ["29", "30", "31", "32", "33", "34", "36", "38"]


# =====================================================================
# 通用工具
# =====================================================================

# _money
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _money(value: float) -> str:
    return f"{value:.2f}"


# _dt_variants
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _dt_variants(dt: datetime | None, rng: random.Random) -> str:
    if dt is None:
        return ""
    kind = rng.random()
    if kind < 0.60:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if kind < 0.70:
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    if kind < 0.80:
        return dt.strftime("%Y%m%d%H%M%S")
    if kind < 0.88:
        return dt.strftime("%Y-%m-%d %H:%M")
    if kind < 0.93:
        return dt.strftime("%Y/%m/%d %H:%M")
    if kind < 0.97:
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y.%m.%d %H:%M:%S")


# _write_xlsx
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _write_xlsx(path: Path, sheet_name: str, headers: list[str], rows: list[list],
                extra_sheet: tuple[str, list[str], list[list]] | None = None) -> None:
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=sheet_name)
    ws.append(headers)
    for row in rows:
        ws.append(row)
    if extra_sheet:
        title, e_headers, e_rows = extra_sheet
        ws2 = wb.create_sheet(title=title)
        ws2.append(e_headers)
        for row in e_rows:
            ws2.append(row)
    wb.save(path)


# _stable_owner
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _stable_owner(shop_id: str, item_id: str) -> str:
    pool = config.OWNER_POOL.get(shop_id) or [config.DEMO_OPERATOR]
    h = int(hashlib.md5(item_id.encode("utf-8")).hexdigest()[:8], 16)
    return pool[h % len(pool)]


# =====================================================================
# 链接主数据
# =====================================================================

# _primary_styles
# 作用：为两店各选 10 个不重叠款号作为分层/主推链接；头部款互不相同。
def _primary_styles(styles: list[dict]) -> dict[str, list[dict]]:
    """为两店各选 10 个不重叠款号作为分层/主推链接；头部款互不相同。"""
    # ① 准备输入与上下文
    used = set()
    plan = {"shop_a": [], "shop_b": []}

    # pick
    # 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
    def pick(category, season, material):
        for style in styles:
            if (style["style_idx"] not in used and style["category_l2"] == category
                    and style["season_key"] == season and style["material"] == material):
                used.add(style["style_idx"])
                return style
        raise RuntimeError(f"缺少可用款号：{category}/{season}/{material}")

    specs_a = [
        ("休闲裤", "羊羔绒", "纯棉"),   # A5 样例①
        ("卫衣", "加绒", "纯棉"),
        ("棉服", "加绒", "纯棉"),
        ("毛呢裤", "加绒", "纯棉"),
        ("卫裤", "羊羔绒", "纯棉"),
        ("运动裤", "加绒", "纯棉"),
        ("休闲裤", "加绒", "纯棉"),
        ("卫衣", "春秋", "纯棉"),
        ("棉服", "羊羔绒", "纯棉"),
        ("T恤", "春秋", "纯棉"),
    ]
    # ② 处理主体数据
    specs_b = [
        ("运动裤", "加绒", "纯棉"),    # A5 样例②，另一店另一款号
        ("毛呢裤", "加绒", "纯棉"),
        ("棉服", "加绒", "纯棉"),
        ("卫裤", "加绒", "纯棉"),
        ("卫衣", "加绒", "纯棉"),
        ("休闲裤", "加绒", "纯棉"),
        ("运动裤", "春秋", "纯棉"),
        ("卫裤", "春秋", "纯棉"),
        ("棉服", "加绒", "纯棉"),
        ("T恤", "春秋", "纯棉"),
    ]
    for spec in specs_a:
        plan["shop_a"].append(pick(*spec))
    for spec in specs_b:
        plan["shop_b"].append(pick(*spec))
    # ③ 整理并返回结果
    return plan


# build_master
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def build_master(rng: random.Random) -> tuple[list[dict], list[dict], dict]:
    # ① 准备输入与上下文
    styles = _build_styles()
    primary = _primary_styles(styles)
    id_rng = random.Random(config.RANDOM_SEED + 1201)

    links = []
    for shop_idx, shop in enumerate(config.SHOPS):
        prefix = "6928" if shop == "shop_a" else "7712"
        used_ids = set()
        for index in range(config.TOTAL_LINKS_PER_SHOP):
            item_id = ""
            while not item_id or item_id in used_ids:
                suffix = f"{id_rng.randint(1000, 99999999):08d}"
                item_id = prefix + suffix
            used_ids.add(item_id)
            if index < config.PRIMARY_LINKS_PER_SHOP:
                style = primary[shop][index]
                tier = index
            else:
                style = styles[(index * 7 + shop_idx * 3) % len(styles)]
                tier = None
            price = round(style["base_price"] * _price_scale(styles) *
                          rng.uniform(0.95, 1.05), 2)
            new_link = {
                "shop_id": shop,
                "item_id": item_id,
                "index": index,
                "style": style,
                "title": style["title"],
                "price": price,
                "sizes": _size_pool(style["category_l2"]),
                "tier": tier,
                "is_primary": 0,
                "is_summer": style["is_summer"],
                "launch_date": None,
                "peak_units": 0,
                "new_arrival": False,
                "mapped": True,
                "owner": _stable_owner(shop, item_id),
                "refund_prop": 0.025,
                "item_status": "在售",
            }
            links.append(new_link)
    # 上面循环中 links 已直接追加，但每店链接按顺序混在一起，重新按店铺分组
    by_shop = {shop: [] for shop in config.SHOPS}
    for link in links:
        by_shop[link["shop_id"]].append(link)

    # 分层销量目标：每店 2 / 3 / 5
    for shop in config.SHOPS:
        shop_links = by_shop[shop]
        tier_specs = []
        for count, low, high in config.TOP_TIER:
            for _ in range(count):
                tier_specs.append(rng.randint(low, high))
        for slot, peak in enumerate(tier_specs):
            link = shop_links[slot]
            link["is_primary"] = 1
            link["launch_date"] = date(2026, 9, 5) if shop == "shop_a" and slot == 0 else (
                date(2026, 9, 10) if shop == "shop_b" and slot == 0 else
                date(2025, 9, 1) + timedelta(days=rng.randint(0, 300)))
            link["peak_units"] = peak
            link["new_arrival"] = True
            link["new_target_buyers"] = 0
            # 头部两款的主推推广花费占比目标 9%~15%
            link["ad_ratio"] = round(rng.uniform(0.09, 0.15), 4)

        # 普通链接：峰值月销量（不等同于月销分层，仅作为季节曲线基准）
        for link in shop_links[config.PRIMARY_LINKS_PER_SHOP:]:
            link["peak_units"] = rng.randint(30, 120)
            link["launch_date"] = _ordinary_launch(link, rng)
            link["ad_ratio"] = 0.0

        # 新品：仅秋冬/春秋品类，9~11 月上架；包含 A5 的潜力/测试/低表现样例
        _assign_new_arrivals(shop_links, rng)

    # 反季长尾：指定一条旧的冰丝短裤作为样例（既有有数据，近 7 天零销量）
    # ② 处理主体数据
    summer_links = [l for l in links if l["is_summer"]]
    for link in summer_links:
        link["launch_date"] = date(2026, 4, 1) + timedelta(days=rng.randint(0, 27))

    # 退款率超标款：2 个款号（冬季款），整体退款倾向显著偏高
    high_refund_styles = {styles[0]["style_code"], styles[3]["style_code"]}
    for link in links:
        if link["style"]["style_code"] in high_refund_styles:
            link["refund_prop"] = 0.24

    # 未映射链接：每店 2 条（近 30 天有动销的非主推链接）
    unmapped = 0
    for shop in config.SHOPS:
        candidates = [l for l in by_shop[shop]
                      if l["is_primary"] == 0 and not l["is_summer"]
                      and l["new_arrival"] is False]
        for link in candidates[:2]:
            link["mapped"] = False
            unmapped += 1

    # 标题自检
    invalid = [l for l in links if not _title_is_valid(l["title"], l["style"])]
    if invalid:
        raise RuntimeError(f"标题矛盾组合命中 {len(invalid)} 条，例如："
                           f"{invalid[0]['title']}")
    # ③ 整理并返回结果
    return styles, links, {"primary_styles": primary, "unmapped": unmapped}


_PRICE_SCALE_CACHE = None


# _price_scale
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _price_scale(styles: list[dict]) -> float:
    global _PRICE_SCALE_CACHE
    if _PRICE_SCALE_CACHE is None:
        mean_price = sum(s["base_price"] for s in styles) / len(styles)
        _PRICE_SCALE_CACHE = config.AVG_ORDER_VALUE / (mean_price * 1.62 * 0.955)
    return _PRICE_SCALE_CACHE


# _ordinary_launch
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _ordinary_launch(link: dict, rng: random.Random) -> date:
    if link["is_summer"]:
        return date(2025, 4, 1) + timedelta(days=rng.randint(0, 300))
    # 秋冬款既有链接：2025 年至 2026 年 8 月
    return date(2025, 1, 1) + timedelta(days=rng.randint(0, 590))


# _assign_new_arrivals
# 作用：分配 10 条新品，上架日期落在近 30 天内，且只选秋冬/春秋品类。
def _assign_new_arrivals(shop_links: list[dict], rng: random.Random) -> None:
    """分配 10 条新品，上架日期落在近 30 天内，且只选秋冬/春秋品类。"""
    occupied = {id(l) for l in shop_links if l["is_primary"] == 1}
    candidates = [l for l in shop_links if id(l) not in occupied and not l["is_summer"]]
    rng.shuffle(candidates)
    # A5 三类样例的品类与上架天数固定；其余新品使用合理年龄
    sample_ages = {"毛呢裤": 14, "卫衣": 3, "T恤": 8}
    ages = [21, 27, 10, 18, 25, 6, 30]
    chosen = []
    for category in ("毛呢裤", "卫衣", "T恤"):
        for link in candidates:
            if link["style"]["category_l2"] == category and link not in chosen:
                chosen.append(link)
                break
    for link in candidates:
        if len(chosen) >= config.NEW_LINK_SAMPLE_COUNT:
            break
        if link not in chosen:
            chosen.append(link)
    extra_index = 0
    for link in chosen:
        category = link["style"]["category_l2"]
        if category in sample_ages:
            age = sample_ages[category]
        else:
            age = ages[extra_index % len(ages)]
            extra_index += 1
        link["new_arrival"] = True
        link["launch_date"] = config.END_DATE - timedelta(days=age - 1)
        link["peak_units"] = rng.randint(30, 80)
        link["new_target_buyers"] = rng.randint(*config.NEW_LINK_TARGET_BUYERS)


# =====================================================================
# T1 订单
# =====================================================================

MEMBER_NAMES = ["夏日微风1988", "清风徐来_01", "老张的衣柜", "南山南1990", "岁月静好66",
                "闲云野鹤", "松间明月", "临风听雨", "北城以北", "秋水长天"]
ADDRESS_REGIONS = ["江苏省南京市江宁区", "浙江省杭州市余杭区", "山东省青岛市市北区",
                   "广东省广州市天河区", "四川省成都市武侯区", "河南省郑州市金水区",
                   "湖北省武汉市洪山区", "北京市朝阳区"]
LOGISTICS = ["中通快递", "圆通速递", "韵达快递", "申通快递", "顺丰速运"]


# _month_weight
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _month_weight(link: dict, day: date) -> float:
    style = link["style"]
    return config.SEASON_RULES[(style["category_l2"], style["season_key"],
                                style["material"])][day.month - 1]


# _new_link_daily_units
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _new_link_daily_units(link: dict, age: int) -> int:
    target = link.get("new_target_buyers", 0)
    if target <= 0 or age <= 0:
        return 0

    # cumulative
    # 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
    def cumulative(days: int) -> float:
        return target * (min(days, 30) / 30.0) ** 1.2

    return max(0, int(round(cumulative(age) - cumulative(age - 1))))


# _make_order_rows
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _make_order_rows(link: dict, day: date, main_seq: int, rng: random.Random,
                     order_status: str, paid_at: datetime | None,
                     units_budget: int) -> list[dict]:
    # ① 准备输入与上下文
    shop_idx = config.SHOPS.index(link["shop_id"])
    order_id = f"382910{shop_idx}{day.timetuple().tm_yday:04d}{main_seq:08d}"
    order_id = order_id[:19].ljust(19, "0")
    child_count = 1 if (units_budget < 2 or rng.random() < 0.88) else 2
    child_rows = []
    # ② 处理主体数据
    remaining = units_budget
    order_total = 0.0
    for c in range(child_count):
        qty = 1
        if remaining > 1:
            qty = rng.choice([1, 1, 1, 1, 2, 2, 3])
            qty = min(qty, remaining)
        remaining -= qty
        goods = round(link["price"] * qty, 2)
        discount = 0.0 if rng.random() < 0.55 else round(
            goods * rng.choice([0.05, 0.10]), 2)
        shipping = 0.0 if rng.random() < 0.88 else rng.choice([8.0, 10.0, 12.0])
        line_pay = round(goods - discount + shipping, 2)
        order_total += line_pay
        style = link["style"]
        size = rng.choice(link["sizes"])
        created = datetime.combine(day, datetime.min.time()) + timedelta(
            hours=rng.randint(7, 22), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
        paid = paid_at
        shipped = None
        received = None
        if paid is not None and order_status != "交易关闭":
            if order_status in ("卖家已发货", "交易成功"):
                shipped = paid + timedelta(hours=rng.randint(6, 30))
            if order_status == "交易成功":
                received = shipped + timedelta(days=rng.randint(2, 6)) if shipped else None
        refund_status = "无退款"
        refund_amount = 0.0
        if order_status != "等待买家付款" and rng.random() < link["refund_prop"]:
            roll = rng.random()
            if roll < 0.60:
                refund_status = "退款成功"
                refund_amount = line_pay
            elif roll < 0.80:
                refund_status = "部分退款"
                refund_amount = round(line_pay * rng.uniform(0.30, 0.70), 2)
            else:
                refund_status = "退款中"
                refund_amount = round(line_pay * rng.uniform(0.30, 0.70), 2)
        if rng.random() < 0.008:
            refund_status = ""
        merchant_code = ""
        if link["mapped"] and rng.random() >= 0.20:
            merchant_code = f"{style['style_code']}-{style['color_code']}-{size}"
        child_rows.append({
            "订单编号": order_id,
            "子订单编号": order_id + f"{c + 1:02d}",
            "买家会员名": "" if rng.random() < 0.08 else rng.choice(MEMBER_NAMES),
            "宝贝ID": link["item_id"],
            "宝贝标题": link["title"],
            "商品属性": f"颜色分类:{style['color_name']};尺码:{size}",
            "商家编码": merchant_code,
            "购买数量": str(qty),
            "宝贝单价": _money(link["price"]),
            "买家应付货款": _money(goods),
            "买家应付邮费": _money(shipping),
            "优惠金额": _money(discount),
            "总金额": _money(round(goods + shipping, 2)),
            "买家实付金额": "",
            "订单状态": order_status,
            "订单创建时间": _dt_variants(created, rng),
            "订单付款时间": _dt_variants(paid, rng),
            "发货时间": _dt_variants(shipped, rng),
            "确认收货时间": _dt_variants(received, rng),
            "收货人姓名": rng.choice(["张*", "李*", "王*", "刘*", "陈*", "杨*"]),
            "收货地址": f"{rng.choice(ADDRESS_REGIONS)}双龙大道***号",
            "联系手机": f"1{rng.randint(3,9)}{rng.randint(0,9)}****{rng.randint(1000,9999)}",
            "物流公司": "" if shipped is None else rng.choice(LOGISTICS),
            "物流单号": "" if shipped is None else f"7583{rng.randint(100000,999999)}{rng.randint(1000,9999)}",
            "买家留言": rng.choice(["", "", "", "", "请发顺丰，谢谢", "尺码建议再确认"]),
            "卖家备注": rng.choice(["", "", "", "", "老客复购"]),
            "退款状态": refund_status,
            "退款金额": _money(refund_amount),
            "_line_pay": line_pay,
            "_child_qty": qty,
        })
    for row in child_rows:
        row["买家实付金额"] = _money(round(order_total, 2))
    # ③ 整理并返回结果
    return child_rows


# generate_t1
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def generate_t1(links: list[dict], dates: list[date], rng: random.Random
                ) -> tuple[list[dict], dict, dict, list[str], dict]:
    # ① 准备输入与上下文
    headers = [f["cn"] for f in field_spec.T1_FIELDS]
    rows: list[dict] = []
    activity: dict[tuple[str, str, str], dict] = {}
    daily_counts: dict[tuple[str, str], int] = {}
    main_seq = 0
    by_shop = {shop: [l for l in links if l["shop_id"] == shop] for shop in config.SHOPS}
    last_sold: dict[str, int] = {}

    for shop in config.SHOPS:
        shop_links = by_shop[shop]
        for day in dates:
            day_key = day.strftime("%Y-%m-%d")
            targets = []
            for link in shop_links:
                if link["launch_date"] is None or day < link["launch_date"]:
                    continue
                age = (day - link["launch_date"]).days + 1
                if link["new_arrival"] and age <= 30:
                    units = _new_link_daily_units(link, age)
                    weight = 1.0
                else:
                    weight = _month_weight(link, day)
                    units = int(round(link["peak_units"] * weight / 30.0 *
                                      rng.uniform(0.65, 1.35)))
                    if link["tier"] is not None or weight > 0.15:
                        units = max(1, units)
                if units <= 0:
                    continue
                targets.append((units, link, weight))
            # 头部链接与新品优先；其余按「最久未售」轮换，保证长尾近期也有成交
            forced = [item for item in targets
                      if item[1]["is_primary"] == 1 or (item[1]["new_arrival"]
                                                        and (day - item[1]["launch_date"]).days < 30)]
            forced_ids = {item[1]["item_id"] for item in forced}
            others = [item for item in targets if item[1]["item_id"] not in forced_ids]
            others.sort(key=lambda item: (last_sold.get(item[1]["item_id"], -999),
                                          -item[0], rng.random()))
            selected = forced + others[: max(0, config.DAILY_SELLING_LINKS - len(forced))]
            selected = selected[:config.DAILY_SELLING_LINKS]
            for _, chosen_link, _ in selected:
                last_sold[chosen_link["item_id"]] = day.toordinal()
            daily_counts[(shop, day_key)] = len(selected)

            for units, link, weight in selected:
                units_left = units
                order_count = 0
                sales = 0.0
                while units_left > 0:
                    main_seq += 1
                    status = "交易成功" if rng.random() < 0.85 else (
                        "卖家已发货" if rng.random() < 0.67 else "买家已付款")
                    paid = datetime.combine(day, datetime.min.time()) + timedelta(
                        hours=rng.randint(8, 23), minutes=rng.randint(0, 59),
                        seconds=rng.randint(0, 59))
                    child_rows = _make_order_rows(link, day, main_seq, rng, status,
                                                  paid, units_left)
                    sold = sum(r["_child_qty"] for r in child_rows)
                    units_left -= sold
                    order_count += 1
                    sales += sum(r["_line_pay"] for r in child_rows)
                    rows.extend(child_rows)
                key = (shop, link["item_id"], day_key)
                bucket = activity.setdefault(key, {"units": 0, "orders": 0,
                                                   "sales": 0.0})
                bucket["units"] += units
                bucket["orders"] += order_count
                bucket["sales"] += sales

            # 补充非常规数据订单：交易关闭、等待买家付款
            if day.toordinal() % 2 == 0:
                tier_links = [l for l in shop_links if l["tier"] is not None]
                victim = rng.choice(tier_links)
                main_seq += 1
                closed_paid = datetime.combine(day, datetime.min.time()) + timedelta(
                    hours=rng.randint(9, 20))
                rows.extend(_make_order_rows(victim, day, main_seq, rng, "交易关闭",
                                             closed_paid, 1))
                main_seq += 1
                rows.extend(_make_order_rows(victim, day, main_seq, rng,
                                             "等待买家付款", None, 1))

    # ---- 非常规数据注入：金额格式、日期、重复行（与  一致的清洗场景）
    payable_dirty = [i for i, r in enumerate(rows) if r["订单状态"] != "等待买家付款"]
    # ② 处理主体数据
    rng.shuffle(payable_dirty)
    dirty_specs = (
        [("买家应付货款", lambda v: "￥" + v, 12)] +
        [("买家应付货款", lambda v: "", 6)] +
        [("买家应付货款", lambda v: "未知", 5)] +
        [("买家应付货款", lambda v: "-89.00", 5)] +
        [("优惠金额", lambda v: "", 8)] +
        [("优惠金额", lambda v: "N/A", 4)] +
        [("买家应付邮费", lambda v: "", 5)] +
        [("退款金额", lambda v: "待核实", 4)] +
        [("退款金额", lambda v: "", 4)]
    )
    cursor = 0
    for field_name, fn, count in dirty_specs:
        for _ in range(count):
            if cursor >= len(payable_dirty):
                break
            idx = payable_dirty[cursor]
            cursor += 1
            rows[idx][field_name] = fn(rows[idx][field_name])
    for _ in range(4):
        if cursor < len(payable_dirty):
            rows[payable_dirty[cursor]]["订单付款时间"] = "2026-13-45 99:99:99"
            cursor += 1
    duplicates = [dict(rows[idx]) for idx in payable_dirty[:12]]
    rows.extend(duplicates)
    rng.shuffle(rows)

    stats = {
        "order_rows": len(rows),
        "duplicate_rows": len(duplicates),
        "unique_child_orders": len({r["子订单编号"] for r in rows}),
        "daily_selling_links": sum(daily_counts.values()),
        "daily_selling_days": len(daily_counts),
    }
    # ③ 整理并返回结果
    return rows, activity, daily_counts, headers, stats


# write_t1
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def write_t1(path: Path, rows: list[dict], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="gbk", newline="", errors="strict") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore",
                                lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# =====================================================================
# T2 商品效果
# =====================================================================

# generate_t2
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def generate_t2(links: list[dict], dates: list[date], activity: dict,
                rng: random.Random) -> tuple[list[list], dict]:
    # ① 准备输入与上下文
    headers = [f["cn"] for f in field_spec.T2_FIELDS]
    rows: list[list] = []
    by_shop = {shop: [l for l in links if l["shop_id"] == shop] for shop in config.SHOPS}
    state: dict[str, dict] = {}
    # ② 处理主体数据
    for shop in config.SHOPS:
        for link in by_shop[shop]:
            key = f"{shop}|{link['item_id']}"
            state[key] = {
                "year": round(link["price"] * max(link["peak_units"], 1) *
                              rng.uniform(90, 150), 2),
                "month": 0.0, "month_units": 0, "month_key": None,
            }
    active_counts = []
    for day in dates:
        day_key = day.strftime("%Y-%m-%d")
        for shop in config.SHOPS:
            shop_links = by_shop[shop]
            active = []
            on_sale = [l for l in shop_links if l["item_status"] == "在售"]
            for link in shop_links:
                if link["launch_date"] is None or day < link["launch_date"]:
                    continue
                key = (shop, link["item_id"], day_key)
                has_activity = key in activity
                if has_activity or (link in on_sale and rng.random() < 0.20):
                    active.append(link)
            active_counts.append(len(active))
            for link in active:
                key = (shop, link["item_id"], day_key)
                act = activity.get(key, {"units": 0, "orders": 0, "sales": 0.0})
                st = state[f"{shop}|{link['item_id']}"]
                month_key = (day.year, day.month)
                if st["month_key"] != month_key:
                    st["month_key"] = month_key
                    st["month"] = 0.0
                    st["month_units"] = 0
                units = int(act["units"])
                orders = int(act["orders"])
                sales = round(float(act["sales"]), 2)
                if units > 0:
                    visitors = max(8, int(units * rng.uniform(8, 30) +
                                          orders * rng.uniform(8, 20)))
                else:
                    visitors = rng.randint(3, 60)
                page_views = max(visitors, int(visitors * rng.uniform(1.2, 2.4)))
                avg_stay = round(rng.uniform(18, 96), 1)
                bounce = round(rng.uniform(0.30, 0.72), 4)
                favorite_users = int(visitors * rng.uniform(0.001, 0.012))
                cart_users = int(visitors * rng.uniform(0.008, 0.05))
                cart_units = cart_users + int(cart_users * rng.uniform(0.1, 0.6))
                pay_buyers = min(units, orders) if orders else 0
                pay_units = units
                pay_amount = round(sales * rng.uniform(0.98, 1.02), 2) if sales else 0.0
                order_buyers = pay_buyers + (rng.randint(0, 2) if units else 0)
                order_units = units + (rng.randint(0, 2) if units else 0)
                order_amount = round(pay_amount * rng.uniform(1.0, 1.08), 2)
                new_buyers = int(pay_buyers * rng.uniform(0.30, 0.60))
                old_buyers = pay_buyers - new_buyers
                old_pay = round(pay_amount * rng.uniform(0.30, 0.55), 2)
                juhuasuan = round(pay_amount * rng.uniform(0.05, 0.15), 2) \
                    if rng.random() < 0.10 else 0.0
                visitor_avg = round(pay_amount / visitors, 2) if visitors else 0.0
                refund_ratio = 0.24 if link["refund_prop"] > 0.2 else rng.uniform(0.005, 0.04)
                success_refund = round(pay_amount * refund_ratio, 2)
                score = round(rng.uniform(2.5, 4.9), 2)
                st["year"] = round(st["year"] + pay_amount, 2)
                st["month"] = round(st["month"] + pay_amount, 2)
                st["month_units"] += pay_units
                search_visitors = int(visitors * rng.uniform(0.10, 0.40))
                search_pay_buyers = int(pay_buyers * rng.uniform(0.10, 0.40))
                rows.append([
                    link["item_id"], day,
                    visitors, page_views, avg_stay, bounce, favorite_users,
                    cart_units, cart_users, order_buyers, order_units, order_amount,
                    round(order_buyers / visitors, 5) if visitors else 0.0,
                    pay_buyers, pay_units, pay_amount,
                    round(pay_buyers / visitors, 5) if visitors else 0.0,
                    new_buyers, old_buyers, old_pay, juhuasuan, visitor_avg,
                    success_refund, score,
                    st["year"], st["month"], st["month_units"],
                    round(pay_buyers / visitors * rng.uniform(0.6, 1.4), 5)
                    if visitors else 0.0,
                    search_visitors, search_pay_buyers,
                    round(pay_buyers / visitors * rng.uniform(0.3, 0.8), 5)
                    if visitors else 0.0,
                    round(rng.uniform(0.05, 0.30), 5),
                ])
    stats = {"t2_rows": len(rows),
             "avg_active_links_per_day": round(sum(active_counts) / max(len(active_counts), 1), 1)}
    # ③ 整理并返回结果
    return rows, stats


# =====================================================================
# T3 商品推广
# =====================================================================

# generate_t3
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def generate_t3(links: list[dict], dates: list[date], activity: dict,
                rng: random.Random) -> tuple[list[list], dict]:
    # ① 准备输入与上下文
    headers = [f["cn"] for f in field_spec.T3_FIELDS]
    rows: list[list] = []
    plans_by_shop = {}
    for shop_idx, shop in enumerate(config.SHOPS):
        plans = []
        for j in range(8):
            plans.append({
                "plan_id": f"9{shop_idx + 1}{j + 1:06d}",
                "plan_name": ["促进成交_最大化拿量", "促进成交_控成本", "货品加速_控成本",
                              "货品加速_拉新", "人群推广_拉新", "人群推广_控成本",
                              "关键词推广_标准计划", "关键词推广_放量"][j],
                "scene_l1": ["全站推广", "全站推广", "全站推广", "全站推广",
                             "精准人群推广", "精准人群推广", "关键词推广", "关键词推广"][j],
                "scene_l2": ["货品加速", "货品加速", "货品加速", "货品加速",
                             "拉新计划", "拉新计划", "标准计划", "标准计划"][j],
                "low_roi": j in (5, 7),
            })
        plans_by_shop[shop] = plans
    multi_plan_days = 0
    ratio_records = []
    # ② 处理主体数据
    for day in dates:
        day_key = day.strftime("%Y-%m-%d")
        for shop in config.SHOPS:
            plans = plans_by_shop[shop]
            for link in links:
                if link["shop_id"] != shop or link["is_primary"] != 1:
                    continue
                if link["launch_date"] is None or day < link["launch_date"]:
                    continue
                act = activity.get((shop, link["item_id"], day_key))
                if not act or act["sales"] <= 0:
                    continue
                ratio = link.get("ad_ratio") or 0.10
                cost_total = round(act["sales"] * ratio * rng.uniform(0.92, 1.08), 2)
                if cost_total <= 0:
                    continue
                ratio_records.append((link["item_id"], act["sales"], cost_total))
                base_plan = plans[link["index"] % len(plans)]
                slots = [base_plan]
                if (day.toordinal() + link["index"]) % 3 == 0:
                    slots.append(plans[(link["index"] + 3) % len(plans)])
                    multi_plan_days += 1
                shares = [1.0 / len(slots)] * len(slots)
                if len(slots) == 2:
                    shares = [rng.uniform(0.4, 0.6), 0.0]
                    shares[1] = 1.0 - shares[0]
                for plan, share in zip(slots, shares):
                    cost = round(cost_total * share, 2)
                    if cost <= 0:
                        continue
                    ppc = rng.uniform(0.8, 2.0)
                    clicks = max(1, int(round(cost / ppc)))
                    ctr = rng.uniform(0.015, 0.055)
                    impressions = max(clicks, int(round(clicks / ctr)))
                    roi = rng.uniform(1.5, 4.0)
                    total_gmv = round(cost * roi, 2)
                    direct_gmv = round(total_gmv * rng.uniform(0.55, 0.85), 2)
                    indirect_gmv = round(total_gmv - direct_gmv, 2)
                    total_orders = max(1, int(round(total_gmv / (link["price"] * 1.2))))
                    direct_orders = int(round(total_orders * rng.uniform(0.55, 0.85)))
                    indirect_orders = total_orders - direct_orders
                    total_carts = int(clicks * rng.uniform(0.02, 0.08))
                    direct_carts = int(round(total_carts * rng.uniform(0.55, 0.85)))
                    indirect_carts = total_carts - direct_carts
                    favorite_count = int(clicks * rng.uniform(0.005, 0.03))
                    total_fav_cart = favorite_count + total_carts
                    cart_users_click = max(1, int(clicks * rng.uniform(0.01, 0.045)))
                    click_cart_rate = round(cart_users_click / clicks, 5)
                    rows.append([
                        datetime.combine(day, datetime.min.time()),
                        plan["scene_l1"], plan["scene_l2"], config.PROMOTION_SUBJECT_TYPE,
                        link["item_id"], link["title"], link["item_id"], link["title"],
                        plan["plan_id"], plan["plan_name"],
                        impressions, clicks, cost,
                        round(clicks / impressions, 5),
                        round(cost / clicks, 2),
                        round(cost / impressions * 1000, 2),
                        direct_gmv, indirect_gmv, total_gmv, total_orders,
                        direct_orders, indirect_orders,
                        round(total_orders / clicks, 5),
                        cart_users_click, click_cart_rate,
                        round(total_gmv / cost, 2) if cost else 0.0,
                        total_carts, direct_carts, indirect_carts,
                        round(total_carts / clicks, 5),
                        favorite_count, total_fav_cart,
                    ])
    ratio_by_item = {}
    for item_id, sales, cost in ratio_records:
        bucket = ratio_by_item.setdefault(item_id, {"sales": 0.0, "cost": 0.0})
        bucket["sales"] += sales
        bucket["cost"] += cost
    ratios = {item: (bucket["cost"] / bucket["sales"]
                     if bucket["sales"] else 0.0)
              for item, bucket in ratio_by_item.items()}
    stats = {"t3_rows": len(rows), "multi_plan_item_days": multi_plan_days,
             "low_roi_plans": 4, "main_push_ad_ratios": ratios}
    # ③ 整理并返回结果
    return rows, stats


# =====================================================================
# 主数据映射表
# =====================================================================

# build_mapping_rows
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def build_mapping_rows(links: list[dict]) -> list[dict]:
    # ① 准备输入与上下文
    rows = []
    for link in links:
        if not link["mapped"]:
            continue
        style = link["style"]
        rows.append({
            "shop_id": link["shop_id"],
            "owner": link["owner"],
            "item_id": link["item_id"],
            "item_title": link["title"],
            "category_l1": style["category_l1"],
            "category_l2": style["category_l2"],
            "style_code": style["style_code"],
            "style_name": style["style_name"],
            "asset_lib_id": style["asset_lib_id"],
            "season_asset_version": style["season_asset_version"],
            "main_image_copy_version": style["main_image_copy_version"],
            "similar_group_id": style["similar_group_id"],
            "item_status": link["item_status"],
            "mapping_source": "系统生成" if link["index"] % 3 == 0 else (
                "手工维护" if link["index"] % 3 == 1 else "批量导入"),
            "frozen_flag": 1 if link["index"] % 97 == 0 else 0,
            "is_primary": link["is_primary"],
            "launch_date": link["launch_date"].strftime("%Y-%m-%d"),
            "remark": "",
        })
    # 相似链接串款：两个相似链接组内各混入一个不同款号（模拟主数据归集错误）
    # ② 处理主体数据
    for group_id in ("SG007", "SG022"):
        members = [r for r in rows if r["similar_group_id"] == group_id]
        if len(members) >= 2:
            victim = members[-1]
            other = next(r for r in rows
                         if r["style_code"] != victim["style_code"]
                         and r["similar_group_id"] != group_id)
            victim["style_code"] = other["style_code"]
            victim["style_name"] = other["style_name"]
            victim["mapping_source"] = "批量导入"
            victim["remark"] = "相似链接组归集异常（模拟数据）"
    # ③ 整理并返回结果
    return rows


# write_mapping
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def write_mapping(path: Path, rows: list[dict]) -> None:
    headers = [name for name, _ in field_spec.MAPPING_FIELDS]
    data = [[row.get(h, "") for h in headers] for row in rows]
    notes = [[name, desc] for name, desc in field_spec.MAPPING_FIELDS]
    _write_xlsx(path, "商品主数据映射", headers, data,
                extra_sheet=("字段说明", ["字段", "说明"], notes))


# =====================================================================
# A4 生成后自检与样例
# =====================================================================

# _validate_generation
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def _validate_generation(links: list[dict], mapping: list[dict], activity: dict,
                         daily_counts: dict, t3_stats: dict) -> dict:
    # ① 准备输入与上下文
    from collections import defaultdict
    result: dict = {}
    # 标题逐条扫描
    title_hits = []
    mapping_by_item = {(r["shop_id"], r["item_id"]): r for r in mapping}
    for link in links:
        if not _title_is_valid(link["title"], link["style"]):
            title_hits.append(link["item_id"])
        row = mapping_by_item.get((link["shop_id"], link["item_id"]))
        if row:
            if row["category_l2"] not in link["title"] or link["style"]["material"] not in link["title"]:
                title_hits.append(link["item_id"])
    result["title_conflict_count"] = len(set(title_hits))

    # 11 月品类占比（按 11 月 1~5 日订单销售额）
    nov_sales = defaultdict(float)
    nov_total = 0.0
    for (shop, item_id, day_key), act in activity.items():
        if day_key.startswith("2026-11"):
            row = mapping_by_item.get((shop, item_id))
            category = row["category_l2"] if row else "未映射"
            nov_sales[category] += act["sales"]
            nov_total += act["sales"]
    winter = sum(nov_sales.get(c, 0.0) for c in config.NOVEMBER_WINTER_CATEGORIES)
    anti = sum(nov_sales.get(c, 0.0) for c in config.SUMMER_CATEGORIES)
    result["november_total_sales"] = round(nov_total, 2)
    result["november_winter_share"] = (winter / nov_total) if nov_total else 0.0
    result["november_anti_season_share"] = (anti / nov_total) if nov_total else 0.0
    result["november_category_sales"] = {k: round(v, 2) for k, v in
                                         sorted(nov_sales.items(), key=lambda kv: -kv[1])}

    # 主推款号唯一
    primary_rows = [r for r in mapping if r["is_primary"] == 1]
    result["primary_link_count"] = len(primary_rows)
    result["primary_style_count"] = len({r["style_code"] for r in primary_rows})
    result["primary_style_unique"] = (result["primary_link_count"] ==
                                      result["primary_style_count"])

    # 主推推广花费占比
    ratios = [value for value in t3_stats.get("main_push_ad_ratios", {}).values()]
    result["main_push_ratio_min"] = round(min(ratios), 4) if ratios else 0.0
    result["main_push_ratio_max"] = round(max(ratios), 4) if ratios else 0.0
    result["main_push_ratio_ok"] = bool(ratios) and all(
        0.06 <= value <= 0.18 for value in ratios)

    # 生命周期：在售池中上架 >180 天且近30天零销量
    last30_start = (config.END_DATE - timedelta(days=29)).strftime("%Y-%m-%d")
    recent_units = defaultdict(int)
    # ② 处理主体数据
    for (shop, item_id, day_key), act in activity.items():
        if day_key >= last30_start:
            recent_units[(shop, item_id)] += act["units"]
    on_sale = {shop: [] for shop in config.SHOPS}
    down_count = defaultdict(int)
    for link in links:
        if link["item_status"] == "在售":
            on_sale[link["shop_id"]].append(link)
        else:
            down_count[link["shop_id"]] += 1
        if link["item_status"] == "在售":
            age = (config.END_DATE - link["launch_date"]).days
            if age > config.LIFECYCLE_OLD_DAYS and recent_units[(link["shop_id"], link["item_id"])] == 0:
                result.setdefault("stale_on_sale", []).append(link["item_id"])
    stale = result.pop("stale_on_sale", [])
    result["stale_on_sale_count"] = len(stale)
    result["on_sale_counts"] = {shop: len(items) for shop, items in on_sale.items()}
    result["off_shelf_counts"] = dict(down_count)

    # 日成交链接数
    per_day = [count for (shop, day_key), count in daily_counts.items()]
    result["daily_selling_avg"] = round(sum(per_day) / len(per_day), 2) if per_day else 0

    # 主推/潜力/测试/低表现/滞销/反季样例
    tier_links = [l for l in links if l["is_primary"] == 1]
    samples = []
    roles = [("主推", tier_links[0] if tier_links else None)]
    new_links = [l for l in links if l["new_arrival"] and l["is_primary"] == 0]
    for role, category in (("潜力", "毛呢裤"), ("测试", "卫衣"), ("低表现", "T恤")):
        candidate = next((l for l in new_links if l["style"]["category_l2"] == category), None)
        roles.append((role, candidate))
    slow_pool = [l for l in links if l["item_status"] == "在售" and not l["is_primary"]
                 and l["launch_date"] and
                 config.SLOW_CANDIDATE_MIN_DAYS <= (config.END_DATE - l["launch_date"]).days
                 <= config.SLOW_CANDIDATE_MAX_DAYS]
    slow_pool.sort(key=lambda l: recent_units[(l["shop_id"], l["item_id"])])
    slow = slow_pool[0] if slow_pool else None
    roles.append(("滞销", slow))
    anti = next((l for l in links if l["style"]["category_l2"] == "短裤"
                 and l["style"]["material"] == "冰丝" and l["launch_date"] <= date(2026, 5, 1)), None)
    if anti is None:
        anti = next((l for l in links if l["is_summer"]
                     and l["launch_date"] <= date(2026, 5, 1)), None)
    roles.append(("反季长尾", anti))
    for role, link in roles:
        if not link:
            continue
        recent = sum(act["units"] for (shop, item_id, day_key), act in activity.items()
                     if item_id == link["item_id"] and day_key >= last30_start)
        recent7_start = (config.END_DATE - timedelta(days=6)).strftime("%Y-%m-%d")
        recent7 = sum(act["sales"] for (shop, item_id, day_key), act in activity.items()
                      if item_id == link["item_id"] and day_key >= recent7_start)
        samples.append({
            "role": role, "item_id": link["item_id"], "title": link["title"],
            "category_l2": link["style"]["category_l2"],
            "season_key": link["style"]["season_key"],
            "material": link["style"]["material"],
            "launch_date": link["launch_date"].strftime("%Y-%m-%d"),
            "launch_days": (config.END_DATE - link["launch_date"]).days + 1,
            "is_primary": link["is_primary"],
            "item_status": link["item_status"],
            "recent30_units": recent, "recent7_sales": round(recent7, 2),
            "ad_ratio": round(t3_stats.get("main_push_ad_ratios", {}).get(
                link["item_id"], 0.0), 4),
        })
    result["samples"] = samples
    # ③ 整理并返回结果
    return result


# =====================================================================
# 总入口
# =====================================================================

# generate_all
# 作用：完成模拟数据生成中的该步骤，结果交给调用方继续使用。
def generate_all(verbose: bool = True) -> dict:
    # ① 准备输入与上下文
    rng = random.Random(config.RANDOM_SEED)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    dates = [config.START_DATE + timedelta(days=i) for i in range(config.DAYS)]

    styles, links, extras = build_master(rng)
    rows, activity, daily_counts, t1_headers, t1_stats = generate_t1(links, dates, rng)

    # 生命周期：>180 天且近 30 天零销 -> 已下架
    last30_start = (config.END_DATE - timedelta(days=29)).strftime("%Y-%m-%d")
    recent_units: dict[str, int] = {}
    for (shop, item_id, day_key), act in activity.items():
        if day_key >= last30_start:
            recent_units[f"{shop}|{item_id}"] = recent_units.get(
                f"{shop}|{item_id}", 0) + act["units"]
    for link in links:
        age = (config.END_DATE - link["launch_date"]).days
        if age > config.LIFECYCLE_OLD_DAYS and recent_units.get(
                f"{link['shop_id']}|{link['item_id']}", 0) == 0:
            link["item_status"] = "已下架"

    t2_rows, t2_stats = generate_t2(links, dates, activity, rng)
    t3_rows, t3_stats = generate_t3(links, dates, activity, rng)
    mapping = build_mapping_rows(links)

    # 写文件（按店铺拆分）
    files = []
    # ② 处理主体数据
    for shop in config.SHOPS:
        shop_dir = config.DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        t1_path = shop_dir / f"订单导出_{config.EXPORT_STAMP}_{config.ORDER_EXPORT_TIME}.csv"
        t2_path = shop_dir / f"商品效果_{config.EXPORT_STAMP}.xlsx"
        t3_path = shop_dir / f"商品推广报表_{config.EXPORT_STAMP}.xlsx"
        shop_item_ids = {l["item_id"] for l in links if l["shop_id"] == shop}
        shop_t1 = [r for r in rows if r["宝贝ID"] in shop_item_ids]
        write_t1(t1_path, shop_t1, t1_headers)
        shop_t2 = [r for r in t2_rows if r[0] in shop_item_ids]
        _write_xlsx(t2_path, "商品效果", [f["cn"] for f in field_spec.T2_FIELDS], shop_t2)
        shop_t3 = [r for r in t3_rows if r[6] in shop_item_ids]
        _write_xlsx(t3_path, field_spec.T3_SHEET_NAME,
                    [f["cn"] for f in field_spec.T3_FIELDS], shop_t3)
        files.extend([
            {"path": str(t1_path), "table": "T1", "rows": len(shop_t1),
             "columns": len(t1_headers)},
            {"path": str(t2_path), "table": "T2", "rows": len(shop_t2),
             "columns": len(field_spec.T2_FIELDS)},
            {"path": str(t3_path), "table": "T3", "rows": len(shop_t3),
             "columns": len(field_spec.T3_FIELDS)},
        ])
    write_mapping(config.MAPPING_FILE, mapping)
    files.append({"path": str(config.MAPPING_FILE), "table": "MAPPING",
                  "rows": len(mapping), "columns": len(field_spec.MAPPING_FIELDS)})

    total_units = sum(item["units"] for item in activity.values())
    total_sales = sum(item["sales"] for item in activity.values())
    total_orders = sum(item["orders"] for item in activity.values())
    total_sales_amount = round(total_sales, 2)
    t1_stats.update({"activity_sales": total_sales_amount,
                     "activity_orders": total_orders,
                     "activity_units": total_units,
                     "aov_estimate": round(total_sales / total_orders, 2)
                     if total_orders else 0.0})
    validation = _validate_generation(links, mapping, activity, daily_counts, t3_stats)
    validation["aov_estimate"] = t1_stats["aov_estimate"]
    # 用真实每日链接数替换占位
    stats = {
        "styles": len(styles), "links": len(links),
        "mapped_links": len(mapping),
        "unmapped_links": len(links) - len(mapping),
        "dates": [str(dates[0]), str(dates[-1])],
        "files": files,
        **t1_stats, **t2_stats, **t3_stats,
        "season_validation": validation,
    }
    if verbose:
        print("[数据生成]  季节约束生成完成：款数 %d，链接数 %d（映射 %d / 未映射 %d）"
              % (stats["styles"], stats["links"], stats["mapped_links"],
                 stats["unmapped_links"]))
        for item in files:
            print("[数据生成] %-7s %6d 行 %2d 列  %s"
                  % (item["table"], item["rows"], item["columns"],
                     Path(item["path"]).relative_to(config.BASE_DIR)))
        for sample in validation.get("samples", []):
            print(f"[样例] {sample['role']:<4} {sample['item_id']} | "
                  f"{sample['category_l2']}/{sample['season_key']}/{sample['material']} | "
                  f"上架 {sample['launch_date']}({sample['launch_days']}天) | "
                  f"近30天销量 {sample['recent30_units']} | 近7天销售额 "
                  f"{sample['recent7_sales']} | 主推 {sample['is_primary']} | "
                  f"{sample['title']}")
    # ③ 整理并返回结果
    return stats


if __name__ == "__main__":
    generate_all()
