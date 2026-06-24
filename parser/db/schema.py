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
