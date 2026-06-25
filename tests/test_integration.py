import os
import pytest
import openpyxl

from core.pipeline import Pipeline
from utils.config_loader import list_configs, match_template


@pytest.fixture(scope="function")
def _config():
    """加载配置，不可用时跳过"""
    try:
        from db.config import load_config
        return load_config()
    except FileNotFoundError:
        pytest.skip("Config file not found — integration tests require db setup")


@pytest.fixture(scope="function")
def _engine(_config):
    """创建异步引擎，不可用时跳过"""
    try:
        from db.connection import create_engine
        return create_engine(_config)
    except Exception:
        pytest.skip("Cannot connect to database")


@pytest.mark.asyncio
async def test_db_init(_config, _engine):
    """固定表可正常创建"""
    from db.schema import init_db
    from sqlalchemy import text

    await init_db(_engine)
    async with _engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :db"),
            {"db": _config.DB_NAME},
        )
        count = result.scalar()
        assert count > 0


@pytest.mark.asyncio
async def test_data_tables_created(_engine):
    """所有模板数据表可正常创建"""
    from db.schema import create_data_table
    from sqlalchemy import text

    configs = list_configs()
    for cfg in configs:
        await create_data_table(_engine, cfg["template_id"], cfg.get("columns", []))

    async with _engine.connect() as conn:
        for cfg in configs:
            result = await conn.execute(
                text(f"SHOW TABLES LIKE 'data_{cfg['template_id']}'")
            )
            assert result.fetchone() is not None, f"Table data_{cfg['template_id']} not found"


def test_full_parse_with_real_excel():
    """15 张 sheet 全量解析测试"""
    excel_path = "excel/xxx项目主体施工动态成本表-样式 - 副本.xlsx"
    if not os.path.exists(excel_path):
        pytest.skip("Excel file not found")

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    results = []
    skipped = 0

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        config = match_template(sheet_name)
        if config:
            pipeline = Pipeline(config)
            result = pipeline.run(ws, batch_id=0)
            results.append(result)
            print(f"\n  {result['sheet_name']}: {result['success_rows']} rows "
                  f"({result['error_rows']} errors) [template: {result['template_id']}]")
        else:
            skipped += 1
            print(f"\n  {sheet_name}: SKIPPED")

    matched = len(results)
    total_rows = sum(r["success_rows"] for r in results)
    print(f"\nMatched: {matched}, Skipped: {skipped}, Total rows: {total_rows}")

    assert matched > 0, "At least one sheet should match"
    assert total_rows > 0, "Should extract some data"
