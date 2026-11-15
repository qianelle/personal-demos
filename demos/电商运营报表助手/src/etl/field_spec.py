# -*- coding: utf-8 -*-
# 源表字段说明
# 作用：描述三张源表的列名、类型与用途，供读取和文档使用。
"""字段映射与口径规格（唯一事实来源）。

1. 三张源表的中文字段名逐字取自 docs/source_schema/ 下两份表头依据文件；
2. 中文源字段 -> 英文库字段 -> 口径说明；
3. 指标公式、口径声明、三表结构说明统一在此维护，
   供 /dictionary 页面与 Excel 导出「口径页」共同使用。
"""

from __future__ import annotations

import config

# =====================================================================
# T1 千牛订单（28 列，CSV / GBK / 无 BOM / CRLF / 0 前导行）
# collected=False 的列不读入、不入库、不进宽表、不进报表。
# =====================================================================

T1_FIELDS = [
    {"cn": "订单编号", "en": "order_id", "dtype": "文本", "collected": False,
     "sensitive": False,
     "caliber": "主订单号，仅用于主订单级「买家实付金额」重复求和校验，校验后不落库",
     "note": "18~20 位纯数字；Excel 直接打开会变科学计数法"},
    {"cn": "子订单编号", "en": "child_order_id", "dtype": "文本", "collected": True,
     "sensitive": False,
     "caliber": "子订单粒度主键，去重后作为订单行唯一标识",
     "note": "同主订单多子订单时前缀相同"},
    {"cn": "买家会员名", "en": "buyer_nick", "dtype": "文本", "collected": False,
     "sensitive": True,
     "caliber": config.SENSITIVE_NOTE,
     "note": "买家账号、匿名/注销订单为空"},
    {"cn": "宝贝ID", "en": "item_id", "dtype": "文本", "collected": True,
     "sensitive": False,
     "caliber": "商品标识，与主数据映射表 item_id 显式关联；不与 T2/T3 商品 ID 自动对齐",
     "note": "长数字按文本读取，禁止数值化"},
    {"cn": "宝贝标题", "en": "item_title", "dtype": "文本", "collected": True,
     "sensitive": False,
     "caliber": "商品标题，仅作明细展示，不参与映射推断",
     "note": "含【】与逗号，CSV 内以双引号包裹"},
    {"cn": "商品属性", "en": "sku_attr", "dtype": "文本", "collected": False,
     "sensitive": False,
     "caliber": "白名单外，不写入：SKU 规格仅用于源表核对，本期分析粒度为链接日",
     "note": "无规格商品为空；T2/T3 无 SKU 粒度"},
    {"cn": "商家编码", "en": "merchant_code", "dtype": "文本", "collected": True,
     "sensitive": False,
     "caliber": "商家自定义编码，仅作映射核对辅助；主数据映射以 shop_id + item_id 为准",
     "note": "未维护商家编码时为空，不作为映射唯一依据"},
    {"cn": "购买数量", "en": "quantity", "dtype": "数字", "collected": True,
     "sensitive": False,
     "caliber": "子订单件数，累加为销量",
     "note": "不为空"},
    {"cn": "宝贝单价", "en": "unit_price", "dtype": "金额", "collected": False,
     "sensitive": False,
     "caliber": "白名单外，不写入：售价不参与实付口径计算",
     "note": "纯数字不带 ¥"},
    {"cn": "买家应付货款", "en": "payable_goods_amount", "dtype": "金额", "collected": True,
     "sensitive": False,
     "caliber": "行级实付公式项之一：应付货款 − 优惠金额 + 应付邮费",
     "note": "存在 ¥ 前缀、空值、文本、负数等非常规数据，清洗时逐条留痕"},
    {"cn": "买家应付邮费", "en": "payable_shipping_fee", "dtype": "金额", "collected": True,
     "sensitive": False,
     "caliber": "行级实付公式项之一，包邮为 0.00",
     "note": "空值与文本值进问题列表，不按 0 补齐"},
    {"cn": "优惠金额", "en": "discount_amount", "dtype": "金额", "collected": True,
     "sensitive": False,
     "caliber": "行级实付公式项之一，无优惠为 0.00",
     "note": "空值与文本值进问题列表，不按 0 补齐"},
    {"cn": "总金额", "en": "total_amount", "dtype": "金额", "collected": False,
     "sensitive": False,
     "caliber": "白名单外，不写入：= 货款 + 邮费但未扣优惠，不参与口径计算",
     "note": "与「买家实付金额」口径不同"},
    {"cn": "买家实付金额", "en": "buyer_paid_amount", "dtype": "金额", "collected": False,
     "sensitive": False,
     "caliber": "主订单级金额，同一主订单多子订单重复出现；仅用于主订单级合计校验，不参与任何求和",
     "note": "按行求和会翻倍，禁止入库、禁止进宽表"},
    {"cn": "订单状态", "en": "order_status", "dtype": "文本", "collected": True,
     "sensitive": False,
     "caliber": "交易状态；仅「交易成功 / 卖家已发货 / 买家已付款」计入销售额",
     "note": "等待买家付款、交易关闭不计入"},
    {"cn": "订单创建时间", "en": "created_at", "dtype": "日期时间", "collected": False,
     "sensitive": False,
     "caliber": "白名单外，不写入：报表日期统一取「订单付款时间」的日期部分",
     "note": "多格式非常规数据，仅付款时间参与解析"},
    {"cn": "订单付款时间", "en": "paid_at", "dtype": "日期时间", "collected": True,
     "sensitive": False,
     "caliber": "报表统计日期唯一来源，取日期部分作为 stat_date",
     "note": "多格式、可空；未付款订单为空"},
    {"cn": "发货时间", "en": "shipped_at", "dtype": "日期时间", "collected": False,
     "sensitive": False,
     "caliber": "白名单外，不写入：本期不分析履约时效",
     "note": "未发货为空"},
    {"cn": "确认收货时间", "en": "received_at", "dtype": "日期时间", "collected": False,
     "sensitive": False,
     "caliber": "白名单外，不写入：本期不分析收货时效",
     "note": "未收货为空"},
    {"cn": "收货人姓名", "en": "receiver_name", "dtype": "文本", "collected": False,
     "sensitive": True, "caliber": config.SENSITIVE_NOTE, "note": "收件人，部分脱敏"},
    {"cn": "收货地址", "en": "receiver_address", "dtype": "文本", "collected": False,
     "sensitive": True, "caliber": config.SENSITIVE_NOTE, "note": "常含逗号/换行"},
    {"cn": "联系手机", "en": "receiver_phone", "dtype": "文本", "collected": False,
     "sensitive": True, "caliber": config.SENSITIVE_NOTE, "note": "中间四位脱敏"},
    {"cn": "物流公司", "en": "logistics_company", "dtype": "文本", "collected": False,
     "sensitive": True, "caliber": config.SENSITIVE_NOTE, "note": "虚拟商品/未发货为空"},
    {"cn": "物流单号", "en": "tracking_no", "dtype": "文本", "collected": False,
     "sensitive": True, "caliber": config.SENSITIVE_NOTE, "note": "长数字，未发货为空"},
    {"cn": "买家留言", "en": "buyer_message", "dtype": "文本", "collected": False,
     "sensitive": True, "caliber": config.SENSITIVE_NOTE, "note": "含换行时会撑成多行"},
    {"cn": "卖家备注", "en": "seller_note", "dtype": "文本", "collected": False,
     "sensitive": True, "caliber": config.SENSITIVE_NOTE, "note": "大面积为空"},
    {"cn": "退款状态", "en": "refund_status", "dtype": "文本", "collected": True,
     "sensitive": False,
     "caliber": "退款进度；仅「退款成功 / 部分退款」计为当期已完结退款",
     "note": "「退款中」未完结，不计入净销售额"},
    {"cn": "退款金额", "en": "refund_amount", "dtype": "金额", "collected": True,
     "sensitive": False,
     "caliber": "当期已完结退款金额，用于净销售额扣减与款级退款率",
     "note": "无退款为 0.00；退款后买家实付金额不回写"},
]

T1_WHITELIST = [f["cn"] for f in T1_FIELDS if f["collected"]]
T1_TRANSIENT_ONLY = ["订单编号", "买家实付金额"]

# =====================================================================
# T2 商品效果（32 列，电商后台表头；本项目样本为模拟数据）
# =====================================================================

_T2_RAW = [
    ("主商品ID", "item_id", "文本", "主商品标识，按文本读取；与 T1 宝贝ID、T3 商品ID 显式映射，不自动对齐"),
    ("日期", "stat_date", "日期", "统计日，一行 = 一个主商品ID 在一个统计日"),
    ("商品访客数", "visitors", "数字", "详情页去重人数；推广点击量不可与之相加"),
    ("商品浏览量", "page_views", "数字", "详情页浏览次数（PV），与访客数不同量纲"),
    ("平均停留时长", "avg_stay_seconds", "数字(秒)", "平均停留秒数，派生均值，不跨行求和"),
    ("商品详情页跳出率", "detail_bounce_rate", "比率", "跳出率，比率字段保留原列名，不跨行求和"),
    ("商品收藏人数", "favorite_users", "数字", "收藏去重人数，≠ T3 收藏宝贝数（归因次数）"),
    ("商品加购件数", "cart_units", "数字", "加购件数，与加购人数并列，不合并"),
    ("商品加购人数", "cart_users", "数字", "加购去重人数，与加购件数并列，不合并"),
    ("下单买家数", "order_buyers", "数字", "下单人数"),
    ("下单件数", "order_units", "数字", "下单件数，与支付件数口径不同"),
    ("下单金额", "order_amount", "金额", "拍下金额，未支付也计入，≠ 支付金额"),
    ("下单转化率", "order_cvr", "比率", "下单买家数 / 访客数，分母为访客数"),
    ("支付买家数", "pay_buyers", "数字", "支付人数，款级转化率分子取其合计"),
    ("支付件数", "pay_units", "数字", "支付件数"),
    ("支付金额", "pay_amount", "金额", "商品维度支付金额，未剔事后退款；不与 T1 实付互校或相加"),
    ("商品支付转化率", "pay_cvr", "比率", "支付买家数 / 访客数，≠ T3 点击转化率（分母为点击量）"),
    ("支付新买家数", "new_buyers", "数字", "支付新买家数，与老买家数并列，不自行相加校验"),
    ("支付老买家数", "old_buyers", "数字", "支付老买家数"),
    ("老买家支付金额", "old_buyer_pay_amount", "金额", "支付金额的老客子集，不与支付金额相加"),
    ("聚划算支付金额", "juhuasuan_pay_amount", "金额", "支付金额的渠道子集，不与支付金额相加"),
    ("访客平均价值", "visitor_avg_value", "数字(派生均值)", "支付金额 / 访客数，派生均值，不跨行求和"),
    ("成功退款金额", "success_refund_amount", "金额", "商品维度当日成功退款，与 T1 退款金额口径不同，分别展示"),
    ("竞争力评分", "competitiveness_score", "评分", "评分字段无量纲，不参与金额汇总"),
    ("年累计支付金额", "year_cum_pay_amount", "金额(累计)", "滚动累计值，按原样保留，不按日求和"),
    ("月累计支付金额", "month_cum_pay_amount", "金额(累计)", "滚动累计值，按原样保留，不按日求和"),
    ("月累计支付件数", "month_cum_pay_units", "数字(累计)", "滚动累计值，按原样保留，不按日求和"),
    ("搜索引导支付转化率", "search_pay_cvr", "比率", "搜索渠道子集口径，不换算"),
    ("搜索引导访客数", "search_visitors", "数字", "商品访客数的搜索渠道子集，不与母字段相加"),
    ("搜索引导支付买家数", "search_pay_buyers", "数字", "搜索渠道支付买家数"),
    ("结构化详情引导转化率", "structured_detail_cvr", "比率", "仅确认列名，口径待核实，不换算"),
    ("结构化详情引导成交占比", "structured_detail_gmv_ratio", "比率", "占比类字段不跨行求和"),
]
T2_FIELDS = [
    {"cn": cn, "en": en, "dtype": dtype, "collected": True, "sensitive": False,
     "caliber": caliber, "note": caliber}
    for cn, en, dtype, caliber in _T2_RAW
]

# =====================================================================
# T3 商品推广（32 列，xlsx，sheet「商品报表_样例」； 新增加购人数/加购率）
# =====================================================================

_T3_RAW = [
    ("日期", "stat_date", "日期", "推广数据归属自然日；文件单元格为 datetime 带 00:00:00"),
    ("一级推广场景", "scene_l1", "文本", "推广所属一级场景；中文列名属部分推断，使用文件标注"),
    ("二级推广场景", "scene_l2", "文本", "一级场景下的细分场景；中文列名属部分推断"),
    ("推广主体类型", "subject_type", "文本", "商品推广报表固定为「商品」"),
    ("推广主体ID", "subject_id", "文本", "被推广对象平台 ID；与「商品ID」双写，先校验恒等再取其一"),
    ("推广主体名称", "subject_name", "文本", "被推广对象名称"),
    ("商品ID", "item_id", "文本", "商品维度分析主键；与推广主体ID 双写校验后取此列"),
    ("商品名称", "item_name", "文本", "商品名称，与推广主体名称同源"),
    ("计划ID", "plan_id", "文本", "推广计划 ID；商品ID 去重会丢失计划粒度"),
    ("计划名称", "plan_name", "文本", "推广计划名称"),
    ("展现量", "impressions", "整数", "广告展示次数，可加总"),
    ("点击量", "clicks", "整数", "广告点击次数，与访客数不同量纲"),
    ("花费", "cost", "金额", "推广消耗金额，按计划×商品×日可加总"),
    ("点击率", "ctr", "比率", "点击量 / 展现量，小数存储，跨行需重算"),
    ("平均点击花费", "cpc", "金额", "花费 / 点击量，派生均值，不跨行求和"),
    ("千次展现花费", "cpm", "金额", "花费 / 展现量 × 1000，派生均值，不跨行求和"),
    ("直接成交金额", "direct_gmv", "金额", "推广直接引导成交金额；总成交金额的子集"),
    ("间接成交金额", "indirect_gmv", "金额", "推广间接引导成交金额；总成交金额的子集"),
    ("总成交金额", "total_gmv", "金额", "直接 + 间接；归因周期在口径字典固定为模拟 7 日，不与 T1 实付互校或相加"),
    ("总成交笔数", "total_orders", "整数", "直接 + 间接成交笔数"),
    ("直接成交笔数", "direct_orders", "整数", "直接引导成交笔数"),
    ("间接成交笔数", "indirect_orders", "整数", "间接引导成交笔数"),
    ("点击转化率", "click_cvr", "比率", "总成交笔数 / 点击量，小数存储；平台口径待核实"),
    ("加购人数", "cart_users_click", "整数",
     " 新增列：点击后加购去重人数；与总购物车数并列，不合并"),
    ("加购率", "click_cart_rate", "比率",
     " 新增列：加购人数 / 点击量，小数存储；合计相除不取平均"),
    ("投入产出比", "roi", "数值", "总成交金额 / 花费；比值不可跨行求和，需重算"),
    ("总购物车数", "total_carts", "整数", "直接 + 间接加购数"),
    ("直接购物车数", "direct_carts", "整数", "直接引导加购数"),
    ("间接购物车数", "indirect_carts", "整数", "间接引导加购数"),
    ("购物车率", "cart_rate", "比率", "总购物车数 / 点击量；原「加购率」列改名为购物车率，避免与新增加购率重复"),
    ("收藏宝贝数", "favorite_count", "整数", "推广引导收藏次数，与 T2 收藏人数不同量纲"),
    ("总收藏加购数", "total_fav_cart", "整数", "收藏宝贝数 + 总购物车数"),
]
T3_FIELDS = [
    {"cn": cn, "en": en, "dtype": dtype, "collected": True, "sensitive": False,
     "caliber": caliber, "note": caliber}
    for cn, en, dtype, caliber in _T3_RAW
]
T3_SHEET_NAME = "商品报表_样例"
T3_REDLINE_FIELDS = ["七日花费", "七日直接ROI", "七日总成交金额", "七日点击量",
                       "七日成交笔数", "滚动聚合字段"]

# =====================================================================
# 主数据映射表（粒度 = shop_id + item_id，逻辑两层、物理一张表）
# =====================================================================

MAPPING_FIELDS = [
    ("shop_id", "店铺标识，由 data/shop_a、data/shop_b 子目录注入，源表本身无店铺列"),
    ("owner", "既有字段保留， 页面不读取、不展示、不参与逻辑"),
    ("item_id", "链接（商品）ID，主数据映射主键之一"),
    ("item_title", "链接标题，仅展示，不参与映射推断"),
    ("category_l1", "一级品类，本期固定「中老年男装」"),
    ("category_l2", "二级品类：工装裤/休闲裤/毛呢裤/运动裤/卫裤/卫衣/T恤/棉服/短裤/短袖/迷彩裤"),
    ("style_code", "款号归集键，格式 JS6628（款号主体）；款号完整形态为 JS6628-008-36"),
    ("style_name", "款名，由品类、材质、季节词组合"),
    ("asset_lib_id", "素材库编号，一款一库"),
    ("season_asset_version", "详情页派生素材版本，1~2 版"),
    ("main_image_copy_version", "主图文案版本，按四季文案版本区分"),
    ("similar_group_id", "相似链接组编号，同款跨店链接归入同一组"),
    ("item_status", "链接状态：在售 / 已下架；动销率分母取在售链接数"),
    ("mapping_source", "映射来源：手工维护 / 批量导入 / 系统生成"),
    ("frozen_flag", "冻结标记：1 = 该映射已冻结，不参与自动调整（模拟字段）"),
    ("is_primary", "主推标记：1 = 主推链接，对应筛选「只看主推」"),
    ("launch_date", "上架日期（ 新增），用于新品观察与上架天数计算；不参与销售额口径"),
    ("remark", "备注"),
]

# =====================================================================
# 链接管理表（ 引入、 语义调整为运营主动添加的管理表，唯一新增表）
# =====================================================================

LINK_TAGS_FIELDS = [
    ("shop_id", "店铺标识；主键之一；仅在运营添加链接后写入"),
    ("item_id", "链接 ID；主键之一；必须在在售可选池中"),
    ("tag", "人工标签：测试款 / 潜力款 / 动销款 / 主推款 / 滞销款；单选，可为空"
            "（空即「未打标」派生状态，不是标签值）"),
    ("owner", "既有字段保留， 不读取、不展示、不参与逻辑"),
    ("updated_by", "最近更新人（演示环境固定为演示操作人）"),
    ("updated_at", "最近更新时间"),
]

# =====================================================================
# 宽表字段（英文）
# =====================================================================

WIDE_FIELDS = [
    ("stat_date", "统计日期，取自 T1 订单付款时间日期部分"),
    ("shop_id", "店铺标识，子目录注入"),
    ("item_id", "链接（商品）ID，宽表主键之一"),
    ("style_code", "款号（冗余属性，上卷路径：链接→款）"),
    ("style_name", "款名（冗余属性）"),
    ("category_l1", "一级品类（冗余属性，上卷路径：款→品类）"),
    ("category_l2", "二级品类（冗余属性）"),
    ("asset_lib_id", "素材库编号（冗余属性）"),
    ("season_asset_version", "详情页素材版本（冗余属性）"),
    ("main_image_copy_version", "主图文案版本（冗余属性）"),
    ("similar_group_id", "相似链接组（冗余属性）"),
    ("item_status", "链接状态（冗余属性）"),
    ("mapping_source", "映射来源（冗余属性）"),
    ("frozen_flag", "冻结标记（冗余属性）"),
    ("is_primary", "主推标记（冗余属性）"),
    ("mapping_status", "映射状态：已映射 / 未映射"),
    ("pay_amount", "行级实付合计：买家应付货款 − 优惠金额 + 买家应付邮费，按子订单编号去重后汇总"),
    ("net_amount", "净销售额：实付 − 当期已完结退款"),
    ("units", "销量：购买数量合计"),
    ("order_count", "订单数：去重子订单编号数"),
    ("refund_amount", "当期已完结退款金额（退款成功 / 部分退款）"),
    ("refund_order_count", "发生当期已完结退款的子订单数"),
    ("visitors", "访客数（T2 商品访客数合计，人数可跨日相加）"),
    ("page_views", "浏览量（T2）"),
    ("pay_buyers", "支付买家数（T2，款级转化率分子）"),
    ("t2_pay_amount", "T2 支付金额（保留原口径，不与实付互校或相加）"),
    ("t2_refund_amount", "T2 成功退款金额（保留原口径，不与 T1 退款互校）"),
    ("cart_units", "加购件数（T2）"),
    ("cart_users", "加购人数（T2）"),
    ("favorite_users", "收藏人数（T2）"),
    ("avg_stay_seconds", "平均停留时长（T2，派生均值，不跨行求和）"),
    ("ad_cost", "推广花费（T3，多计划按日×商品相加）"),
    ("ad_gmv", "推广总成交金额（T3，按归因周期统计，不与实付互校）"),
    ("ad_orders", "推广总成交笔数（T3）"),
    ("ad_clicks", "推广点击量（T3）"),
    ("ad_impressions", "推广展现量（T3）"),
    ("ad_carts", "推广总购物车数（T3）"),
    ("ad_plan_count", "当日参与推广的计划数（T3 计划维计数）"),
    ("ad_roi", "投产比 = 推广总成交金额 / 推广花费（区间重算，不取计划均值）"),
    ("conversion_rate", "转化率 = 支付买家数 / 访客数（款级合计相除，不取算术平均）"),
    ("refund_rate", "退款率 = 当期已完结退款金额 / 实付金额"),
    ("aov", "客单价 = 实付金额 / 订单数"),
    ("is_active", "是否动销：当日实付金额 > 0"),
    ("year_month", "年月，用于月度聚合"),
    ("week_start", "自然周起始日（周一），用于周口径聚合"),
]

# =====================================================================
# 异常表 / 日志表字段
# =====================================================================

LOG_TABLES = [
    ("etl_log", "ETL 运行日志：步骤、级别、消息、行数"),
    ("source_file_probe", "源文件探测结果：编码、行列数、表头、首行样例"),
    ("fact_order_line", "订单清洗行表（T1 白名单 12 列 + 派生金额与清洗标记）"),
    ("fact_item_traffic_daily", "T2 商品效果日表（32 列英文映射）"),
    ("fact_ad_plan_daily", "T3 推广计划日表（32 列英文映射，保留计划粒度）"),
    ("fact_ad_item_daily", "T3 按日×商品聚合表（多计划花费相加）"),
    ("fact_wide_daily", "宽表：日期 × 店铺 × 链接，主键 stat_date + shop_id + item_id"),
    ("dim_item_mapping", "商品主数据映射表（shop_id + item_id）"),
]

# =====================================================================
# 指标口径
# =====================================================================

METRIC_DEFS = [
    {
        "name": "销售额",
        "formula": "SUM(行级实付)，行级实付 = 买家应付货款 − 优惠金额 + 买家应付邮费",
        "includes": "含运费；订单状态为交易成功 / 卖家已发货 / 买家已付款；按子订单编号去重",
        "excludes": "不含跨期退款扣减、不含等待买家付款与交易关闭订单、不含金额解析失败与负值行",
        "date": "取订单付款时间的日期部分",
        "note": "唯一权威销售额口径；不与其他系统支付金额互校",
    },
    {
        "name": "净销售额",
        "formula": "销售额 − 当期已完结退款金额",
        "includes": "当期已完结退款（退款成功 / 部分退款）",
        "excludes": "不含跨期回溯退款，不含退款中、不含 T2 成功退款金额",
        "date": "退款按订单付款日期归属当期",
        "note": "不跨期重算",
    },
    {
        "name": "销量",
        "formula": "SUM(购买数量)",
        "includes": "有效订单行的购买数量",
        "excludes": "不含退款行扣减（退款不扣销量）",
        "date": "订单付款日期",
        "note": "件数口径",
    },
    {
        "name": "订单数",
        "formula": "COUNT(DISTINCT 子订单编号)",
        "includes": "有效订单行的去重子订单编号",
        "excludes": "主订单编号不在白名单，不按主订单计数",
        "date": "订单付款日期",
        "note": "本期订单数 = 子订单口径，已在字段映射表声明",
    },
    {
        "name": "客单价",
        "formula": "销售额 / 订单数",
        "includes": "含运费实付",
        "excludes": "不含退款扣减",
        "date": "同销售额",
        "note": "保留两位小数",
    },
    {
        "name": "访客数",
        "formula": "SUM(T2 商品访客数)",
        "includes": "详情页去重人数按日累加",
        "excludes": "不与推广点击量相加或互校",
        "date": "T2 日期",
        "note": "人数按日可加，跨日不去重",
    },
    {
        "name": "转化率",
        "formula": "SUM(支付买家数) / SUM(访客数)",
        "includes": "款级、区间级均按合计相除",
        "excludes": "不取各款转化率的算术平均；不与 T3 点击转化率混用",
        "date": "T2 日期",
        "note": "款级转化率口径",
    },
    {
        "name": "退款率",
        "formula": "SUM(当期已完结退款金额) / SUM(销售额)",
        "includes": "款级、区间级均按合计相除",
        "excludes": "不取算术平均；不含退款中；不含 T2 成功退款金额",
        "date": "订单付款日期",
        "note": "款级退款率超标判定阈值 8%",
    },
    {
        "name": "推广花费",
        "formula": "SUM(T3 花费)",
        "includes": "同商品同日多计划花费相加",
        "excludes": "不包含其他推广平台花费",
        "date": "T3 日期",
        "note": "金额纯数字无 ¥",
    },
    {
        "name": "推广成交金额",
        "formula": "SUM(T3 总成交金额)",
        "includes": "直接 + 间接归因成交",
        "excludes": "不与销售额相加或互校",
        "date": "T3 日期",
        "note": "归因周期固定为 7 日（模拟值），见口径声明",
    },
    {
        "name": "投产比",
        "formula": "推广成交金额 / 推广花费",
        "includes": "区间级按合计相除",
        "excludes": "不取计划投产比算术平均；花费为 0 时不计算",
        "date": "T3 日期",
        "note": "页面仅作展示与核对筛选参考，不再按固定阈值判定",
    },
    {
        "name": "周环比",
        "formula": "(本周 − 上周) / 上周",
        "includes": "自然周（周一至周日）",
        "excludes": "不按滚动 7 天计算",
        "date": "自然周",
        "note": "周口径固定为自然周",
    },
    {
        "name": "推广花费占比",
        "formula": "推广花费 / 订单行级实付销售额",
        "includes": "分子分母同为金额、同为当期；按链接 / 款 / 品类 / 店铺 / 全店各层级合计相除",
        "excludes": "不取各对象算术平均；不使用推广成交金额作分子或分母",
        "date": "T3 日期与订单付款日期同区间",
        "note": " 新增唯一指标；推广成交金额为归因口径，与订单实付不构成相除关系",
    },
]

