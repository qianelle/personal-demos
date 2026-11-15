# -*- coding: utf-8 -*-
# 源表读取与整理
# 作用：把三张源文件读成数据表，统一列名、日期、金额与商品编码。
"""源表清洗。

T1：白名单 12 列读入（订单编号 / 买家实付金额仅作主订单级校验，不落库），
    金额解析、日期解析、状态过滤、子订单去重、行级实付计算。
T2：32 列英文映射，累计值按原样保留，不做按日求和。
T3：30 列英文映射，双写列恒等校验，按日×商品聚合（多计划花费相加）。
主数据：映射表载入与唯一性校验。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import config
from src.etl import field_spec

T1_CN = [f["cn"] for f in field_spec.T1_FIELDS]
T1_WHITELIST = field_spec.T1_WHITELIST
T1_READ_COLS = T1_WHITELIST + field_spec.T1_TRANSIENT_ONLY

T2_CN = [f["cn"] for f in field_spec.T2_FIELDS]
T2_EN = [f["en"] for f in field_spec.T2_FIELDS]
T2_NUMERIC = [f["en"] for f in field_spec.T2_FIELDS
              if f["cn"] != "主商品ID" and f["cn"] != "日期"]

T3_CN = [f["cn"] for f in field_spec.T3_FIELDS]
T3_EN = [f["en"] for f in field_spec.T3_FIELDS]
T3_NUMERIC = [f["en"] for f in field_spec.T3_FIELDS
              if f["cn"] not in ("日期", "一级推广场景", "二级推广场景",
                                 "推广主体类型", "推广主体ID", "推广主体名称",
                                 "商品ID", "商品名称", "计划ID", "计划名称")]

_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y.%m.%d %H:%M:%S",
    "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d", "%Y/%m/%d",
    "%Y.%m.%d", "%Y%m%d%H%M%S", "%Y%m%d",
)


# parse_datetime
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat", "-", "—"}:
        return None
    if re.fullmatch(r"\d{14}", text):
        try:
            return datetime.strptime(text, "%Y%m%d%H%M%S")
        except ValueError:
            return None
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d")
        except ValueError:
            return None
    cleaned = text.replace("T", " ")
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(cleaned, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    except (ValueError, TypeError):
        return None


# parse_money
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def parse_money(value) -> tuple[float | None, str | None]:
    if value is None:
        return None, "金额缺失"
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "nat", "-", "—"}:
        return None, "金额缺失"
    cleaned = text.replace("￥", "").replace("¥", "").replace(",", "").replace(" ", "")
    try:
        amount = float(cleaned)
    except ValueError:
        return None, "金额非数值"
    if amount < 0:
        return None, "金额为负"
    return round(amount, 2), None


# _as_text
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


# normalize_item_id
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def normalize_item_id(value) -> str:
    text = _as_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


# =====================================================================
# T1 订单
# =====================================================================

# clean_t1
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def clean_t1(path: Path, shop_id: str) -> tuple[pd.DataFrame, dict, list[dict]]:
    # ① 准备输入与上下文
    df_raw = pd.read_csv(
        path, dtype=str, keep_default_na=False, encoding="gbk",
        usecols=T1_READ_COLS,
    )
    read_rows = len(df_raw)
    source_name = Path(path).name

    # 原始行快照（仅白名单 12 列，敏感字段 列未读入，因此不可能进入快照）
    raw_dicts = df_raw[T1_WHITELIST].to_dict(orient="records")
    raw_rows = [
        json.dumps({cn: str(value) for cn, value in rec.items()}, ensure_ascii=False)
        for rec in raw_dicts
    ]

    dup_mask = df_raw.duplicated(subset=["子订单编号"], keep="first")
    duplicate_rows = int(dup_mask.sum())
    df = df_raw.loc[~dup_mask].reset_index(drop=True)
    raw_rows = [raw for raw, keep in zip(raw_rows, ~dup_mask) if keep]

    # ② 处理主体数据
    records = []
    issue_counter: Counter = Counter()
    for i in range(len(df)):
        row = df.iloc[i]
        issues: list[str] = []

        paid_at = parse_datetime(row["订单付款时间"])
        if paid_at is None:
            issues.append("订单付款时间无法解析/缺失")
        stat_date = paid_at.strftime("%Y-%m-%d") if paid_at else ""

        goods, issue = parse_money(row["买家应付货款"])
        if issue:
            issues.append(f"买家应付货款{issue}")
        discount, issue = parse_money(row["优惠金额"])
        if issue:
            issues.append(f"优惠金额{issue}")
        shipping, issue = parse_money(row["买家应付邮费"])
        if issue:
            issues.append(f"买家应付邮费{issue}")

        try:
            quantity = int(float(_as_text(row["购买数量"])))
        except (ValueError, TypeError):
            quantity = None
            issues.append("购买数量无法解析")

        line_pay = None
        if goods is not None and discount is not None and shipping is not None:
            line_pay = round(goods - discount + shipping, 2)

        order_status = _as_text(row["订单状态"])
        if order_status not in config.PAID_ORDER_STATUS:
            issues.append(f"订单状态不计入销售额（{order_status or '空'}）")

        refund_status = _as_text(row["退款状态"])
        if refund_status not in config.REFUND_STATUS_LIST:
            refund_status = "未知"
        refund_amount, refund_issue = parse_money(row["退款金额"])
        if refund_issue:
            issues.append(f"退款金额{refund_issue}")
        is_refund_completed = int(
            refund_status in ("退款成功", "部分退款") and (refund_amount or 0) > 0)

        valid = (
            paid_at is not None
            and order_status in config.PAID_ORDER_STATUS
            and line_pay is not None
            and quantity is not None
            and quantity >= 1
        )
        if not valid and not issues:
            issues.append("行级实付无法计算")
        issue_counter.update(issues)

        records.append({
            "shop_id": shop_id,
            "source_file": source_name,
            "source_row_no": i + 2,  # 表头为第 1 行
            "child_order_id": _as_text(row["子订单编号"]),
            "item_id": normalize_item_id(row["宝贝ID"]),
            "item_title": _as_text(row["宝贝标题"]),
            "merchant_code": _as_text(row["商家编码"]),
            "quantity": quantity,
            "payable_goods_amount": goods,
            "discount_amount": discount,
            "payable_shipping_fee": shipping,
            "order_status": order_status,
            "paid_at": paid_at.strftime("%Y-%m-%d %H:%M:%S") if paid_at else "",
            "stat_date": stat_date,
            "refund_status": refund_status,
            "refund_amount": refund_amount,
            "line_pay_amount": line_pay,
            "is_refund_completed": is_refund_completed,
            "is_valid": int(valid),
            "issue_flags": json.dumps(issues, ensure_ascii=False),
            "raw_row_json": raw_rows[i],
            "_order_id": _as_text(row["订单编号"]),
            "_buyer_paid_raw": _as_text(row["买家实付金额"]),
        })

    clean = pd.DataFrame(records)
    # 金额防翻倍校验：行级实付合计 vs 主订单级「买家实付金额」去重合计
    # 只在「全部子订单有效且主订单金额可解析」的主订单上比较，避免脏行干扰
    main_validation = _validate_main_order_amount(clean)
    clean = clean.drop(columns=["_order_id", "_buyer_paid_raw"])
    valid = clean[clean["is_valid"] == 1]

    stats = {
        "read_rows": read_rows,
        "duplicate_rows": duplicate_rows,
        "stored_rows": len(clean),
        "valid_rows": len(valid),
        "invalid_rows": len(clean) - len(valid),
        "valid_pay_amount": round(float(valid["line_pay_amount"].sum()), 2),
        "invalid_pay_amount": round(float(
            clean.loc[clean["is_valid"] == 0, "line_pay_amount"].fillna(0).sum()), 2),
        "issue_counter": dict(issue_counter.most_common()),
        "refund_completed_amount": round(float(
            valid.loc[valid["is_refund_completed"] == 1, "refund_amount"].fillna(0).sum()), 2),
        "main_order_validation": main_validation,
        "source_file": source_name,
    }
    validations = [{
        "check_id": "T1_MAIN_ORDER_DUP_AMOUNT",
        "check_name": "主订单级「买家实付金额」重复列校验（有效子订单子集）",
        "expected": "主订单级去重合计 = 行级实付合计",
        "actual": f"主订单级 {main_validation['main_order_sum']:.2f} / "
                  f"行级 {main_validation['line_sum']:.2f}",
        "diff": main_validation["diff"],
        "passed": int(abs(main_validation["diff"]) < 0.01
                      and main_validation["mismatch_orders"] == 0),
        "detail": json.dumps(main_validation, ensure_ascii=False),
    }]
    # ③ 整理并返回结果
    return clean, stats, validations


# _validate_main_order_amount
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def _validate_main_order_amount(clean: pd.DataFrame) -> dict:
    """用「买家实付金额」对行级实付做合计校验；该列只在内存中使用，不落库。

    主订单级金额在同一主订单的多个子订单上重复出现，直接按行求和会翻倍；
    这里先按订单编号去重取一次主订单金额，再与各子订单行级实付之和比较。
    """
    work = clean[["_order_id", "is_valid", "line_pay_amount", "_buyer_paid_raw"]].copy()
    work["all_valid"] = work.groupby("_order_id")["is_valid"].transform("min")
    first = work.drop_duplicates("_order_id")[["_order_id", "_buyer_paid_raw"]].copy()
    parsed = first["_buyer_paid_raw"].map(parse_money)
    first["main_amount"] = [item[0] for item in parsed]
    first["main_issue"] = [item[1] for item in parsed]
    usable = first[first["main_issue"].isna()].set_index("_order_id")
    line_sums = (work[work["all_valid"] == 1]
                 .groupby("_order_id")["line_pay_amount"].sum().round(2))
    joined = usable.join(line_sums, how="inner")
    mismatch = int(((joined["main_amount"] - joined["line_pay_amount"]).abs() > 0.01).sum())
    return {
        "checked_orders": int(len(joined)),
        "skipped_orders": int(len(first) - len(joined)),
        "mismatch_orders": mismatch,
        "line_sum": round(float(joined["line_pay_amount"].sum()), 2),
        "main_order_sum": round(float(joined["main_amount"].sum()), 2),
        "diff": round(float(joined["main_amount"].sum()
                             - joined["line_pay_amount"].sum()), 2),
    }


# =====================================================================
# T2 商品效果
# =====================================================================

# clean_t2
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def clean_t2(path: Path, shop_id: str) -> tuple[pd.DataFrame, dict]:
    df = pd.read_excel(path)
    read_rows = len(df)
    df["item_id"] = df["主商品ID"].map(normalize_item_id)
    df["stat_date"] = pd.to_datetime(df["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    invalid_date = int(df["stat_date"].isna().sum())
    df = df[df["stat_date"].notna() & (df["item_id"] != "")].copy()

    for cn, en in zip(T2_CN, T2_EN):
        if en in ("item_id", "stat_date"):
            continue
        df[en] = pd.to_numeric(df[cn], errors="coerce")

    df["shop_id"] = shop_id
    df = df[["shop_id"] + T2_EN]
    dup = int(df.duplicated(subset=["stat_date", "shop_id", "item_id"], keep="last").sum())
    if dup:
        df = df.drop_duplicates(subset=["stat_date", "shop_id", "item_id"], keep="last")
    df = df.sort_values(["stat_date", "item_id"]).reset_index(drop=True)
    stats = {
        "read_rows": read_rows,
        "t2_rows": len(df),
        "duplicate_keys": dup,
        "invalid_date_rows": invalid_date,
        "t2_visitors": round(float(df["visitors"].fillna(0).sum()), 2),
        "t2_pay_amount": round(float(df["pay_amount"].fillna(0).sum()), 2),
        "t2_year_cum_max": round(float(df["year_cum_pay_amount"].fillna(0).max()), 2),
        "source_file": Path(path).name,
    }
    return df, stats


# =====================================================================
# T3 商品推广
# =====================================================================

# clean_t3
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def clean_t3(path: Path, shop_id: str) -> tuple[pd.DataFrame, pd.DataFrame, dict, list[dict]]:
    # ① 准备输入与上下文
    df = pd.read_excel(path, sheet_name=field_spec.T3_SHEET_NAME)
    read_rows = len(df)
    for cn, en in zip(T3_CN, T3_EN):
        if en == "stat_date":
            df[en] = pd.to_datetime(df[cn], errors="coerce").dt.strftime("%Y-%m-%d")
        elif en in ("item_id", "subject_id", "plan_id"):
            df[en] = df[cn].map(normalize_item_id)
        elif en in T3_NUMERIC:
            df[en] = pd.to_numeric(df[cn], errors="coerce")
        else:
            df[en] = df[cn].astype(str).str.strip()
    df["shop_id"] = shop_id

    # 双写列恒等校验
    id_identity = int((df["subject_id"] == df["item_id"]).sum())
    id_total = len(df)
    name_identity = int((df["subject_name"] == df["item_name"]).sum())
    gmv_bad = int((df["direct_gmv"].fillna(0) + df["indirect_gmv"].fillna(0)
                   - df["total_gmv"].fillna(0)).abs().gt(0.011).sum())
    orders_bad = int((df["direct_orders"].fillna(0) + df["indirect_orders"].fillna(0)
                      - df["total_orders"].fillna(0)).abs().gt(0).sum())
    carts_bad = int((df["direct_carts"].fillna(0) + df["indirect_carts"].fillna(0)
                     - df["total_carts"].fillna(0)).abs().gt(0).sum())
    fav_bad = int((df["favorite_count"].fillna(0) + df["total_carts"].fillna(0)
                   - df["total_fav_cart"].fillna(0)).abs().gt(0).sum())
    # 比率重算校验（点击率 / 加购率 / 点击转化率 保留原列，另做反算一致性校验）
    ctr_recalc_bad = int(
        (df["clicks"].fillna(0) / df["impressions"].replace(0, float("nan"))
         - df["ctr"].fillna(0)).abs().gt(0.0005).sum())

    # ② 处理主体数据
    df_plan = df.copy()
    df_plan = df_plan[["shop_id"] + T3_EN]
    df_plan = df_plan[df_plan["stat_date"].notna() & (df_plan["item_id"] != "")]

    agg = df_plan.groupby(["stat_date", "shop_id", "item_id"], as_index=False).agg(
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        cost=("cost", "sum"),
        direct_gmv=("direct_gmv", "sum"),
        indirect_gmv=("indirect_gmv", "sum"),
        total_gmv=("total_gmv", "sum"),
        total_orders=("total_orders", "sum"),
        direct_orders=("direct_orders", "sum"),
        indirect_orders=("indirect_orders", "sum"),
        total_carts=("total_carts", "sum"),
        direct_carts=("direct_carts", "sum"),
        indirect_carts=("indirect_carts", "sum"),
        favorite_count=("favorite_count", "sum"),
        total_fav_cart=("total_fav_cart", "sum"),
        plan_count=("plan_id", "nunique"),
    )
    agg["ctr"] = (agg["clicks"] / agg["impressions"].replace(0, float("nan"))).round(5)
    agg["click_cvr"] = (agg["total_orders"] / agg["clicks"].replace(0, float("nan"))).round(5)
    agg["roi"] = (agg["total_gmv"] / agg["cost"].replace(0, float("nan"))).round(2)
    agg["cart_rate"] = (agg["total_carts"] / agg["clicks"].replace(0, float("nan"))).round(5)
    agg["cpc"] = (agg["cost"] / agg["clicks"].replace(0, float("nan"))).round(2)
    agg["cpm"] = (agg["cost"] / agg["impressions"].replace(0, float("nan")) * 1000).round(2)

    validations = [
        {"check_id": "T3_ID_DOUBLE_WRITE", "check_name": "T3「推广主体ID」与「商品ID」恒等校验",
         "expected": "两列逐行恒等", "actual": f"{id_identity}/{id_total} 行恒等",
         "diff": float(id_total - id_identity), "passed": int(id_identity == id_total),
         "detail": "校验通过后取「商品ID」作为 item_id，不再按推广主体ID 去重"},
        {"check_id": "T3_NAME_DOUBLE_WRITE", "check_name": "T3「推广主体名称」与「商品名称」同源校验",
         "expected": "两列逐行恒等", "actual": f"{name_identity}/{id_total} 行恒等",
         "diff": float(id_total - name_identity), "passed": int(name_identity == id_total),
         "detail": "同源双写列，仅展示用"},
        {"check_id": "T3_GMV_IDENTITY", "check_name": "T3 总成交金额 = 直接 + 间接",
         "expected": "逐行成立", "actual": f"不成立 {gmv_bad} 行", "diff": float(gmv_bad),
         "passed": int(gmv_bad == 0), "detail": "按原表字段校验，不做重算替换"},
        {"check_id": "T3_ORDER_IDENTITY", "check_name": "T3 总成交笔数 = 直接 + 间接",
         "expected": "逐行成立", "actual": f"不成立 {orders_bad} 行", "diff": float(orders_bad),
         "passed": int(orders_bad == 0), "detail": ""},
        {"check_id": "T3_CART_IDENTITY", "check_name": "T3 总购物车数 = 直接 + 间接",
         "expected": "逐行成立", "actual": f"不成立 {carts_bad} 行", "diff": float(carts_bad),
         "passed": int(carts_bad == 0), "detail": ""},
        {"check_id": "T3_FAV_CART_IDENTITY", "check_name": "T3 总收藏加购数 = 收藏宝贝数 + 总购物车数",
         "expected": "逐行成立", "actual": f"不成立 {fav_bad} 行", "diff": float(fav_bad),
         "passed": int(fav_bad == 0), "detail": ""},
        {"check_id": "T3_CTR_RECALC", "check_name": "T3 点击率反算一致性",
         "expected": "clicks / impressions = 点击率", "actual": f"偏差 {ctr_recalc_bad} 行",
         "diff": float(ctr_recalc_bad), "passed": int(ctr_recalc_bad == 0),
         "detail": "比率列保留原表值，另做反算校验"},
    ]
    stats = {
        "read_rows": read_rows,
        "t3_plan_rows": len(df_plan),
        "t3_item_rows": len(agg),
        "t3_cost": round(float(agg["cost"].fillna(0).sum()), 2),
        "t3_gmv": round(float(agg["total_gmv"].fillna(0).sum()), 2),
        "multi_plan_item_days": int((agg["plan_count"] > 1).sum()),
        "identity_rate": round(id_identity / id_total, 6) if id_total else 0.0,
        "source_file": Path(path).name,
    }
    # ③ 整理并返回结果
    return df_plan, agg, stats, validations


# =====================================================================
# 主数据映射表
# =====================================================================

# load_mapping
# 作用：完成源表读取与整理中的该步骤，结果交给调用方继续使用。
def load_mapping(path: Path) -> tuple[pd.DataFrame, dict, list[dict]]:
    # ① 准备输入与上下文
    df = pd.read_excel(path, sheet_name="映射表", dtype=str)
    df = df.fillna("")
    headers = [name for name, _ in field_spec.MAPPING_FIELDS]
    df = df[headers]
    read_rows = len(df)
    dup = int(df.duplicated(subset=["shop_id", "item_id"], keep="first").sum())
    df = df.drop_duplicates(subset=["shop_id", "item_id"], keep="first")
    # ② 处理主体数据
    for col in ("frozen_flag", "is_primary"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["item_id"] = df["item_id"].map(normalize_item_id)
    df["remark"] = df["remark"].astype(str)
    df = df.sort_values(["shop_id", "item_id"]).reset_index(drop=True)

    style_conflict = (df.groupby("similar_group_id")["style_code"].nunique()
                      .loc[lambda s: s > 1])
    validations = [
        {"check_id": "MAPPING_KEY_UNIQUE", "check_name": "映射表主键 shop_id + item_id 唯一",
         "expected": "无重复", "actual": f"重复 {dup} 行", "diff": float(dup),
         "passed": int(dup == 0), "detail": "物理一张表，逻辑两层：款号归集 / 链接主键"},
        {"check_id": "MAPPING_SIMILAR_GROUP_CONFLICT",
         "check_name": "相似链接组内款号唯一性检查（结构化留痕）",
         "expected": "同组同款", "actual": f"存在冲突的相似链接组 {len(style_conflict)} 个",
         "diff": float(len(style_conflict)), "passed": 1,
         "detail": "冲突即业务异常，由 /diagnostics「相似链接串款」全量列出；"
                   "本校验仅留痕，不阻断流程、不自动修正"},
    ]
    stats = {
        "mapping_rows": len(df),
        "mapping_duplicates": dup,
        "style_count": int(df["style_code"].nunique()),
        "similar_group_count": int(df["similar_group_id"].nunique()),
        "unmapped_links": 0,
    }
    # ③ 整理并返回结果
    return df, stats, validations
