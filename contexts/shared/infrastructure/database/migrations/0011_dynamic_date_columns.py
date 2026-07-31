# ruff: noqa: I001
# noinspection PyPackageRequirements
from tortoise import migrations

# noinspection PyPackageRequirements
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0010_upload_batch_index_notification_cleanup")]
    initial = False
    operations = [
        # 源表中这两列是纯日期（计划退场时间 31/31 为日期、计划核销时间 1/1 为日期），
        # 此前按 varchar 存储为 'YYYY-MM-DD HH:MM:SS' 字符串；改为 date 类型。
        # 注意：planned_start（计划使用时间）含 '按需使用' 等文本值，是混合列，
        # 保持 varchar 不动。tortoise 1.1.7 的 AlterField 不支持类型变更，用 RunSQL。
        ops.RunSQL(
            "ALTER TABLE `data_machinery` MODIFY COLUMN `planned_end` DATE NULL",
            reverse_sql="ALTER TABLE `data_machinery` MODIFY COLUMN `planned_end` VARCHAR(50) NULL",
        ),
        ops.RunSQL(
            "ALTER TABLE `data_budget_lease` MODIFY COLUMN `planned_writeoff_date` DATE NULL",
            reverse_sql="ALTER TABLE `data_budget_lease` MODIFY COLUMN `planned_writeoff_date` VARCHAR(50) NULL",
        ),
    ]
