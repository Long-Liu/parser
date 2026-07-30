from tortoise import migrations
from tortoise.migrations import operations as ops


async def _shift_datetime_columns(apps, schema_editor, hours: int) -> None:
    rows = await schema_editor.client.execute_query_dict(
        """
        SELECT TABLE_NAME, COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND DATA_TYPE = 'datetime'
          AND TABLE_NAME <> 'tortoise_migrations'
        """
    )
    operator = "+" if hours >= 0 else "-"
    interval = abs(hours)
    for row in rows:
        table = row["TABLE_NAME"].replace("`", "``")
        column = row["COLUMN_NAME"].replace("`", "``")
        await schema_editor.client.execute_query(
            f"UPDATE `{table}` SET `{column}` = `{column}` {operator} INTERVAL {interval} HOUR "
            f"WHERE `{column}` IS NOT NULL"
        )


async def forward(apps, schema_editor) -> None:
    await _shift_datetime_columns(apps, schema_editor, 8)


async def backward(apps, schema_editor) -> None:
    await _shift_datetime_columns(apps, schema_editor, -8)


class Migration(migrations.Migration):
    """Convert existing UTC DATETIME values to Beijing local time."""

    operations = [ops.RunPython(forward, backward)]
