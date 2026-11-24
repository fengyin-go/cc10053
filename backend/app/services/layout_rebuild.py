"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class LayoutRebuildService(BaseModuleService):
    MODULE = "layout_rebuild"
    ENTITY = "版面结构"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["文件指纹", "版面块数", "阅读顺序", "表格块数", "重建质量"]
    REQUIRED_FIELDS = ["文件指纹", "版面块数", "阅读顺序"]
    STATUS_ORDER = ["待重建", "已重建", "重建失败"]
    ACTION_RULES = {"执行重建": "已重建", "重试重建": "重建失败"}
    NEGATIVE_ACTIONS = []
