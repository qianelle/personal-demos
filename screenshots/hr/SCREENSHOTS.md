# 通用人事管理系统 · 界面截图

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

[![通用人事管理 · 总览看板]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/9f794818-db4d-4564-a412-879c38e140cf" />



应用落地页。展示在职人数、待离职人数、使用中账号数、未闭环事项数四个指标，以及部门人数分布、账号状态分布、合同到期预警与未闭环交接事项清单。

<details>
<summary>应用导航（可选）</summary>

[![应用导航]<img width="369" height="999" alt="image" src="https://github.com/user-attachments/assets/d3342bb5-5e27-4a51-a929-fe5beacf4e2e" />


左侧导航按数据看板、业务办理、主数据与台账分组。

</details>

## 4. 主数据

### 4.1 员工档案列表

[![员工档案列表]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/7404fbb9-18d3-4883-9dba-61c403397b71" />


30 条员工记录，展示工号、姓名、所属部门、岗位、员工状态与合同到期日；列表顶部提供在职人员、试用期、30 天内合同到期、已离职等视图入口。

### 4.2 员工档案数据看板

[![员工档案数据看板]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/8d54a13e-2bde-45a8-9cc0-371f2ac0586d" />


在职人数指标、部门人数分布、年度入职人数分布与合同到期预警 3 条。

## 5. 业务单据与审批

### 5.1 请假申请单

[![请假申请单填写页]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/6b10459a-51ba-42d0-bdb9-0c6e14edba6a" />


起止时间、只读的请假时长、请假类型、事由与附件字段；时长按含首尾整天计算。

### 5.2 两级审批单据

[![2 天请假单与流程轨迹]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/ceebb69a-74b9-4f13-a113-a5c8713cf8ab" />

时长未触发加签条件的单据，经主管审批后由 HR 备案结束。

### 5.3 三级审批单据

[![5 天请假单与流程轨迹]<img width="2022" height="1411" alt="image" src="https://github.com/user-attachments/assets/751fe52d-a032-4d2d-9cd5-9da4a7a5684b" />


时长触发加签条件的单据，在主管与 HR 备案之间增加部门负责人节点。

### 5.4 请假数据看板

[![请假数据看板]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/c6c87ec1-185b-42f4-b09e-93f6562d70e5" />

请假类型占比、部门请假时长排行与个人请假明细。

## 6. 台账与闭环

### 6.1 账号与权限台账

[![账号与权限台账]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/1044e54a-9292-4189-9c01-640cf13fddb7" />

18 条记录，含系统名称、账号角色、账号状态、开通日与回收日。

### 6.2 离职交接单

[![离职交接单详情]<img width="2022" height="2011" alt="image" src="https://github.com/user-attachments/assets/d6771310-3d39-4049-9bcb-fb476a211fdb" />

主表信息与 5 行交接事项，含事项类别、完成状态、完成日期与责任人。

### 6.3 并行会签轨迹

[![离职并行会签流程轨迹]<img width="2229" height="1203" alt="image" src="https://github.com/user-attachments/assets/b295aa8f-7540-4019-abad-afa6eb069e6b" />

四条处理线并行执行，全部办结后流程结束。

### 6.4 入转调离看板

[![入转调离看板]<img width="2022" height="1259" alt="image" src="https://github.com/user-attachments/assets/c81b657c-e0a9-448f-8def-24833382e28d" />

在职与待离职指标、异动类型分布、账号状态分布与已回收账号明细。
