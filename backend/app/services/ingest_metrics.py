"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class IngestMetricsService(BaseModuleService):
    MODULE = "ingest_metrics"
    ENTITY = "量级快照"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["统计时间", "文档源", "采集量", "抽取量", "归档量"]
    REQUIRED_FIELDS = ["统计时间", "文档源", "采集量"]
    STATUS_ORDER = ["正常", "量级波动", "断流"]
    ACTION_RULES = {"查看趋势": "量级波动", "忽略波动": "断流"}
    NEGATIVE_ACTIONS = ["忽略波动"]
