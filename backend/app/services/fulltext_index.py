"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class FulltextIndexService(BaseModuleService):
    MODULE = "fulltext_index"
    ENTITY = "索引分片"
    OPERATION_TERM = "合并"
    LIST_FIELDS = ["分片标识", "索引词数", "文档数", "分片状态", "合并水位"]
    REQUIRED_FIELDS = ["分片标识", "索引词数", "文档数"]
    STATUS_ORDER = ["构建中", "已构建", "待合并"]
    ACTION_RULES = {"构建索引": "已构建", "合并分片": "待合并"}
    NEGATIVE_ACTIONS = []
