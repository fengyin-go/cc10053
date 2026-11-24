"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class OcrExtractService(BaseModuleService):
    MODULE = "ocr_extract"
    ENTITY = "抽取结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["文件指纹", "抽取文本", "置信度均值", "页码范围", "抽取引擎版本"]
    REQUIRED_FIELDS = ["文件指纹", "抽取文本", "置信度均值"]
    STATUS_ORDER = ["待抽取", "已抽取", "抽取失败"]
    ACTION_RULES = {"执行抽取": "已抽取", "重试抽取": "抽取失败"}
    NEGATIVE_ACTIONS = []
