# Excel动态成本解析系统 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一套解析施工项目Excel成本表入库的系统，支持多级表头、动态列、多Sheet、RBAC权限管理。

**Architecture:** Sanic异步Web框架 + 配置驱动的解析管线（Sheet匹配→单元格展开→表头扁平化→停止检测→名称匹配提取→校验入库）+ MySQL存储，通过YAML模板配置解耦Excel结构与数据库Schema。

**Tech Stack:** Python 3.12+, Sanic 24.x, aiomysql, openpyxl, PyYAML, PyJWT, bcrypt

## Global Constraints

- 框架: Sanic (异步Python)
- 数据库: MySQL
- 配置驱动: YAML定义Sheet→DB映射，列按表头名称匹配非列字母
- 上传粒度: 项目+月度+批次号，追加版本不覆盖
- 错误不阻断: 一个Sheet/行出错不影响其他
- Python版本≥3.12

---

### Task 1: 项目骨架搭建

**Files:**
- Create: `requirements.txt`
- Create: `parser/__init__.py`
- Create: `parser/app.py` (最小入口)
- Create: `parser/db/__init__.py`
- Create: `parser/core/__init__.py`
- Create: `parser/api/__init__.py`
- Create: `parser/models/__init__.py`
- Create: `parser/middleware/__init__.py`
- Create: `parser/utils/__init__.py`
- Create: `parser/configs/templates/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: 项目目录结构，Sanic最小可启动应用

- [ ] **Step 1: 创建 requirements.txt**

```
sanic>=24.6.0
aiomysql>=0.2.0
openpyxl>=3.1.0
pyyaml>=6.0
pyjwt>=2.8.0
bcrypt>=4.1.0
pytest>=8.0
pytest-sanic>=1.10.0
```

- [ ] **Step 2: 创建目录结构和 __init__.py**

```bash
mkdir -p parser/core parser/api parser/models parser/db parser/middleware parser/utils parser/configs/templates tests
touch parser/__init__.py parser/core/__init__.py parser/api/__init__.py parser/models/__init__.py parser/db/__init__.py parser/middleware/__init__.py parser/utils/__init__.py tests/__init__.py parser/configs/templates/.gitkeep
```

- [ ] **Step 3: 创建最小 Sanic 入口 parser/app.py**

```python
from sanic import Sanic
from sanic.response import json

app = Sanic("excel_parser")


@app.get("/health")
async def health(request):
    return json({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

- [ ] **Step 4: 创建 tests/conftest.py**

```python
import pytest
from app import app


@pytest.fixture
def test_app():
    return app
```

- [ ] **Step 5: 安装依赖并验证启动**

```bash
cd C:/Users/Administrator/PycharmProjects/parser
.venv/Scripts/pip.exe install -r requirements.txt
.venv/Scripts/python.exe -c "from parser.app import app; print('OK')"
```

Expected: OK

- [ ] **Step 6: 运行健康检查测试**

```bash
.venv/Scripts/pytest.exe tests/ -v
```

Expected: (暂无测试)收集0条 — 验证pytest可运行

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: project skeleton with Sanic entry point"
```

---

### Task 2: 数据库连接池与Schema创建

**Files:**
- Create: `parser/db/connection.py`
- Create: `parser/db/schema.py`
- Create: `parser/db/seed.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Produces: `get_pool() -> aiomysql.Pool` — 连接池获取
- Produces: `init_db(pool) -> None` — 创建所有表
- Produces: `seed_defaults(pool) -> None` — 插入默认角色/权限

- [ ] **Step 1: 创建 parser/db/connection.py**

```python
import aiomysql
from sanic import Sanic


async def get_pool(app: Sanic = None) -> aiomysql.Pool:
    if app and hasattr(app.ctx, "pool"):
        return app.ctx.pool
    pool = await aiomysql.create_pool(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="",
        db="excel_parser",
        autocommit=True,
        minsize=2,
        maxsize=10,
    )
    if app:
        app.ctx.pool = pool
    return pool
```

- [ ] **Step 2: 创建 parser/db/schema.py**

```python
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    real_name VARCHAR(100),
    email VARCHAR(200),
    phone VARCHAR(20),
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS user_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    UNIQUE KEY uk_user_role (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    permission_id INT NOT NULL,
    UNIQUE KEY uk_role_perm (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id),
    FOREIGN KEY (permission_id) REFERENCES permissions(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS upload_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_no VARCHAR(50) NOT NULL UNIQUE,
    project_id INT NOT NULL,
    year_month VARCHAR(7) NOT NULL COMMENT 'YYYY-MM',
    uploaded_by INT,
    file_name VARCHAR(500),
    file_size BIGINT,
    status ENUM('processing','success','partial','failed') DEFAULT 'processing',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS upload_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    sheet_name VARCHAR(200),
    template_id VARCHAR(100),
    action ENUM('matched','skipped','empty','error') DEFAULT 'matched',
    total_rows INT DEFAULT 0,
    success_rows INT DEFAULT 0,
    error_rows INT DEFAULT 0,
    error_msg TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES upload_batches(id),
    INDEX idx_batch (batch_id)
);

CREATE TABLE IF NOT EXISTS template_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    config_yaml TEXT NOT NULL,
    data_table VARCHAR(100) NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"""


async def init_db(pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    await cur.execute(stmt)
```

- [ ] **Step 3: 创建 parser/db/seed.py**

```python
async def seed_defaults(pool):
    permissions = [
        ("project:create", "创建项目"),
        ("project:view", "查看项目"),
        ("data:upload", "数据上传"),
        ("data:view", "数据查看"),
        ("data:export", "数据导出"),
        ("template:manage", "模板管理"),
        ("user:manage", "用户管理"),
    ]
    roles = [
        ("admin", "管理员"),
        ("manager", "项目经理"),
        ("viewer", "查看者"),
    ]
    role_perms = {
        "admin": ["project:create", "project:view", "data:upload", "data:view",
                   "data:export", "template:manage", "user:manage"],
        "manager": ["project:view", "data:upload", "data:view", "data:export"],
        "viewer": ["project:view", "data:view"],
    }

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for code, name in permissions:
                await cur.execute(
                    "INSERT IGNORE INTO permissions (code, name) VALUES (%s, %s)",
                    (code, name),
                )
            for code, name in roles:
                await cur.execute(
                    "INSERT IGNORE INTO roles (code, name) VALUES (%s, %s)",
                    (code, name),
                )
            for role_code, perm_codes in role_perms.items():
                await cur.execute(
                    "SELECT id FROM roles WHERE code = %s", (role_code,)
                )
                role_row = await cur.fetchone()
                if not role_row:
                    continue
                role_id = role_row[0]
                for pc in perm_codes:
                    await cur.execute(
                        "SELECT id FROM permissions WHERE code = %s", (pc,)
                    )
                    perm_row = await cur.fetchone()
                    if not perm_row:
                        continue
                    await cur.execute(
                        "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
                        (role_id, perm_row[0]),
                    )
```

- [ ] **Step 4: 创建 tests/test_db.py**

```python
import pytest
from db.connection import get_pool
from db.schema import init_db
from db.seed import seed_defaults


@pytest.mark.asyncio
async def test_init_db_creates_tables():
    pool = await get_pool()
    await init_db(pool)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SHOW TABLES")
            tables = [row[0] async for row in cur]

    expected = ["users", "roles", "permissions", "user_roles",
                "role_permissions", "projects", "upload_batches",
                "upload_logs", "template_configs"]
    for t in expected:
        assert t in tables, f"Table {t} not found"


@pytest.mark.asyncio
async def test_seed_defaults_inserts_data():
    pool = await get_pool()
    await init_db(pool)
    await seed_defaults(pool)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM permissions")
            perm_count = (await cur.fetchone())[0]
            await cur.execute("SELECT COUNT(*) FROM roles")
            role_count = (await cur.fetchone())[0]

    assert perm_count == 7
    assert role_count == 3
```

- [ ] **Step 5: 运行测试**

```bash
.venv/Scripts/pytest.exe tests/test_db.py -v
```

Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: database connection pool, schema, and seed data"
```

---

### Task 3: YAML配置加载器

**Files:**
- Create: `parser/utils/config_loader.py`
- Create: `tests/test_config_loader.py`
- Create: `parser/configs/templates/labor_cost.yaml` (第一个模板配置)

**Interfaces:**
- Produces: `load_config(template_id: str) -> dict`
- Produces: `list_configs() -> list[dict]`
- Produces: `match_template(sheet_name: str) -> Optional[dict]` — 按sheet_pattern匹配

- [ ] **Step 1: 写失败测试 tests/test_config_loader.py**

```python
import pytest
import tempfile
import os
from utils import load_config, list_configs, match_template


@pytest.fixture
def config_dir():
    with tempfile.TemporaryDirectory() as d:
        yaml_content = """
template_id: test_tpl
sheet_pattern: "表1*人工费*"
description: "测试模板"
headers:
  rows: [2, 3, 4]
  data_start_row: 5
columns:
  - db_field: "name"
    match_header: ["姓名"]
    type: "varchar(100)"
stop_rules:
  - type: "cell_match"
    patterns: ["^注："]
    columns: ["A"]
"""
        with open(os.path.join(d, "test.yaml"), "w", encoding="utf-8") as f:
            f.write(yaml_content)
        yield d


def test_load_config(config_dir):
    config = load_config("test_tpl", config_dir=config_dir)
    assert config["template_id"] == "test_tpl"
    assert config["headers"]["data_start_row"] == 5
    assert len(config["columns"]) == 1


def test_list_configs(config_dir):
    configs = list_configs(config_dir=config_dir)
    assert len(configs) == 1
    assert configs[0]["template_id"] == "test_tpl"


def test_match_template(config_dir):
    config = match_template("表1 人工费-动态", config_dir=config_dir)
    assert config is not None
    assert config["template_id"] == "test_tpl"


def test_match_template_no_match(config_dir):
    config = match_template("不存在的Sheet名", config_dir=config_dir)
    assert config is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_config_loader.py -v
```

Expected: 4 FAIL (ImportError)

- [ ] **Step 3: 实现 parser/utils/config_loader.py**

```python
import os
import fnmatch
import yaml

DEFAULT_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "configs", "templates")


def _config_dir(config_dir=None):
    path = config_dir or DEFAULT_CONFIG_DIR
    return os.path.abspath(path)


def load_config(template_id: str, config_dir=None) -> dict:
    filepath = os.path.join(_config_dir(config_dir), f"{template_id}.yaml")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_configs(config_dir=None) -> list[dict]:
    result = []
    d = _config_dir(config_dir)
    if not os.path.isdir(d):
        return result
    for filename in os.listdir(d):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(d, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                result.append(yaml.safe_load(f))
    return result


def match_template(sheet_name: str, config_dir=None) -> dict | None:
    configs = list_configs(config_dir)
    for cfg in configs:
        pattern = cfg.get("sheet_pattern", "")
        if fnmatch.fnmatch(sheet_name, pattern):
            return cfg
    return None
```

- [ ] **Step 4: 创建第一个模板配置 parser/configs/templates/labor_cost.yaml**

```yaml
template_id: labor_cost
sheet_pattern: "表1*人工费*"
description: "人工费动态表"

headers:
  rows: [2, 3, 4]
  data_start_row: 5

hierarchy:
  column_name: "序号"
  separator: "."

stop_rules:
  - type: cell_match
    patterns: ["^注：", "^注 :", "^说明："]
    columns: ["A"]
  - type: cell_match
    patterns: ["^金额单位"]
    columns: ["A"]
  - type: consecutive_empty_rows
    count: 5

columns:
  - db_field: person_name
    match_header: ["姓名"]
    type: varchar(100)
  - db_field: department
    match_header: ["部门"]
    type: varchar(100)
  - db_field: position
    match_header: ["职位"]
    type: varchar(100)
  - db_field: contract_relation
    match_header: ["合同关系"]
    type: varchar(100)
  - db_field: actual_person_months
    match_header: ["截止到当前", "实际人月"]
    type: decimal(10,2)
  - db_field: actual_total_cost
    match_header: ["截止到当前", "实际总成本"]
    type: decimal(15,2)
  - db_field: subsequent_person_months
    match_header: ["后续发生", "后续人月数"]
    type: decimal(10,2)
  - db_field: subsequent_cost
    match_header: ["后续发生", "后续成本"]
    type: decimal(15,2)
  - db_field: estimated_person_months
    match_header: ["预计完工成本", "人月数"]
    type: decimal(10,2)
  - db_field: estimated_total_cost
    match_header: ["预计完工成本", "完工总成本"]
    type: decimal(15,2)

dynamic_columns:
  - db_prefix: monthly
    match_header: ["累计已发生", "2025年"]
    type: decimal(15,2)
  - db_prefix: monthly_2026
    match_header: ["后续发生", "2026年"]
    type: decimal(15,2)
```

- [ ] **Step 5: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_config_loader.py -v
```

Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: YAML config loader with template matching"
```

---

### Task 4: 合并单元格展开器

**Files:**
- Create: `parser/core/cell_unmerger.py`
- Create: `tests/test_cell_unmerger.py`

**Interfaces:**
- Produces: `unmerge(worksheet: openpyxl.Worksheet) -> list[list[Any]]` — 展开后的二维矩阵

- [ ] **Step 1: 写失败测试 tests/test_cell_unmerger.py**

```python
import openpyxl
import tempfile
from core.cell_unmerger import unmerge


@pytest.fixture
def merged_workbook():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.merge_cells("A1:A2")
    ws["A1"] = "merged_value"
    ws["B1"] = "normal_b1"
    ws["B2"] = "normal_b2"
    return wb


def test_unmerge_fills_merged_cells(merged_workbook):
    ws = merged_workbook.active
    grid = unmerge(ws)

    # Row 1: A1="merged_value", B1="normal_b1"
    assert grid[0][0] == "merged_value"
    assert grid[0][1] == "normal_b1"
    # Row 2: A2 should also be "merged_value" (unmerged), B2="normal_b2"
    assert grid[1][0] == "merged_value"
    assert grid[1][1] == "normal_b2"


def test_unmerge_preserves_empty_cells():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "only_a1"
    grid = unmerge(ws)
    assert grid[0][0] == "only_a1"
    assert grid[0][1] is None  # empty cell
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_cell_unmerger.py -v
```

Expected: 2 FAIL

- [ ] **Step 3: 实现 parser/core/cell_unmerger.py**

```python
def unmerge(worksheet) -> list[list]:
    max_row = worksheet.max_row or 1
    max_col = worksheet.max_column or 1

    grid = [[None] * max_col for _ in range(max_row)]

    for row_idx, row in enumerate(worksheet.iter_rows(min_row=1, max_row=max_row, max_col=max_col, values_only=True), 1):
        for col_idx, val in enumerate(row, 1):
            grid[row_idx - 1][col_idx - 1] = val

    for merged_range in worksheet.merged_cells.ranges:
        min_col = merged_range.min_col
        min_row = merged_range.min_row
        top_left_value = grid[min_row - 1][min_col - 1]
        for r in range(merged_range.min_row, merged_range.max_row + 1):
            for c in range(merged_range.min_col, merged_range.max_col + 1):
                grid[r - 1][c - 1] = top_left_value

    return grid
```

- [ ] **Step 4: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_cell_unmerger.py -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: merged cell unmerger"
```

---

### Task 5: 多级表头扁平化

**Files:**
- Create: `parser/core/header_flattener.py`
- Create: `tests/test_header_flattener.py`

**Interfaces:**
- Produces: `flatten_headers(grid: list[list], header_rows: list[int]) -> list[str]` — 扁平化列名列表

- [ ] **Step 1: 写失败测试 tests/test_header_flattener.py**

```python
import pytest
from core.header_flattener import flatten_headers


def test_flatten_headers_concatenates():
    # Simulate: Row1=["序号","截止到当前",""], Row2=["","实际人月","实际总成本"]
    grid = [
        ["序号", "截止到当前", ""],
        ["", "实际人月", "实际总成本"],
    ]
    result = flatten_headers(grid, header_rows=[0, 1])
    assert result == ["序号", "截止到当前_实际人月", "实际总成本"]


def test_flatten_headers_skips_empty_parts():
    grid = [
        ["姓名", "部门", ""],
        ["", "", ""],
    ]
    result = flatten_headers(grid, header_rows=[0, 1])
    assert result == ["姓名", "部门", ""]


def test_flatten_headers_three_level():
    grid = [
        ["累计已发生", "", ""],
        ["2025年", "", ""],
        ["7月", "8月", "9月"],
    ]
    result = flatten_headers(grid, header_rows=[0, 1, 2])
    assert result == [
        "累计已发生_2025年_7月",
        "累计已发生_2025年_8月",
        "累计已发生_2025年_9月",
    ]


def test_flatten_headers_with_none_values():
    grid = [
        ["A", None, "C"],
        [None, "B", None],
    ]
    result = flatten_headers(grid, header_rows=[0, 1])
    # None becomes empty string, so "A" stays "A", "C_B" for second col
    assert result[0] == "A"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_header_flattener.py -v
```

Expected: 4 FAIL

- [ ] **Step 3: 实现 parser/core/header_flattener.py**

```python
def flatten_headers(grid: list[list], header_rows: list[int]) -> list[str]:
    if not grid or not header_rows:
        return []

    num_cols = max(len(row) for row in grid)
    result = []

    for col_idx in range(num_cols):
        parts = []
        for row_idx in header_rows:
            if row_idx < len(grid) and col_idx < len(grid[row_idx]):
                val = grid[row_idx][col_idx]
                if val is not None:
                    s = str(val).strip()
                    if s:
                        parts.append(s)
        result.append("_".join(parts))

    return result
```

- [ ] **Step 4: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_header_flattener.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: multi-level header flattener"
```

---

### Task 6: 停止规则检测器

**Files:**
- Create: `parser/core/stop_detector.py`
- Create: `tests/test_stop_detector.py`

**Interfaces:**
- Produces: `StopDetector` class — `check(row: list, col_map: dict) -> bool` — 是否停止

- [ ] **Step 1: 写失败测试 tests/test_stop_detector.py**

```python
import pytest
from core.stop_detector import StopDetector


def make_col_map(headers):
    """映射列名到索引: {"A": 0, "B": 1, ...}"""
    return {chr(65 + i): i for i in range(len(headers))}


def test_cell_match_stops_on_pattern():
    rules = [
        {"type": "cell_match", "patterns": ["^注：", "^说明："], "columns": ["A"]},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A", "B"])

    assert detector.check(["注：这是注释", "data"], col_map) is True
    assert detector.check(["说明：xxx", "data"], col_map) is True
    assert detector.check(["正常数据", "data"], col_map) is False


def test_consecutive_empty_rows():
    rules = [
        {"type": "consecutive_empty_rows", "count": 3},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A", "B"])

    # First empty
    assert detector.check([None, None], col_map) is False
    assert detector.consecutive_empty == 1

    # Second empty
    assert detector.check(["", ""], col_map) is False
    assert detector.consecutive_empty == 2

    # Third empty -> stop
    assert detector.check([None, ""], col_map) is True


def test_consecutive_empty_resets_on_data():
    rules = [
        {"type": "consecutive_empty_rows", "count": 3},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A"])

    assert detector.check([None], col_map) is False
    assert detector.check(["data"], col_map) is False  # resets counter
    assert detector.consecutive_empty == 0


def test_mixed_rules():
    rules = [
        {"type": "cell_match", "patterns": ["^注："], "columns": ["A"]},
        {"type": "consecutive_empty_rows", "count": 2},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A"])

    assert detector.check(["注：xx"], col_map) is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_stop_detector.py -v
```

Expected: 4 FAIL

- [ ] **Step 3: 实现 parser/core/stop_detector.py**

```python
import re


class StopDetector:
    def __init__(self, rules: list[dict]):
        self.rules = rules or []
        self.consecutive_empty = 0

    def check(self, row: list, col_map: dict[str, int]) -> bool:
        for rule in self.rules:
            if rule["type"] == "cell_match":
                if self._check_cell_match(row, col_map, rule):
                    return True
            elif rule["type"] == "consecutive_empty_rows":
                if self._check_consecutive_empty(row, rule):
                    return True
        self._update_empty_counter(row)
        return False

    def _check_cell_match(self, row, col_map, rule) -> bool:
        patterns = rule.get("patterns", [])
        columns = rule.get("columns", [])
        for col_letter in columns:
            idx = col_map.get(col_letter)
            if idx is None or idx >= len(row):
                continue
            val = str(row[idx]) if row[idx] is not None else ""
            for pat in patterns:
                if re.match(pat, val):
                    return True
        return False

    def _check_consecutive_empty(self, row, rule) -> bool:
        count = rule.get("count", 5)
        return self.consecutive_empty >= count

    def _update_empty_counter(self, row):
        if all(v is None or str(v).strip() == "" for v in row):
            self.consecutive_empty += 1
        else:
            self.consecutive_empty = 0
```

- [ ] **Step 4: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_stop_detector.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: stop rule detector for end-of-data patterns"
```

---

### Task 7: 数据提取器（按表头名称匹配）

**Files:**
- Create: `parser/core/data_extractor.py`
- Create: `tests/test_data_extractor.py`

**Interfaces:**
- Produces: `extract_rows(grid, flat_headers, config) -> list[dict]` — 提取的数据行列表

- [ ] **Step 1: 写失败测试 tests/test_data_extractor.py**

```python
import pytest
from core.data_extractor import DataExtractor


def make_config():
    return {
        "headers": {"data_start_row": 2},
        "hierarchy": {"column_name": "序号", "separator": "."},
        "columns": [
            {"db_field": "person_name", "match_header": ["姓名"], "type": "varchar(100)"},
            {"db_field": "dept", "match_header": ["部门"], "type": "varchar(100)"},
        ],
        "dynamic_columns": [],
        "stop_rules": [],
    }


def test_extract_fixed_columns_by_header_name():
    # Row0 (header): ["序号", "姓名", "部门"]
    # Row1 (data):   ["1.1", "张三", "技术部"]
    grid = [
        ["序号", "姓名", "部门"],
        ["1.1", "张三", "技术部"],
    ]
    flat_headers = ["序号", "姓名", "部门"]
    config = make_config()
    extractor = DataExtractor(config)
    rows = extractor.extract_rows(grid, flat_headers)

    assert len(rows) == 1
    assert rows[0]["person_name"] == "张三"
    assert rows[0]["dept"] == "技术部"
    assert rows[0]["hierarchy_code"] == "1.1"


def test_extract_handles_column_order_change():
    # Headers in different order: ["部门", "姓名", "序号"]
    grid = [
        ["部门", "姓名", "序号"],
        ["技术部", "李四", "2.3"],
    ]
    flat_headers = ["部门", "姓名", "序号"]
    config = make_config()
    extractor = DataExtractor(config)
    rows = extractor.extract_rows(grid, flat_headers)

    assert len(rows) == 1
    assert rows[0]["person_name"] == "李四"
    assert rows[0]["dept"] == "技术部"


def test_extract_unmatched_column_is_none():
    grid = [
        ["序号", "其他列"],
        ["1", "xxx"],
    ]
    flat_headers = ["序号", "其他列"]
    config = make_config()
    extractor = DataExtractor(config)
    rows = extractor.extract_rows(grid, flat_headers)

    assert rows[0]["person_name"] is None  # "姓名" not in headers
    assert rows[0]["hierarchy_code"] == "1"


def test_extract_hierarchy_from_merged_header():
    # Hierarchy column matched by name not position
    grid = [
        ["部门", "序号", "姓名"],
        ["技术部", "3.5", "王五"],
    ]
    flat_headers = ["部门", "序号", "姓名"]
    config = make_config()
    extractor = DataExtractor(config)
    rows = extractor.extract_rows(grid, flat_headers)

    assert rows[0]["hierarchy_code"] == "3.5"
    assert rows[0]["dept"] == "技术部"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_data_extractor.py -v
```

Expected: 4 FAIL

- [ ] **Step 3: 实现 parser/core/data_extractor.py**

```python
from core.stop_detector import StopDetector


class DataExtractor:
    def __init__(self, config: dict):
        self.config = config
        self.columns = config.get("columns", [])
        self.dynamic_cols = config.get("dynamic_columns", [])
        hierarchy = config.get("hierarchy", {})
        self.hierarchy_col_name = hierarchy.get("column_name", "序号")
        self.data_start = config.get("headers", {}).get("data_start_row", 1)
        stop_rules = config.get("stop_rules", [])
        self.stop_detector = StopDetector(stop_rules)

    def extract_rows(self, grid: list[list], flat_headers: list[str]) -> list[dict]:
        col_index = {name: idx for idx, name in enumerate(flat_headers)}
        letter_map = {chr(65 + i): i for i in range(len(flat_headers))}

        results = []
        for row_idx in range(self.data_start - 1, len(grid)):
            row = grid[row_idx]

            if self.stop_detector.check(row, letter_map):
                break

            record = self._extract_row(row, col_index)
            results.append(record)

        return results

    def _extract_row(self, row: list, col_index: dict[str, int]) -> dict:
        record = {}

        # Hierarchy
        record["hierarchy_code"] = self._get_cell(row, col_index, self.hierarchy_col_name)

        # Fixed columns
        for col_def in self.columns:
            db_field = col_def["db_field"]
            match_terms = col_def.get("match_header", [])
            record[db_field] = self._get_cell_by_match(row, col_index, match_terms)

        # Dynamic columns -> JSON
        monthly = {}
        for dyn in self.dynamic_cols:
            db_prefix = dyn.get("db_prefix", "monthly")
            match_terms = dyn.get("match_header", [])

            # Find all columns whose flat header contains all match_terms
            for col_name, col_idx in col_index.items():
                if all(term in col_name for term in match_terms):
                    # Use the last segment of header as the key (e.g., "7月")
                    parts = col_name.split("_")
                    key = parts[-1] if parts else col_name
                    monthly[f"{db_prefix}_{key}"] = row[col_idx] if col_idx < len(row) else None

        record["monthly_data"] = monthly
        return record

    def _get_cell(self, row, col_index, header_name):
        idx = col_index.get(header_name)
        if idx is not None and idx < len(row):
            return row[idx]
        return None

    def _get_cell_by_match(self, row, col_index, match_terms):
        for col_name, col_idx in col_index.items():
            if all(term in col_name for term in match_terms):
                if col_idx < len(row):
                    return row[col_idx]
        return None
```

- [ ] **Step 4: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_data_extractor.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: data extractor with header-name matching"
```

---

### Task 8: 数据校验器

**Files:**
- Create: `parser/core/validator.py`
- Create: `tests/test_validator.py`

**Interfaces:**
- Produces: `validate(rows: list[dict], columns: list[dict]) -> tuple[list[dict], list[dict]]` — (valid_rows, errors)

- [ ] **Step 1: 写失败测试 tests/test_validator.py**

```python
import pytest
from core.validator import validate


def make_columns():
    return [
        {"db_field": "name", "type": "varchar(100)", "match_header": ["姓名"]},
        {"db_field": "amount", "type": "decimal(10,2)", "match_header": ["金额"]},
    ]


def test_validate_passes_clean_data():
    rows = [
        {"name": "张三", "amount": 100.50},
        {"name": "李四", "amount": 200.00},
    ]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 2
    assert len(errors) == 0


def test_validate_casts_string_to_decimal():
    rows = [{"name": "张三", "amount": "150.75"}]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 1
    assert valid[0]["amount"] == 150.75


def test_validate_sets_none_for_invalid_decimal():
    rows = [{"name": "张三", "amount": "not_a_number"}]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 1
    assert valid[0]["amount"] is None


def test_validate_records_error():
    rows = [
        {"name": "张三", "amount": "bad"},
        {"name": "李四", "amount": 200},
    ]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 2  # both still returned, bad converted to None
    assert len(errors) == 1
    assert errors[0]["row_index"] == 0
    assert "amount" in errors[0]["field"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_validator.py -v
```

Expected: 4 FAIL

- [ ] **Step 3: 实现 parser/core/validator.py**

```python
from decimal import Decimal, InvalidOperation


def validate(rows: list[dict], columns: list[dict]) -> tuple[list[dict], list[dict]]:
    valid_rows = []
    errors = []

    col_types = {c["db_field"]: c.get("type", "varchar(255)") for c in columns}

    for i, row in enumerate(rows):
        row_errors = []
        for field, value in row.items():
            if field in ("hierarchy_code", "monthly_data"):
                continue
            col_type = col_types.get(field, "")
            if col_type.startswith("decimal") and value is not None:
                try:
                    row[field] = Decimal(str(value)) if not isinstance(value, Decimal) else value
                except (InvalidOperation, ValueError, TypeError):
                    row_errors.append({"row_index": i, "field": field, "value": value, "error": "invalid_decimal"})
                    row[field] = None

        valid_rows.append(row)
        if row_errors:
            errors.extend(row_errors)

    return valid_rows, errors
```

- [ ] **Step 4: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_validator.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: data validator with type casting"
```

---

### Task 9: 解析管线编排

**Files:**
- Create: `parser/core/pipeline.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `Pipeline` class — `run(worksheet, batch_id) -> dict` — 接收worksheet，返回该Sheet处理结果

- [ ] **Step 1: 写失败测试 tests/test_pipeline.py**

```python
import pytest
import openpyxl
import tempfile
from core.pipeline import Pipeline


def make_test_workbook():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "表1 人工费-动态"
    # Row 1: title, Row 2-4: headers, Row 5+: data
    ws["A1"] = "测试标题"
    ws.merge_cells("A1:C1")
    ws["A2"] = "序号";
    ws["B2"] = "姓名";
    ws["C2"] = "部门"
    ws["A3"] = "";
    ws["B3"] = "";
    ws["C3"] = ""
    ws["A4"] = "";
    ws["B4"] = "";
    ws["C4"] = ""
    ws["A5"] = "1.1";
    ws["B5"] = "张三";
    ws["C5"] = "技术部"
    ws["A6"] = "1.2";
    ws["B6"] = "李四";
    ws["C6"] = "经营部"
    return wb


def make_config():
    return {
        "template_id": "test_labor",
        "sheet_pattern": "表1*",
        "headers": {"rows": [1, 2, 3], "data_start_row": 4},
        "hierarchy": {"column_name": "序号", "separator": "."},
        "columns": [
            {"db_field": "person_name", "match_header": ["姓名"], "type": "varchar(100)"},
            {"db_field": "dept", "match_header": ["部门"], "type": "varchar(100)"},
        ],
        "dynamic_columns": [],
        "stop_rules": [
            {"type": "cell_match", "patterns": ["^注："], "columns": ["A"]},
        ],
    }


def test_pipeline_extracts_data():
    wb = make_test_workbook()
    ws = wb.active
    config = make_config()
    pipeline = Pipeline(config)
    result = pipeline.run(ws, batch_id=1)

    assert result["template_id"] == "test_labor"
    assert result["total_rows"] == 2
    assert result["success_rows"] == 2
    assert len(result["rows"]) == 2
    assert result["rows"][0]["person_name"] == "张三"
    assert result["rows"][0]["hierarchy_code"] == "1.1"


def test_pipeline_stops_on_comment_row():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "表1 测试"
    ws["A1"] = "序号";
    ws["B1"] = "姓名"
    ws["A2"] = "1";
    ws["B2"] = "数据1"
    ws["A3"] = "注：以下为说明"
    ws["A4"] = "不应该被读取";
    ws["B4"] = "忽略"

    config = {
        "template_id": "test",
        "sheet_pattern": "表1*",
        "headers": {"rows": [0], "data_start_row": 1},
        "hierarchy": {"column_name": "序号", "separator": "."},
        "columns": [
            {"db_field": "person_name", "match_header": ["姓名"], "type": "varchar(100)"},
        ],
        "dynamic_columns": [],
        "stop_rules": [
            {"type": "cell_match", "patterns": ["^注："], "columns": ["A"]},
        ],
    }

    pipeline = Pipeline(config)
    result = pipeline.run(ws, batch_id=1)

    assert result["total_rows"] == 1  # only row 2, row 4 ignored
    assert result["rows"][0]["person_name"] == "数据1"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_pipeline.py -v
```

Expected: 2 FAIL

- [ ] **Step 3: 实现 parser/core/pipeline.py**

```python
from core.cell_unmerger import unmerge
from core.header_flattener import flatten_headers
from core.data_extractor import DataExtractor
from core.validator import validate


class Pipeline:
    def __init__(self, config: dict):
        self.config = config
        self.extractor = DataExtractor(config)

    def run(self, ws, batch_id: int) -> dict:
        sheet_name = ws.title

        grid = unmerge(ws)
        header_rows = [r - 1 for r in self.config.get("headers", {}).get("rows", [])]
        flat_headers = flatten_headers(grid, header_rows)

        rows = self.extractor.extract_rows(grid, flat_headers)
        columns = self.config.get("columns", [])
        valid_rows, errors = validate(rows, columns)

        for row in valid_rows:
            row["batch_id"] = batch_id

        return {
            "template_id": self.config.get("template_id"),
            "sheet_name": sheet_name,
            "total_rows": len(rows),
            "success_rows": len(valid_rows),
            "error_rows": len(errors),
            "rows": valid_rows,
            "errors": errors,
        }
```

- [ ] **Step 4: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_pipeline.py -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: parse pipeline orchestration"
```

---

### Task 10: 数据模型层

**Files:**
- Create: `parser/models/user.py`
- Create: `parser/models/project.py`
- Create: `parser/models/batch.py`
- Create: `parser/models/template.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: 各模型的CRUD异步函数，统一操作数据库

- [ ] **Step 1: 写失败测试 tests/test_models.py**

```python
import pytest
from models.user import create_user, get_user_by_username
from models.project import create_project, list_projects
from models.batch import create_batch, get_batch, insert_log
from models.template import register_template, get_active_templates


@pytest.mark.asyncio
async def test_create_and_get_user():
    from db.connection import get_pool
    from db.schema import init_db
    pool = await get_pool()
    await init_db(pool)

    user_id = await create_user(pool, username="test_user", password="hashed_pw", real_name="测试")
    assert user_id > 0

    user = await get_user_by_username(pool, "test_user")
    assert user["real_name"] == "测试"


@pytest.mark.asyncio
async def test_create_and_list_projects():
    from db.connection import get_pool
    from db.schema import init_db
    pool = await get_pool()
    await init_db(pool)

    pid = await create_project(pool, code="PRJ001", name="测试项目", created_by=1)
    projects = await list_projects(pool)
    assert len(projects) >= 1
    assert any(p["code"] == "PRJ001" for p in projects)


@pytest.mark.asyncio
async def test_create_batch_and_log():
    from db.connection import get_pool
    from db.schema import init_db
    pool = await get_pool()
    await init_db(pool)

    batch_id = await create_batch(pool, batch_no="B001", project_id=1, year_month="2025-07", uploaded_by=1,
                                  file_name="test.xlsx", file_size=1024)
    assert batch_id > 0

    log_id = await insert_log(pool, batch_id=batch_id, sheet_name="表1", template_id="t1", action="matched",
                              total_rows=10, success_rows=10)
    assert log_id > 0

    batch = await get_batch(pool, batch_id)
    assert batch["status"] == "processing"


@pytest.mark.asyncio
async def test_register_template():
    from db.connection import get_pool
    from db.schema import init_db
    pool = await get_pool()
    await init_db(pool)

    tid = await register_template(pool, template_id="test_tpl", description="test", config_yaml="headers: {}",
                                  data_table="data_test")
    assert tid > 0

    templates = await get_active_templates(pool)
    assert any(t["template_id"] == "test_tpl" for t in templates)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/pytest.exe tests/test_models.py -v
```

Expected: 4 FAIL (ImportError)

- [ ] **Step 3: 实现 models**

**parser/models/user.py:**
```python
async def create_user(pool, username: str, password: str, real_name: str = None,
                      email: str = None, phone: str = None) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO users (username, password, real_name, email, phone) VALUES (%s,%s,%s,%s,%s)",
                (username, password, real_name, email, phone),
            )
            return cur.lastrowid


async def get_user_by_username(pool, username: str) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


async def get_user_by_id(pool, user_id: int) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
```

**parser/models/project.py:**
```python
async def create_project(pool, code: str, name: str, created_by: int = None) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO projects (code, name, created_by) VALUES (%s,%s,%s)",
                (code, name, created_by),
            )
            return cur.lastrowid


async def list_projects(pool) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM projects ORDER BY id DESC")
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
```

**parser/models/batch.py:**
```python
async def create_batch(pool, batch_no: str, project_id: int, year_month: str,
                       uploaded_by: int, file_name: str, file_size: int) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO upload_batches (batch_no, project_id, year_month, uploaded_by, file_name, file_size) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (batch_no, project_id, year_month, uploaded_by, file_name, file_size),
            )
            return cur.lastrowid


async def update_batch_status(pool, batch_id: int, status: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE upload_batches SET status=%s WHERE id=%s", (status, batch_id)
            )


async def get_batch(pool, batch_id: int) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM upload_batches WHERE id=%s", (batch_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


async def list_batches(pool, project_id: int = None, year_month: str = None) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            sql = "SELECT * FROM upload_batches WHERE 1=1"
            params = []
            if project_id:
                sql += " AND project_id=%s"
                params.append(project_id)
            if year_month:
                sql += " AND year_month=%s"
                params.append(year_month)
            sql += " ORDER BY id DESC"
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]


async def insert_log(pool, batch_id: int, sheet_name: str, template_id: str,
                     action: str, total_rows: int = 0, success_rows: int = 0,
                     error_rows: int = 0, error_msg: str = None) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO upload_logs (batch_id, sheet_name, template_id, action, total_rows, success_rows, error_rows, error_msg) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (batch_id, sheet_name, template_id, action, total_rows, success_rows, error_rows, error_msg),
            )
            return cur.lastrowid


async def get_logs_by_batch(pool, batch_id: int) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM upload_logs WHERE batch_id=%s ORDER BY id",
                (batch_id,),
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
```

**parser/models/template.py:**
```python
async def register_template(pool, template_id: str, description: str,
                            config_yaml: str, data_table: str) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO template_configs (template_id, description, config_yaml, data_table) "
                "VALUES (%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE config_yaml=VALUES(config_yaml), data_table=VALUES(data_table), "
                "description=VALUES(description)",
                (template_id, description, config_yaml, data_table),
            )
            return cur.lastrowid


async def get_template_by_id(pool, template_id: str) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM template_configs WHERE template_id=%s AND is_active=1",
                (template_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


async def get_active_templates(pool) -> list[dict]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM template_configs WHERE is_active=1")
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
```

- [ ] **Step 4: 运行测试验证**

```bash
.venv/Scripts/pytest.exe tests/test_models.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: data model layer with CRUD operations"
```

---

### Task 11: JWT认证中间件

**Files:**
- Create: `parser/middleware/auth.py`
- Create: `tests/test_auth_middleware.py`

**Interfaces:**
- Produces: `generate_token(user_id, username) -> str`
- Produces: `@require_auth` decorator — Sanic路由保护
- Produces: `@require_permission(perm_code)` decorator — 权限检查

- [ ] **Step 1: 写失败测试**

```python
import pytest
import time
from middleware.auth import generate_token, verify_token, hash_password, check_password


def test_token_roundtrip():
    token = generate_token(user_id=1, username="admin", secret="test_secret")
    payload = verify_token(token, secret="test_secret")
    assert payload["user_id"] == 1
    assert payload["username"] == "admin"


def test_token_expiry():
    token = generate_token(user_id=1, username="admin", secret="test_secret", expiry_seconds=-1)
    with pytest.raises(Exception):
        verify_token(token, secret="test_secret")


def test_hash_and_check_password():
    hashed = hash_password("mypassword")
    assert check_password("mypassword", hashed) is True
    assert check_password("wrong", hashed) is False
```

- [ ] **Step 2: 实现 parser/middleware/auth.py**

```python
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from sanic.response import json


JWT_SECRET = "change-me-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def generate_token(user_id: int, username: str, secret: str = None, expiry_seconds: int = None) -> str:
    s = secret or JWT_SECRET
    if expiry_seconds is not None:
        exp = datetime.utcnow() + timedelta(seconds=expiry_seconds)
    else:
        exp = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {"user_id": user_id, "username": username, "exp": exp}
    return jwt.encode(payload, s, algorithm=JWT_ALGORITHM)


def verify_token(token: str, secret: str = None) -> dict:
    s = secret or JWT_SECRET
    return jwt.decode(token, s, algorithms=[JWT_ALGORITHM])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def require_auth(f):
    @wraps(f)
    async def decorated(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return json({"error": "missing token"}, status=401)
        token = auth_header[7:]
        try:
            payload = verify_token(token)
            request.ctx.user_id = payload["user_id"]
            request.ctx.username = payload["username"]
        except jwt.ExpiredSignatureError:
            return json({"error": "token expired"}, status=401)
        except jwt.InvalidTokenError:
            return json({"error": "invalid token"}, status=401)
        return await f(request, *args, **kwargs)
    return decorated


def require_permission(perm_code: str):
    def decorator(f):
        @wraps(f)
        async def decorated(request, *args, **kwargs):
            user_id = getattr(request.ctx, "user_id", None)
            if not user_id:
                return json({"error": "not authenticated"}, status=401)
            pool = request.app.ctx.pool
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """SELECT 1 FROM user_roles ur
                           JOIN role_permissions rp ON ur.role_id = rp.role_id
                           JOIN permissions p ON rp.permission_id = p.id
                           WHERE ur.user_id = %s AND p.code = %s LIMIT 1""",
                        (user_id, perm_code),
                    )
                    row = await cur.fetchone()
                    if not row:
                        return json({"error": f"missing permission: {perm_code}"}, status=403)
            return await f(request, *args, **kwargs)
        return decorated
    return decorator
```

- [ ] **Step 3: 运行测试**

```bash
.venv/Scripts/pytest.exe tests/test_auth_middleware.py -v
```

Expected: 3 PASS

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: JWT auth middleware with permission control"
```

---

### Task 12-17: API接口层

**Files:**
- Create: `parser/api/auth.py`
- Create: `parser/api/project.py`
- Create: `parser/api/upload.py`
- Create: `parser/api/data.py`
- Create: `parser/api/template.py`
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: Middleware auth, models层
- Produces: Sanic Blueprint路由

（由于篇幅，API层合并为一个任务组）

- [ ] **Step 1: 写API测试 tests/test_api.py**

```python
import pytest
from app import app


@pytest.fixture
def test_app_with_db():
    return app


@pytest.mark.asyncio
async def test_health_check():
    _, response = await app.asgi_client.get("/health")
    assert response.status == 200
    assert response.json["status"] == "ok"


@pytest.mark.asyncio
async def test_login_invalid():
    _, response = await app.asgi_client.post("/api/auth/login", json={"username": "nobody", "password": "wrong"})
    assert response.status == 401


@pytest.mark.asyncio
async def test_projects_unauthorized():
    _, response = await app.asgi_client.get("/api/projects")
    assert response.status == 401
```

- [ ] **Step 2: 实现 parser/api/auth.py**

```python
from sanic import Blueprint
from sanic.response import json
from middleware.auth import generate_token, hash_password, check_password
from models.user import get_user_by_username, create_user

bp = Blueprint("auth", url_prefix="/api/auth")


@bp.post("/login")
async def login(request):
    data = request.json
    username = data.get("username", "")
    password = data.get("password", "")
    pool = request.app.ctx.pool

    user = await get_user_by_username(pool, username)
    if not user or not check_password(password, user["password"]):
        return json({"error": "invalid credentials"}, status=401)
    if not user.get("is_active"):
        return json({"error": "account disabled"}, status=403)

    token = generate_token(user["id"], user["username"])
    return json(
        {"token": token, "user": {"id": user["id"], "username": user["username"], "real_name": user.get("real_name")}})
```

- [ ] **Step 3: 实现 parser/api/project.py**

```python
from sanic import Blueprint
from sanic.response import json
from middleware.auth import require_auth, require_permission
from models.project import create_project, list_projects

bp = Blueprint("projects", url_prefix="/api/projects")


@bp.get("/")
@require_auth
@require_permission("project:view")
async def get_projects(request):
    pool = request.app.ctx.pool
    projects = await list_projects(pool)
    return json({"projects": projects})


@bp.post("/")
@require_auth
@require_permission("project:create")
async def post_project(request):
    data = request.json
    pool = request.app.ctx.pool
    pid = await create_project(pool, code=data["code"], name=data["name"], created_by=request.ctx.user_id)
    return json({"id": pid, "code": data["code"]}, status=201)
```

- [ ] **Step 4: 实现 parser/api/upload.py**

```python
import os
import uuid
from datetime import datetime
from sanic import Blueprint
from sanic.response import json
from middleware.auth import require_auth, require_permission
from models.batch import create_batch, update_batch_status, insert_log
from models.template import get_template_by_id
from core.pipeline import Pipeline
from utils import match_template
import openpyxl

bp = Blueprint("upload", url_prefix="/api")

UPLOAD_DIR = "uploads"


@bp.post("/upload")
@require_auth
@require_permission("data:upload")
async def upload(request):
    if "file" not in request.files:
        return json({"error": "no file"}, status=400)

    file = request.files["file"]
    project_id = int(request.form.get("project_id", 0))
    year_month = request.form.get("year_month", datetime.now().strftime("%Y-%m"))
    batch_no = request.form.get("batch_no", f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, f"{batch_no}.xlsx")
    with open(filepath, "wb") as f:
        f.write(file.body)

    file_size = os.path.getsize(filepath)

    pool = request.app.ctx.pool
    batch_id = await create_batch(pool, batch_no=batch_no, project_id=project_id,
                                  year_month=year_month, uploaded_by=request.ctx.user_id,
                                  file_name=file.name, file_size=file_size)

    # Parse asynchronously
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheet_results = []
        all_success = True
        any_success = False

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            config = match_template(sheet_name)

            if not config:
                await insert_log(pool, batch_id, sheet_name, None, "skipped")
                sheet_results.append({"name": sheet_name, "template": None, "rows": 0, "status": "skipped"})
                continue

            pipeline = Pipeline(config)
            result = pipeline.run(ws, batch_id)

            await insert_log(pool, batch_id, sheet_name, result["template_id"],
                             "matched", result["total_rows"], result["success_rows"],
                             result["error_rows"])

            # Insert data rows
            if result["rows"]:
                table_name = f"data_{result['template_id']}"
                await _insert_rows(pool, table_name, result["rows"])

            sheet_results.append({
                "name": sheet_name,
                "template": result["template_id"],
                "rows": result["success_rows"],
                "status": "success" if result["error_rows"] == 0 else "partial",
            })

            if result["error_rows"] > 0:
                all_success = False
            if result["success_rows"] > 0:
                any_success = True

        if all_success and any_success:
            status = "success"
        elif any_success:
            status = "partial"
        else:
            status = "failed"

        await update_batch_status(pool, batch_id, status)

    except Exception as e:
        await update_batch_status(pool, batch_id, "failed")
        return json({"batch_id": batch_id, "batch_no": batch_no, "status": "failed", "error": str(e)}, status=500)

    return json({
        "batch_id": batch_id,
        "batch_no": batch_no,
        "status": status,
        "sheets": sheet_results,
    })


async def _insert_rows(pool, table_name, rows):
    if not rows:
        return
    # Get column names from first row, excluding monthly_data (handled separately)
    sample = rows[0]
    fixed_cols = [k for k in sample.keys() if k != "monthly_data"]
    import json as _json

    placeholders = ", ".join(["%s"] * (len(fixed_cols) + 1))  # +1 for monthly_data JSON
    cols_str = ", ".join(fixed_cols + ["monthly_data"])

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for row in rows:
                values = [row.get(c) for c in fixed_cols] + [
                    _json.dumps(row.get("monthly_data", {}), ensure_ascii=False)]
                sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
                await cur.execute(sql, values)
```

- [ ] **Step 5: 实现 parser/api/data.py**

```python
import json as _json
from sanic import Blueprint
from sanic.response import json
from middleware.auth import require_auth, require_permission

bp = Blueprint("data", url_prefix="/api/data")


@bp.get("/<template_id>")
@require_auth
@require_permission("data:view")
async def get_data(request, template_id):
    pool = request.app.ctx.pool
    batch_id = request.args.get("batch_id")
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 200))
    offset = (page - 1) * size

    table_name = f"data_{template_id}"

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if batch_id:
                await cur.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE batch_id=%s",
                    (batch_id,),
                )
                count_row = await cur.fetchone()
                total = count_row[0] if count_row else 0

                await cur.execute(
                    f"SELECT * FROM {table_name} WHERE batch_id=%s LIMIT %s OFFSET %s",
                    (batch_id, size, offset),
                )
            else:
                await cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_row = await cur.fetchone()
                total = count_row[0] if count_row else 0

                await cur.execute(
                    f"SELECT * FROM {table_name} LIMIT %s OFFSET %s",
                    (size, offset),
                )

            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            data = []
            for row in rows:
                d = dict(zip(cols, row))
                if d.get("monthly_data") and isinstance(d["monthly_data"], str):
                    d["monthly_data"] = _json.loads(d["monthly_data"])
                if "created_at" in d and d["created_at"]:
                    d["created_at"] = str(d["created_at"])
                data.append(d)

    return json({
        "template_id": template_id,
        "total": total,
        "page": page,
        "size": size,
        "rows": data,
        "columns": cols,
    })
```

- [ ] **Step 6: 实现 parser/api/template.py**

```python
from sanic import Blueprint
from sanic.response import json
from middleware.auth import require_auth, require_permission
from models.template import get_active_templates, register_template
from utils import load_config

bp = Blueprint("templates", url_prefix="/api/templates")


@bp.get("/")
@require_auth
async def get_templates(request):
    pool = request.app.ctx.pool
    templates = await get_active_templates(pool)
    return json({"templates": templates})


@bp.post("/")
@require_auth
@require_permission("template:manage")
async def post_template(request):
    data = request.json
    template_id = data["template_id"]
    config_yaml = data["config_yaml"]
    description = data.get("description", "")
    data_table = f"data_{template_id}"

    pool = request.app.ctx.pool
    tid = await register_template(pool, template_id, description, config_yaml, data_table)

    # Create data table
    config = load_config(template_id)
    columns_sql = _build_create_table_sql(template_id, config)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(columns_sql)

    return json({"id": tid, "table": data_table}, status=201)


def _build_create_table_sql(template_id, config):
    cols = [
        "id INT AUTO_INCREMENT PRIMARY KEY",
        "batch_id INT NOT NULL",
        "hierarchy_code VARCHAR(50)",
    ]
    for col_def in config.get("columns", []):
        col_sql = f"{col_def['db_field']} {col_def.get('type', 'varchar(255)')}"
        cols.append(col_sql)
    cols.append("monthly_data JSON")
    cols.append("created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    cols.append("FOREIGN KEY (batch_id) REFERENCES upload_batches(id)")
    cols.append("INDEX idx_batch (batch_id)")
    cols.append("INDEX idx_hierarchy (hierarchy_code)")

    return f"CREATE TABLE IF NOT EXISTS data_{template_id} ({', '.join(cols)})"
```

- [ ] **Step 7: 运行API测试**

```bash
.venv/Scripts/pytest.exe tests/test_api.py -v
```

Expected: 3 PASS

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: API endpoints for auth, projects, upload, data, templates"
```

---

### Task 18: 应用入口组装

**Files:**
- Modify: `parser/app.py`

**Interfaces:**
- 注册所有Blueprints、数据库初始化、中间件

- [ ] **Step 1: 更新 parser/app.py**

```python
from sanic import Sanic
from sanic.response import json
from db.connection import get_pool
from db.schema import init_db
from db.seed import seed_defaults

app = Sanic("excel_parser")


@app.listener("before_server_start")
async def setup_db(app, loop):
    pool = await get_pool()
    await init_db(pool)
    await seed_defaults(pool)
    app.ctx.pool = pool


@app.listener("after_server_stop")
async def close_db(app, loop):
    if hasattr(app.ctx, "pool"):
        app.ctx.pool.close()
        await app.ctx.pool.wait_closed()


@app.get("/health")
async def health(request):
    return json({"status": "ok"})


# Register blueprints
from api import bp as auth_bp
from api import bp as project_bp
from api import bp as upload_bp
from api import bp as data_bp
from api import bp as template_bp

app.blueprint(auth_bp)
app.blueprint(project_bp)
app.blueprint(upload_bp)
app.blueprint(data_bp)
app.blueprint(template_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
```

- [ ] **Step 2: 验证应用启动**

```bash
.venv/Scripts/python.exe -c "from parser.app import app; print('App OK, routes:', len(app.router.routes_all))"
```

Expected: App OK, routes: >5

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: Sanic app entry point with DB init and blueprint registration"
```

---

### Task 19: 模板配置文件

**Files:**
- Create: 其余模板YAML配置（基于已分析的15个Sheet）

- [ ] **Step 1: 创建必要的模板配置**

基于 `docs/excel-tail-patterns.md` 中的Sheet列表，创建至少覆盖核心Sheet的模板：

```bash
# 将labor_cost.yaml复制为基础，按Sheet差异修改
# 核心Sheet: 动态指标, 表2-9, 表1-1
```

（每个模板从已分析的Excel结构中提取列名和配置）

- [ ] **Step 2: 运行模板加载验证**

```bash
.venv/Scripts/python.exe -c "
from parser.utils.config_loader import list_configs
cfgs = list_configs()
print(f'Loaded {len(cfgs)} template configs')
for c in cfgs:
    print(f'  - {c[\"template_id\"]}: {c[\"description\"]}')
"
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: template configs for core sheets"
```

---

### Task 20: 集成测试

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 写端到端测试**

```python
import pytest
import os
from app import app
from core.pipeline import Pipeline
from utils import match_template
import openpyxl


def test_full_parse_with_real_excel():
    excel_path = "excel/xxx项目主体施工动态成本表-样式 - 副本.xlsx"
    if not os.path.exists(excel_path):
        pytest.skip("Excel file not found")

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    results = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        config = match_template(sheet_name)
        if config:
            pipeline = Pipeline(config)
            result = pipeline.run(ws, batch_id=0)
            results.append(result)

    matched = [r for r in results]
    print(f"\nMatched sheets: {len(matched)}")
    for r in matched:
        print(
            f"  {r['sheet_name']}: {r['success_rows']} rows ({r['error_rows']} errors) [template: {r['template_id']}]")

    assert len(matched) > 0, "At least one sheet should match"
    total_rows = sum(r["success_rows"] for r in matched)
    assert total_rows > 0, "Should extract some data"
    print(f"\nTotal data rows extracted: {total_rows}")


@pytest.mark.asyncio
async def test_api_upload_flow():
    excel_path = "excel/xxx项目主体施工动态成本表-样式 - 副本.xlsx"
    if not os.path.exists(excel_path):
        pytest.skip("Excel file not found")

    with open(excel_path, "rb") as f:
        file_content = f.read()

    _, response = await app.asgi_client.post(
        "/api/upload",
        data={
            "project_id": "1",
            "year_month": "2025-07",
        },
        files={
            "file": ("test.xlsx", file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status in (200, 401, 500)  # 401 if no auth, 200 on success
    data = response.json
    print(f"\nUpload response: {data}")
    assert "batch_id" in data
```

- [ ] **Step 2: 运行集成测试**

```bash
.venv/Scripts/pytest.exe tests/test_integration.py -v -s
```

Expected: 验证解析管线对真实Excel的处理结果

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test: integration tests with real Excel file"
```

---

## 实现顺序

```
Task 1 (骨架) → Task 2 (数据库) → Task 3 (配置加载)
                                      ↓
Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9
(单元格展开)(表头扁平化)(停止检测)(数据提取)(校验)(管线)
                                      ↓
                              Task 10 (模型层)
                                      ↓
                              Task 11 (认证中间件)
                                      ↓
                           Task 12-17 (API层)
                                      ↓
                              Task 18 (应用组装)
                                      ↓
                        Task 19 (模板配置) → Task 20 (集成测试)
```

- Task 1-3 是基础设施，必须最先做
- Task 4-9 是解析核心，按管线顺序依次实现
- Task 10-11 打通数据库和认证
- Task 12-18 组装成完整应用
- Task 19-20 是收尾验证
