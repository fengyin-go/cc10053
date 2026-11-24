"""文档源注册领域服务：管理多类型文档资料采集来源的登记、验证与停用。
数据链路位置：采集接入层，是文档资料进入平台的第一入口，负责把验证通过的
文档源配置传递给采集批次，并把源状态同步到采集量指标。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class DocSourceService(BaseModuleService):
    MODULE = "doc_source"
    ENTITY = "文档源"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["源标识", "源名称", "源类型", "接入方式", "采集范围"]
    REQUIRED_FIELDS = ["源标识", "源名称", "源类型"]
    STATUS_ORDER = ["待验证", "已验证", "已停用"]
    ACTION_RULES = {"验证源": "已验证", "停用源": "已停用"}
    NEGATIVE_ACTIONS = ["停用源"]

    # ---- 业务扩展：源验证与采集接入 ----
    def verify_source(self, entry_id: int) -> dict[str, Any]:
        """验证文档源可连通性：检查接入方式与采集范围配置完整。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": f"{self.ENTITY} {entry_id} 不存在"}
        access = entry.get("接入方式", "")
        scope = entry.get("采集范围", "")
        if not access or not scope:
            entry["abnormal"] = True
            return {"ok": False, "message": "缺少接入方式或采集范围配置"}
        entry["status"] = "已验证"
        entry["pending"] = True
        entry["abnormal"] = False
        return {"ok": True, "message": f"文档源 {entry.get('源名称', '')} 验证通过"}

    def create_ingest_batch(self, entry_id: int, file_count: int) -> dict[str, Any]:
        """基于已验证文档源创建采集批次，写入采集器模块。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已验证":
            return {"ok": False, "message": "文档源不存在或未验证"}
        rows = store.rows("file_ingest")
        batch_no = f"FILE-{datetime.now(timezone.utc).strftime('%m%d%H%M%S')}"
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "批次编号": batch_no,
            "文档源": entry.get("源名称", ""),
            "文件数量": max(file_count, 1),
            "批次大小": f"{max(file_count, 1) * 1024}KB",
            "采集时间": datetime.now(timezone.utc).isoformat(),
            "status": "进行中",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "采集批次已创建", "batch_no": batch_no}

    def disable_source(self, entry_id: int) -> dict[str, Any]:
        """停用文档源并把进行中的采集批次标记为批次失败。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "文档源不存在"}
        entry["status"] = "已停用"
        entry["abnormal"] = True
        halted = 0
        for batch in store.rows("file_ingest"):
            if batch.get("文档源") == entry.get("源名称") and batch.get("status") == "进行中":
                batch["status"] = "批次失败"
                batch["abnormal"] = True
                halted += 1
        return {"ok": True, "message": "文档源已停用", "halted_batches": halted}

    def report_source_metrics(self, entry_id: int) -> dict[str, Any]:
        """把文档源的采集量上报到采集量指标快照。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "文档源不存在"}
        rows = store.rows("ingest_metrics")
        total = sum(
            int(b.get("文件数量", 0) or 0)
            for b in store.rows("file_ingest")
            if b.get("文档源") == entry.get("源名称")
        )
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "统计时间": datetime.now(timezone.utc).isoformat(),
            "文档源": entry.get("源名称", ""),
            "采集量": total,
            "抽取量": 0,
            "归档量": 0,
            "status": "正常",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "源采集量已上报", "total": total}

    def pending_format_records(self, entry_id: int) -> list[dict[str, Any]]:
        """列出该文档源产出、仍待识别的格式记录。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return []
        batches = [
            b.get("批次编号") for b in store.rows("file_ingest")
            if b.get("文档源") == entry.get("源名称")
        ]
        return [
            r for r in store.rows("format_detect")
            if r.get("文件指纹", "") in batches and r.get("status") == "待识别"
        ]
