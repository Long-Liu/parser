"""SQLAlchemy Core table definitions — used with aiomysql for type-safe SQL generation."""

import sqlalchemy as sa

metadata = sa.MetaData()

# ── Fixed application tables ─────────────────────────────────────────────────

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("username", sa.String(50), nullable=False, unique=True),
    sa.Column("password", sa.String(255), nullable=False),
    sa.Column("real_name", sa.String(100)),
    sa.Column("email", sa.String(200)),
    sa.Column("phone", sa.String(20)),
    sa.Column("is_active", sa.Boolean, default=True),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

roles = sa.Table(
    "roles",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("code", sa.String(50), nullable=False, unique=True),
    sa.Column("name", sa.String(100), nullable=False),
    sa.Column("description", sa.String(500)),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

permissions = sa.Table(
    "permissions",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("code", sa.String(100), nullable=False, unique=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.String(500)),
)

user_roles = sa.Table(
    "user_roles",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
    sa.UniqueConstraint("user_id", "role_id"),
)

role_permissions = sa.Table(
    "role_permissions",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
    sa.Column("permission_id", sa.Integer, sa.ForeignKey("permissions.id"), nullable=False),
    sa.UniqueConstraint("role_id", "permission_id"),
)

projects = sa.Table(
    "projects",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("code", sa.String(50), nullable=False, unique=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

upload_batches = sa.Table(
    "upload_batches",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_no", sa.String(50), nullable=False, unique=True),
    sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
    sa.Column("ym", sa.String(7), nullable=False),
    sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("file_name", sa.String(500)),
    sa.Column("file_size", sa.BigInteger),
    sa.Column("status", sa.String(20), default="processing"),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
)

upload_logs = sa.Table(
    "upload_logs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("sheet_name", sa.String(200)),
    sa.Column("template_id", sa.String(100)),
    sa.Column("action", sa.String(20), default="matched"),
    sa.Column("total_rows", sa.Integer, default=0),
    sa.Column("success_rows", sa.Integer, default=0),
    sa.Column("error_rows", sa.Integer, default=0),
    sa.Column("error_msg", sa.Text),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
)

template_configs = sa.Table(
    "template_configs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("template_id", sa.String(100), nullable=False, unique=True),
    sa.Column("description", sa.String(500)),
    sa.Column("config_yaml", sa.Text, nullable=False),
    sa.Column("data_table", sa.String(100), nullable=False),
    sa.Column("is_active", sa.Boolean, default=True),
    sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
)

# ── Data tables — one per template, generated from config/templates/*.yaml ──

data_social_insurance = sa.Table(
    "data_social_insurance", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("person_name", sa.String(100)),
    sa.Column("department", sa.String(100)),
    sa.Column("position", sa.String(100)),
    sa.Column("contract_relation", sa.String(100)),
    sa.Column("actual_person_months", sa.Numeric(10, 2)),
    sa.Column("actual_total_cost", sa.Numeric(15, 2)),
    sa.Column("subsequent_person_months", sa.Numeric(10, 2)),
    sa.Column("subsequent_cost", sa.Numeric(15, 2)),
    sa.Column("estimated_person_months", sa.Numeric(10, 2)),
    sa.Column("estimated_total_cost", sa.Numeric(15, 2)),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_site_management = sa.Table(
    "data_site_management", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("fee_name", sa.String(200)),
    sa.Column("unit", sa.String(50)),
    sa.Column("quantity", sa.Numeric(10, 2)),
    sa.Column("unit_price_ex_tax", sa.Numeric(15, 2)),
    sa.Column("tax_rate", sa.Numeric(5, 4)),
    sa.Column("unit_price_with_tax", sa.Numeric(15, 2)),
    sa.Column("total_ex_tax", sa.Numeric(15, 2)),
    sa.Column("tax_amount", sa.Numeric(15, 2)),
    sa.Column("total_with_tax", sa.Numeric(15, 2)),
    sa.Column("remark", sa.Text),
    sa.Column("current_amount", sa.Numeric(15, 2)),
    sa.Column("subsequent_amount", sa.Numeric(15, 2)),
    sa.Column("estimated_amount", sa.Numeric(15, 2)),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_machinery = sa.Table(
    "data_machinery", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("machine_name", sa.String(200)),
    sa.Column("model_spec", sa.String(100)),
    sa.Column("quantity", sa.Integer),
    sa.Column("planned_start", sa.String(50)),
    sa.Column("planned_end", sa.String(50)),
    sa.Column("source", sa.String(50)),
    sa.Column("usage_desc", sa.Text),
    sa.Column("billing_method", sa.String(50)),
    sa.Column("planned_period", sa.Numeric(10, 2)),
    sa.Column("planned_monthly_rate", sa.Numeric(15, 2)),
    sa.Column("planned_entry_exit_fee", sa.Numeric(15, 2)),
    sa.Column("planned_mgmt_fee", sa.Numeric(15, 2)),
    sa.Column("planned_total", sa.Numeric(15, 2)),
    sa.Column("contract_period", sa.Numeric(10, 2)),
    sa.Column("contract_monthly_rate", sa.Numeric(15, 2)),
    sa.Column("contract_entry_exit_fee", sa.Numeric(15, 2)),
    sa.Column("contract_mgmt_fee", sa.Numeric(15, 2)),
    sa.Column("contract_ex_tax", sa.Numeric(15, 2)),
    sa.Column("contract_tax", sa.Numeric(15, 2)),
    sa.Column("contract_total", sa.Numeric(15, 2)),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_dynamic_indicator = sa.Table(
    "data_dynamic_indicator", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("item_name", sa.String(300)),
    sa.Column("indicator_ex_tax", sa.Numeric(15, 2)),
    sa.Column("indicator_tax_rate", sa.Numeric(5, 4)),
    sa.Column("indicator_tax", sa.Numeric(15, 2)),
    sa.Column("indicator_with_tax", sa.Numeric(15, 2)),
    sa.Column("indicator_ratio", sa.Numeric(15, 10)),
    sa.Column("estimated_ex_tax", sa.Numeric(15, 2)),
    sa.Column("estimated_tax_rate", sa.Numeric(5, 4)),
    sa.Column("estimated_tax", sa.Numeric(15, 2)),
    sa.Column("estimated_with_tax", sa.Numeric(15, 2)),
    sa.Column("estimated_ratio", sa.Numeric(15, 10)),
    sa.Column("qty_change", sa.Numeric(15, 2)),
    sa.Column("remark", sa.Text),
    sa.Column("transfer_in", sa.Numeric(15, 2)),
    sa.Column("transfer_in_desc", sa.Text),
    sa.Column("transfer_out", sa.Numeric(15, 2)),
    sa.Column("transfer_out_desc", sa.Text),
    sa.Column("adjusted_ex_tax", sa.Numeric(15, 2)),
    sa.Column("adjusted_with_tax", sa.Numeric(15, 2)),
    sa.Column("current_budget", sa.Numeric(15, 2)),
    sa.Column("incurred_cost", sa.Numeric(15, 2)),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_labor_cost = sa.Table(
    "data_labor_cost", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("person_name", sa.String(100)),
    sa.Column("department", sa.String(100)),
    sa.Column("position", sa.String(100)),
    sa.Column("contract_relation", sa.String(100)),
    sa.Column("actual_person_months", sa.Numeric(10, 2)),
    sa.Column("actual_total_cost", sa.Numeric(15, 2)),
    sa.Column("subsequent_person_months", sa.Numeric(10, 2)),
    sa.Column("subsequent_cost", sa.Numeric(15, 2)),
    sa.Column("estimated_person_months", sa.Numeric(10, 2)),
    sa.Column("estimated_total_cost", sa.Numeric(15, 2)),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_gross_profit = sa.Table(
    "data_gross_profit", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("item_name", sa.String(200)),
    sa.Column("contract_price", sa.Numeric(15, 2)),
    sa.Column("estimated_completion_price", sa.Numeric(15, 2)),
    sa.Column("economic_assessment", sa.Numeric(15, 2)),
    sa.Column("estimated_quantity", sa.Numeric(15, 2)),
    sa.Column("gross_profit_total", sa.Numeric(15, 2)),
    sa.Column("gross_profit_mgmt_fee", sa.Numeric(15, 2)),
    sa.Column("gross_profit_net", sa.Numeric(15, 2)),
    sa.Column("gross_profit_rate", sa.Numeric(15, 10)),
    sa.Column("estimated_gross_profit_total", sa.Numeric(15, 2)),
    sa.Column("estimated_gross_profit_mgmt_fee", sa.Numeric(15, 2)),
    sa.Column("estimated_gross_profit_net", sa.Numeric(15, 2)),
    sa.Column("estimated_gross_profit_rate", sa.Numeric(15, 10)),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_labor_cost_summary = sa.Table(
    "data_labor_cost_summary", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("total_labor", sa.Numeric(15, 2)),
    sa.Column("planned_progress", sa.Numeric(10, 4)),
    sa.Column("planned_labor", sa.Numeric(15, 2)),
    sa.Column("actual_progress", sa.Numeric(10, 4)),
    sa.Column("actual_labor", sa.Numeric(15, 2)),
    sa.Column("planned_person_months", sa.Numeric(10, 2)),
    sa.Column("planned_labor_indicator", sa.Numeric(15, 2)),
    sa.Column("actual_person_months", sa.Numeric(10, 2)),
    sa.Column("actual_labor_indicator", sa.Numeric(15, 2)),
    sa.Column("indicator_person_months", sa.Numeric(10, 2)),
    sa.Column("indicator_labor", sa.Numeric(15, 2)),
    sa.Column("completed_person_months", sa.Numeric(10, 2)),
    sa.Column("completed_labor", sa.Numeric(15, 2)),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_bid_comparison = sa.Table(
    "data_bid_comparison", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("item_name", sa.String(300)),
    sa.Column("subcontract_budget", sa.Numeric(15, 2)),
    sa.Column("subcontract_price", sa.Numeric(15, 2)),
    sa.Column("deviation", sa.Numeric(15, 2)),
    sa.Column("process_settlement", sa.Numeric(15, 2)),
    sa.Column("estimated_in_scope", sa.Numeric(15, 2)),
    sa.Column("estimated_out_scope_active", sa.Numeric(15, 2)),
    sa.Column("estimated_out_scope_passive", sa.Numeric(15, 2)),
    sa.Column("estimated_total", sa.Numeric(15, 2)),
    sa.Column("estimated_indicator", sa.Numeric(15, 2)),
    sa.Column("indicator_deviation", sa.Numeric(15, 2)),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_construction_dynamic = sa.Table(
    "data_construction_dynamic", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("work_content", sa.String(300)),
    sa.Column("quota_code", sa.String(50)),
    sa.Column("project_name", sa.String(300)),
    sa.Column("project_feature", sa.Text),
    sa.Column("unit", sa.String(50)),
    sa.Column("remark", sa.Text),
    sa.Column("bill_qty", sa.Numeric(15, 2)),
    sa.Column("subcontract_category", sa.String(200)),
    sa.Column("contract_unit_price", sa.Numeric(15, 2)),
    sa.Column("contract_total_price", sa.Numeric(15, 2)),
    sa.Column("device_ex_tax", sa.Numeric(15, 2)),
    sa.Column("material_concrete", sa.Numeric(15, 2)),
    sa.Column("material_rebar", sa.Numeric(15, 2)),
    sa.Column("material_steel", sa.Numeric(15, 2)),
    sa.Column("material_iron", sa.Numeric(15, 2)),
    sa.Column("material_other", sa.Numeric(15, 2)),
    sa.Column("material_name", sa.String(200)),
    sa.Column("material_subtotal", sa.Numeric(15, 2)),
    sa.Column("construction_fixed", sa.Numeric(15, 2)),
    sa.Column("construction_adjustment", sa.Numeric(15, 2)),
    sa.Column("construction_assessment", sa.Numeric(15, 2)),
    sa.Column("construction_lighting", sa.Numeric(15, 2)),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_installation_dynamic = sa.Table(
    "data_installation_dynamic", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("project_code", sa.String(50)),
    sa.Column("project_name", sa.String(300)),
    sa.Column("project_feature", sa.Text),
    sa.Column("unit", sa.String(50)),
    sa.Column("remark", sa.Text),
    sa.Column("clarification", sa.Text),
    sa.Column("cost_category", sa.String(200)),
    sa.Column("initial_bid_qty", sa.Numeric(15, 2)),
    sa.Column("device_material_fee", sa.Numeric(15, 2)),
    sa.Column("installation_fee", sa.Numeric(15, 2)),
    sa.Column("contract_device_material", sa.Numeric(15, 2)),
    sa.Column("contract_installation", sa.Numeric(15, 2)),
    sa.Column("indicator_device_material", sa.Numeric(15, 2)),
    sa.Column("indicator_fabrication", sa.Numeric(15, 2)),
    sa.Column("indicator_construction", sa.Numeric(15, 2)),
    sa.Column("upstream_qty", sa.Numeric(15, 2)),
    sa.Column("drawing_stat_qty", sa.Numeric(15, 2)),
    sa.Column("drawing_confirmed_qty", sa.Numeric(15, 2)),
    sa.Column("cumulative_settlement_qty", sa.Numeric(15, 2)),
    sa.Column("estimated_device_material", sa.Numeric(15, 2)),
    sa.Column("estimated_installation", sa.Numeric(15, 2)),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_other_items = sa.Table(
    "data_other_items", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("item_name", sa.String(300)),
    sa.Column("work_desc", sa.Text),
    sa.Column("calc_instruction", sa.Text),
    sa.Column("unit", sa.String(50)),
    sa.Column("quantity", sa.Numeric(15, 2)),
    sa.Column("pricing_method", sa.String(200)),
    sa.Column("contract_price", sa.Numeric(15, 2)),
    sa.Column("cost_amount", sa.Numeric(15, 2)),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_material_cost = sa.Table(
    "data_material_cost", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("budget_category", sa.String(200)),
    sa.Column("unit", sa.String(50)),
    sa.Column("indicator_qty", sa.Numeric(15, 4)),
    sa.Column("indicator_unit_price", sa.Numeric(15, 4)),
    sa.Column("indicator_total", sa.Numeric(15, 2)),
    sa.Column("budget_qty", sa.Numeric(15, 4)),
    sa.Column("budget_unit_price", sa.Numeric(15, 4)),
    sa.Column("budget_total", sa.Numeric(15, 2)),
    sa.Column("contract_qty", sa.Numeric(15, 4)),
    sa.Column("contract_unit_price", sa.Numeric(15, 4)),
    sa.Column("contract_total", sa.Numeric(15, 2)),
    sa.Column("contract_remark", sa.Text),
    sa.Column("actual_paid_qty", sa.Numeric(15, 4)),
    sa.Column("actual_paid_unit_price", sa.Numeric(15, 4)),
    sa.Column("actual_paid_total", sa.Numeric(15, 2)),
    sa.Column("actual_unpaid_qty", sa.Numeric(15, 4)),
    sa.Column("actual_unpaid_unit_price", sa.Numeric(15, 4)),
    sa.Column("actual_unpaid_total", sa.Numeric(15, 2)),
    sa.Column("estimated_completion_qty", sa.Numeric(15, 4)),
    sa.Column("estimated_completion_unit_price", sa.Numeric(15, 4)),
    sa.Column("estimated_completion_total", sa.Numeric(15, 2)),
    sa.Column("qty_diff", sa.Numeric(15, 4)),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_concrete_ledger = sa.Table(
    "data_concrete_ledger", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("pour_number", sa.String(100)),
    sa.Column("application_date", sa.String(50)),
    sa.Column("drawing_unit_name", sa.String(300)),
    sa.Column("drawing_number", sa.String(100)),
    sa.Column("drawing_name", sa.String(300)),
    sa.Column("usage_location", sa.String(500)),
    sa.Column("concrete_grade", sa.String(100)),
    sa.Column("unit", sa.String(50)),
    sa.Column("design_qty", sa.Numeric(15, 2)),
    sa.Column("pour_applied_qty", sa.Numeric(15, 2)),
    sa.Column("contract_scope", sa.String(200)),
    sa.Column("indicator_budget_qty", sa.Numeric(15, 2)),
    sa.Column("upstream_settlement_qty", sa.Numeric(15, 2)),
    sa.Column("actual_pour_date", sa.String(50)),
    sa.Column("actual_pour_hours", sa.String(50)),
    sa.Column("actual_pour_method", sa.String(100)),
    sa.Column("actual_pour_qty", sa.Numeric(15, 2)),
    sa.Column("settlement_qty", sa.Numeric(15, 2)),
    sa.Column("supplier_name", sa.String(200)),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_rebar_ledger = sa.Table(
    "data_rebar_ledger", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("drawing_number", sa.String(100)),
    sa.Column("drawing_name", sa.String(300)),
    sa.Column("rebar_diameter", sa.String(50)),
    sa.Column("rebar_length", sa.Numeric(15, 2)),
    sa.Column("rebar_count", sa.Integer),
    sa.Column("unit_weight", sa.Numeric(15, 4)),
    sa.Column("total_weight", sa.Numeric(15, 2)),
    sa.Column("connection_qty", sa.Integer),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

data_installation_material = sa.Table(
    "data_installation_material", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("batch_id", sa.Integer, sa.ForeignKey("upload_batches.id"), nullable=False),
    sa.Column("hierarchy_code", sa.String(50)),
    sa.Column("project_category", sa.String(300)),
    sa.Column("project_feature", sa.Text),
    sa.Column("unit", sa.String(50)),
    sa.Column("drawing_qty", sa.Numeric(15, 2)),
    sa.Column("budget_unit_price", sa.Numeric(15, 4)),
    sa.Column("budget_total", sa.Numeric(15, 2)),
    sa.Column("contract_qty", sa.Numeric(15, 2)),
    sa.Column("contract_unit_price", sa.Numeric(15, 4)),
    sa.Column("contract_total", sa.Numeric(15, 2)),
    sa.Column("remark", sa.Text),
    sa.Column("monthly_data", sa.JSON),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Index("idx_batch", "batch_id"),
    sa.Index("idx_hierarchy", "hierarchy_code"),
)

# ── Template lookup ──────────────────────────────────────────────────────────

TEMPLATE_DATA_TABLES: dict[str, sa.Table] = {
    "social_insurance": data_social_insurance,
    "site_management": data_site_management,
    "machinery": data_machinery,
    "dynamic_indicator": data_dynamic_indicator,
    "labor_cost": data_labor_cost,
    "gross_profit": data_gross_profit,
    "labor_cost_summary": data_labor_cost_summary,
    "bid_comparison": data_bid_comparison,
    "construction_dynamic": data_construction_dynamic,
    "installation_dynamic": data_installation_dynamic,
    "other_items": data_other_items,
    "material_cost": data_material_cost,
    "concrete_ledger": data_concrete_ledger,
    "rebar_ledger": data_rebar_ledger,
    "installation_material": data_installation_material,
}


def data_table_for(template_id: str) -> sa.Table:
    """Return the SA Core Table for a data_{template_id} table."""
    return TEMPLATE_DATA_TABLES[template_id]


# ── ORM model mappings (thin wrappers over the Core tables above) ──────────

from sqlalchemy.orm import registry  # noqa: E402

mapper_registry = registry(metadata=metadata)


class _OrmBase:
    """Imperative-mapped base. SA 2.0 mapping is via __table__, not annotations."""
    __allow_unmapped__ = True


@mapper_registry.mapped
class User(_OrmBase):
    __table__ = users


@mapper_registry.mapped
class Role(_OrmBase):
    __table__ = roles


@mapper_registry.mapped
class Permission(_OrmBase):
    __table__ = permissions


@mapper_registry.mapped
class UserRole(_OrmBase):
    __table__ = user_roles


@mapper_registry.mapped
class RolePermission(_OrmBase):
    __table__ = role_permissions


@mapper_registry.mapped
class Project(_OrmBase):
    __table__ = projects


@mapper_registry.mapped
class UploadBatch(_OrmBase):
    __table__ = upload_batches


@mapper_registry.mapped
class UploadLog(_OrmBase):
    __table__ = upload_logs


@mapper_registry.mapped
class TemplateConfig(_OrmBase):
    __table__ = template_configs


@mapper_registry.mapped
class DataSocialInsurance(_OrmBase):
    __table__ = data_social_insurance


@mapper_registry.mapped
class DataSiteManagement(_OrmBase):
    __table__ = data_site_management


@mapper_registry.mapped
class DataMachinery(_OrmBase):
    __table__ = data_machinery


@mapper_registry.mapped
class DataDynamicIndicator(_OrmBase):
    __table__ = data_dynamic_indicator


@mapper_registry.mapped
class DataLaborCost(_OrmBase):
    __table__ = data_labor_cost


@mapper_registry.mapped
class DataGrossProfit(_OrmBase):
    __table__ = data_gross_profit


@mapper_registry.mapped
class DataLaborCostSummary(_OrmBase):
    __table__ = data_labor_cost_summary


@mapper_registry.mapped
class DataBidComparison(_OrmBase):
    __table__ = data_bid_comparison


@mapper_registry.mapped
class DataConstructionDynamic(_OrmBase):
    __table__ = data_construction_dynamic


@mapper_registry.mapped
class DataInstallationDynamic(_OrmBase):
    __table__ = data_installation_dynamic


@mapper_registry.mapped
class DataOtherItems(_OrmBase):
    __table__ = data_other_items


@mapper_registry.mapped
class DataMaterialCost(_OrmBase):
    __table__ = data_material_cost


@mapper_registry.mapped
class DataConcreteLedger(_OrmBase):
    __table__ = data_concrete_ledger


@mapper_registry.mapped
class DataRebarLedger(_OrmBase):
    __table__ = data_rebar_ledger


@mapper_registry.mapped
class DataInstallationMaterial(_OrmBase):
    __table__ = data_installation_material


TEMPLATE_DATA_MODELS: dict[str, type] = {
    "social_insurance": DataSocialInsurance,
    "site_management": DataSiteManagement,
    "machinery": DataMachinery,
    "dynamic_indicator": DataDynamicIndicator,
    "labor_cost": DataLaborCost,
    "gross_profit": DataGrossProfit,
    "labor_cost_summary": DataLaborCostSummary,
    "bid_comparison": DataBidComparison,
    "construction_dynamic": DataConstructionDynamic,
    "installation_dynamic": DataInstallationDynamic,
    "other_items": DataOtherItems,
    "material_cost": DataMaterialCost,
    "concrete_ledger": DataConcreteLedger,
    "rebar_ledger": DataRebarLedger,
    "installation_material": DataInstallationMaterial,
}


def data_model_for(template_id: str) -> type:
    """Return the ORM data model class for a given template_id."""
    return TEMPLATE_DATA_MODELS[template_id]
