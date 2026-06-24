from sqlalchemy import text
from parser.db.models import Base
from parser.db.connection import engine


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_data_table(template_id: str, columns: list):
    """动态创建模板数据表"""
    col_defs = [
        "id INT AUTO_INCREMENT PRIMARY KEY",
        "batch_id INT NOT NULL",
        "hierarchy_code VARCHAR(50)",
    ]
    for col in columns:
        col_defs.append(f"`{col['db_field']}` {col.get('type', 'varchar(255)')}")
    col_defs.append("monthly_data JSON")
    col_defs.append("created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    col_defs.append("INDEX idx_batch (batch_id)")
    col_defs.append("INDEX idx_hierarchy (hierarchy_code)")

    sql = f"CREATE TABLE IF NOT EXISTS data_{template_id} ({', '.join(col_defs)})"
    async with engine.begin() as conn:
        await conn.execute(text(sql))
