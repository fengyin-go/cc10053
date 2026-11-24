"""阶段重试器领域服务：对失败阶段执行断点重试恢复，管理重试策略与次数。
数据链路位置：恢复层，消费各处理阶段写入的失败记录，产出恢复状态数据，
恢复成功后把任务回流管线编排继续执行。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class StageRetryService(BaseModuleService):
    MODULE = "stage_retry"
    ENTITY = "重试记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["重试编号", "失败阶段", "重试策略", "重试次数", "恢复状态"]
    REQUIRED_FIELDS = ["重试编号", "失败阶段", "重试策略"]
    STATUS_ORDER = ["待重试", "重试中", "已恢复", "重试耗尽"]
    ACTION_RULES = {"执行重试": "重试中", "放弃记录": "重试耗尽"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：断点重试与恢复回流 ----

    MAX_RETRIES = 5

    def execute_retry(self, entry_id: int) -> dict[str, Any]:
        """执行重试：推进重试次数，判定恢复或耗尽。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待重试":
            return {"ok": False, "message": "记录不存在或不在待重试"}
        count = int(entry.get("重试次数", 0) or 0) + 1
        entry["重试次数"] = count
        if count >= self.MAX_RETRIES:
            entry["status"] = "重试耗尽"
            entry["恢复状态"] = "重试耗尽"
            entry["pending"] = False
            entry["abnormal"] = True
            return {"ok": True, "message": "重试已耗尽", "count": count}
        entry["status"] = "重试中"
        entry["恢复状态"] = "重试中"
        entry["pending"] = True
        return {"ok": True, "message": "重试执行中", "count": count}

    def mark_recovered(self, entry_id: int) -> dict[str, Any]:
        """标记已恢复：把任务回流管线编排继续执行。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "重试中":
            return {"ok": False, "message": "记录不存在或不在重试中"}
        entry["status"] = "已恢复"
        entry["恢复状态"] = "已恢复"
        entry["pending"] = False
        orch_rows = store.rows("pipeline_orch")
        orch_rows.append({
            "id": max((int(r.get("id", 0)) for r in orch_rows), default=0) + 1,
            "任务标识": f"ORCH-RETRY-{entry_id}",
            "处理阶段": entry.get("失败阶段", ""),
            "输入批次": entry.get("重试编号", ""),
            "输出批次": "",
            "编排状态": "断点恢复回流",
            "status": "运行中",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已恢复并回流编排"}

    def consume_from_stage(self, stage: str) -> list[dict[str, Any]]:
        """读取指定失败阶段的全部待重试记录。"""
        return [
            dict(r) for r in store.rows(self.MODULE)
            if r.get("失败阶段") == stage and r.get("status") == "待重试"
        ]

    def give_up(self, entry_id: int) -> dict[str, Any]:
        """放弃重试：标记耗尽并通知质量闸拦截。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "记录不存在"}
        entry["status"] = "重试耗尽"
        entry["恢复状态"] = "重试耗尽"
        entry["abnormal"] = True
        entry["pending"] = False
        gate_rows = store.rows("quality_gate")
        gate_rows.append({
            "id": max((int(r.get("id", 0)) for r in gate_rows), default=0) + 1,
            "检查批次": entry.get("重试编号", ""),
            "处理阶段": entry.get("失败阶段", ""),
            "检查项数": 1,
            "不通过项": 1,
            "闸门结论": "全量拦截",
            "status": "全量拦截",
            "pending": True,
            "abnormal": True,
        })
        return {"ok": True, "message": "已放弃并通知质量闸"}

    def exhausted_stats(self) -> dict[str, int]:
        """统计各失败阶段的重试耗尽数量。"""
        stats: dict[str, int] = {}
        for row in store.rows(self.MODULE):
            if row.get("status") == "重试耗尽":
                stage = str(row.get("失败阶段", "") or "未知")
                stats[stage] = stats.get(stage, 0) + 1
        return stats
