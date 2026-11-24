"""全文索引器领域服务：构建文档全文检索索引分片，管理索引词数与合并水位。
数据链路位置：检索层，消费归档存储库与语种检测器产出的文档数据，产出
可查询的索引分片，供检索查询服务消费。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class FulltextIndexService(BaseModuleService):
    MODULE = "fulltext_index"
    ENTITY = "索引分片"
    OPERATION_TERM = "合并"
    LIST_FIELDS = ["分片标识", "索引词数", "文档数", "分片状态", "合并水位"]
    REQUIRED_FIELDS = ["分片标识", "索引词数", "文档数"]
    STATUS_ORDER = ["构建中", "已构建", "待合并"]
    ACTION_RULES = {"构建索引": "已构建", "合并分片": "待合并"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：分片构建与合并水位 ----

    MERGE_WATERMARK_STEP = 10

    def build_shard(self, entry_id: int) -> dict[str, Any]:
        """构建索引分片：统计文档数与索引词数，推进构建状态。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "构建中":
            return {"ok": False, "message": "分片不存在或不在构建中"}
        docs = int(entry.get("文档数", 0) or 0) or 1
        entry["索引词数"] = docs * 350
        entry["分片状态"] = "已构建"
        entry["status"] = "已构建"
        entry["pending"] = False
        return {"ok": True, "message": "分片已构建", "words": entry["索引词数"]}

    def merge_shards(self) -> dict[str, Any]:
        """合并待合并分片：汇总文档数并推进合并水位。"""
        pending = [
            r for r in store.rows(self.MODULE) if r.get("status") == "待合并"
        ]
        if not pending:
            return {"ok": False, "message": "无待合并分片"}
        total_docs = sum(int(r.get("文档数", 0) or 0) for r in pending)
        watermark = 0
        for r in pending:
            r["合并水位"] = str(self.MERGE_WATERMARK_STEP)
            r["status"] = "已构建"
            r["分片状态"] = "已合并"
            r["pending"] = False
            watermark = max(watermark, int(r.get("合并水位", "0") or 0))
        return {
            "ok": True,
            "message": "分片已合并",
            "merged": len(pending),
            "docs": total_docs,
            "watermark": watermark,
        }

    def consume_from_archive(self) -> dict[str, Any]:
        """读取归档存储库已归档条目数量，作为索引文档来源。"""
        rows = [r for r in store.rows("archive_store") if r.get("status") == "已归档"]
        return {
            "ok": True,
            "message": "已读取归档条目",
            "archived": len(rows),
            "levels": sorted({str(r.get("归档层级", "")) for r in rows}),
        }

    def consume_from_lang(self) -> dict[str, int]:
        """读取语种检测器的主语种分布，确定分词策略。"""
        stats: dict[str, int] = {}
        for row in store.rows("lang_detect"):
            if row.get("status") == "已检测":
                lang = str(row.get("主语种", "") or "未知")
                stats[lang] = stats.get(lang, 0) + 1
        return stats

    def searchable_docs(self, keyword: str) -> list[dict[str, Any]]:
        """提供可检索文档列表给检索查询服务，返回包含关键词的分片。"""
        return [
            {"分片标识": r.get("分片标识", ""), "文档数": r.get("文档数", 0)}
            for r in store.rows(self.MODULE)
            if r.get("status") == "已构建" and keyword.casefold() in str(r.get("分片标识", "")).casefold()
        ]
