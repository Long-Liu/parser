"""ORM models mapped to the existing SQLAlchemy Table definitions."""

from sqlalchemy.orm import registry

from db import tables

mapper_registry = registry(metadata=tables.metadata)


@mapper_registry.mapped
class User:
    __table__ = tables.users


@mapper_registry.mapped
class Role:
    __table__ = tables.roles


@mapper_registry.mapped
class Permission:
    __table__ = tables.permissions


@mapper_registry.mapped
class UserRole:
    __table__ = tables.user_roles


@mapper_registry.mapped
class RolePermission:
    __table__ = tables.role_permissions


@mapper_registry.mapped
class Project:
    __table__ = tables.projects


@mapper_registry.mapped
class UploadBatch:
    __table__ = tables.upload_batches


@mapper_registry.mapped
class UploadLog:
    __table__ = tables.upload_logs


@mapper_registry.mapped
class TemplateConfig:
    __table__ = tables.template_configs


@mapper_registry.mapped
class DataSocialInsurance:
    __table__ = tables.data_social_insurance


@mapper_registry.mapped
class DataSiteManagement:
    __table__ = tables.data_site_management


@mapper_registry.mapped
class DataMachinery:
    __table__ = tables.data_machinery


@mapper_registry.mapped
class DataDynamicIndicator:
    __table__ = tables.data_dynamic_indicator


@mapper_registry.mapped
class DataLaborCost:
    __table__ = tables.data_labor_cost


@mapper_registry.mapped
class DataGrossProfit:
    __table__ = tables.data_gross_profit


@mapper_registry.mapped
class DataLaborCostSummary:
    __table__ = tables.data_labor_cost_summary


@mapper_registry.mapped
class DataBidComparison:
    __table__ = tables.data_bid_comparison


@mapper_registry.mapped
class DataConstructionDynamic:
    __table__ = tables.data_construction_dynamic


@mapper_registry.mapped
class DataInstallationDynamic:
    __table__ = tables.data_installation_dynamic


@mapper_registry.mapped
class DataOtherItems:
    __table__ = tables.data_other_items


@mapper_registry.mapped
class DataMaterialCost:
    __table__ = tables.data_material_cost


@mapper_registry.mapped
class DataConcreteLedger:
    __table__ = tables.data_concrete_ledger


@mapper_registry.mapped
class DataRebarLedger:
    __table__ = tables.data_rebar_ledger


@mapper_registry.mapped
class DataInstallationMaterial:
    __table__ = tables.data_installation_material


TEMPLATE_DATA_MODELS = {
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


def data_model_for(template_id: str):
    return TEMPLATE_DATA_MODELS[template_id]
