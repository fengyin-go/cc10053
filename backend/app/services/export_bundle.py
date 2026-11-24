"""资料导出包领域服务：按编目范围打包导出文档资料，管理分卷与生成状态。
数据链路位置：导出层，消费元数据编目器产出的已编目条目，产出打包分卷
数据，供外部系统下载消费。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class ExportBundleService(BaseModuleService):
    MODULE = "export_bundle"
    ENTITY = "导出任务"
    OPERATION_TERM = "导出"
    LIST_FIELDS = ["任务名称", "编目范围", "导出格式", "分卷大小", "生成状态"]
    REQUIRED_FIELDS = ["任务名称", "编目范围", "导出格式"]
    STATUS_ORDER = ["排队中", "打包中", "已完成", "打包失败"]
    ACTION_RULES = {"开始打包": "打包中", "重试打包": "打包失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：打包导出与分卷生成 ----
    VOLUME_SIZE = 100

    def start_packaging(self, entry_id: int) -> dict[str, Any]:
        """开始打包：按编目范围统计条目数并计算分卷数。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "排队中":
            return {"ok": False, "message": "任务不存在或不在排队中"}
        scope = str(entry.get("编目范围", ""))
        cataloged = sum(
            1 for r in store.rows("meta_catalog")
            if r.get("status") == "已编目" and (not scope or scope in str(r.get("条目标识", "")))
        )
        volumes = max((cataloged + self.VOLUME_SIZE - 1) // self.VOLUME_SIZE, 1)
        entry["分卷大小"] = f"{self.VOLUME_SIZE}条/卷"
        entry["生成状态"] = f"共{volumes}卷"
        entry["status"] = "打包中"
        entry["pending"] = True
        return {"ok": True, "message": "打包已开始", "cataloged": cataloged, "volumes": volumes}

    def finish_packaging(self, entry_id: int) -> dict[str, Any]:
        """完成打包：标记已完成并产出分卷清单。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "打包中":
            return {"ok": False, "message": "任务不存在或不在打包中"}
        entry["status"] = "已完成"
        entry["生成状态"] = f"{entry.get('生成状态', '')} 已就绪"
        entry["pending"] = False
        return {"ok": True, "message": "打包完成", "bundle": entry.get("任务名称", "")}

    def consume_from_catalog(self, scope: str) -> list[dict[str, Any]]:
        """读取编目器中指定范围的已编目条目作为导出内容。"""
        return [
            {"条目标识": r.get("条目标识", ""), "编目等级": r.get("编目等级", "")}
            for r in store.rows("meta_catalog")
            if r.get("status") == "已编目" and (not scope or scope in str(r.get("条目标识", "")))
        ]

    def fail_packaging(self, entry_id: int, reason: str) -> dict[str, Any]:
        """打包失败：写阶段重试记录等待重新打包。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "任务不存在"}
        entry["status"] = "打包失败"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-EB-{entry_id}",
            "失败阶段": "导出打包",
            "重试策略": "分卷重建重试",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"打包已标记失败: {reason}"}

    def retry_packaging(self, entry_id: int) -> dict[str, Any]:
        """重试打包：恢复排队中重新走打包流程。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "打包失败":
            return {"ok": False, "message": "任务不存在或未失败"}
        entry["status"] = "排队中"
        entry["pending"] = True
        entry["abnormal"] = False
        return {"ok": True, "message": "打包任务已重新排队"}
