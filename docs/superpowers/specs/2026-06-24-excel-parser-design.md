# Excel动态成本解析系统 — 架构设计

## 需求概述

解析API上传的Excel文件入库，支持多级表头、动态表头（月度扩展列）、多个Sheet。Excel模板来自施工项目动态成本管理系统。

### 约束条件

- **框架**: Sanic (异步Python)
- **数据库**: MySQL
- **映射策略**: 配置驱动（YAML配置定义Sheet→DB映射）
- **上传粒度**: 项目 + 月度，每次上传产生一个批次号
- **更新策略**: 追加版本，每次上传INSERT新批次数据
- **规模**: 5-10个项目，中等数据量

---

## 整体架构

```
┌──────────────────────────────────────────────┐
│                  API Layer (Sanic)            │
│  POST /upload   GET /batches   GET /data     │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│              Parse Pipeline                   │
│  Sheet匹配 → 单元格展开 → 表头扁平化          │
│       → 数据提取 → 校验 → 入库               │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│            Config Registry                    │
│  模板配置(YAML)的加载、匹配、验证             │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│              MySQL Database                   │
│  用户/权限表 / 项目表 / 批次表 / 日志表 /     │
│  模板配置表 / 各模板数据表                    │
└──────────────────────────────────────────────┘
```

### 目录结构

```
parser/
├── app.py                    # Sanic应用入口
├── configs/
│   └── templates/
│       ├── labor_cost.yaml        # 表1 人工费-动态
│       ├── social_insurance.yaml  # 表2 社会统筹-动态
│       ├── site_mgmt.yaml         # 表3 现场管理费-动态
│       ├── machinery.yaml         # 表4 机械费用-动态
│       └── ...                    # 其余模板
├── core/
│   ├── pipeline.py           # 解析管线编排
│   ├── cell_unmerger.py      # 合并单元格展开
│   ├── header_flattener.py   # 多级表头扁平化
│   ├── data_extractor.py     # 数据行提取（按表头名称匹配）
│   ├── stop_detector.py      # 停止规则检测
│   └── validator.py          # 数据校验
├── api/
│   ├── auth.py               # 认证接口
│   ├── upload.py             # 文件上传接口
│   ├── data.py               # 数据查询接口
│   ├── project.py            # 项目管理接口
│   └── template.py           # 模板管理接口
├── models/
│   ├── user.py
│   ├── project.py
│   ├── batch.py
│   └── template.py
├── db/
│   ├── connection.py         # MySQL连接池 (aiomysql)
│   └── schema.py             # 建表/迁移
├── middleware/
│   └── auth.py               # JWT认证中间件
└── utils/
    ├── excel_reader.py       # openpyxl封装
    └── config_loader.py      # YAML配置加载
```

---

## 模板配置设计 (YAML)

列映射采用**表头名称匹配**而非列字母位置，适应列顺序变化。

### 示例：表1 人工费-动态

```yaml
template_id: "labor_cost"
sheet_pattern: "表1*人工费*"
description: "人工费动态表"

headers:
  rows: [2, 3, 4]              # 表头行号
  data_start_row: 5            # 数据起始行

hierarchy:
  column_name: "序号"           # 层级列的表头名称
  separator: "."

# 停止规则
stop_rules:
  - type: "cell_match"
    patterns: ["^注：", "^注 :", "^说明："]
    columns: ["A"]
  - type: "cell_match"
    patterns: ["^金额单位"]
    columns: ["A"]
  - type: "consecutive_empty_rows"
    count: 5

# 固定列 — 按展平后的表头名称匹配
columns:
  - db_field: "person_name"
    match_header: ["姓名"]
    type: "varchar(100)"
  - db_field: "department"
    match_header: ["部门"]
    type: "varchar(100)"
  - db_field: "position"
    match_header: ["职位"]
    type: "varchar(100)"
  - db_field: "contract_relation"
    match_header: ["合同关系"]
    type: "varchar(100)"
  - db_field: "actual_person_months"
    match_header: ["截止到当前", "实际人月"]
    type: "decimal(10,2)"
  - db_field: "actual_total_cost"
    match_header: ["截止到当前", "实际总成本"]
    type: "decimal(15,2)"
  - db_field: "subsequent_person_months"
    match_header: ["后续发生", "后续人月数"]
    type: "decimal(10,2)"
  - db_field: "subsequent_cost"
    match_header: ["后续发生", "后续成本"]
    type: "decimal(15,2)"
  - db_field: "estimated_person_months"
    match_header: ["预计完工成本", "人月数"]
    type: "decimal(10,2)"
  - db_field: "estimated_total_cost"
    match_header: ["预计完工成本", "完工总成本"]
    type: "decimal(15,2)"

# 动态列 — 按月表头名称模式匹配，存入JSON
dynamic_columns:
  - db_prefix: "monthly"
    match_header: ["累计已发生", "2025年"]
    type: "decimal(15,2)"
  - db_prefix: "monthly_2026"
    match_header: ["后续发生", "2026年"]
    type: "decimal(15,2)"
```

### 列匹配逻辑

多级表头展平后得到如 `"截止到当前_实际人月"` 的列名，与 `match_header: ["截止到当前", "实际人月"]` 做交集匹配（所有关键词都在展平列名中出现即命中）。列顺序变化不影响匹配结果。

---

## 核心解析管线

```
Excel文件
  │
  ▼
┌──────────────────┐
│ ① Sheet匹配      │  遍历Sheet，按sheet_pattern匹配模板
│                  │  未匹配→skip日志，已匹配→继续
└──────┬───────────┘
       ▼
┌──────────────────┐
│ ② 单元格展开      │  合并单元格值填充到每个子格
└──────┬───────────┘
       ▼
┌──────────────────┐
│ ③ 表头扁平化      │  多行表头逐列拼接（空值跳过）
│                  │  Row2+Row3+Row4 → "截止到当前_实际人月"
└──────┬───────────┘
       ▼
┌──────────────────┐
│ ④ 停止规则检查    │  每行检查stop_rules，命中则停止该Sheet
└──────┬───────────┘
       ▼
┌──────────────────┐
│ ⑤ 数据提取        │  逐行：固定列match_header匹配
│                  │  动态列区域展平为JSON
│                  │  层级列从指定名称提取
└──────┬───────────┘
       ▼
┌──────────────────┐
│ ⑥ 校验+入库       │  类型校验→批量INSERT→写日志
└──────────────────┘
```

### 停止规则（见 docs/excel-tail-patterns.md）

基于15个Sheet的尾部特征分析，三类停止规则：

| 规则 | 特征 | 动作 |
|------|------|------|
| `cell_match` | A列匹配 `^注：` / `^金额单位` | 立即停止 |
| `consecutive_empty_rows` | 连续5行全空 | 停止 |
| 自然结束 | 数据到最后一行 | 正常结束 |

"合计"、"小计"、"总计"不作为停止规则，它们是需要入库的有效数据。

---

## 数据库设计

### 用户与权限

```
users ──── user_roles ──── roles ──── role_permissions ──── permissions
```

```sql
-- 用户
CREATE TABLE users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    real_name   VARCHAR(100),
    email       VARCHAR(200),
    phone       VARCHAR(20),
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 角色
CREATE TABLE roles (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(50) NOT NULL UNIQUE,
    name        VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 权限
CREATE TABLE permissions (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(100) NOT NULL UNIQUE,
    name        VARCHAR(200) NOT NULL,
    description VARCHAR(500)
);

-- 用户-角色
CREATE TABLE user_roles (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    UNIQUE KEY uk_user_role (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

-- 角色-权限
CREATE TABLE role_permissions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    role_id       INT NOT NULL,
    permission_id INT NOT NULL,
    UNIQUE KEY uk_role_perm (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id),
    FOREIGN KEY (permission_id) REFERENCES permissions(id)
);
```

### 预设权限

| 编码 | 名称 |
|------|------|
| `project:create` | 创建项目 |
| `project:view` | 查看项目 |
| `data:upload` | 数据上传 |
| `data:view` | 数据查看 |
| `data:export` | 数据导出 |
| `template:manage` | 模板管理 |
| `user:manage` | 用户管理 |

### 预设角色

| 角色 | 权限 |
|------|------|
| admin | 全部 |
| manager | project:view, data:upload, data:view, data:export |
| viewer | project:view, data:view |

### 业务表

```sql
-- 项目表
CREATE TABLE projects (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(50) NOT NULL UNIQUE,
    name        VARCHAR(200) NOT NULL,
    created_by  INT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 上传批次表
CREATE TABLE upload_batches (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    batch_no     VARCHAR(50) NOT NULL UNIQUE,
    project_id   INT NOT NULL,
    year_month   VARCHAR(7) NOT NULL COMMENT 'YYYY-MM',
    uploaded_by  INT,
    file_name    VARCHAR(500),
    file_size    BIGINT,
    status       ENUM('processing','success','partial','failed') DEFAULT 'processing',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- 上传日志表
CREATE TABLE upload_logs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    batch_id     INT NOT NULL,
    sheet_name   VARCHAR(200),
    template_id  VARCHAR(100),
    action       ENUM('matched','skipped','empty','error') DEFAULT 'matched',
    total_rows   INT DEFAULT 0,
    success_rows INT DEFAULT 0,
    error_rows   INT DEFAULT 0,
    error_msg    TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES upload_batches(id),
    INDEX idx_batch (batch_id)
);

-- 模板配置表
CREATE TABLE template_configs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    template_id  VARCHAR(100) NOT NULL UNIQUE,
    description  VARCHAR(500),
    config_yaml  TEXT NOT NULL,
    data_table   VARCHAR(100) NOT NULL,
    is_active    TINYINT(1) DEFAULT 1,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 模板数据表（示例）

由模板配置的 `columns` 定义自动生成。动态列存入 `monthly_data` JSON字段。

```sql
CREATE TABLE data_labor_cost (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    batch_id        INT NOT NULL,
    hierarchy_code  VARCHAR(50),
    person_name     VARCHAR(100),
    department      VARCHAR(100),
    position        VARCHAR(100),
    contract_relation VARCHAR(100),
    actual_person_months DECIMAL(10,2),
    actual_total_cost DECIMAL(15,2),
    subsequent_person_months DECIMAL(10,2),
    subsequent_cost DECIMAL(15,2),
    estimated_person_months DECIMAL(10,2),
    estimated_total_cost DECIMAL(15,2),
    monthly_data    JSON,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES upload_batches(id),
    INDEX idx_batch (batch_id),
    INDEX idx_hierarchy (hierarchy_code)
);
```

---

## API设计

```
POST   /api/auth/login              # 登录，返回JWT token
POST   /api/auth/logout             # 登出

GET    /api/projects                 # 项目列表
POST   /api/projects                 # 创建项目

POST   /api/upload                   # 上传Excel (multipart/form-data)
        Fields: file, project_id, year_month, batch_no(可选)

GET    /api/batches                  # 批次列表 (?project_id=&year_month=)
GET    /api/batches/<batch_id>       # 批次详情 + 各Sheet处理日志

GET    /api/data/<template_id>       # 查询解析数据
        ?batch_id=&page=&size=

GET    /api/templates                # 模板列表
POST   /api/templates                # 注册新模板

GET    /api/users                    # 用户管理 (admin)
POST   /api/users
PUT    /api/users/<id>/roles
```

### POST /api/upload 响应示例

```json
{
  "batch_id": 42,
  "batch_no": "B20250624001",
  "status": "processing",
  "sheets": [
    {"name": "表1 人工费-动态", "template": "labor_cost", "rows": 72, "status": "success"},
    {"name": "表2 社会统筹-动态", "template": "social_insurance", "rows": 72, "status": "success"},
    {"name": "毛利", "template": null, "rows": 0, "status": "skipped"}
  ]
}
```

---

## 错误处理与校验

### 分层校验

| 层级 | 内容 | 失败处理 |
|------|------|---------|
| 0 — 文件级 | 类型(.xlsx)、大小(≤50MB)、可读性 | 直接拒绝，返回4xx |
| 1 — Sheet级 | 模板匹配、表头识别、有效行数 | skip/empty记录日志 |
| 2 — 行级 | 类型转换、必填字段 | 该行记error继续 |
| 3 — 业务级 | 数值异常预警（可配置开关） | warn不阻断 |

### 不阻断原则

- 一个Sheet出错不影响其他Sheet
- 一行出错不影响后续行
- 批次状态按成功率判定: 全成功→success, 部分→partial, 全失败→failed
- 所有错误汇入 `upload_logs.error_msg`

---

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 列映射方式 | 表头名称匹配 | 列顺序变化不感知，比字母位置稳健 |
| 动态列存储 | JSON字段 | 月度列无限扩展，避免频繁DDL |
| 数据表策略 | 每模板一张表 | 查询性能好，类型安全，业务语义清晰 |
| 批次版本 | INSERT追加 | 保留历史追溯，符合成本审计需求 |
| 停止规则 | 多级fallback，合计/总计不作为停止 | 覆盖注释行+子表+空行+尾部说明，汇总行入库 |
| 上传处理 | 异步 | 不阻塞API响应，大文件友好 |
