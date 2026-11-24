"""处理质量闸领域服务：按质量阈值拦截低质处理结果，管理闸门结论与拦截范围。
数据链路位置：质量层，消费管线编排推送的已完成批次，产出放行/拦截结论，
拦截批次转阶段重试器恢复，放行批次进归档存储库。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class QualityGateService(BaseModuleService):
    MODULE = "quality_gate"
    ENTITY = "质量结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["检查批次", "处理阶段", "检查项数", "不通过项", "闸门结论"]
    REQUIRED_FIELDS = ["检查批次", "处理阶段", "检查项数"]
    STATUS_ORDER = ["放行", "部分拦截", "全量拦截"]
    ACTION_RULES = {"放行批次": "部分拦截", "拦截批次": "全量拦截"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：质量检查与拦截分流 ----
    FULL_BLOCK_RATIO = 0.5

    def run_check(self, entry_id: int) -> dict[str, Any]:
        """执行质量检查：统计异常来源数量并得出闸门结论。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "结果不存在"}
        batch_no = str(entry.get("检查批次", ""))
        failed_sources = sum(
            1 for r in store.rows("stage_retry")
            if batch_no in str(r.get("重试编号", "")) and r.get("abnormal")
        )
        items = int(entry.get("检查项数", 0) or 0) or 6
        entry["不通过项"] = failed_sources
        ratio = failed_sources / items
        if ratio >= self.FULL_BLOCK_RATIO:
            entry["闸门结论"] = "全量拦截"
            entry["status"] = "全量拦截"
            entry["abnormal"] = True
        elif failed_sources > 0:
            entry["闸门结论"] = "部分拦截"
            entry["status"] = "部分拦截"
        else:
            entry["闸门结论"] = "放行"
            entry["status"] = "放行"
            entry["pending"] = False
        return {"ok": True, "message": "检查完成", "conclusion": entry["闸门结论"]}

    def route_blocked(self, entry_id: int) -> dict[str, Any]:
        """拦截批次转阶段重试器：写入待重试记录。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") not in ("部分拦截", "全量拦截"):
            return {"ok": False, "message": "结果不存在或未被拦截"}
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-QG-{entry_id}",
            "失败阶段": entry.get("处理阶段", ""),
            "重试策略": "闸门拦截重试",
            "重试次数": 0,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "拦截批次已转重试器"}

    def release_batch(self, entry_id: int) -> dict[str, Any]:
        """放行批次推入归档存储库：生成待归档条目。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "放行":
            return {"ok": False, "message": "结果不存在或未放行"}
        rows = store.rows("archive_store")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "归档标识": f"AR-QG-{entry_id}",
            "文件指纹": "",
            "归档层级": "L2",
            "存储位置": "",
            "保留期限": "5年",
            "status": "待归档",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "放行批次已推入归档"}

    def consume_from_pipeline(self, batch_no: str) -> list[dict[str, Any]]:
        """读取管线编排中指定批次的任务状态。"""
        return [
            {"任务标识": r.get("任务标识", ""), "status": r.get("status", "")}
            for r in store.rows("pipeline_orch")
            if batch_no in (r.get("输入批次", ""), r.get("输出批次", ""))
        ]

    def gate_stats(self) -> dict[str, int]:
        """统计各闸门结论数量，供采集量指标观测。"""
        stats: dict[str, int] = {}
        for row in store.rows(self.MODULE):
            conclusion = str(row.get("闸门结论", "") or row.get("status", "待检查"))
            stats[conclusion] = stats.get(conclusion, 0) + 1
        return stats
