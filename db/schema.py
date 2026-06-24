async def init_db(pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DROP TABLE IF EXISTS upload_logs, upload_batches, template_configs")

            await cur.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) NOT NULL, UNIQUE(username), password VARCHAR(255) NOT NULL, real_name VARCHAR(100), email VARCHAR(200), phone VARCHAR(20), is_active TINYINT(1) DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

            await cur.execute("CREATE TABLE IF NOT EXISTS roles (id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(50) NOT NULL, UNIQUE(code), name VARCHAR(100) NOT NULL, description VARCHAR(500), created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

            await cur.execute("CREATE TABLE IF NOT EXISTS permissions (id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(100) NOT NULL, UNIQUE(code), name VARCHAR(200) NOT NULL, description VARCHAR(500))")

            await cur.execute("CREATE TABLE IF NOT EXISTS user_roles (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, role_id INT NOT NULL, UNIQUE(user_id, role_id))")

            await cur.execute("CREATE TABLE IF NOT EXISTS role_permissions (id INT AUTO_INCREMENT PRIMARY KEY, role_id INT NOT NULL, permission_id INT NOT NULL, UNIQUE(role_id, permission_id))")

            await cur.execute("CREATE TABLE IF NOT EXISTS projects (id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(50) NOT NULL, UNIQUE(code), name VARCHAR(200) NOT NULL, created_by INT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

            await cur.execute("CREATE TABLE IF NOT EXISTS upload_batches (id INT AUTO_INCREMENT PRIMARY KEY, batch_no VARCHAR(50) NOT NULL, UNIQUE(batch_no), project_id INT NOT NULL, ym VARCHAR(7) NOT NULL, uploaded_by INT, file_name VARCHAR(500), file_size BIGINT, status VARCHAR(20) DEFAULT 'processing', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

            await cur.execute("CREATE TABLE IF NOT EXISTS upload_logs (id INT AUTO_INCREMENT PRIMARY KEY, batch_id INT NOT NULL, sheet_name VARCHAR(200), template_id VARCHAR(100), action VARCHAR(20) DEFAULT 'matched', total_rows INT DEFAULT 0, success_rows INT DEFAULT 0, error_rows INT DEFAULT 0, error_msg TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, INDEX(batch_id))")

            await cur.execute("CREATE TABLE IF NOT EXISTS template_configs (id INT AUTO_INCREMENT PRIMARY KEY, template_id VARCHAR(100) NOT NULL, UNIQUE(template_id), description VARCHAR(500), config_yaml TEXT NOT NULL, data_table VARCHAR(100) NOT NULL, is_active TINYINT(1) DEFAULT 1, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)")
