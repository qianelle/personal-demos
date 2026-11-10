# 通用仓库管理系统 · 界面截图

本文档收录系统界面截图。

## 1. 数据说明

截图中的业务数据均为演示用模拟数据，不涉及真实人员与组织信息。人员姓名、组织名称、联系电话与证件信息在上传前做遮盖处理；单据编号、物品编码、工号、金额、数量与日期属于系统编号与业务口径，予以保留。

## 2. 应用总览

### 2.1 总览看板

[![通用仓库管理 · 总览看板]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/8e2948da-e615-4271-b288-2cef13d9d769" />

应用落地页。展示物品总数、在用数量、出入库金额、库存变动四个指标，以及分类分布、金额趋势、低库存预警与部门申领排行。

<details>
<summary>应用导航（可选）</summary>

[![应用导航]<img width="345" height="912" alt="image" src="https://github.com/user-attachments/assets/fa098b39-bf70-4c30-ae01-9906a68ae15d" />

左侧导航按数据看板、业务办理、主数据与台账分组。

</details>

## 3. 主数据

### 3.1 物品档案列表

[![物品档案列表]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/458ea0d1-e335-444b-a7c4-88d238570255" />

20 条物品记录，展示物品编码、名称、分类、计量单位、默认库位与状态；列表顶部提供在用物品、停用物品等视图入口。

### 3.2 物品档案数据看板

[![物品档案数据看板]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/169f1792-401a-42bb-95ad-36357ca5ea2a" />

分类分布饼图、在用与停用指标卡、库位明细表。

## 4. 业务单据与审批

### 4.1 出入库申请单

[![出入库申请单填写页]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/f9e45e1e-0308-455e-8bbb-2560e62002f4" />

明细行选中物品后自动带出分类、计量单位、默认库位与单价；行内金额小计与主表总数量、总金额由公式计算。

### 4.2 两级审批单据

[![111.00 单据与流程轨迹]<img width="2022" height="2161" alt="image" src="https://github.com/user-attachments/assets/8bb7aede-2cc1-4cde-a998-7c9b514616bd" />

金额未触发加签条件的单据，经主管审批后由仓管确认结束。

### 4.3 三级审批单据

[![5025.00 单据与流程轨迹]<img width="2022" height="2318" alt="image" src="https://github.com/user-attachments/assets/924fcfba-9ab6-45f5-b74e-38d895779e22" />

金额触发加签条件的单据，在主管与仓管之间增加仓库负责人节点。

## 5. 台账与盘点

### 5.1 库存结存

[![库存结存列表]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/89169559-21f8-4c52-811a-fa1de037821b" />

20 条结存记录，按物品编码定位，展示当前数量与安全库存。

### 5.2 库存流水

[![库存流水列表]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/5993dadc-967f-4b46-9c9b-161f548bdc93" />

3 条变动记录，含来源单号、单据类型、变动数量与变动后结存，变动数量合计 206。
