"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class PipelineOrchService(BaseModuleService):
    MODULE = "pipeline_orch"
    ENTITY = "管线任务"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["任务标识", "处理阶段", "输入批次", "输出批次", "编排状态"]
    REQUIRED_FIELDS = ["任务标识", "处理阶段", "输入批次"]
    STATUS_ORDER = ["待编排", "运行中", "已完成", "编排失败"]
    ACTION_RULES = {"启动管线": "运行中", "重试管线": "编排失败"}
    NEGATIVE_ACTIONS = []
