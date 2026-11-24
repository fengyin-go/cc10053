"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class RetentionPolicyService(BaseModuleService):
    MODULE = "retention_policy"
    ENTITY = "保留规则"
    OPERATION_TERM = "归档"
    LIST_FIELDS = ["规则名称", "归档层级", "保留期限", "清理方式", "保护条件"]
    REQUIRED_FIELDS = ["规则名称", "归档层级", "保留期限"]
    STATUS_ORDER = ["待生效", "已生效", "已暂停"]
    ACTION_RULES = {"生效规则": "已生效", "暂停规则": "已暂停"}
    NEGATIVE_ACTIONS = []
