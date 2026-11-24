"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class TextCleanService(BaseModuleService):
    MODULE = "text_clean"
    ENTITY = "清洗结果"
    OPERATION_TERM = "清洗"
    LIST_FIELDS = ["文件指纹", "清洗规则集", "乱码标记", "清洗产出", "字符损耗率"]
    REQUIRED_FIELDS = ["文件指纹", "清洗规则集", "乱码标记"]
    STATUS_ORDER = ["待清洗", "已清洗", "清洗异常"]
    ACTION_RULES = {"执行清洗": "已清洗", "重试清洗": "清洗异常"}
    NEGATIVE_ACTIONS = []
