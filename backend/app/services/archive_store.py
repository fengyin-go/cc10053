"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ArchiveStoreService(BaseModuleService):
    MODULE = "archive_store"
    ENTITY = "归档条目"
    OPERATION_TERM = "归档"
    LIST_FIELDS = ["归档标识", "文件指纹", "归档层级", "存储位置", "保留期限"]
    REQUIRED_FIELDS = ["归档标识", "文件指纹", "归档层级"]
    STATUS_ORDER = ["待归档", "已归档", "归档失败"]
    ACTION_RULES = {"执行归档": "已归档", "重试归档": "归档失败"}
    NEGATIVE_ACTIONS = []
