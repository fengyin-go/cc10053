"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ExportBundleService(BaseModuleService):
    MODULE = "export_bundle"
    ENTITY = "导出任务"
    OPERATION_TERM = "导出"
    LIST_FIELDS = ["任务名称", "编目范围", "导出格式", "分卷大小", "生成状态"]
    REQUIRED_FIELDS = ["任务名称", "编目范围", "导出格式"]
    STATUS_ORDER = ["排队中", "打包中", "已完成", "打包失败"]
    ACTION_RULES = {"开始打包": "打包中", "重试打包": "打包失败"}
    NEGATIVE_ACTIONS = []
