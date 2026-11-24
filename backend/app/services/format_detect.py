"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class FormatDetectService(BaseModuleService):
    MODULE = "format_detect"
    ENTITY = "格式记录"
    OPERATION_TERM = "解析"
    LIST_FIELDS = ["文件指纹", "识别格式", "置信度", "识别版本", "处理分支"]
    REQUIRED_FIELDS = ["文件指纹", "识别格式", "置信度"]
    STATUS_ORDER = ["已识别", "待识别", "识别失败"]
    ACTION_RULES = {"重新识别": "已识别", "转人工": "识别失败"}
    NEGATIVE_ACTIONS = []
