"""编目复核队列领域服务：人工复核低置信度的编目与分类结果，管理办结流转。
数据链路位置：复核层，消费元数据编目器与分类器写入的待复核记录，产出
复核结论，通过后回流编目器完成编目，驳回后转阶段重试器。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class CatalogReviewService(BaseModuleService):
    MODULE = "catalog_review"
    ENTITY = "复核记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["记录编号", "编目条目", "复核结论", "复核角色", "复核时间"]
    REQUIRED_FIELDS = ["记录编号", "编目条目", "复核结论"]
    STATUS_ORDER = ["待复核", "已通过", "已驳回"]
    ACTION_RULES = {"通过记录": "已通过", "驳回记录": "已驳回"}
    NEGATIVE_ACTIONS = ["驳回记录"]

    # ---- 业务扩展：人工复核与办结回流 ----
    def approve_record(self, entry_id: int, reviewer: str) -> dict[str, Any]:
        """通过复核：回写复核角色与时间，回流编目器确认编目。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待复核":
            return {"ok": False, "message": "记录不存在或不在待复核"}
        entry["复核角色"] = reviewer or "编目复核员"
        entry["复核时间"] = datetime.now(timezone.utc).isoformat()
        entry["status"] = "已通过"
        entry["pending"] = False
        catalog_rows = store.rows("meta_catalog")
        catalog_rows.append({
            "id": max((int(r.get("id", 0)) for r in catalog_rows), default=0) + 1,
            "条目标识": f"CAT-RV-{entry_id}",
            "文档标题": str(entry.get("编目条目", "")),
            "作者机构": "复核确认",
            "成文日期": datetime.now(timezone.utc).date().isoformat(),
            "编目等级": "一级",
            "status": "待编目",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "复核已通过并回流编目器"}

    def reject_record(self, entry_id: int, reason: str) -> dict[str, Any]:
        """驳回复核：写阶段重试记录等待重新处理。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待复核":
            return {"ok": False, "message": "记录不存在或不在待复核"}
        entry["复核结论"] = f"驳回: {reason}"
        entry["复核时间"] = datetime.now(timezone.utc).isoformat()
        entry["status"] = "已驳回"
        entry["abnormal"] = True
        entry["pending"] = False
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-CR-{entry_id}",
            "失败阶段": "复核",
            "重试策略": "驳回回流重处理",
            "重试次数": 0,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "复核已驳回并转重试器"}

    def consume_from_classify(self) -> list[dict[str, Any]]:
        """读取分类器中全部置信不足的待复核记录。"""
        return [
            {"文件指纹": r.get("文件指纹", ""), "置信度": r.get("分类置信度", "0")}
            for r in store.rows("doc_classify")
            if r.get("status") == "置信不足"
        ]

    def today_done(self) -> dict[str, Any]:
        """统计今日办结数量，供采集量指标观测。"""
        today = datetime.now(timezone.utc).date().isoformat()
        done = sum(
            1 for r in store.rows(self.MODULE)
            if str(r.get("复核时间", "")).startswith(today)
            and r.get("status") in ("已通过", "已驳回")
        )
        pending = sum(1 for r in store.rows(self.MODULE) if r.get("status") == "待复核")
        return {"today_done": done, "pending": pending}

    def load_pending(self, role: str | None = None) -> list[dict[str, Any]]:
        """加载待复核队列，可按复核角色过滤。"""
        rows = [dict(r) for r in store.rows(self.MODULE) if r.get("status") == "待复核"]
        if role:
            rows = [r for r in rows if r.get("复核角色") == role]
        return rows
