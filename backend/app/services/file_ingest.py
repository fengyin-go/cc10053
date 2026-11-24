"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class FileIngestService(BaseModuleService):
    MODULE = "file_ingest"
    ENTITY = "采集批次"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["批次编号", "文档源", "文件数量", "批次大小", "采集时间"]
    REQUIRED_FIELDS = ["批次编号", "文档源", "文件数量"]
    STATUS_ORDER = ["进行中", "已完成", "批次失败"]
    ACTION_RULES = {"开始采集": "进行中", "重试批次": "批次失败"}
    NEGATIVE_ACTIONS = []
