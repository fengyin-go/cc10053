"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class StageRetryService(BaseModuleService):
    MODULE = "stage_retry"
    ENTITY = "重试记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["重试编号", "失败阶段", "重试策略", "重试次数", "恢复状态"]
    REQUIRED_FIELDS = ["重试编号", "失败阶段", "重试策略"]
    STATUS_ORDER = ["待重试", "重试中", "已恢复", "重试耗尽"]
    ACTION_RULES = {"执行重试": "重试中", "放弃记录": "重试耗尽"}
    NEGATIVE_ACTIONS = []
