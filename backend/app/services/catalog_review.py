"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class CatalogReviewService(BaseModuleService):
    MODULE = "catalog_review"
    ENTITY = "复核记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["记录编号", "编目条目", "复核结论", "复核角色", "复核时间"]
    REQUIRED_FIELDS = ["记录编号", "编目条目", "复核结论"]
    STATUS_ORDER = ["待复核", "已通过", "已驳回"]
    ACTION_RULES = {"通过记录": "已通过", "驳回记录": "已驳回"}
    NEGATIVE_ACTIONS = ["驳回记录"]
