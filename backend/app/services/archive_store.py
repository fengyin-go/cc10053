"""归档存储库领域服务：把处理完成的文档分层归档保存，管理存储位置与保留期限。
数据链路位置：存储层，消费元数据编目器产出的编目条目，产出分层归档数据，
供全文索引器与保留清理策略消费。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class ArchiveStoreService(BaseModuleService):
    MODULE = "archive_store"
    ENTITY = "归档条目"
    OPERATION_TERM = "归档"
    LIST_FIELDS = ["归档标识", "文件指纹", "归档层级", "存储位置", "保留期限"]
    REQUIRED_FIELDS = ["归档标识", "文件指纹", "归档层级"]
    STATUS_ORDER = ["待归档", "已归档", "归档失败"]
    ACTION_RULES = {"执行归档": "已归档", "重试归档": "归档失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：分层归档与下游消费 ----
    def run_archive(self, entry_id: int) -> dict[str, Any]:
        """执行归档：按层级分配存储位置并标记已归档。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待归档":
            return {"ok": False, "message": "条目不存在或不在待归档"}
        level = str(entry.get("归档层级", "L2") or "L2")
        entry["存储位置"] = f"store/{level}/{entry.get('归档标识', '')}"
        entry["status"] = "已归档"
        entry["pending"] = False
        return {"ok": True, "message": "归档完成", "location": entry["存储位置"]}

    def push_to_index(self, entry_id: int) -> dict[str, Any]:
        """把已归档文档推送给全文索引器构建索引分片。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已归档":
            return {"ok": False, "message": "条目不存在或未完成归档"}
        rows = store.rows("fulltext_index")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "分片标识": f"SHARD-{entry.get('归档标识', '')}",
            "索引词数": 0,
            "文档数": 1,
            "分片状态": "构建中",
            "合并水位": "0",
            "status": "构建中",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给全文索引器"}

    def consume_from_catalog(self, catalog_id: str) -> list[dict[str, Any]]:
        """读取元数据编目器中指定条目的编目等级与标题。"""
        return [
            {"条目标识": r.get("条目标识", ""), "编目等级": r.get("编目等级", "")}
            for r in store.rows("meta_catalog")
            if r.get("条目标识") == catalog_id
        ]

    def apply_retention(self, entry_id: int) -> dict[str, Any]:
        """套用保留清理策略：读取生效规则更新保留期限。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "条目不存在"}
        rule = next(
            (r for r in store.rows("retention_policy")
             if r.get("status") == "已生效" and r.get("归档层级") == entry.get("归档层级")),
            None,
        )
        if rule is None:
            return {"ok": False, "message": "无匹配的生效保留规则"}
        entry["保留期限"] = rule.get("保留期限", "5年")
        return {"ok": True, "message": "保留期限已套用", "period": entry["保留期限"]}

    def fail_archive(self, entry_id: int, reason: str) -> dict[str, Any]:
        """归档失败：写阶段重试记录等待恢复。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "条目不存在"}
        entry["status"] = "归档失败"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-AS-{entry_id}",
            "失败阶段": "归档",
            "重试策略": "存储迁移重试",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"归档已标记失败: {reason}"}

    def stats_by_level(self) -> dict[str, int]:
        """按归档层级统计条目数量，供导出与清理策略消费。"""
        stats: dict[str, int] = {}
        for row in store.rows(self.MODULE):
            level = str(row.get("归档层级", "") or "未分层")
            stats[level] = stats.get(level, 0) + 1
        return stats
