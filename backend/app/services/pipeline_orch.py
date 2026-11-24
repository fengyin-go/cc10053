"""处理管线编排领域服务：编排采集到归档的全链路处理任务，管理阶段流转。
数据链路位置：编排层，消费采集批次的输入数据，驱动格式识别、抽取、清洗、
编目、归档各阶段顺序执行，并把任务状态同步到质量闸。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class PipelineOrchService(BaseModuleService):
    MODULE = "pipeline_orch"
    ENTITY = "管线任务"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["任务标识", "处理阶段", "输入批次", "输出批次", "编排状态"]
    REQUIRED_FIELDS = ["任务标识", "处理阶段", "输入批次"]
    STATUS_ORDER = ["待编排", "运行中", "已完成", "编排失败"]
    ACTION_RULES = {"启动管线": "运行中", "重试管线": "编排失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：管线编排与阶段推进 ----
    STAGE_CHAIN = ["采集", "识别", "抽取", "清洗", "编目", "归档"]

    def start_pipeline(self, entry_id: int) -> dict[str, Any]:
        """启动管线：校验输入批次存在并进入运行中。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待编排":
            return {"ok": False, "message": "任务不存在或不在待编排"}
        batch_no = entry.get("输入批次", "")
        source = next(
            (b for b in store.rows("file_ingest") if b.get("批次编号") == batch_no), None
        )
        if source is None:
            entry["status"] = "编排失败"
            entry["abnormal"] = True
            return {"ok": False, "message": f"输入批次 {batch_no} 不存在"}
        entry["status"] = "运行中"
        entry["pending"] = True
        return {"ok": True, "message": "管线已启动", "files": source.get("文件数量", 0)}

    def advance_stage(self, entry_id: int) -> dict[str, Any]:
        """推进到下一处理阶段：按阶段链顺序流转。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "运行中":
            return {"ok": False, "message": "任务不存在或不在运行中"}
        stage = str(entry.get("处理阶段", self.STAGE_CHAIN[0]))
        idx = self.STAGE_CHAIN.index(stage) if stage in self.STAGE_CHAIN else 0
        if idx + 1 >= len(self.STAGE_CHAIN):
            entry["status"] = "已完成"
            entry["pending"] = False
            entry["输出批次"] = f"{entry.get('输入批次', '')}-final"
            return {"ok": True, "message": "管线已完成", "stage": stage}
        next_stage = self.STAGE_CHAIN[idx + 1]
        entry["处理阶段"] = next_stage
        return {"ok": True, "message": "阶段已推进", "next_stage": next_stage}

    def push_to_quality_gate(self, entry_id: int) -> dict[str, Any]:
        """把已完成任务推送给处理质量闸执行检查。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已完成":
            return {"ok": False, "message": "任务不存在或未完成"}
        rows = store.rows("quality_gate")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "检查批次": entry.get("输出批次", "") or entry.get("输入批次", ""),
            "处理阶段": entry.get("处理阶段", "归档"),
            "检查项数": 6,
            "不通过项": 0,
            "闸门结论": "放行",
            "status": "放行",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给质量闸"}

    def consume_stage_stats(self) -> dict[str, int]:
        """读取格式识别器按分支统计数据，作为编排输入。"""
        stats: dict[str, int] = {}
        for row in store.rows("format_detect"):
            branch = str(row.get("处理分支", "") or "未路由")
            stats[branch] = stats.get(branch, 0) + 1
        return stats

    def fail_pipeline(self, entry_id: int, reason: str) -> dict[str, Any]:
        """管线编排失败：写阶段重试记录等待断点恢复。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "任务不存在"}
        entry["status"] = "编排失败"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-PO-{entry_id}",
            "失败阶段": entry.get("处理阶段", "编排"),
            "重试策略": "断点续跑",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"管线已标记失败: {reason}"}

    def retry_pipeline(self, entry_id: int) -> dict[str, Any]:
        """重试编排失败任务：从断点阶段恢复运行中。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "编排失败":
            return {"ok": False, "message": "任务不存在或未失败"}
        entry["status"] = "运行中"
        entry["pending"] = True
        entry["abnormal"] = False
        return {"ok": True, "message": "管线已从断点恢复"}
