import pytest
from parser.db.connection import get_pool
from parser.db.schema import init_db
from parser.db.seed import seed_defaults


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
