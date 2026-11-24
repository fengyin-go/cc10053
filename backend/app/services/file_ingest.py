"""文件采集器领域服务：批量采集文档文件进入处理管线，管理批次状态与失败重试。
数据链路位置：采集执行层，承接文档源注册的配置，把采集到的文件批次推送给
格式识别器，并把完成量同步到采集量指标。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class FileIngestService(BaseModuleService):
    MODULE = "file_ingest"
    ENTITY = "采集批次"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["批次编号", "文档源", "文件数量", "批次大小", "采集时间"]
    REQUIRED_FIELDS = ["批次编号", "文档源", "文件数量"]
    STATUS_ORDER = ["进行中", "已完成", "批次失败"]
    ACTION_RULES = {"开始采集": "进行中", "重试批次": "批次失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：批次执行与下游推送 ----

    def complete_batch(self, entry_id: int) -> dict[str, Any]:
        """完成采集批次：为每个文件生成格式识别记录并推给格式识别器。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "进行中":
            return {"ok": False, "message": "批次不存在或不在进行中"}
        count = int(entry.get("文件数量", 0) or 0)
        rows = store.rows("format_detect")
        pushed = 0
        for _ in range(max(count, 1)):
            rows.append({
                "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
                "文件指纹": f"{entry.get('批次编号', '')}-F{pushed + 1}",
                "识别格式": "",
                "置信度": "0",
                "识别版本": "",
                "处理分支": "",
                "status": "待识别",
                "pending": True,
                "abnormal": False,
            })
            pushed += 1
        entry["status"] = "已完成"
        entry["pending"] = False
        return {"ok": True, "message": "批次已完成并推送识别", "pushed": pushed}

    def fail_batch(self, entry_id: int, reason: str) -> dict[str, Any]:
        """标记批次失败并写入阶段重试记录，等待断点恢复。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "批次不存在"}
        entry["status"] = "批次失败"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-{entry.get('批次编号', '')}",
            "失败阶段": "采集",
            "重试策略": "批次重跑",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"批次已标记失败: {reason}"}

    def retry_batch(self, entry_id: int) -> dict[str, Any]:
        """重试失败批次：恢复为进行中并清空失败标记。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "批次失败":
            return {"ok": False, "message": "批次不存在或未失败"}
        entry["status"] = "进行中"
        entry["pending"] = True
        entry["abnormal"] = False
        entry["采集时间"] = datetime.now(timezone.utc).isoformat()
        return {"ok": True, "message": "批次已重试，恢复进行中"}

    def consume_from_doc_source(self, source_name: str) -> list[dict[str, Any]]:
        """读取文档源注册中指定源的验证状态与配置数据。"""
        return [
            dict(s) for s in store.rows("doc_source")
            if s.get("源名称") == source_name and s.get("status") == "已验证"
        ]

    def report_batch_metrics(self, entry_id: int) -> dict[str, Any]:
        """把批次完成量上报采集量指标。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "批次不存在"}
        rows = store.rows("ingest_metrics")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "统计时间": datetime.now(timezone.utc).isoformat(),
            "文档源": entry.get("文档源", ""),
            "采集量": int(entry.get("文件数量", 0) or 0),
            "抽取量": 0,
            "归档量": 0,
            "status": "正常",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "批次指标已上报"}
