"""Tortoise models for parsed template data tables."""

from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class DataSocialInsurance(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    person_name = fields.CharField(max_length=100, null=True)
    department = fields.CharField(max_length=100, null=True)
    position = fields.CharField(max_length=100, null=True)
    contract_relation = fields.CharField(max_length=100, null=True)
    actual_person_months = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    actual_total_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    subsequent_person_months = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    subsequent_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_person_months = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    estimated_total_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_social_insurance"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataSiteManagement(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    fee_name = fields.CharField(max_length=200, null=True)
    unit = fields.CharField(max_length=50, null=True)
    quantity = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    unit_price_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    unit_price_with_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    total_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    tax_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    total_with_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    current_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    subsequent_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_site_management"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataMachinery(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    machine_name = fields.CharField(max_length=200, null=True)
    model_spec = fields.CharField(max_length=100, null=True)
    quantity = fields.IntField(null=True)
    planned_start = fields.CharField(max_length=50, null=True)
    planned_end = fields.CharField(max_length=50, null=True)
    source = fields.CharField(max_length=50, null=True)
    usage_desc = fields.TextField(null=True)
    billing_method = fields.CharField(max_length=50, null=True)
    planned_period = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    planned_monthly_rate = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    planned_entry_exit_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    planned_mgmt_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    planned_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_period = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    contract_monthly_rate = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_entry_exit_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_mgmt_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_machinery"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataDynamicIndicator(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    item_name = fields.CharField(max_length=300, null=True)
    indicator_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_tax_rate = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    indicator_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_with_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_ratio = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    estimated_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_tax_rate = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    estimated_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_with_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_ratio = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    qty_change = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    transfer_in = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    transfer_in_desc = fields.TextField(null=True)
    transfer_out = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    transfer_out_desc = fields.TextField(null=True)
    adjusted_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    adjusted_with_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    current_budget = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    incurred_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_dynamic_indicator"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataLaborCost(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    person_name = fields.CharField(max_length=100, null=True)
    department = fields.CharField(max_length=100, null=True)
    position = fields.CharField(max_length=100, null=True)
    contract_relation = fields.CharField(max_length=100, null=True)
    actual_person_months = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    actual_total_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    subsequent_person_months = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    subsequent_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_person_months = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    estimated_total_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_labor_cost"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataGrossProfit(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    item_name = fields.CharField(max_length=200, null=True)
    contract_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_completion_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    economic_assessment = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_quantity = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    gross_profit_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    gross_profit_mgmt_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    gross_profit_net = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    gross_profit_rate = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    estimated_gross_profit_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_gross_profit_mgmt_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_gross_profit_net = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_gross_profit_rate = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    bid_revenue = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    bid_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    bid_profit = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    bid_profit_rate = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    indicator_revenue = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_profit = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_profit_rate = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    actual_revenue = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    actual_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    actual_profit = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    actual_profit_rate = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    forecast_revenue = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    forecast_cost = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    forecast_profit = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    forecast_profit_rate = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_gross_profit"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataBidComparison(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    item_name = fields.CharField(max_length=300, null=True)
    subcontract_budget = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    subcontract_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    deviation = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    process_settlement = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_in_scope = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_out_scope_active = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_out_scope_passive = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_indicator = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_deviation = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_bid_comparison"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataConstructionDynamic(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    work_content = fields.CharField(max_length=300, null=True)
    quota_code = fields.CharField(max_length=50, null=True)
    project_name = fields.CharField(max_length=300, null=True)
    project_feature = fields.TextField(null=True)
    unit = fields.CharField(max_length=50, null=True)
    remark = fields.TextField(null=True)
    bill_qty = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    subcontract_category = fields.CharField(max_length=200, null=True)
    contract_unit_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_total_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    device_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    material_concrete = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    material_rebar = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    material_steel = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    material_iron = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    material_other = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    material_name = fields.CharField(max_length=200, null=True)
    material_subtotal = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    construction_fixed = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    construction_adjustment = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    construction_assessment = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    construction_lighting = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_construction_dynamic"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataInstallationDynamic(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    project_code = fields.CharField(max_length=50, null=True)
    project_name = fields.CharField(max_length=300, null=True)
    project_feature = fields.TextField(null=True)
    unit = fields.CharField(max_length=50, null=True)
    remark = fields.TextField(null=True)
    clarification = fields.TextField(null=True)
    cost_category = fields.CharField(max_length=200, null=True)
    initial_bid_qty = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    device_material_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    installation_fee = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_device_material = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_installation = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_device_material = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_fabrication = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_construction = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    upstream_qty = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    drawing_stat_qty = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    drawing_confirmed_qty = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    cumulative_settlement_qty = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_device_material = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_installation = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_installation_dynamic"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataOtherItems(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    item_name = fields.CharField(max_length=300, null=True)
    work_desc = fields.TextField(null=True)
    calc_instruction = fields.TextField(null=True)
    unit = fields.CharField(max_length=50, null=True)
    quantity = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    pricing_method = fields.CharField(max_length=200, null=True)
    contract_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    cost_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_other_items"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataMaterialCost(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    budget_category = fields.CharField(max_length=200, null=True)
    unit = fields.CharField(max_length=50, null=True)
    indicator_qty = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    indicator_unit_price = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    indicator_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    budget_qty = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    budget_unit_price = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    budget_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_qty = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    contract_unit_price = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    contract_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    contract_remark = fields.TextField(null=True)
    actual_paid_qty = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    actual_paid_unit_price = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    actual_paid_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    actual_unpaid_qty = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    actual_unpaid_unit_price = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    actual_unpaid_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    estimated_completion_qty = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    estimated_completion_unit_price = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    estimated_completion_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    qty_diff = fields.DecimalField(max_digits=15, decimal_places=4, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_material_cost"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataBudgetAdjustmentSummary(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    item_name = fields.CharField(max_length=300, null=True)
    indicator_ex_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_tax_rate = fields.DecimalField(max_digits=15, decimal_places=10, null=True)
    indicator_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    indicator_with_tax = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    adjustment_1 = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    adjustment_2 = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    adjustment_n = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    adjustment_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    current_budget = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_budget_adjustment_summary"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataBudgetAdjustmentInternal(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    adjustment_count = fields.CharField(max_length=50, null=True)
    request_no = fields.CharField(max_length=100, null=True)
    request_name = fields.CharField(max_length=300, null=True)
    project_name = fields.CharField(max_length=300, null=True)
    bid_price = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    budget_before = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    adjustment_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    budget_after = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_budget_adjustment_internal"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataBudgetIncrease(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    increase_count = fields.CharField(max_length=50, null=True)
    upstream_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    upstream_doc_no = fields.CharField(max_length=100, null=True)
    upstream_doc_name = fields.CharField(max_length=300, null=True)
    report_no = fields.CharField(max_length=100, null=True)
    increase_project = fields.CharField(max_length=300, null=True)
    eas_increase = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    writeoff_amount = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remaining_quota = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_budget_increase"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataBudgetLease(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    request_name = fields.CharField(max_length=300, null=True)
    lease_date = fields.CharField(max_length=50, null=True)
    budget_subject = fields.CharField(max_length=300, null=True)
    budget_before = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    lease_bid = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    lease_active = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    lease_passive = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    lease_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    budget_after = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    writeoff_bid = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    writeoff_active = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    writeoff_passive = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    writeoff_total = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    lease_status = fields.TextField(null=True)
    remaining_bid = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remaining_active = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    remaining_passive = fields.DecimalField(max_digits=15, decimal_places=2, null=True)
    planned_writeoff_date = fields.CharField(max_length=50, null=True)
    actual_writeoff_date = fields.CharField(max_length=50, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_budget_lease"
        indexes = (("batch_id",), ("hierarchy_code",))


class DataSettlementOutput(Model):
    id = fields.IntField(primary_key=True)
    batch_id = fields.IntField()
    hierarchy_code = fields.CharField(max_length=50, null=True)
    indicator_name = fields.CharField(max_length=200, null=True)
    cumulative_value = fields.DecimalField(max_digits=20, decimal_places=6, null=True)
    indicator_desc = fields.TextField(null=True)
    data_source = fields.CharField(max_length=300, null=True)
    monthly_data = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "data_settlement_output"
        indexes = (("batch_id",), ("hierarchy_code",))


TEMPLATE_DATA_MODELS: dict[str, type[Model]] = {
    "social_insurance": DataSocialInsurance,
    "site_management": DataSiteManagement,
    "machinery": DataMachinery,
    "dynamic_indicator": DataDynamicIndicator,
    "labor_cost": DataLaborCost,
    "gross_profit": DataGrossProfit,
    "bid_comparison": DataBidComparison,
    "construction_dynamic": DataConstructionDynamic,
    "installation_dynamic": DataInstallationDynamic,
    "other_items": DataOtherItems,
    "material_cost": DataMaterialCost,
    "budget_adjustment_summary": DataBudgetAdjustmentSummary,
    "budget_adjustment_internal": DataBudgetAdjustmentInternal,
    "budget_increase": DataBudgetIncrease,
    "budget_lease": DataBudgetLease,
    "settlement_output": DataSettlementOutput,
}


def data_model_for(template_id: str) -> type[Model]:
    """Return the Tortoise data model class for a given template_id."""
    return TEMPLATE_DATA_MODELS[template_id]
