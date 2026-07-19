from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise import fields
from tortoise.indexes import Index


class Migration(migrations.Migration):
    """Replace obsolete template data tables with budget adjustment and
    settlement output tables.

    Creates the five tables backing the new 表10/表10.1/表10.2/表10.3/表11
    sheets of the 电源A workbook and drops the four tables whose sheets were
    retired (表1-1/表9-1/表9-2/表9-3). data_gross_profit is kept on purpose:
    analytics and alert still read it.
    """

    operations = [
        ops.CreateModel(
            name='DataBudgetAdjustmentSummary',
            fields=[
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('batch_id', fields.IntField()),
                ('hierarchy_code', fields.CharField(null=True, max_length=50)),
                ('item_name', fields.CharField(null=True, max_length=300)),
                ('indicator_ex_tax', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('indicator_tax_rate', fields.DecimalField(null=True, max_digits=15, decimal_places=10)),
                ('indicator_tax', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('indicator_with_tax', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('adjustment_1', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('adjustment_2', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('adjustment_n', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('adjustment_total', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('current_budget', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('remark', fields.TextField(null=True)),
                ('monthly_data', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'data_budget_adjustment_summary', 'app': 'models', 'indexes': [Index(fields=['batch_id']), Index(fields=['hierarchy_code'])], 'pk_attr': 'id'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='DataBudgetAdjustmentInternal',
            fields=[
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('batch_id', fields.IntField()),
                ('hierarchy_code', fields.CharField(null=True, max_length=50)),
                ('adjustment_count', fields.CharField(null=True, max_length=50)),
                ('request_no', fields.CharField(null=True, max_length=100)),
                ('request_name', fields.CharField(null=True, max_length=300)),
                ('project_name', fields.CharField(null=True, max_length=300)),
                ('bid_price', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('budget_before', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('adjustment_amount', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('budget_after', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('remark', fields.TextField(null=True)),
                ('monthly_data', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'data_budget_adjustment_internal', 'app': 'models', 'indexes': [Index(fields=['batch_id']), Index(fields=['hierarchy_code'])], 'pk_attr': 'id'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='DataBudgetIncrease',
            fields=[
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('batch_id', fields.IntField()),
                ('hierarchy_code', fields.CharField(null=True, max_length=50)),
                ('increase_count', fields.CharField(null=True, max_length=50)),
                ('upstream_amount', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('upstream_doc_no', fields.CharField(null=True, max_length=100)),
                ('upstream_doc_name', fields.CharField(null=True, max_length=300)),
                ('report_no', fields.CharField(null=True, max_length=100)),
                ('increase_project', fields.CharField(null=True, max_length=300)),
                ('eas_increase', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('writeoff_amount', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('remaining_quota', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('remark', fields.TextField(null=True)),
                ('monthly_data', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'data_budget_increase', 'app': 'models', 'indexes': [Index(fields=['batch_id']), Index(fields=['hierarchy_code'])], 'pk_attr': 'id'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='DataBudgetLease',
            fields=[
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('batch_id', fields.IntField()),
                ('hierarchy_code', fields.CharField(null=True, max_length=50)),
                ('request_name', fields.CharField(null=True, max_length=300)),
                ('lease_date', fields.CharField(null=True, max_length=50)),
                ('budget_subject', fields.CharField(null=True, max_length=300)),
                ('budget_before', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('lease_bid', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('lease_active', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('lease_passive', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('lease_total', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('budget_after', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('writeoff_bid', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('writeoff_active', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('writeoff_passive', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('writeoff_total', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('lease_status', fields.TextField(null=True)),
                ('remaining_bid', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('remaining_active', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('remaining_passive', fields.DecimalField(null=True, max_digits=15, decimal_places=2)),
                ('planned_writeoff_date', fields.CharField(null=True, max_length=50)),
                ('actual_writeoff_date', fields.CharField(null=True, max_length=50)),
                ('monthly_data', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'data_budget_lease', 'app': 'models', 'indexes': [Index(fields=['batch_id']), Index(fields=['hierarchy_code'])], 'pk_attr': 'id'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='DataSettlementOutput',
            fields=[
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('batch_id', fields.IntField()),
                ('hierarchy_code', fields.CharField(null=True, max_length=50)),
                ('indicator_name', fields.CharField(null=True, max_length=200)),
                ('cumulative_value', fields.DecimalField(null=True, max_digits=20, decimal_places=6)),
                ('indicator_desc', fields.TextField(null=True)),
                ('data_source', fields.CharField(null=True, max_length=300)),
                ('monthly_data', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'data_settlement_output', 'app': 'models', 'indexes': [Index(fields=['batch_id']), Index(fields=['hierarchy_code'])], 'pk_attr': 'id'},
            bases=['Model'],
        ),
        ops.DeleteModel(name='DataLaborCostSummary'),
        ops.DeleteModel(name='DataConcreteLedger'),
        ops.DeleteModel(name='DataRebarLedger'),
        ops.DeleteModel(name='DataInstallationMaterial'),
    ]
