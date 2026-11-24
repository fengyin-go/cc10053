"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DupDocumentService(BaseModuleService):
    MODULE = "dup_document"
    ENTITY = "查重结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["查重批次", "候选组数", "相似文档对", "判定阈值", "查重方法"]
    REQUIRED_FIELDS = ["查重批次", "候选组数", "相似文档对"]
    STATUS_ORDER = ["查重中", "已完成", "查重失败"]
    ACTION_RULES = {"开始查重": "已完成", "重试查重": "查重失败"}
    NEGATIVE_ACTIONS = []
