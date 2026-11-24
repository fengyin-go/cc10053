"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class SearchServiceService(BaseModuleService):
    MODULE = "search_service"
    ENTITY = "查询记录"
    OPERATION_TERM = "查询"
    LIST_FIELDS = ["查询标识", "查询词", "命中文档数", "响应耗时", "查询用户"]
    REQUIRED_FIELDS = ["查询标识", "查询词", "命中文档数"]
    STATUS_ORDER = ["已响应", "慢查询", "查询失败"]
    ACTION_RULES = {"标记慢查": "慢查询", "重试查询": "查询失败"}
    NEGATIVE_ACTIONS = []
