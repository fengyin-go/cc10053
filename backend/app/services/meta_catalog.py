"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class MetaCatalogService(BaseModuleService):
    MODULE = "meta_catalog"
    ENTITY = "编目条目"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["条目标识", "文档标题", "作者机构", "成文日期", "编目等级"]
    REQUIRED_FIELDS = ["条目标识", "文档标题", "作者机构"]
    STATUS_ORDER = ["待编目", "已编目", "编目冲突"]
    ACTION_RULES = {"执行编目": "已编目", "解决冲突": "编目冲突"}
    NEGATIVE_ACTIONS = []
