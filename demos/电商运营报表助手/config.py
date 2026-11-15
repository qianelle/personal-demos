# -*- coding: utf-8 -*-
# 全局配置
# 作用：集中维护路径、数据规模、时间区间、业务口径、标签、色板与报表配置。
"""项目全局配置。

所有路径均基于本文件位置相对定位，不写死盘符。
模拟数据规模、时间口径、阈值集中在本文件，可修改后重新运行 run.py。
 扩展：店铺中文名、默认近 7 天、标签与数据范围、推广场景映射、分层区间。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------- 路径

# ── 路径与目录 ──
# 作用：集中定义项目内各目录与数据库文件位置。
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SRC_DIR = BASE_DIR / "src"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DOCS_DIR = BASE_DIR / "docs"
OUTPUT_DIR = BASE_DIR / "output"
VENDOR_DIR = STATIC_DIR / "vendor"

DB_PATH = DATA_DIR / "warehouse.db"
MAPPING_FILE = DATA_DIR / "商品主数据映射表.xlsx"

# ---------------------------------------------------------------- 数据规模

# ── 数据规模 ──
# 作用：定义店铺数、链接数、成交链接数和客单价目标。
N_SHOPS = 1
SHOPS = ["shop_a"]
# 显示层名称：shop_id、目录、宽表主键、源文件均保持不变，仅展示与导出使用中文店名
SHOP_DISPLAY = {"shop_a": "A男装旗舰店"}
SHOP_NAMES = SHOP_DISPLAY  # 兼容旧引用

ONSALE_LINKS = 220            # 全店在售链接目标值（生成后按生命周期校验）
TOTAL_LINKS_PER_SHOP = 266    # 单店生成链接数：生命周期规则后约 220 条在售
DAILY_SELLING_LINKS = 40      # 每天有成交的链接
DAYS = 95                     # 时间跨度：08-06 ~ 11-08（95 天）
AVG_ORDER_VALUE = 150         # 客单价设计目标（元）
PRICE_CALIBRATION = 1.48      # 价格校准系数：使模拟数据行级客单价接近 AVG_ORDER_VALUE
TOP_TIER = [(2, 1000, 1600), (3, 500, 1000), (5, 100, 500)]  # 月销量分层
ADS_LINKS = 20                # 主推链接总数（两店合计）：TOP_TIER 头部链接参与推广
PRIMARY_LINKS_PER_SHOP = 10   # 每店主推/分层链接数：2 + 3 + 5

RANDOM_SEED = 20261106

# 数据时间范围：固定截止日，便于结果可复现
# ── 数据时间范围 ──
# 作用：定义数据截止日、起始日与默认查看窗口。
END_DATE = date(2026, 11, 8)
START_DATE = END_DATE - timedelta(days=DAYS - 1)
DEFAULT_WINDOW_DAYS = 7       # 默认视图：近 7 天

EXPORT_STAMP = END_DATE.strftime("%Y%m%d")
ORDER_EXPORT_TIME = "235900"

# ---------------------------------------------------------------- 业务口径

# ── 商品与订单口径 ──
# 作用：定义品类、材质、订单状态和退款状态。
CATEGORY_L1 = "中老年男装"
CATEGORY_L2 = [
    "工装裤", "休闲裤", "毛呢裤", "运动裤", "卫裤", "卫衣",
    "T恤", "棉服", "短裤", "短袖", "迷彩裤",
]
BASE_PRICE = {
    "工装裤": 129.0, "休闲裤": 119.0, "毛呢裤": 159.0, "运动裤": 99.0,
    "卫裤": 89.0, "卫衣": 139.0, "T恤": 79.0, "棉服": 259.0,
    "短裤": 69.0, "短袖": 89.0, "迷彩裤": 109.0,
}
MATERIALS = ["纯棉", "冰丝"]
SEASON_KEYS = ["春秋", "夏季", "加绒", "羊羔绒"]
ITEM_STATUS = ["在售", "已下架"]
MAPPING_SOURCES = ["手工维护", "批量导入", "系统生成"]

PAID_ORDER_STATUS = ["已付款", "已发货", "退款成功", "部分退款"]
INVALID_ORDER_STATUS = ["已关闭"]
REFUND_STATUS_LIST = ["无退款", "退款成功", "部分退款", "退款中"]

ATTRIBUTION_WINDOW_DAYS = 7      # 推广归因周期（模拟值，写入口径字典）
PROMOTION_SCENE_L1 = ["全站推广", "关键词推广", "精准人群推广"]
PROMOTION_SCENE_L2 = ["货品加速", "标准计划", "拉新计划"]
PROMOTION_SUBJECT_TYPE = "商品"

SENSITIVE_NOTE = "源表含 敏感字段，本项目不写入"

# ----------------------------------------------------------------  标签与数据范围

# ── 标签与数据范围 ──
# 作用：定义人工标签、演示操作人和数据范围。
TAG_OPTIONS = ["测试款", "潜力款", "动销款", "主推款", "滞销款"]
TAG_DEFINITIONS = {
    "测试款": "新链接小流量验证阶段，观察点击与加购表现",
    "潜力款": "上架 30 天内支付买家数达到观察阈值，具备放量潜力",
    "动销款": "报告期内有稳定成交，维持常态化运营",
    "主推款": "运营确认的主推链接，集中推广与素材资源",
    "滞销款": "长期零成交或低动销，进入人工复核清单",
}
# 无账号体系：以固定的演示操作人模拟「仅我的链接」，不做登录与权限
DEMO_OPERATOR = "演示环境"
OWNER_POOL = {
    "shop_a": ["运营A", "运营B", "运营C", "运营D", "运营E", "运营F"],
}
DATA_SCOPE_ALL = "all"
DATA_SCOPE_MINE = "mine"
DATA_SCOPE_OWNER_PREFIX = "owner:"

NEW_LAUNCH_DAYS = 30             # 新品观察窗口
NEW_LAUNCH_PAY_BUYERS_TARGET = 20  # 新品观察达标线（仅标记）
ZERO_SALES_DAYS = 30             # 零销量候选观察窗口

# 链接销售分层维度与分箱（config 可配置；页面可切换维度）
SALES_DISTRIBUTION_DIMENSIONS = {
    "pay_buyers": {
        "label": "支付买家数",
        "unit": "人",
        "bins": [0, 1, 10, 30, 100, 300, float("inf")],
        "labels": ["0 人", "1~9 人", "10~29 人", "30~99 人", "100~299 人", "300 人以上"],
    },
    "units": {
        "label": "销量",
        "unit": "件",
        "bins": [0, 1, 10, 30, 100, 300, float("inf")],
        "labels": ["0 件", "1~9 件", "10~29 件", "30~99 件", "100~299 件", "300 件以上"],
    },
    "sales": {
        "label": "销售额",
        "unit": "元",
        "bins": [0, 0.0001, 1000, 5000, 20000, 100000, float("inf")],
        "labels": ["零成交", "1~999 元", "1,000~4,999 元", "5,000~19,999 元",
                   "20,000~99,999 元", "100,000 元以上"],
    },
}
DEFAULT_SALES_DISTRIBUTION = "pay_buyers"

# =====================================================================
#  A1 季节—品类—材质—标题约束
# =====================================================================

# 颜色码与标题颜色词必须一致；商家编码使用该颜色码
# ── 标题与季节规则 ──
# 作用：定义标题颜色、季节权重和品类组合。
COLOR_MAP = {
    "001": "黑色", "002": "藏青", "003": "深灰", "004": "卡其",
    "005": "墨绿", "006": "酒红", "007": "浅灰", "008": "军绿",
    "009": "棕色", "010": "米白",
}

# 标题模板：[年份+季节+核心属性] + 中老年男装 + 材质/工艺 + 品类 + 版型/功能
TITLE_TEMPLATE = "【2026{season_label} {color_name}】中老年男装{material_word}{category}{suffix}"

# 禁止出现的标题组合（生成后逐条扫描，命中即重生成/中止）
FORBIDDEN_TITLE_COMBOS = [
    ("羊羔绒", "冰丝"),
    ("加绒", "短裤"),
    ("冬季", "冰丝"),
    ("春秋", "羊羔绒"),
    ("短袖", "加绒"),
    ("棉服", "纯棉薄款"),
    ("毛呢裤", "冰丝"),
]

# 品类月度基础权重（1~12 月，本数据仅使用 8~11 月）
# 权重用于销售曲线：夏季品类 6~8 月高，10 月后趋零；秋冬品类 9 月爬升、11 月达峰
CATEGORY_MONTH_WEIGHTS = {
    "短裤":   [0.00, 0.00, 0.00, 0.00, 0.35, 0.90, 1.00, 1.00, 0.55, 0.02, 0.00, 0.00],
    "短袖":   [0.00, 0.00, 0.00, 0.00, 0.30, 0.90, 1.00, 1.00, 0.50, 0.02, 0.00, 0.00],
    "T恤":    [0.10, 0.10, 0.20, 0.35, 0.55, 0.85, 1.00, 0.95, 0.60, 0.25, 0.10, 0.05],
    "工装裤": [0.40, 0.45, 0.55, 0.60, 0.60, 0.55, 0.50, 0.55, 0.65, 0.75, 0.60, 0.45],
    "休闲裤": [0.50, 0.50, 0.55, 0.55, 0.50, 0.45, 0.40, 0.50, 0.75, 0.95, 0.75, 0.55],
    "运动裤": [0.50, 0.50, 0.55, 0.55, 0.50, 0.40, 0.35, 0.45, 0.70, 0.95, 0.80, 0.55],
    "毛呢裤": [0.20, 0.20, 0.25, 0.25, 0.20, 0.10, 0.05, 0.15, 0.55, 0.95, 0.90, 0.60],
    "卫裤":   [0.35, 0.35, 0.40, 0.40, 0.35, 0.30, 0.25, 0.35, 0.60, 0.90, 0.80, 0.55],
    "卫衣":   [0.25, 0.25, 0.35, 0.40, 0.35, 0.30, 0.20, 0.35, 0.70, 0.95, 0.85, 0.55],
    "棉服":   [0.10, 0.10, 0.10, 0.05, 0.00, 0.00, 0.00, 0.05, 0.40, 0.90, 1.00, 0.85],
    "迷彩裤": [0.35, 0.40, 0.50, 0.55, 0.50, 0.45, 0.40, 0.45, 0.55, 0.65, 0.55, 0.40],
}

# 季节词对月度权重的调整（用于构建 SEASON_RULES 矩阵）
SEASON_MONTH_FACTORS = {
    "夏季": [0.0, 0.0, 0.0, 0.0, 0.4, 1.0, 1.0, 1.0, 0.2, 0.0, 0.0, 0.0],
    "春秋": [0.8, 0.8, 1.0, 1.1, 1.0, 0.7, 0.5, 0.6, 1.0, 1.0, 0.8, 0.7],
    "加绒": [0.2, 0.2, 0.3, 0.3, 0.2, 0.1, 0.0, 0.1, 0.7, 1.0, 1.0, 0.8],
    "羊羔绒": [0.1, 0.1, 0.2, 0.2, 0.1, 0.0, 0.0, 0.1, 0.6, 1.0, 1.0, 0.8],
}

# 材质对月度权重的调整；冰丝为夏季材质，10 月后趋零
MATERIAL_MONTH_FACTORS = {
    "纯棉": [1.0] * 12,
    "冰丝": [0.0, 0.0, 0.0, 0.1, 0.5, 1.0, 1.0, 1.0, 0.2, 0.0, 0.0, 0.0],
}

# 合法组合：品类 -> 允许的季节词；不在此表的组合权重为 0，不用于生成
LEGAL_CATEGORY_SEASONS = {
    "短裤": ["夏季"], "短袖": ["夏季"], "T恤": ["春秋", "夏季"],
    "棉服": ["加绒", "羊羔绒"], "毛呢裤": ["加绒", "春秋"],
    "休闲裤": ["春秋", "加绒", "羊羔绒"], "运动裤": ["春秋", "加绒"],
    "卫裤": ["春秋", "加绒", "羊羔绒"], "卫衣": ["春秋", "加绒"],
    "工装裤": ["春秋"], "迷彩裤": ["春秋"],
}
LEGAL_CATEGORY_MATERIALS = {
    "短裤": ["纯棉", "冰丝"], "短袖": ["纯棉", "冰丝"],
    "T恤": ["纯棉", "冰丝"], "棉服": ["纯棉"],
    "毛呢裤": ["纯棉"], "休闲裤": ["纯棉"], "运动裤": ["纯棉"],
    "卫裤": ["纯棉"], "卫衣": ["纯棉"], "工装裤": ["纯棉"], "迷彩裤": ["纯棉"],
}


# _build_season_rules
# 作用：按 (二级品类, 季节词, 材质) 构建 12 个月销量权重矩阵。
def _build_season_rules() -> dict:
    """按 (二级品类, 季节词, 材质) 构建 12 个月销量权重矩阵。"""
    rules = {}
    for category in CATEGORY_L2:
        for season in SEASON_KEYS:
            for material in MATERIALS:
                if season not in LEGAL_CATEGORY_SEASONS.get(category, []):
                    weights = [0.0] * 12
                elif material not in LEGAL_CATEGORY_MATERIALS.get(category, []):
                    weights = [0.0] * 12
                else:
                    weights = []
                    for month in range(12):
                        value = (CATEGORY_MONTH_WEIGHTS[category][month]
                                 * SEASON_MONTH_FACTORS[season][month]
                                 * MATERIAL_MONTH_FACTORS[material][month])
                        weights.append(round(value, 4))
                rules[(category, season, material)] = tuple(weights)
    return rules


SEASON_RULES = _build_season_rules()

# A2：11 月品类结构验收阈值
# ── 结构与生成约束 ──
# 作用：定义月度结构、客单价和链接生命周期阈值。
NOVEMBER_WINTER_CATEGORIES = ["棉服", "休闲裤", "运动裤", "毛呢裤", "卫裤", "卫衣", "T恤"]
NOVEMBER_WINTER_SHARE_MIN = 0.60
SUMMER_CATEGORIES = ["短裤", "短袖"]
SUMMER_MATERIAL = "冰丝"
NOVEMBER_ANTI_SEASON_SHARE_MAX = 0.02
AOV_MIN = 130.0
AOV_MAX = 170.0
DAILY_SELLING_LINKS_MIN = 38
DAILY_SELLING_LINKS_MAX = 42
ONSALE_LINKS_MIN = 212
ONSALE_LINKS_MAX = 228

# A3：链接生命周期
LIFECYCLE_OLD_DAYS = 180
LIFECYCLE_RECENT_ZERO_DAYS = 30
SLOW_CANDIDATE_MIN_DAYS = 30
SLOW_CANDIDATE_MAX_DAYS = 180

# A3：新品成长曲线（上架天数 -> 累计支付买家数合理区间）
NEW_LINK_GROWTH = {
    3: (2, 6), 7: (5, 15), 14: (12, 35), 30: (20, 80),
}
NEW_LINK_SAMPLE_COUNT = 10       # 每店预置新品数量
NEW_LINK_TARGET_BUYERS = (30, 80)
MAIN_PUSH_AD_RATIO_RANGE = (0.06, 0.18)
HIGH_AD_RATIO_LIMIT = 0.25

# A5：六类对照样例（生成时优先挑选符合结构的目标链接，打印供人工核对）
SAMPLE_ROLE_SPECS = {
    "主推": {"category_l2": "休闲裤", "season_key": "羊羔绒", "material": "纯棉", "launch_month": 9},
    "主推_2": {"category_l2": "运动裤", "season_key": "加绒", "material": "纯棉", "launch_month": 9},
    "潜力": {"category_l2": "毛呢裤", "season_key": "加绒", "material": "纯棉", "launch_age_days": 14},
    "测试": {"category_l2": "卫衣", "season_key": "加绒", "material": "纯棉", "launch_age_days": 3},
    "低表现": {"category_l2": "T恤", "season_key": "春秋", "material": "纯棉", "launch_age_days": 8},
    "反季长尾": {"category_l2": "短裤", "season_key": "夏季", "material": "冰丝", "launch_month": 4},
}

# B：链接管理标签枚举（「未打标」不是标签值，是 tag IS NULL 的派生状态）
MANAGEMENT_TAG_OPTIONS = ["测试款", "潜力款", "动销款", "主推款", "滞销款"]
TAG_OPTIONS = MANAGEMENT_TAG_OPTIONS
CARD_OPTIONS = [
    {"key": "untagged", "label": "未打标"},
    *[{"key": tag, "label": tag} for tag in MANAGEMENT_TAG_OPTIONS],
]
ADD_LINK_SCOPE_NOTE = "仅可添加在售链接池中的链接；系统不预展开管理记录"

# 链接管理表分页
MANAGEMENT_PAGE_SIZE = 20
MANAGEMENT_PAGE_SIZE_OPTIONS = [20, 50, 100]
PLAN_PAGE_SIZE = 10



# 推广场景归类：按计划名称前缀自动归纳，不在模板中硬编码场景名
SCENE_L1_OPTIONS = ["全站推广", "关键词推广", "精准人群推广"]

# 前端展示
PAGE_SIZE_OPTIONS = [25, 50, 100]
DEFAULT_PAGE_SIZE = 50

# 推送通知：本期占位，不接生产
FOOTER_NOTE = "个人练习项目 · 模拟脱敏数据 · 未接生产 · 无账号体系"

# 项目与界面名称
PROJECT_NAME = "店铺报表助手"
SYSTEM_NAME = "电商运营报表助手"
BRAND_MARK = "报"
BRAND_SUBTITLE = "经营速览 · 日报周报月报导出"
BROWSER_TITLE = "电商运营报表助手｜日报 / 周报 / 月报"
DATA_SNAPSHOT_NOTE = f"模拟脱敏数据，统计截止 {END_DATE.strftime('%Y-%m-%d')}"


# shop_display
# 作用：完成全局配置中的该步骤，结果交给调用方继续使用。
def shop_display(shop_id: str) -> str:
    return SHOP_DISPLAY.get(shop_id, shop_id)


# =====================================================================
#  三模块与报表
# =====================================================================
NAV_ITEMS = [
    {"key": "analysis", "title": "经营分析", "path": "/"},
    {"key": "links", "title": "链接管理", "path": "/links"},
    {"key": "reports", "title": "数据报表", "path": "/reports"},
]

DATA_CUTOFF_LABEL = f"{(END_DATE + timedelta(days=1)).strftime('%Y-%m-%d')} 08:20"  # 取数时点，含 END_DATE 全天
DATA_END_LABEL = END_DATE.strftime("%Y-%m-%d")
REPORT_SAVE_DIR = OUTPUT_DIR / "报表快照"
GOAL_LOG_FILE = OUTPUT_DIR / "目标变更日志.md"

# 目标设置：万元 / 百分比；空值表示不显示该项达成判定
GOAL_FIELDS = [
    ("monthly_sales_wan", "月度销售目标（万元）"),
    ("paid_ratio_limit", "月度付费占比上限（%）"),
]
GOAL_DEFAULTS = {"monthly_sales_wan": None, "paid_ratio_limit": None}

REPORT_TABS = [
    {"key": "daily", "label": "日报", "grain": "日"},
    {"key": "weekly", "label": "周报", "grain": "自然周", "default": True},
    {"key": "monthly", "label": "月报", "grain": "自然月"},
]

# 固定 20 列，列顺序不许用户改
REPORT_COLUMNS = [
    ("period_label", "统计区间"), ("shop_name", "店铺"), ("item_id", "链接ID"),
    ("style_code", "款号"), ("item_title", "链接标题"), ("tag", "标签"),
    ("sales", "销售额"), ("net_sales", "净销售额"), ("units", "销量"),
    ("visitors", "访客数"), ("conversion_rate", "转化率"), ("refund_rate", "退款率"),
    ("ad_cost", "推广花费"), ("roi", "投产比"), ("paid_ratio", "付费占比"),
    ("prev_value", "上期同值"), ("wow", "环比"), ("anomaly_mark", "异常标记"),
    ("action", "本期动作（手写）"), ("caliber_note", "口径注脚"),
]

REPORT_STATIC_CHECKS = {
    "daily": ["流量：今日访客与转化率是否同步变化", "转化：主推链接支付买家数是否低于近 7 日均值",
              "订单：待付款与退款单是否出现异常峰值", "售后：退款率是否超过既有区间",
              "推广：重点计划花费是否出现空转"],
    "weekly": ["确认本周与上周同口径（支付口径、含不含退款、归因周期）",
               "检查两店进度差与周目标完成情况", "核对连续两周走弱链接并补动作",
               "确认新增映射与问题列表已处理", "下周动作清单补齐后再导出"],
    "monthly": ["确认月度目标与上周进度", "核对两店月度进度差",
                "检查品类结构与付费占比合规", "确认月报动作栏与口径注脚后再发出"],
}

REPORT_CALIBER_NOTES = [
    "支付口径：订单行级实付（含运费、不扣跨期退款）",
    "净销售额：销售额 − 当期已完结退款",
    "推广口径：多计划花费相加；推广成交金额为归因口径，不参与付费占比",
    "归因周期：固定 7 日（模拟值）",
    "付费占比 = SUM(推广花费) / SUM(订单实付销售额)，按合计相除",
    "编码：shop_id + item_id 显式关联；未映射链接只报不猜",
]
REPORT_SCOPE_NOTE = "个人练习项目 · 模拟脱敏数据 · 未接生产 · 无账号体系"


# 经营分析标签勾选：未打标是 tag IS NULL 的派生筛选状态
ANALYSIS_TAG_OPTIONS = ["未打标"] + MANAGEMENT_TAG_OPTIONS

# ：我的链接集合（全局共享上下文，文件集合，表/配置均可；独立于源表）
MY_LINKS_FILE = DATA_DIR / "my_links.json"
MY_LINKS_LOG_FILE = OUTPUT_DIR / "链接池变更日志.md"
