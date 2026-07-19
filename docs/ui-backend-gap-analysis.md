# 前端 UI × 后端功能 逐页对比差距分析

- **UI 来源**：https://ethics-try-60075565.figma.site/ （Figma Make SPA，分析基于其发布 bundle 美化版 `.figma-app.pretty.js`，行号下文以 `F:行号` 引用）
- **后端来源**：本仓库 `contexts/`（Sanic + DDD，61 个 HTTP 端点 + 1 个 WebSocket，`/api` 前缀）
- **分析日期**：2026-07-17

## 0. 总览结论

1. **前端目前是 100% mock 演示**：bundle 内无 `fetch/axios/WebSocket` 任何调用（仅主题用 localStorage）；登录直接跳转、6 个"导出"按钮全部无 onClick、AI 分析是 setTimeout 假加载。所以"对比"的实质是：**UI 设计稿需要后端提供什么，后端是否已具备**。
2. **后端覆盖面比预期好**：项目汇总 KPI、全局搜索、通知、同步状态、数据大屏、四口径毛利报表、成本科目报表、单项目导出等 UI 需要的接口大多已存在（明显是按此 UI 反向建设过，如 `project_permission_overview`、`/api/system/sync-status`、迁移 0002 补的 UI 字段）。
3. **主要差距集中在 6 处**：
   - 月度经营数据接口字段太薄（缺基础指标/预计完工/租借核销），撑不起项目详情页；
   - 成本科目多口径（六口径 vs 三口径）+ `hierarchy_code` 解析层未填充，两级展开表撑不起来；
   - 数据表格页的"单元格编辑+保存"在后端没有任何 UPDATE 接口；
   - 两个表单字段对不上：项目表单缺 `code`（后端必填）、用户表单缺 `username/password`（后端必填）；
   - 预警中心、预警规则、角色管理、批次记录、模板列表这些后端能力在 UI 里没有页面；
   - 口径/命名前后端不统一，且 UI 内部自己也不统一（settlement vs revenue、成本科目分类三套）。

## 1. 页面-后端支撑状态总表

| UI 页面 | 路由 | 后端支撑 | 状态 |
|---|---|---|---|
| 登录页 | `/login` | `POST /auth/login`、`GET /auth/me` | 🟡 基本具备，缺忘记密码 |
| 项目总览 | `/` | `GET /projects`、`GET /projects/summary` | 🟡 列表项缺 profitRate 等经营指标 |
| 项目详情 | `/project/:id` | `analysis`、`monthly-data`、`progress`、`milestones`、`ai-analysis`、`/projects/<id>/export` | 🔴 monthly-data 字段太薄 |
| 数据表格（可编辑） | `/project/:id/data-table` | `GET /data/<template_id>` 只读 | 🔴 无 UPDATE 接口 |
| 数据管理+上传 | `/management/project/:id` | `upload/preview/confirm/cancel`、`batches`、`monthly-data` 删除 | 🟡 链路具备，UI 缺错误态/模板下载 |
| 月度趋势对比 | `/compare/single` | `POST /projects/<id>/month-comparison` | 🟡 有接口，缺环比与构成维度 |
| 多项目横向对比 | `/compare/multi` | `POST /projects/compare` | 🟡 指标维度需确认补齐，无多项目 AI |
| 成本科目 | `/cost-category` | `GET /reports/cost-categories` + export | 🟡 两级结构依赖 hierarchy_code 修复 |
| 项目毛利情况 | `/project-profit` | `GET /reports/project-profits` + export | 🟢 四口径完全对应 |
| 人员管理 | `/users` | users CRUD、project-permissions、roles CRUD | 🟡 表单字段对不上；角色管理无 UI |
| 数据大屏 | `/dashboard` | `GET /dashboard` + 6 个子端点 | 🟢 基本对应，雷达维度不一致 |
| 全局（搜索/通知/同步状态） | — | `GET /search`、`/notifications`、`/system/sync-status`、WS `/ws/alerts` | 🟢 全部具备，前端未接线 |

---

## 2. 逐页对比明细

### 2.1 登录页 `/login`

UI（F:16473–16606）：账号 + 密码 + 记住密码 + 忘记密码；提交直接 `navigate("/")`，无任何校验与请求。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 账号密码登录 | `POST /api/auth/login {username,password}` → `{token, user}`（`auth_controller.py:36-45`） | ✅ 具备，前端接线即可 |
| 当前用户信息（头像/姓名/部门/角色） | `GET /api/auth/me` 返回 real_name/email/department/system_roles/projects | ✅ 具备（UI 现在硬编码"张三·工程部·管理员" F:16074） |
| 忘记密码 | ❌ 无任何密码找回/重置流程（仅管理员 `PUT /users/<id>/password` 重置） | 🔴 后端缺，或 UI 去掉该入口 |
| 记住密码 | 纯前端行为 | 🟡 UI 自行实现 |
| 退出登录 | UI 仅跳 /login；后端 JWT 24h（`jwt_service.py:10-24`），**无登出/吊销接口** | 🟡 建议后端加 logout（黑名单）或接受短 token |
| 注册 | UI 无入口；后端 `POST /auth/register` **开放注册无审批** | ⚠️ 安全问题：建议加管理员审批或关闭开放注册 |

### 2.2 项目总览 `/`

UI（F:17500–18457）：4 张 KPI 卡（项目总数/正常运行/预警项目/合同总额）；项目卡片（名称、unitType·capacity、负责人、工期、阶段、状态、进度条、合同价、当前毛利率）；列表 Tab（操作：数据管理/编辑/删除）；新增/编辑弹窗（name/contract/startDate/leader/notes）；搜索 + 状态筛选；多项目对比入口。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 4 张 KPI 卡 | `GET /api/projects/summary` → `{total,normal,warning,contract_total}` | ✅ 一一对应 |
| 项目列表字段 | `GET /api/projects` → `id,code,name,project_type,capacity_mw,contract_price,start_date,end_date,manager_id,stage,status,progress,description` | 🟡 见下行缺口 |
| 卡片上的**当前毛利率 profitRate** | ❌ 项目序列化不含任何经营指标（毛利率在月度数据里） | 🔴 后端需补：项目列表/详情携带最新月份 profitRate（及 cost/profit/month） |
| 负责人姓名 | 后端只有 `manager_id` | 🟡 列表接口需 join 返回 manager 姓名 |
| 阶段 phase | 后端 `stage` 英文枚举（planning/design/construction/completion/maintenance）且只能前进 | 🟡 需中英字典映射（前端展示"在建/完工"） |
| 新增项目 | 后端 `POST /projects` **必填 code + name**；UI 表单无"项目编号"字段 | 🔴 UI 需加 code 字段（或后端自动生成 code） |
| 编辑/删除 | `PUT/DELETE /projects/<id>` 具备（删除级联清理） | ✅ 具备（UI 删除按钮目前无 onClick） |
| 状态筛选 | 后端支持 `status` query；枚举 normal/warning/suspended/closed 比 UI 多两个 | ✅ |

### 2.3 项目详情 `/project/:id`

UI 四个 Tab（F:45039–46909）：

**Tab1 单项目**：进度与节点表、基础指标（合同价/预计完工成本/指标毛利/指标毛利率）、动态指标（累计结算/累计成本/毛利/毛利率）、预计完工指标（4 项）、租借及核销（rental×3 + 核销率 writeOffRate）、动态统计与成本构成（两级展开表，**六口径**：初始考核指标/预计完工清单/分包策划调整/现执行预算/实际已发生/预计完工）。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 进度与节点 | `GET /projects/<id>/progress`、`/milestones`（CRUD 全） | ✅ |
| 动态指标 4 项 | `GET /projects/<id>/monthly-data` → `revenue,cost,profit,profit_rate` | ✅（命名为 revenue 系） |
| 基础指标/预计完工指标/租借核销 | ❌ monthly-data 只有 4 字段；`expectedCompleteCost/targetProfit/writeOffRate/rental*` 未暴露（gross_profit 表有四口径数据但接口没带出来） | 🔴 **后端需扩 monthly-data 或 analysis 返回结构** |
| 成本构成六口径两级表 | `GET /projects/<id>/cost-details` → `{name,indicator,actual,deviation,deviation_rate}` 三口径；且 `hierarchy_code` 解析层未填充（`data_extractor.py` 从未赋值）→ 大类/明细两级无法组装 | 🔴 两处都要修：解析层补 hierarchy_code；聚合层补 listTarget/adjTarget/budget/forecast（dynamic_indicator 表里有列，只是没查出来） |

**Tab2 月度对比**：`POST /projects/<id>/month-comparison {months[]}` 已存在 ✅；环比变化率后端无计算（前端可自行算）🟡。

**Tab3 数据详情**（工程量经济指标管控表，19 列含增值税/含税/调进调出/备注）：与 `data_dynamic_indicator` 表结构几乎一一对应，可经 `GET /api/data/dynamic_indicator?batch_id=...` 提供 ✅；同样受 hierarchy_code 缺失影响 🔴。

**Tab4 AI 分析**：`POST /projects/<id>/ai-analysis {ym}` 已存在（外部服务+确定性兜底）✅。

**顶部"导出数据"**：`GET /api/projects/<id>/export`（xlsx 双表）✅。

### 2.4 数据表格 `/project/:id/data-table`

UI（F:69923–70367）：行=字段（基础指标/动态指标/成本构成 3 Tab，14+ 字段）、列=月份；**点击单元格直接编辑 + "保存更改"**。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 按月份横排读数 | 可经 monthly-data / data 行查询拼装 | 🟡 需聚合接口（现需多次调用） |
| **编辑并保存单元格** | ❌ data 上下文只有 GET/DELETE，**全后端无任何 UPDATE 行数据接口** | 🔴 二选一：后端补 `PUT /data/<template_id>/<row_id>`（并处理重算/审计）；或产品确认去掉编辑能力 |
| 字段口径 | UI mock 用 `cumulativeRevenue/expectedCompleteRevenue`，详情页用 `cumulativeSettlement/expectedCompleteSettlement`，后端用 `revenue` | 🟡 需统一"收入/结算"命名字典 |

### 2.5 数据管理 `/management/project/:id`

UI（F:65743–66289）：项目信息卡；月度数据列表（月份/合同价/总成本/毛利/毛利率/状态/上传时间/操作）；4 步上传向导（选择月份→上传Excel→预览确认→提交完成）。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 月度列表 | `GET /projects/<id>/monthly-data`（batch_id,ym,file_name,status,uploaded_at,revenue,cost,profit,profit_rate） | 🟡 缺"合同价"列（可取项目实体）；"状态"列：UI 是经营预警态，后端返回的是批次状态，口径需明确 |
| 删除月度数据 | `DELETE /projects/<id>/monthly-data/<ym>` | ✅（UI 删除按钮无逻辑+无确认框，前端补） |
| 上传 4 步向导 | `POST /upload/preview` → `POST /upload/<batch>/confirm` → `DELETE .../preview` 取消，与 UI 步骤完全同构 | ✅ 链路具备 |
| 文件限制提示 | 后端 .xlsx + 50MB（`upload_constraints.py`） | 🟡 UI 补提示文案 |
| **官方模板下载** | ❌ templates 接口只返回列结构 JSON，无 Excel 模板文件下载 | 🔴 建议后端加模板下载，或 UI 去掉"按官方模板上传"提示 |
| **解析失败/错误行展示** | 后端 preview 返回 `errors[20]` + 每 sheet `error_rows`；UI 只有"校验通过"成功态 | 🔴 UI 必须补失败分支（错误行号/字段/原因列表） |
| 批次/文件维度历史 | `GET /api/batches/`（file_name/file_size/每 sheet total/success/error 行数） | 🟡 后端有、UI 无此区块，建议补"上传记录" |

### 2.6 月度趋势对比 `/compare/single`

UI（F:61744–62306）：月份多选（≥2，URL 驱动）、双轴趋势图（成本/毛利/毛利率）、成本构成柱状图（人工/机械/建筑/材料 4 项）、对比数据表（指标×月份+环比）、"导出对比报表"。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 多月指标对比 | `POST /projects/<id>/month-comparison {months[]}` | ✅ |
| 成本构成按月 4 项 | monthly-data 无 breakdown；需按 ym 多次调 cost-details 拼装 | 🟡 建议 month-comparison 返回携带构成维度 |
| 环比变化 | ❌ 后端无环比/同比计算 | 🟡 前端计算即可 |
| 导出对比报表 | ❌ 3 个 export 端点不含对比报表 | 🔴 后端补导出或前端本地生成 xlsx |

### 2.7 多项目横向对比 `/compare/multi`

UI（F:63540–65741）：核心指标 9 项对比表（进度/合同价/结算产值/营收/总成本/毛利/毛利率/结算完成率/营收比率 + 最优最差标注）、横向条形图、成本结构雷达图、AI 分析报告 Tab（5 章节：核心经营总览/进度对标/成本专项/盈利专项/综合评级，含评分模型）、"导出报表/导出报告"。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 多项目核心指标 | `POST /projects/compare {project_ids,ym}` → `{cost_categories,profits}` | 🟡 需确认返回是否含 settlement/revenue/progress 全 9 项；结算完成率/营收比率为派生可前端算 |
| 成本结构雷达 | compare 的 cost_categories 可支撑，但 UI 雷达 5 维（人工/机械/建筑/材料/管理）与其自身科目页 6 大类**互相不一致**（F:63633 vs 63626） | 🟡 先统一 UI 科目口径，再对齐后端 |
| 多项目 AI 报告 | ❌ 仅单项目 ai-analysis | 🟡 可后端扩展或多调单项目拼接；报告"生成时间"目前写死 |
| 综合评级（A–D 五维评分） | ❌ 后端无评分模型（阈值写死在前端 F:63799–63856） | 🟡 建议评分下沉后端以便预警联动 |
| 导出 | ❌ | 🔴 同 2.6 |

### 2.8 成本科目 `/cost-category`

UI（F:66990–68061）：固定 3 项目 × 6 大类 25 子项，每项目"指标/实际/偏差/偏差率"4 列，大类+子项两级，偏差红绿着色；无筛选器。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 多项目科目对比 | `GET /reports/cost-categories?project_ids&ym`（indicator/actual/deviation/deviation_rate） | ✅ 口径吻合 |
| 大类+子项两级结构 | 🔴 依赖 `hierarchy_code`，解析层未填充（`data_extractor.py` 全文无赋值） | 🔴 **必须修解析层**，否则只有平铺科目行 |
| 导出 | `GET /reports/cost-categories/export` | ✅ |
| 筛选器 | 后端支持 ym/project_ids；UI 没有任何筛选 | 🟡 UI 建议补项目/月份筛选 |

### 2.9 项目毛利情况 `/project-profit`

UI（F:68062–68659）：11 项目 × 四阶段（投标/指标/截至当前实际/预计完工，均含税）×（结算/成本/毛利/毛利率）+ 合计行；实际成本注明"不含两级本部管理费"。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 四口径毛利表 | `GET /reports/project-profits?ym` → 每项目 `bid/indicator/current/forecast × {revenue,cost,profit,profit_rate}` | 🟢 完全对应（命名 revenue vs UI settlement 需映射） |
| 合计行 | 后端分页返回，合计需确认 | 🟡 可在接口加 total 或前端算 |
| 导出 | `GET /reports/project-profits/export`（⚠️ 仅 current 口径、硬编码前 100 条、文件名 ASCII） | 🟡 建议导出补全四口径+中文文件名 |

### 2.10 人员管理 `/users`

UI（F:66290–66993）：用户表（姓名/邮箱/部门/系统角色 admin 二分/项目权限概览/操作）；新增编辑表单（姓名/邮箱/部门/isAdmin，**无用户名无密码**）；项目权限弹窗（每项目 manager/viewer/none）。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 用户 CRUD | `GET/POST/PUT/DELETE /users`（含 keyword 搜索、project_permission_overview 字段——正好对应"项目权限概览"列） | ✅ |
| 创建用户 | 后端必填 `{username,password,...}`；UI 表单缺这两项 | 🔴 UI 加"用户名+初始密码"字段，或后端改为"邮箱即账号+随机初始密码" |
| 项目授权 | `GET/PUT /users/<id>/project-permissions`（manager/viewer/none） | ✅ 与 UI 弹窗完全同构 |
| 系统角色 | UI 只有 isAdmin 二分；后端是完整 RBAC（9 权限点 + admin/manager/viewer 预置角色 + roles CRUD + 用户角色分配接口） | 🟡 后端能力远超 UI：要么 UI 补角色管理页，要么明确仅二分（注意后端 `admin:roles`/`user:manage` 可绕过项目级校验，语义≠UI 的 isAdmin） |
| 手机号 | 后端有 phone，UI 无 | 🟡 UI 可选补 |

### 2.11 数据大屏 `/dashboard`

UI（F:68660–69683）：KPI 4 卡（总项目数/总合同额/总毛利/预警项目）、营收成本趋势面积图、项目毛利分布饼图、成本构成条形图、健康雷达 6 维（进度/成本/质量/安全/效率/毛利）、项目实时状态列表、滚动播报条、实时时钟。

| UI 需求 | 后端现状 | 结论 |
|---|---|---|
| 整屏数据 | `GET /api/dashboard` 一次返回 summary/project_status/profit_distribution/trends/cost_composition/health_radar，另有 6 个子端点 | 🟢 几乎一对一 |
| 健康雷达 | 后端 5 维（profit/cost/progress/schedule/risk） vs UI 6 维（进度/成本/质量/安全/效率/毛利） | 🟡 维度不一致，需对齐（质量/安全后端无数据源） |
| 滚动播报消息流 | ❌ 无专门接口（可用 /notifications 或 alerts 拼装） | 🟡 |
| 项目实时状态（含预警） | `/dashboard/project-status` + `/dashboard/alerts` | ✅ |

### 2.12 全局布局（导航/搜索/通知/同步状态）

| UI 功能 | 后端现状 | 结论 |
|---|---|---|
| 全局搜索（项目/报表/人员，⌘K） | `GET /api/search?keyword`（项目/用户/报表三类） | ✅ 具备，前端未接线 |
| 通知中心（列表/未读数/已读/清空） | `GET/POST /notifications`、`PUT /notifications/<id>/read`；另有 WS `/ws/alerts` 实时推送+断线补发 | ✅ 具备（注意：无"清空全部"与"单条删除"接口，只有标记已读） |
| 侧边栏"数据已同步至 2026-03" | `GET /api/system/sync-status` → latest_month | ✅ |
| 用户菜单/退出 | `GET /auth/me` | ✅（登出见 2.1） |

---

## 3. 后端有、UI 完全没有的能力（建议补页面或菜单）

1. **预警中心**：`/alerts` 列表 + summary + 详情 + events + acknowledge/resolve/ignore 全生命周期，UI 只有项目卡片上一个"预警"徽标，**没有任何预警列表/处理页面**；内置 4 条规则（成本偏差>10%、毛利率<10%、进度滞后>10%、手动预警）。
2. **预警规则配置**：`GET/PUT /alert-rules`（阈值/级别/启停/连续触发次数/自动恢复）无 UI。
3. **角色管理**：roles CRUD + 用户角色分配（`admin:roles`）无 UI。
4. **上传批次记录**：`/api/batches/` 文件级历史（文件名/大小/每 sheet 行数/状态）无 UI 区块。
5. **模板列表**：`/api/templates` 15 套模板结构只读，无 UI（运维向，可不补）。
6. **管理员重置密码**：`PUT /users/<id>/password` 在 UI 用户表里无入口。
7. **WebSocket 实时推送** `/ws/alerts`：前端通知中心目前用 30 秒轮播假数据，可换成真实推送。

## 4. UI 有、后端缺的能力（需后端补接口/字段）

| # | 缺口 | 影响页面 | 建议 |
|---|---|---|---|
| 1 | monthly-data/analysis 字段太薄：缺基础指标 4 项、预计完工 4 项、租借核销 4 项（gross_profit 表有数据未暴露） | 项目详情 | 扩展返回结构 |
| 2 | 成本构成六口径（listTarget/adjTarget/budget/forecast 缺） | 项目详情 | cost-details 补列（dynamic_indicator 表里有） |
| 3 | `hierarchy_code` 解析层从未填充（`data_extractor.py`）+ stop rule `action:"last"` 被忽略（总计行语义，`yaml_loader.py:56-68` 未读 action） | 详情/成本科目/数据详情，所有两级展开 | 修解析层 |
| 4 | 行数据 UPDATE 接口不存在 | 数据表格 | 补 `PUT /data/<tid>/<row_id>` 或砍功能 |
| 5 | 项目列表缺 profitRate 等最新经营指标、manager 姓名 | 项目总览 | 列表接口 join 最新月度 + users 表 |
| 6 | 忘记密码/自助改密 | 登录页 | 补流程或砍入口 |
| 7 | Excel 模板文件下载 | 数据管理上传 | 补下载接口 |
| 8 | 对比报表导出（单项目月度对比、多项目对比） | 两个对比页 | 补 export 或前端生成 |
| 9 | 环比/同比计算 | 对比页 | 前端算即可 |
| 10 | 多项目 AI 报告、综合评分模型 | 多项目对比 | 后端扩展或保留前端演示 |
| 11 | 通知"清空全部/单条删除" | 通知中心 | 补接口或 UI 去掉按钮 |
| 12 | 登出/token 吊销、refresh token | 全局 | 视安全要求补 |

## 5. 必须修改的不一致清单

1. **项目表单**：UI 缺 `code`（后端必填唯一）→ UI 加字段或后端自动生成。
2. **用户表单**：UI 缺 `username/password`（后端必填）→ 同上。
3. **开放注册无审批**（`POST /auth/register`）→ 安全收口。
4. **命名口径**：settlement（结算）vs revenue（营收/收入）在 UI 内部两个页面已打架（`cumulativeSettlement` vs `cumulativeRevenue`），后端用 revenue → 出一份中英字段字典三方对齐。
5. **成本科目分类三套**：详情页 breakdown 9 科目 / 对比页雷达 5 维+堆叠图 6 大类 / 成本科目页 6 大类 25 子项；后端以 dynamic_indicator 科目树为准 → 统一。
6. **大屏雷达维度**：后端 5 维 vs UI 6 维（质量/安全无数据源）→ 对齐。
7. **月度列表"状态"列**：UI=经营预警态，后端=批次解析状态 → 明确两个字段或改名。
8. **导出细节**：硬编码前 100 条、ASCII 文件名、project-profits 导出仅 current 口径 → 补全。
9. **UI 项目 id 体系混乱**：人员管理用数字 id、成本科目用 sg/sw/dd 字符串键（mock 痕迹）→ 接线时统一用后端 id。
10. **UI 命名不一致**：登录页标题"工程项目数据展示系统" vs Header"工程项目数据分析平台"（F:16491 vs 15985）。

## 6. 上传链路专项（UI 4 步向导 ↔ 后端 preview/confirm/cancel）

后端链路与 UI 步骤**结构完全同构**，是全书对接成本最低的部分，但 UI 侧必须补：
- 解析中 loading（preview 是同步请求，大文件需 loading/超时处理）；
- 失败分支：展示后端返回的 `errors[]`（行号/字段/原因）与每 sheet 的 `error_rows`；
- 文件大小（50MB）与 .xlsx 限制的前端预校验；
- "按官方模板上传"配套模板下载（见缺口 7）；
- 上传成功后刷新月度列表 + 触发通知（后端已自动做告警评估 `upload_app_service.py:87-88`，WS 会推）。

---

*证据文件：前端 `.figma-app.pretty.js`（F:行号）；后端 `contexts/**`（文件:行号）。前端 bundle 为压缩美化产物，组件名为混淆名。*

---

## 7. 实现进展（2026-07-17，详见 plan.md）

第 4 节"后端缺"项的处理结果：

| # | 缺口 | 状态 | 说明 |
|---|---|---|---|
| 1 | monthly-data/analysis 字段太薄 | ✅ 已实现 | 补基础指标/预计完工组；租借核销无数据源返回 null（待模板扩展） |
| 2 | 成本构成六口径 | ✅ 已实现 | cost-details/cost-categories 补 list_target/adj_target/budget/forecast；forecast 暂以预计完工量含税指标近似（表无独立列） |
| 3 | hierarchy_code + stop action 修复 | ✅ 已实现 | 新增层级编码解析器；7 份模板的 `action:"last"` 生效（会改变 machinery/social_insurance 等历史解析行为：合计行 now 入库） |
| 4 | 行数据 UPDATE | ✅ 已实现 | `PUT /api/data/<template_id>/<row_id>`（白名单+decimal 校验+manager 鉴权） |
| 5 | 项目列表 profitRate + manager 姓名 | ✅ 已实现 | 批量查询无 N+1（固定 3 次查询） |
| 6 | 忘记密码/自助改密 | 🟡 部分 | 自助改密 `POST /auth/change-password` 已实现（改密后全会话吊销）；邮箱找回需邮件基础设施，未做 |
| 7 | Excel 模板下载 | ✅ 已实现 | `GET /api/templates/<id>/download`（xlsx 骨架，RFC5987 中文名） |
| 8 | 对比报表导出 | ✅ 已实现 | `month-comparison/export`、`compare/export`；另修复旧导出端点预存 TypeError + 补四口径/中文名/去 100 条限制 |
| 9 | 环比计算 | ✅ 已实现 | month-comparison 响应含 mom.change/change_pct |
| 10 | 多项目 AI 报告、综合评分 | ✅ 已实现 | compare 含五维评分+grade；`POST /projects/compare/ai-analysis`（provider+确定性兜底 5 章节） |
| 11 | 通知清空/删除 | ✅ 已实现 | `POST /notifications/read-all`、`DELETE /notifications/<id>`、`DELETE /notifications`（广播通知保留） |
| 12 | 登出/token 吊销 | ✅ 已实现 | `POST /auth/logout` + jti 黑名单（迁移 0005）+ 注册开关 `auth.allow_open_register`（prod 默认关） |

**额外修复的预存缺陷**：
- 🔴 **P0：认证装饰器绑定方法分发缺陷**——`require_auth` 等 4 个装饰器在类方法上首参收到的是控制器实例而非 request，全部受保护端点运行时必 500（此前测试均经 `__wrapped__` 绕过，从未暴露）。已修复 `_resolve_request` 兼容两种分发方式并回归验证（194 passed）。
- 🔴 旧导出端点分页参数个数错误（TypeError，原本即不可用），A2 包已修复并加回归测试。
- ⚠️ **未修复（建议立项）**：YAML `headers.rows` 为 1-based 而 `HeaderFlattener` 按 0-based 消费，每个模板首行数据会被拼进表头（off-by-one）；修复影响全部 15 个模板的列匹配，需专项处理。
- ⚠️ compare 中"营收"与"结算"同源（无独立营收列），revenue_ratio 恒 100/None，待模板扩展。
