"""DDL helpers — pure aiomysql (CREATE TABLE statements)."""

import re

from db.connection import execute

_VALID_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_VALID_TEMPLATE_ID = re.compile(r"^[a-zA-Z0-9_]+$")

FIXED_TABLES = [
    """\
    CREATE TABLE IF NOT EXISTS users (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        username    VARCHAR(50)  NOT NULL UNIQUE,
        password    VARCHAR(255) NOT NULL,
        real_name   VARCHAR(100),
        email       VARCHAR(200),
        phone       VARCHAR(20),
        is_active   BOOLEAN DEFAULT TRUE,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    """\
    CREATE TABLE IF NOT EXISTS roles (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        code        VARCHAR(50)  NOT NULL UNIQUE,
        name        VARCHAR(100) NOT NULL,
        description VARCHAR(500),
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    """\
    CREATE TABLE IF NOT EXISTS permissions (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        code        VARCHAR(100) NOT NULL UNIQUE,
        name        VARCHAR(200) NOT NULL,
        description VARCHAR(500)
    )""",
    """\
    CREATE TABLE IF NOT EXISTS user_roles (
        id      INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        role_id INT NOT NULL,
        UNIQUE (user_id, role_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (role_id) REFERENCES roles(id)
    )""",
    """\
    CREATE TABLE IF NOT EXISTS role_permissions (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        role_id       INT NOT NULL,
        permission_id INT NOT NULL,
        UNIQUE (role_id, permission_id),
        FOREIGN KEY (role_id)       REFERENCES roles(id),
        FOREIGN KEY (permission_id) REFERENCES permissions(id)
    )""",
    """\
    CREATE TABLE IF NOT EXISTS projects (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        code       VARCHAR(50)  NOT NULL UNIQUE,
        name       VARCHAR(200) NOT NULL,
        created_by INT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )""",
    """\
    CREATE TABLE IF NOT EXISTS upload_batches (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        batch_no    VARCHAR(50) NOT NULL UNIQUE,
        project_id  INT         NOT NULL,
        ym          VARCHAR(7)  NOT NULL,
        uploaded_by INT,
        file_name   VARCHAR(500),
        file_size   BIGINT,
        status      VARCHAR(20) DEFAULT 'processing',
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id)  REFERENCES projects(id),
        FOREIGN KEY (uploaded_by) REFERENCES users(id)
    )""",
    """\
    CREATE TABLE IF NOT EXISTS upload_logs (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        batch_id     INT NOT NULL,
        sheet_name   VARCHAR(200),
        template_id  VARCHAR(100),
        action       VARCHAR(20) DEFAULT 'matched',
        total_rows   INT DEFAULT 0,
        success_rows INT DEFAULT 0,
        error_rows   INT DEFAULT 0,
        error_msg    TEXT,
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_batch (batch_id),
        FOREIGN KEY (batch_id) REFERENCES upload_batches(id)
    )""",
    """\
    CREATE TABLE IF NOT EXISTS template_configs (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        template_id VARCHAR(100) NOT NULL UNIQUE,
        description VARCHAR(500),
        config_yaml TEXT         NOT NULL,
        data_table  VARCHAR(100) NOT NULL,
        is_active   BOOLEAN DEFAULT TRUE,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )""",
]


async def init_db():
    """Create all fixed application tables if they don't exist."""
    for ddl in FIXED_TABLES:
        await execute(ddl)


async def create_data_table(template_id: str, columns: list):
    """Create a template data table with validated identifiers."""
    if not _VALID_TEMPLATE_ID.match(template_id):
        raise ValueError(f"invalid template_id: {template_id}")

    col_defs = [
        "id INT AUTO_INCREMENT PRIMARY KEY",
        "batch_id INT NOT NULL",
        "hierarchy_code VARCHAR(50)",
    ]
    for col in columns:
        db_field = col["db_field"]
        if not _VALID_IDENT.match(db_field):
            raise ValueError(f"invalid column name: {db_field}")
        col_defs.append(f"`{db_field}` {col.get('type', 'varchar(255)')}")

    col_defs += [
        "monthly_data JSON",
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "FOREIGN KEY (batch_id) REFERENCES upload_batches(id)",
        "INDEX idx_batch (batch_id)",
        "INDEX idx_hierarchy (hierarchy_code)",
    ]

    sql = f"CREATE TABLE IF NOT EXISTS data_{template_id} (\n  " + ",\n  ".join(col_defs) + "\n)"
    await execute(sql)
