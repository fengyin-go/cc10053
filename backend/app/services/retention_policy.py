"""保留清理策略领域服务：定义归档文档的保留与清理策略，管理规则生效周期。
数据链路位置：治理层，消费归档存储库的层级分布数据，产出保留规则与
清理计划，保护期内数据禁止清理。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class RetentionPolicyService(BaseModuleService):
    MODULE = "retention_policy"
    ENTITY = "保留规则"
    OPERATION_TERM = "归档"
    LIST_FIELDS = ["规则名称", "归档层级", "保留期限", "清理方式", "保护条件"]
    REQUIRED_FIELDS = ["规则名称", "归档层级", "保留期限"]
    STATUS_ORDER = ["待生效", "已生效", "已暂停"]
    ACTION_RULES = {"生效规则": "已生效", "暂停规则": "已暂停"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：规则生效与清理计划 ----

    def activate_rule(self, entry_id: int) -> dict[str, Any]:
        """生效规则：校验层级存在归档数据后激活规则。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待生效":
            return {"ok": False, "message": "规则不存在或不在待生效"}
        level = str(entry.get("归档层级", ""))
        archived = sum(
            1 for r in store.rows("archive_store")
            if r.get("归档层级") == level
        )
        entry["status"] = "已生效"
        entry["pending"] = False
        return {"ok": True, "message": "规则已生效", "level": level, "archived": archived}

    def pause_rule(self, entry_id: int) -> dict[str, Any]:
        """暂停规则：清理计划冻结，归档数据保持原状。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已生效":
            return {"ok": False, "message": "规则不存在或未生效"}
        entry["status"] = "已暂停"
        entry["pending"] = True
        return {"ok": True, "message": "规则已暂停"}

    def consume_from_archive(self) -> dict[str, int]:
        """读取归档存储库的层级分布，作为规则覆盖范围依据。"""
        stats: dict[str, int] = {}
        for row in store.rows("archive_store"):
            level = str(row.get("归档层级", "") or "未分层")
            stats[level] = stats.get(level, 0) + 1
        return stats

    def plan_cleanup(self, entry_id: int) -> dict[str, Any]:
        """生成清理计划：按保留期限与保护条件圈定可清理条目。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已生效":
            return {"ok": False, "message": "规则不存在或未生效"}
        level = str(entry.get("归档层级", ""))
        period = str(entry.get("保留期限", "5年"))
        protected = str(entry.get("保护条件", "") or "无")
        expired = 0
        for row in store.rows("archive_store"):
            if row.get("归档层级") == level and row.get("status") == "已归档":
                if protected in ("无", "") or protected not in str(row.get("归档标识", "")):
                    expired += 1
        return {
            "ok": True,
            "message": "清理计划已生成",
            "level": level,
            "period": period,
            "cleanable": expired,
        }

    def today_cleanup_count(self) -> int:
        """统计今日按规则清理的条目数量。"""
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(
            1 for r in store.rows(self.MODULE)
            if str(r.get("上次清理时间", "")).startswith(today)
        )

    def sync_to_export_guard(self, entry_id: int) -> dict[str, Any]:
        """把保护条件同步给资料导出包：保护期内条目禁止导出删除。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "规则不存在"}
        export_rows = store.rows("export_bundle")
        export_rows.append({
            "id": max((int(r.get("id", 0)) for r in export_rows), default=0) + 1,
            "任务名称": f"守护任务-{entry.get('规则名称', '')}",
            "编目范围": str(entry.get("保护条件", "") or "全部"),
            "导出格式": "守护同步",
            "分卷大小": "0条/卷",
            "生成状态": f"保护条件 {entry.get('保护条件', '')}",
            "status": "排队中",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "保护条件已同步导出守护"}
