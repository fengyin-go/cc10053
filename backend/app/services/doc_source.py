"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DocSourceService(BaseModuleService):
    MODULE = "doc_source"
    ENTITY = "文档源"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["源标识", "源名称", "源类型", "接入方式", "采集范围"]
    REQUIRED_FIELDS = ["源标识", "源名称", "源类型"]
    STATUS_ORDER = ["待验证", "已验证", "已停用"]
    ACTION_RULES = {"验证源": "已验证", "停用源": "已停用"}
    NEGATIVE_ACTIONS = ["停用源"]
