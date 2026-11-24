"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class QualityGateService(BaseModuleService):
    MODULE = "quality_gate"
    ENTITY = "质量结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["检查批次", "处理阶段", "检查项数", "不通过项", "闸门结论"]
    REQUIRED_FIELDS = ["检查批次", "处理阶段", "检查项数"]
    STATUS_ORDER = ["放行", "部分拦截", "全量拦截"]
    ACTION_RULES = {"放行批次": "部分拦截", "拦截批次": "全量拦截"}
    NEGATIVE_ACTIONS = []
