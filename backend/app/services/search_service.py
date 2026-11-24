"""检索查询服务领域服务：提供文档全文检索的查询服务，管理查询记录与慢查询。
数据链路位置：查询层，消费全文索引器产出的已构建分片，产出查询记录与
命中文档数，供采集量指标观测检索健康度。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class SearchServiceService(BaseModuleService):
    MODULE = "search_service"
    ENTITY = "查询记录"
    OPERATION_TERM = "查询"
    LIST_FIELDS = ["查询标识", "查询词", "命中文档数", "响应耗时", "查询用户"]
    REQUIRED_FIELDS = ["查询标识", "查询词", "命中文档数"]
    STATUS_ORDER = ["已响应", "慢查询", "查询失败"]
    ACTION_RULES = {"标记慢查": "慢查询", "重试查询": "查询失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：查询执行与慢查治理 ----

    SLOW_MS = 500

    def run_query(self, entry_id: int) -> dict[str, Any]:
        """执行查询：基于已构建分片统计命中文档数与响应耗时。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "查询记录不存在"}
        keyword = str(entry.get("查询词", ""))
        shards = [
            r for r in store.rows("fulltext_index")
            if r.get("status") == "已构建"
        ]
        hits = sum(
            int(r.get("文档数", 0) or 0) for r in shards
            if keyword.casefold() in str(r.get("分片标识", "")).casefold()
        )
        elapsed = 120 + len(keyword) * 8
        entry["命中文档数"] = hits
        entry["响应耗时"] = f"{elapsed}ms"
        entry["status"] = "慢查询" if elapsed > self.SLOW_MS else "已响应"
        entry["pending"] = entry["status"] == "慢查询"
        return {"ok": True, "message": "查询完成", "hits": hits, "elapsed_ms": elapsed}

    def mark_slow(self, entry_id: int) -> dict[str, Any]:
        """标记慢查询：写阶段重试记录驱动索引优化。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "慢查询":
            return {"ok": False, "message": "记录不存在或不是慢查询"}
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-QS-{entry_id}",
            "失败阶段": "查询",
            "重试策略": "索引分片重排",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "慢查询已标记并转优化"}

    def consume_from_index(self, keyword: str) -> list[dict[str, Any]]:
        """读取全文索引器中包含关键词的已构建分片。"""
        return [
            {"分片标识": r.get("分片标识", ""), "文档数": r.get("文档数", 0)}
            for r in store.rows("fulltext_index")
            if r.get("status") == "已构建"
            and keyword.casefold() in str(r.get("分片标识", "")).casefold()
        ]

    def report_query_metrics(self, entry_id: int) -> dict[str, Any]:
        """把查询量上报采集量指标，观测检索健康度。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "查询记录不存在"}
        rows = store.rows("ingest_metrics")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "统计时间": datetime.now(timezone.utc).isoformat(),
            "文档源": "",
            "采集量": 0,
            "抽取量": 0,
            "归档量": int(entry.get("命中文档数", 0) or 0),
            "status": "正常",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "查询指标已上报"}

    def slow_query_stats(self) -> dict[str, Any]:
        """统计慢查询占比，供管线编排优化。"""
        rows = store.rows(self.MODULE)
        slow = sum(1 for r in rows if r.get("status") == "慢查询")
        return {"total": len(rows), "slow": slow, "ratio": slow / max(len(rows), 1)}
