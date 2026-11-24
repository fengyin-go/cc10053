"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class LangDetectService(BaseModuleService):
    MODULE = "lang_detect"
    ENTITY = "语种记录"
    OPERATION_TERM = "转换"
    LIST_FIELDS = ["文件指纹", "主语种", "混合语种", "检测置信度", "编码转换"]
    REQUIRED_FIELDS = ["文件指纹", "主语种", "混合语种"]
    STATUS_ORDER = ["已检测", "待检测", "检测失败"]
    ACTION_RULES = {"执行检测": "已检测", "重试检测": "检测失败"}
    NEGATIVE_ACTIONS = []
