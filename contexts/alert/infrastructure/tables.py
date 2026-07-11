from tortoise import fields
from tortoise.models import Model


class AlertRuleModel(Model):
    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=64, unique=True)
    name = fields.CharField(max_length=100)
    metric = fields.CharField(max_length=64)
    operator = fields.CharField(max_length=8)
    threshold = fields.DecimalField(max_digits=18, decimal_places=4)
    level = fields.CharField(max_length=16, default="warning")
    enabled = fields.BooleanField(default=True)
    consecutive_triggers = fields.IntField(default=1)
    auto_resolve = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "alert_rules"


class AlertModel(Model):
    id = fields.IntField(primary_key=True)
    project_id = fields.IntField(db_index=True)
    rule_code = fields.CharField(max_length=64, db_index=True)
    alert_type = fields.CharField(max_length=64)
    level = fields.CharField(max_length=16, db_index=True)
    title = fields.CharField(max_length=200)
    message = fields.TextField()
    metric_value = fields.DecimalField(max_digits=18, decimal_places=4)
    threshold_value = fields.DecimalField(max_digits=18, decimal_places=4)
    ym = fields.CharField(max_length=7, null=True, db_index=True)
    status = fields.CharField(max_length=20, default="active", db_index=True)
    fingerprint = fields.CharField(max_length=160, db_index=True)
    trigger_count = fields.IntField(default=1)
    first_triggered_at = fields.DatetimeField()
    last_triggered_at = fields.DatetimeField()
    acknowledged_by = fields.IntField(null=True)
    acknowledged_at = fields.DatetimeField(null=True)
    resolved_by = fields.IntField(null=True)
    resolved_at = fields.DatetimeField(null=True)
    resolution_note = fields.TextField(null=True)
    ignored_until = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "alerts"
        indexes = (("project_id", "status"), ("fingerprint", "status"))


class AlertRuleStateModel(Model):
    id = fields.IntField(primary_key=True)
    project_id = fields.IntField(db_index=True)
    rule_code = fields.CharField(max_length=64)
    scope = fields.CharField(max_length=16)
    consecutive_count = fields.IntField(default=0)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "alert_rule_states"
        unique_together = (("project_id", "rule_code", "scope"),)


class AlertEventModel(Model):
    id = fields.IntField(primary_key=True)
    alert_id = fields.IntField(db_index=True)
    event_type = fields.CharField(max_length=32)
    actor_id = fields.IntField(null=True)
    note = fields.TextField(null=True)
    snapshot = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "alert_events"


class AlertOutboxModel(Model):
    id = fields.IntField(primary_key=True)
    event_type = fields.CharField(max_length=64)
    aggregate_id = fields.IntField(db_index=True)
    project_id = fields.IntField(db_index=True)
    payload = fields.JSONField()
    status = fields.CharField(max_length=16, default="pending", db_index=True)
    retry_count = fields.IntField(default=0)
    next_retry_at = fields.DatetimeField(null=True)
    sent_at = fields.DatetimeField(null=True)
    last_error = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "alert_outbox"
