# plan.md — 按后端架构实现缺失功能

> **执行状态（2026-07-17）：全部完成。** Wave 1（A1/B/C/D/E）与 Wave 2（A2）均已交付，主代理另修复装饰器绑定方法分发缺陷（P0），全量 `pytest` 194 passed。

来源：`docs/ui-backend-gap-analysis.md` 第 4 节（UI 有、后端缺）。按 DDD 上下文划分工作包，互不冲突的包并行，存在文件依赖的包串行。

## Wave 1（并行 5 个 coder 子代理）

| 包 | 角色标签 | 范围（文件均相对仓库根） | 任务 |
|---|---|---|---|
| A1 | 后端_分析读模型 | `contexts/analytics/**` | ① `monthly-data` 扩展：基础指标（contract_price/estimated_completion_price/indicator 组）、预计完工 forecast 组；租借核销字段无数据源→返回 null 并注释 ② `cost-details`/`cost-categories` 补六口径（listTarget/adjTarget/budget/forecast，来自 data_dynamic_indicator 现有列）③ `month-comparison` 增加环比计算 ④ `POST /projects/compare` 扩展到 9 项指标 + 五维评分（阈值见 UI 报告 F:63799-63856） |
| B | 后端_解析与模板 | `contexts/parsing/domain/*`、`contexts/template/**` | ① `DataRowExtractor` 填充 `hierarchy_code`（按模板 hierarchy 序号列+分隔符） ② `yaml_loader` 读取 stop rule `action`，`stop_detector` 支持 `action:"last"`（总计行入库） ③ 新增 `GET /api/templates/<id>/download`：按 YAML 生成 xlsx 模板骨架 |
| C | 后端_数据更新 | `contexts/data/**` | 新增 `PUT /api/data/<template_id>/<row_id>`：字段白名单、decimal 校验、权限 data:upload + 批次项目 manager、支持 monthly_data JSON 键更新 |
| D | 后端_项目列表 | `contexts/project/**` | 项目列表/详情序列化补充：`manager_name`（join users）、最新月份经营指标（latest_ym/revenue/cost/profit/profit_rate，查 upload_batches+data_gross_profit，避免 N+1） |
| E | 后端_认证安全 | `contexts/auth/**`、`config/**`、migrations | ① 自助改密 `POST /api/auth/change-password`（验旧密码，≥8 位） ② 登出 `POST /api/auth/logout` + JWT 黑名单（新表+迁移，`require_auth` 校验） ③ 开放注册加开关 `auth.allow_open_register`，默认关闭（关闭时需 admin 权限或 403） |

## Wave 2（串行，待 A1 完成后；同属 analytics 文件）

| 包 | 角色标签 | 任务 |
|---|---|---|
| A2 | 后端_导出与通知 | ① project-profits 导出补四口径+中文文件名（RFC5987）+去掉 100 条硬编码 ② 新增月度对比导出、多项目对比导出 ③ 通知：`POST /notifications/read-all`、`DELETE /notifications/<id>`、`DELETE /notifications`（清空） ④ 多项目 AI 报告 `POST /projects/compare/ai-analysis`（复用 ai_provider + 确定性兜底，5 章节对齐 UI） |

## 统一约束

- 遵循现有分层：interface（路由+权限装饰器）/ application（编排）/ domain（规则）/ infrastructure（ORM）；`BaseController` 前缀 `/api`；`DomainError` 语义化错误码；分页 `page/size` + `pagination` 响应。
- 每个包配 pytest（tests/ 下镜像结构），用项目 venv 运行：`.venv/Scripts/python.exe -m pytest <目标测试>`。
- 只有 E 允许新增数据库迁移（黑名单表）；其余包不得改表结构。
- 完成后主代理跑全量 `pytest` 回归，并更新差距分析文档标注已实现项。
