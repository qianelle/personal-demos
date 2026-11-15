# 千牛 / 淘宝 商家评价管理后台 —— 仿真环境 V1

> 用途：为**影刀 RPA 浏览器自动化**提供一个本地可跑的仿真靶站，用于演示与测试
> 「电商 VOC 评价数据采集」流程：**登录 → 评价管理 → 筛选 → 查询 → 导出 CSV**。

---

## ⚠️ 边界声明（请先读）

本项目**不是**真实商家后台，也**不**接入任何真实平台：

| 不做 | 说明 |
|---|---|
| 真实淘宝 / 千牛登录 | 登录仅为本 Demo 的固定账号校验，无任何平台鉴权 |
| 真实平台接口 | 全部数据来自本地 `mock_data.py`，无网络请求 |
| 验证码绕过 / 风控绕过 | 不存在该能力，也不提供 |
| 爬虫 / 第三方接口 | 不涉及 |
| 真实消费者 / 真实店铺数据 | 全部为虚构仿真数据 |
| 数据库 | 数据在内存中生成，无持久化存储 |

仅实现：**评价管理列表 + 筛选 + 分页 + CSV 导出**，其余菜单为界面占位。

---

## 一、启动方式

```bash
# 1) 安装依赖（建议使用虚拟环境）
pip install -r requirements.txt

# 2) 启动
python app.py

# 3) 浏览器访问
http://localhost:5000
```

自定义端口：

```bash
# Windows
set PORT=8080 && python app.py
# macOS / Linux
PORT=8080 python app.py
```

停止服务：`Ctrl + C`

---

## 二、测试账号

| 项 | 值 |
|---|---|
| 账号 | `demo_admin` |
| 密码 | `123456` |

登录成功后直接进入「评价管理」。未登录访问任何后台页面会 **302 跳回登录页**。

---

## 三、页面说明

| 页面 | 路径 | 说明 |
|---|---|---|
| 登录页 | `/login` | 固定账号校验；错误时展示错误提示 |
| 首页 | `/dashboard` | 界面占位 + Demo 说明 + 数据概览统计 |
| 商品管理 | `/products` | 界面占位：「当前模块仅作为界面占位，Demo V1 未开放。」 |
| 交易管理 | `/orders` | 同上 |
| 数据中心 | `/data` | 同上 |
| **评价管理** | `/reviews` | **唯一真正实现的模块** |
| 导出 | `/export` | 按当前筛选条件导出 CSV 附件 |

右上角「调试」菜单：
- **模拟登录失效**（`session-expire`）：清除 Session，之后访问任何后台页面自动跳登录页
- **退出登录**（`logout`）：正常退出

### 评价管理支持的筛选

1. **快捷日期：全部 / 今天 / 昨天 / 近7天**（按「最后活动时间」，见「五之二」）
2. 最后活动时间范围（起 / 止，自定义区间同样按「最后活动时间」）
3. 店铺（2 个虚构店铺）
4. 商品ID / 商品名称搜索（模糊匹配）
5. 评价类型：全部 / 初评（仅主评价）/ 追评（含追评内容）
6. 评分：全部 / 1星 ~ 5星
7. 是否存在追评：全部 / 是 / 否

按钮：**查询**、**重置**、**导出评价**

> **Source Schema v1 已冻结：一行 = 一个主评价线程。**
> 主评价在 `review_text` / `review_time`，追评在 `append_review_text` / `append_review_time`，
> **追评不再单独生成独立行**（详见「五、Source Schema 冻结说明」）。
> 因此「评价类型」按该线程是否含追评内容划分，下拉框的 `value` 仍为 `初评` / `追评`，不影响已有 RPA 脚本。

表格列：首评时间 · **最后活动时间** · 店铺名称 · 商品ID · 商品名称 · SKU · 订单号 · 买家账号标识 · 评分 · 评价内容（追评在单元格内以 `[追评]` 单独成行展示） · 是否追评 · 卖家回复
分页：默认 **20 条/页**，可切换 20 / 50 / 100。

---

## 四、仿真数据

| 项 | 值 |
|---|---|
| 总条数 | **176 条** |
| 类型分布 | 仅主评价 127 / 含追评 49 |
| 星级分布 | 5星 51 / 4星 29 / 3星 28 / 2星 35 / 1星 33 |
| 店铺 | 元气营养健康旗舰店（天猫）89 条 / 晨光膳食专营店（淘宝）87 条 |
| 商品 | 10 个虚构商品，多个 SKU |
| 含追评 | 是 49 / 否 127 |
| 时间范围 | **滚动窗口：最近 100 天，结束于今天**（窗口起点随今天移动） |
| 定向样本 | 疑似身体不适反馈 10 条 · 增量巡检样本 10 条 |

数据自检（运行 `python mock_data.py` 会打印，当前 **PASS**）：

| # | 规则 | 结果 |
|---|---|---|
| 1 | `review_id` 唯一 | 176 / 176 ✅ |
| 2 | `order_id` 无重复组（不得因同一追评重复建行而重复） | 0 组 ✅ |
| 3 | `append_review_text` 与 `append_review_time` 同空同非空 | 0 异常 ✅ |
| 4 | 任一 `append_review_text` 不得出现在另一行的 `review_text` | 0 条 ✅ |
| 5 | 追评时间晚于主评价时间 | 0 异常 ✅ |
| 6 | `last_activity_time` 取值 = 有追评取追评、无追评取首评 | 0 异常 ✅ |

覆盖场景：五星好评、四星、三星中评、一星差评、包装问题、物流问题、客服问题、口感问题、质量问题、
**疑似身体不适反馈（10 条，可进入 VOC P0/P1 风险判断）**、**增量巡检样本（10 条）**、追评、卖家回复。

示例（不写医学诊断结论，只描述主观感受）：

```
初评：吃了一段时间最近总感觉胃不舒服，先停了。
追评：停用以后好一点了，不知道是不是这个原因。
```

数据由 `mock_data.py` 以固定随机种子 `20261006` 生成，**同一天内每次启动完全一致**，适合 RPA 脚本回归测试。
（唯一例外：时间窗口**结束于今天**，因此跨天启动后整体时间轴会随之平移——这是为了让
「今天 / 昨天 / 近7天」每天都能查到真实数据，见下一节。）

---

## 五、CSV 导出

- 点击「导出评价」→ 显示 **「正在生成文件……」** → 约 **2.5 秒** → **「文件生成成功」** → 触发浏览器下载
- 文件名：`reviews_YYYYMMDD_HHMMSS.csv`
- 编码：**UTF-8 with BOM**（Excel 直接打开中文不乱码）
- 行结束符：CRLF
- **只导出当前筛选结果**（不受分页影响）

字段（固定 15 列，顺序不可变）：

| # | 字段 | 说明 |
|---|---|---|
| 1 | platform | 淘宝 / 天猫 |
| 2 | shop_name | 店铺名称 |
| 3 | item_id | 商品ID |
| 4 | item_name | 商品名称 |
| 5 | sku_id | SKU ID |
| 6 | sku_name | SKU 名称 |
| 7 | order_id | 订单号（虚构，DEMO 前缀） |
| 8 | buyer_id | 买家账号标识（虚构，已脱敏） |
| 9 | review_id | 评价ID |
| 10 | rating | 星级 1-5 |
| 11 | rating_label | 好评 / 中评 / 差评 |
| 12 | review_text | 评价内容 |
| 13 | review_time | 评价时间 `YYYY-MM-DD HH:mm:ss` |
| 14 | append_review_text | 追评内容（无则空） |
| 15 | append_review_time | 追评时间（无则空） |

> 说明：`append_review_text` / `append_review_time` **必须同时为空或同时非空**，
> 且二者不会在任何其他行以 `review_text` 形式重复出现（Source Schema v1 硬约束）。

**与 VOC 系统的衔接**：本 CSV 的字段风格对齐「店透视类插件导出」宽表，
可直接作为 VOC 系统 File Adapter 的输入；
落库侧已配套 `voc.review_source_staging`（见 VOC 项目 `sql/001_create_voc_collector_schema.sql`）。

---

## 五之一、Source Schema 冻结说明（追评重复问题修复）

### 问题

旧版生成逻辑为了让「评价类型=追评」筛选有数据，把**已带追评的初评再复制出一条独立行**，
并复用同一 `order_id` / `buyer_id` / `item_id`。结果是同一条追评内容在导出文件中出现两次：

```
行 A：append_review_text = "停用以后好一点了，不知道是不是这个原因。"
行 B：review_text        = "停用以后好一点了，不知道是不是这个原因。"   ← 同一句话，同订单
```

下游 VOC Source Mapper 会把这条追评**重复拆分、重复分析**，造成重复计数与重复告警。

### 修复

不靠删数据绕开，而是**改生成逻辑本身**：

1. 删除 `mock_data.py` 中「追评独立事件行」生成分支（原第 262-272 行）；
2. `review_type` 不再由外部传入，改由 `append_text` 有无推导，从根上杜绝复制行；
3. 常规评价生成量 142 → 166，使总条数维持 **176**（不因修复而缩水）；
4. 追评文案池扩充到 12 条，降低文案重复度；
5. `mock_data.py` 增加 5 项自检，生成时即可验证约束。

### 冻结后的 Source Schema

```
【一行 = 一个主评价线程】
review_text / review_time              主评价
append_review_text / append_review_time 追评（有则两列同时非空，无则同时为空）

硬约束：追评不得再次作为新的独立 review 行导出。
```

---

## 五之二、增量巡检：last_activity_time

### 为什么要改

运营巡检评价不是按「首评时间」看的，而是看**这条线程最后一次动过是什么时候**。
反例（改动前的行为）：

```
首评 2026-07-10，追评 2026-10-07
→ 按 review_time 排序/筛选：这条线程沉在 7 月，运营永远刷不到
→ 按 last_activity_time：昨天刚动过，必须回到列表顶部并被「昨天」筛出
```

老评价被追评往往是最关键的信号——消费者补充了「停用后好一点了」「客服后来处理了」这类信息，
差评可能恶化也可能已解决。看不到就等于漏判。

### 冻结规则

```
last_activity_time = append_review_time or review_time
```

| 用途 | 是否使用 |
|---|---|
| 列表默认排序（DESC） | ✅ 使用 |
| 快捷日期（今天 / 昨天 / 近7天） | ✅ 使用 |
| 自定义起止日期 | ✅ 使用 |
| **CSV 导出 15 字段** | ❌ **不写入**（字段结构保持冻结） |
| PostgreSQL Source Schema | ❌ 未改动 |

「近7天」= **含今天在内的 7 个自然日**（今天 − 6 天 ~ 今天）。

### 实现位置

| 文件 | 改动 |
|---|---|
| `mock_data.py` | `_build` 写入 `last_activity_time`；时间窗口改为「最近 100 天，结束于今天」；植入 10 条「老首评 + 近期追评」的增量巡检样本；默认排序改为 `last_activity_time` DESC；自检新增第 6 项 |
| `app.py` | `compute_last_activity()` / `quick_range_bounds()`；`parse_filters` 解析 `range`；`filter_reviews` 日期过滤与排序全部改用 `last_activity_time`；页面统计增加「含追评数」 |
| `templates/reviews.html` | 快捷按钮（`#quick-today` / `#quick-yesterday` / `#quick-last7` / `#quick-all`）；新增「最后活动时间」列；评价内容单元格内 `[追评] 正文 + 时间` |
| `static/style.css` | `.quick-btn`、`.append-line` / `.append-badge` / `.append-time` |

### 自动化验证

```bash
python tests/test_last_activity.py     # 25 项，全部通过
```

| # | 用例 | 结果 |
|---|---|---|
| A | 无追评：`last_activity_time == review_time` | ✅ |
| B | 有追评：`last_activity_time == append_review_time` | ✅ |
| C | 旧首评 + 昨天追评，可被「昨天」筛出 | ✅ |
| D | 非昨天追评，不被「昨天」筛出 | ✅ |
| E | 页面默认排序 `last_activity_time` DESC（含老线程因追评回到前 20%） | ✅ |
| F | CSV 仍 15 字段、BOM 正常、导出行数正确 | ✅ |
| 回归 | 一行=一线程、append 同空同非空、追评晚于首评、页面统计与筛选一致、导出=筛选结果 | ✅ |

`range` 参数也可直接拼在 URL 上供 RPA / 采集脚本使用：
`/reviews?range=yesterday`、`/export?range=last7`。

---

## 六、RPA 推荐定位元素清单

所有关键元素均提供**稳定 `id` + `data-testid`**，不依赖屏幕坐标；同时 UI 保留了明确的文字与色块，可用于影刀视觉识别。

### 登录页

| 元素 | id | data-testid |
|---|---|---|
| 账号输入框 | `login-username` | `login-username` |
| 密码输入框 | `login-password` | `login-password` |
| 登录按钮 | `login-submit` | `login-submit` |
| 错误提示 | `login-error` | `login-error` |

### 评价管理 — 筛选区

| 元素 | id | data-testid |
|---|---|---|
| 快捷日期容器 | `review-quick-range` | `review-quick-range` |
| 快捷「全部」 | `quick-all` | `quick-all` |
| 快捷「今天」 | `quick-today` | `quick-today` |
| 快捷「昨天」 | `quick-yesterday` | `quick-yesterday` |
| 快捷「近7天」 | `quick-last7` | `quick-last7` |
| 开始日期（最后活动时间起） | `review-date-start` | `review-date-start` |
| 结束日期（最后活动时间止） | `review-date-end` | `review-date-end` |
| 店铺 | `review-shop` | `review-shop` |
| 商品ID/名称搜索 | `review-product-search` | `review-product-search` |
| 评价类型 | `review-type` | `review-type` |
| 评分 | `review-rating` | `review-rating` |
| 是否存在追评 | `review-has-append` | `review-has-append` |
| 每页条数 | `review-page-size` | `review-page-size` |
| 查询按钮 | `review-search` | `review-search` |
| 重置按钮 | `review-reset` | `review-reset` |
| 导出按钮 | `review-export` | `review-export` |

### 列表 / 分页 / 状态

| 元素 | id | data-testid |
|---|---|---|
| 结果条数 | `result-total` | `result-total` |
| 结果含追评条数 | `result-append-total` | `result-append-total` |
| 表格 | `review-table` | `review-table` |
| 数据行 | — | `review-row` |
| 评分单元格 | — | `cell-rating` |
| 首评时间单元格 | — | `cell-review-time` |
| 最后活动时间单元格 | — | `cell-last-activity` |
| 评价内容单元格 | — | `cell-review-text` |
| 追评行（含 `[追评]` 徽标） | — | `cell-append-line` |
| 追评正文 | — | `cell-append-text` |
| 追评时间 | — | `cell-append-time` |
| 是否追评单元格 | — | `cell-has-append` |
| 分页容器 | `review-pager` | `review-pager` |
| 上一页 / 下一页 | `review-page-prev` / `review-page-next` | 同名 |
| 空状态 | `empty-state` | `empty-state` |
| 空状态文案 | `empty-text` | `empty-text` |

### 导出遮罩 / 菜单 / 调试

| 元素 | id | data-testid |
|---|---|---|
| 导出遮罩 | `export-overlay` | `export-overlay` |
| 导出状态文案 | `export-status` | `export-status`（"正在生成文件……" → "文件生成成功"） |
| 左侧菜单 | `menu-dashboard` / `menu-products` / `menu-orders` / `menu-reviews` / `menu-data` | 同名 |
| 调试按钮 | `debug-toggle` | `debug-toggle` |
| 模拟登录失效 | `session-expire` | `session-expire` |
| 退出登录 | `logout` | `logout` |
| 占位文案 | `placeholder-text` | `placeholder-text` |

**推荐等待策略**：点击导出后，等待 `export-status` 文本变为「文件生成成功」，或直接等待浏览器下载完成（文件名为 `reviews_*.csv`）。

---

## 七、已实现的异常场景

| 场景 | 触发方式 | 预期表现 |
|---|---|---|
| **场景1：无数据** | 设置不可能命中的筛选组合，如 日期 `2026-01-01 ~ 2026-01-02` + 评分 `1星` | 列表显示「**暂无符合条件的评价**」；导出按钮 **disabled**（`is-disabled`），点击提示「暂无可导出数据」；直接请求 `/export` 返回「暂无可导出数据：当前筛选条件下没有符合条件的评价。」 |
| **场景2：模拟登录失效** | 右上角「调试」→「模拟登录失效」 | Session 清除并跳回登录页；此后访问 `/reviews` 等任意后台页面，自动 302 跳回 `/login`，可用于测试 RPA 的 `LOGIN_REQUIRED` 分支 |

---

## 八、验证记录（本机实测）

### 8.1 真实浏览器端到端测试（Chrome headless + Playwright，13/13 通过）

| # | 测试项 | 结果 |
|---|---|---|
| 1 | 未登录访问 `/reviews` | ✅ 自动跳转 `/login` |
| 2 | 使用 `demo_admin / 123456` 登录 | ✅ 进入 `/reviews` |
| 3 | 列表渲染 | ✅ 总数 176 条，首页 20 行（20 条/页） |
| 4 | 筛选「1星」+ 点击查询 | ✅ 结果 23 条 |
| 5 | 点击导出 | ✅ 遮罩出现，文案「正在生成文件……」 |
| 6 | 等待约 2.5 秒 | ✅ 文案变为「文件生成成功」 |
| 7 | **浏览器真实下载** | ✅ 触发下载，文件名 `reviews_20261006_190245.csv` |
| 8 | 下载文件校验 | ✅ UTF-8 BOM = 是，15 列，数据行 23（与筛选结果一致） |
| 9 | 点击重置 | ✅ 恢复 176 条 |
| 10 | 异常场景1（无数据） | ✅ 显示「暂无符合条件的评价」，导出按钮 `disabled` |
| 11 | 异常场景2（模拟登录失效） | ✅ 跳转 `/login` |
| 12 | 失效后访问后台 | ✅ 仍被拦截回 `/login` |
| 13 | 占位模块 | ✅ 商品管理显示「当前模块仅作为界面占位，Demo V1 未开放。」 |

### 8.2 其他已验证行为

| 项 | 结果 |
|---|---|
| 错误密码登录 | ✅ 页面显示「账号或密码错误。Demo 账号：demo_admin / 123456」 |
| 筛选计数 | ✅ 1星 23 / 评价类型=追评 41 / 存在追评=是 41 / 元气营养健康旗舰店 72 / 商品搜索 IT1001 为 18 条 |
| 分页 | ✅ 共 9 页（20条/页）；切 50 条/页时返回 50 行 |
| 导出（无数据时直接请求 `/export`） | ✅ 返回「暂无可导出数据：当前筛选条件下没有符合条件的评价。」 |
| 数据时间范围 | ✅ 2026-07-01 ~ 2026-09-30 |

> 测试过程中通过真实浏览器发现并修复了 2 个前端缺陷：`hidden` 遮罩仍拦截点击、左侧菜单未注入模板上下文。
> 两个问题均已修复并回归通过。

---

## 九、目录结构

```
千牛评价管理后台仿真_V1/
├── app.py                # Flask 主程序（路由 / 登录 / 筛选 / 导出）
├── mock_data.py          # 虚构仿真数据生成器（固定种子）
├── requirements.txt      # 依赖
├── README.md             # 本文档
├── static/
│   └── style.css         # 后台样式
└── templates/
    ├── base.html         # 顶栏 + 左侧菜单 + 调试菜单
    ├── login.html
    ├── placeholder.html  # 未开放模块占位页
    └── reviews.html      # 评价管理（唯一实现模块）
```
