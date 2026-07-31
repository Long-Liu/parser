# ruff: noqa: I001
# noinspection PyPackageRequirements
from tortoise import migrations

# noinspection PyPackageRequirements
from tortoise.indexes import Index

# noinspection PyPackageRequirements
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0009_beijing_time")]
    initial = False
    operations = [
        # upload_batches 是全库最热的过滤/排序表：几乎每个报表接口都按
        # project_id(+ym+status) 过滤并按 (project_id, -ym, -id) 排序。
        # 此前仅有 batch_no unique 约束，批次数增长后每次报表请求都全表扫描。
        ops.AddIndex(
            "UploadBatch",
            Index(
                fields=["project_id", "ym", "status"],
                name="idx_upload_batches_project_ym_status",
            ),
        ),
        # Notification.is_read 列与 (user_id, is_read) 索引从未被写入——
        # 已读状态全部走 notification_reads 表。移除死列与死索引，
        # 保留 user_id 单列索引支撑 notifications 查询。
        # 注意：0002 创建索引时未烘焙 name（状态中 name=None），RemoveIndex
        # 必须按 fields 匹配（按名匹配会抛 IncompatibleStateError）；
        # DROP 时按 tortoise 命名规则生成 idx_notificatio_user_id_46dd57。
        ops.RemoveIndex("Notification", fields=["user_id", "is_read"]),
        ops.RemoveField("Notification", "is_read"),
        ops.AddIndex(
            "Notification",
            Index(fields=["user_id"], name="idx_notifications_user_id"),
        ),
    ]
