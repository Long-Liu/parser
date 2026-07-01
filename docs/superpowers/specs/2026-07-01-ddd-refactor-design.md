# DDD重构设计 — Excel动态成本解析系统

## 目标

将现有分层架构重构为完整DDD战术模式：5个限界上下文 + 共享内核，每个上下文四层结构。

## 限界上下文

```
┌─────────────────────────────────────────────────────────┐
│                    Shared Kernel                        │
│  基础值对象(Money/DateRange)、Entity基类、DomainEvent   │
│  UoW接口、异常定义                                       │
└───────┬──────────┬──────────┬──────────┬────────────────┘
        │          │          │          │
   ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
   │  Auth  │ │Project │ │Template│ │Parsing │
   │ 认证授权│ │项目管理 │ │模板配置│ │解析管线│
   │        │ │        │ │        │ │   ★核心│
   └────────┘ └────────┘ └────────┘ └────┬───┘
                                         │
                                    ┌────▼───┐
                                    │  Data  │
                                    │ 数据查询│
                                    └────────┘
```

| 上下文 | 核心聚合 | DDD深度 |
|--------|---------|---------|
| Auth | User, Role | 实体+值对象+仓储 |
| Project | Project | 实体+仓储 |
| Template | Template | 聚合根+值对象+领域服务 |
| Parsing ⭐ | ParseJob | 聚合根+值对象+领域服务+策略+领域事件 |
| Data | DataQuery (读模型) | 读模型+CQRS-lite |

上下文关系：
- Parsing 依赖 Template（获取解析配置）→ 通过接口依赖反转
- Parsing 依赖 Project（关联项目）→ 通过 ID 引用
- Data 消费 Parsing 产出的领域事件 → 事件解耦
- Auth 被所有上下文接口层依赖 → 共享内核接口

每个上下文内部四层：
```
context/<name>/
├── domain/          # 实体/值对象/聚合/领域服务/仓储接口/领域事件
├── application/     # 应用服务/命令/查询/DTO
├── infrastructure/  # 仓储实现/ORM/消息
└── interface/       # Sanic蓝图/请求校验
```

---

## Parsing 上下文（核心）

### 聚合：ParseJob

```
ParseJob (聚合根)
├── job_id: JobId (值对象)
├── project_id: ProjectId (引用)
├── year_month: YearMonth (值对象)
├── file_info: FileInfo (值对象: filename, size, hash)
├── status: JobStatus (枚举: submitted→matching→extracting→validating→persisting→done/failed)
├── sheets: list[SheetResult] (实体)
└── events: list[DomainEvent]

SheetResult (实体, ParseJob聚合内)
├── sheet_name: str
├── template_id: TemplateId | None
├── match_status: MatchStatus (matched/skipped/empty/error)
├── total_rows: int
├── success_rows: int
├── error_rows: int
├── errors: list[RowError] (值对象列表)
└── extracted_rows: list[ParsedRow] (值对象列表)

RowError (值对象)
├── row_index: int
├── field: str
├── value: str
├── reason: str

ParsedRow (值对象)
├── row_index: int
├── hierarchy_code: str | None
├── fields: dict[str, Any]
├── monthly_data: dict[str, Any] | None
```

### 领域服务

| 服务 | 职责 |
|------|------|
| SheetMatcher | 按 sheet_pattern 匹配模板配置 |
| CellUnmerger | 展开合并单元格 |
| HeaderFlattener | 多级表头 → 扁平列名 |
| StopDetector | 停止规则检测（cell_match / empty_rows） |
| DataRowExtractor | 按表头名称匹配提取数据行 |
| DataValidator | 类型校验 + 必填检查 |

### 领域事件

```
ParseJobSubmitted  →  解析请求已接受
SheetMatched       →  Sheet已匹配模板
SheetSkipped       →  Sheet未匹配
SheetExtracted     →  数据行已提取
SheetValidated     →  数据行已校验
DataReadyToPersist →  校验通过，待入库
ParseJobCompleted  →  解析完成 (→ Data上下文消费)
ParseJobFailed     →  解析失败
```

### 仓储接口（领域层定义）

```python
class ParseJobRepository(ABC):
    async def next_id() -> JobId: ...
    async def save(job: ParseJob) -> None: ...
    async def find_by_id(id: JobId) -> ParseJob | None: ...
    async def find_by_project(project_id: ProjectId, ...) -> list[ParseJob]: ...
```

---

## Template 上下文

### 聚合：Template

```
Template (聚合根)
├── template_id: TemplateId (值对象)
├── description: str
├── sheet_pattern: str
├── header_spec: HeaderSpec (值对象)
│   ├── header_rows: list[int]
│   └── data_start_row: int
├── hierarchy_config: HierarchyConfig | None (值对象)
│   ├── column_name: str
│   └── separator: str
├── stop_rules: list[StopRule] (值对象列表)
│   ├── rule_type: StopRuleType (cell_match | consecutive_empty)
│   ├── patterns: list[str] | None
│   ├── columns: list[str] | None
│   └── empty_row_count: int | None
├── fixed_columns: list[ColumnMapping] (值对象列表)
│   ├── db_field: str
│   ├── match_headers: list[str]
│   └── db_type: str
├── dynamic_columns: list[DynamicColumnMapping] (值对象列表)
│   ├── db_prefix: str
│   ├── match_headers: list[str]
│   └── db_type: str
├── data_table: str
└── is_active: bool
```

### 领域服务

| 服务 | 职责 |
|------|------|
| TemplateValidator | 验证 YAML 配置合法 |
| YamlTemplateLoader | YAML → Template 聚合 |
| ColumnMatcher | 扁平表头名 vs match_headers 匹配 |

### 仓储接口

```python
class TemplateRepository(ABC):
    async def next_id() -> TemplateId: ...
    async def save(template: Template) -> None: ...
    async def find_by_id(id: TemplateId) -> Template | None: ...
    async def find_all_active() -> list[Template]: ...
    async def find_matching(sheet_name: str) -> list[Template]: ...
```

---

## Auth 上下文

```
User (聚合根)
├── user_id: UserId (值对象)
├── username: str
├── password_hash: str
├── real_name: str
├── roles: list[RoleRef] (值对象)
└── is_active: bool

Role (聚合根)
├── role_id: RoleId
├── code: str
├── name: str
├── permissions: list[PermissionRef] (值对象列表)
```

领域服务: AuthenticationService、AuthorizationService

---

## Project 上下文

```
Project (聚合根)
├── project_id: ProjectId (值对象)
├── code: str
├── name: str
├── created_by: UserId (引用)
```

聚合根保证 code 唯一性。仅 CRUD，简单分层。

---

## Data 上下文（读模型）

```
DataQuery (无状态查询聚合)
├── template_id: TemplateId
├── batch_id: BatchId | None
├── filters: list[FilterCriterion] (值对象)
├── pagination: Pagination (值对象)
└── result: list[DataRow] (值对象)
```

消费 ParseCompleted 事件 → 记录处理日志、更新批次状态。

---

## 共享内核

```
shared/
├── domain/
│   ├── base_entity.py           # Entity基类 (id, equality, events收集)
│   ├── base_value_object.py     # ValueObject基类 (immutable, value equality)
│   ├── base_aggregate_root.py   # AggregateRoot (Entity + 事件发布)
│   ├── base_domain_event.py     # DomainEvent基类
│   ├── base_repository.py       # Repository ABC
│   ├── identifiers.py           # 通用Id值对象
│   ├── exceptions.py            # 领域异常层次
│   ├── money.py                 # Money值对象
│   └── date_range.py            # DateRange值对象
├── infrastructure/
│   ├── unit_of_work.py          # UoW接口 + SQLAlchemy实现
│   ├── domain_event_bus.py      # 事件总线接口 + 实现
│   └── auth_context.py          # AuthContext接口
└── interface/
    └── base_controller.py       # Sanic Blueprint基类
```

---

## 最终目录结构

```
parser/
├── app.py
├── contexts/
│   ├── shared/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   └── interface/
│   ├── auth/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── interface/
│   ├── project/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── interface/
│   ├── template/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── interface/
│   ├── parsing/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── interface/
│   └── data/
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       └── interface/
├── config/                   # 模板YAML
├── tests/                    # 按上下文组织
│   ├── shared/
│   ├── auth/
│   ├── project/
│   ├── template/
│   ├── parsing/
│   └── data/
└── docs/                     # 设计文档
```

---

## 关键设计约束

- **跨上下文引用**: 仅通过 ID 引用（UserId → UserId, ProjectId → ProjectId），不持有对方聚合的引用
- **领域事件解耦**: Parsing 发布事件 → Data 订阅消费，通过事件总线
- **仓储接口定义在领域层**: 实现在 infrastructure 层
- **不阻断原则保留**: 校验错误不中断解析，逐行容错
- **现有 pipeline 6 步骤保留**: 逻辑不变，注入到聚合的领域方法中
