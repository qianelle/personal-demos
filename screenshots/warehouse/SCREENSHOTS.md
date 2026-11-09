# 通用仓库管理系统 · 界面截图

本文档收录系统界面截图。截图文件位于同目录 `assets/` 下，文件名与本文档引用名称一一对应；图片尚未上传时，对应位置会显示破图标记，按文件名补齐即可。

截图分为两类：运行界面（文件名以 `APP` 结尾）取自钉钉工作台进入应用后的页面；配置界面（文件名以 `CFG` 结尾）取自应用内的表单、流程与权限配置页面。

## 1. 截图规范

| 项 | 要求 |
| --- | --- |
| 文件命名 | `{项目前缀}-{两位序号}-{页面标识}-{视角}.png` |
| 视角标记 | `APP` 运行界面 / `CFG` 配置界面 |
| 文件格式 | PNG，同一批截图保持相同窗口尺寸与缩放比例 |
| 画面范围 | 全屏窗口，保留应用名称、左侧导航与页面标题；数据列表保留合计条数 |
| 页面文字 | 报表页顶部标题显示为业务名称，不使用模板默认文字 |
| 图片引用 | 点击图片可打开原图查看 |
| 不收录 | 空白页、报错提示、未保存草稿、重复页面、含模板默认文字的报表页 |

截图中的应用名称、字段名称与编号规则，与同目录下其他文档保持一致。

## 2. 数据说明

截图中的业务数据均为演示用模拟数据，不涉及真实人员与组织信息。人员姓名、组织名称、联系电话与证件信息在上传前做遮盖处理；单据编号、物品编码、工号、金额、数量与日期属于系统编号与业务口径，予以保留。

## 3. 应用总览

### 3.1 总览看板

[![通用仓库管理 · 总览看板](assets/warehouse-00-overview-APP.png)](assets/warehouse-00-overview-APP.png)

应用落地页。展示物品总数、在用数量、出入库金额、库存变动四个指标，以及分类分布、金额趋势、低库存预警与部门申领排行。

<details>
<summary>应用导航（可选）</summary>

[![应用导航](assets/warehouse-01-app-home-APP.png)](assets/warehouse-01-app-home-APP.png)

左侧导航按数据看板、业务办理、主数据与台账分组。

</details>

## 4. 主数据

### 4.1 物品档案列表

[![物品档案列表](assets/warehouse-02-item-list-APP.png)](assets/warehouse-02-item-list-APP.png)

20 条物品记录，展示物品编码、名称、分类、计量单位、默认库位与状态；列表顶部提供在用物品、停用物品等视图入口。

### 4.2 物品档案数据看板

[![物品档案数据看板](assets/warehouse-03-item-dashboard-APP.png)](assets/warehouse-03-item-dashboard-APP.png)

分类分布饼图、在用与停用指标卡、库位明细表。

<details>
<summary>视图与字段配置（可选）</summary>

[![视图与显示列](assets/warehouse-04-item-views-CFG.png)](assets/warehouse-04-item-views-CFG.png)

数据管理页的视图显隐、显示列与排序设置。

</details>

## 5. 业务单据与审批

### 5.1 出入库申请单

[![出入库申请单填写页](assets/warehouse-05-inout-form-APP.png)](assets/warehouse-05-inout-form-APP.png)

明细行选中物品后自动带出分类、计量单位、默认库位与单价；行内金额小计与主表总数量、总金额由公式计算。

### 5.2 两级审批单据

[![111.00 单据与流程轨迹](assets/warehouse-06-inout-111-APP.png)](assets/warehouse-06-inout-111-APP.png)

金额未触发加签条件的单据，经主管审批后由仓管确认结束。

### 5.3 三级审批单据

[![5025.00 单据与流程轨迹](assets/warehouse-07-inout-5025-APP.png)](assets/warehouse-07-inout-5025-APP.png)

金额触发加签条件的单据，在主管与仓管之间增加仓库负责人节点。

### 5.4 出入库数据看板

[![出入库数据看板](assets/warehouse-08-inout-dashboard-APP.png)](assets/warehouse-08-inout-dashboard-APP.png)

单据类型占比、部门申领排行与月度金额趋势，金额合计 5136.00。

## 6. 台账与盘点

### 6.1 库存结存

[![库存结存列表](assets/warehouse-09-stock-balance-APP.png)](assets/warehouse-09-stock-balance-APP.png)

20 条结存记录，按物品编码定位，展示当前数量与安全库存。

### 6.2 库存流水

[![库存流水列表](assets/warehouse-10-stock-flow-APP.png)](assets/warehouse-10-stock-flow-APP.png)

3 条变动记录，含来源单号、单据类型、变动数量与变动后结存，变动数量合计 206。

### 6.3 库存看板

[![库存看板](assets/warehouse-11-stock-dashboard-APP.png)](assets/warehouse-11-stock-dashboard-APP.png)

结存明细、低库存预警、出入库趋势与变动笔数。

<details>
<summary>盘点单详情（可选）</summary>

[![盘点单详情](assets/warehouse-12-check-detail-APP.png)](assets/warehouse-12-check-detail-APP.png)

盘点主表信息与子表单中的账面数量、实盘数量、差异及差异原因。

</details>

## 7. 规则配置界面

### 7.1 子表单与汇总公式

[![子表单与公式](assets/warehouse-13-inout-form-CFG.png)](assets/warehouse-13-inout-form-CFG.png)

明细行内的金额小计公式，以及主表总数量、总金额的汇总公式。

### 7.2 关联表单与字段填充

[![关联表单数据填充](assets/warehouse-14-relation-fill-CFG.png)](assets/warehouse-14-relation-fill-CFG.png)

关联物品档案、主要与次要信息、数据筛选条件及字段填充映射。

### 7.3 流程分支

[![出入库流程设计](assets/warehouse-15-workflow-CFG.png)](assets/warehouse-15-workflow-CFG.png)

按金额与数量设置的两组优先级分支，加签分支与其他情况分支统一汇入仓管确认节点。

### 7.4 节点字段权限

[![仓管确认节点字段权限](assets/warehouse-16-node-permission-CFG.png)](assets/warehouse-16-node-permission-CFG.png)

数量、单价、默认库位可编辑，其余字段只读。

<details>
<summary>表单设计与报表配置（可选）</summary>

[![物品档案表单设计](assets/warehouse-17-item-form-CFG.png)](assets/warehouse-17-item-form-CFG.png)

字段类型、必填校验与数值精度设置。

[![报表字段配置](assets/warehouse-18-report-CFG.png)](assets/warehouse-18-report-CFG.png)

分类字段、数值字段与计数聚合方式。

</details>
