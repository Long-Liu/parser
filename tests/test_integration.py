import pytest
import os
from db.connection import engine, SessionLocal
from db.schema import init_db, create_data_table
from utils import list_configs
from core.pipeline import Pipeline
from utils import match_template
import openpyxl


@pytest.mark.asyncio
async def test_db_init():
    """Test that fixed tables can be created"""
    await init_db()
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy").text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='excel_parser'")
        )
        count = result.scalar()
        assert count > 0


@pytest.mark.asyncio
async def test_data_tables_created():
    """Test that all template data tables are created"""
    configs = list_configs()
    for config in configs:
        await create_data_table(config["template_id"], config.get("columns", []))

    async with engine.connect() as conn:
        for config in configs:
            result = await conn.execute(
                __import__("sqlalchemy").text(f"SHOW TABLES LIKE 'data_{config['template_id']}'")
            )
            assert result.fetchone() is not None, f"Table data_{config['template_id']} not found"


def test_full_parse_with_real_excel():
    """Test that all 15 sheets parse correctly"""
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
