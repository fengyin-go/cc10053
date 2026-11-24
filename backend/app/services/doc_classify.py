"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DocClassifyService(BaseModuleService):
    MODULE = "doc_classify"
    ENTITY = "分类结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["文件指纹", "分类体系", "类别编码", "分类置信度", "多类标记"]
    REQUIRED_FIELDS = ["文件指纹", "分类体系", "类别编码"]
    STATUS_ORDER = ["待分类", "已分类", "置信不足"]
    ACTION_RULES = {"执行分类": "已分类", "转人工": "置信不足"}
    NEGATIVE_ACTIONS = []
