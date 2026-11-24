"""重复文档检测领域服务：按指纹与相似度识别重复文档，管理查重批次与判定阈值。
数据链路位置：去重层，消费格式识别器产出的文件指纹集合，产出相似文档对，
避免重复内容流入归档存储库。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class DupDocumentService(BaseModuleService):
    MODULE = "dup_document"
    ENTITY = "查重结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["查重批次", "候选组数", "相似文档对", "判定阈值", "查重方法"]
    REQUIRED_FIELDS = ["查重批次", "候选组数", "相似文档对"]
    STATUS_ORDER = ["查重中", "已完成", "查重失败"]
    ACTION_RULES = {"开始查重": "已完成", "重试查重": "查重失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：指纹查重与相似判定 ----

    SIM_THRESHOLD = 0.92

    def run_dedup(self, entry_id: int) -> dict[str, Any]:
        """执行查重：按指纹前缀聚类相似文档对并回写候选组数。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "查重中":
            return {"ok": False, "message": "批次不存在或不在查重中"}
        fingerprints = [
            str(r.get("文件指纹", "")) for r in store.rows("format_detect")
        ]
        groups: dict[str, list[str]] = {}
        for fp in fingerprints:
            prefix = fp.rsplit("-", 1)[0] if "-" in fp else fp[:6]
            groups.setdefault(prefix, []).append(fp)
        similar = sum(len(v) - 1 for v in groups.values() if len(v) > 1)
        entry["候选组数"] = sum(1 for v in groups.values() if len(v) > 1)
        entry["相似文档对"] = similar
        entry["判定阈值"] = str(self.SIM_THRESHOLD)
        entry["查重方法"] = "指纹前缀聚类"
        entry["status"] = "已完成"
        entry["pending"] = False
        return {"ok": True, "message": "查重完成", "pairs": similar}

    def mark_duplicates(self, entry_id: int) -> dict[str, Any]:
        """把相似文档对中的重复项在归档存储库标记为重复。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已完成":
            return {"ok": False, "message": "批次不存在或未完成查重"}
        marked = 0
        for archived in store.rows("archive_store"):
            if str(archived.get("归档标识", "")).endswith("-D"):
                archived["abnormal"] = True
                marked += 1
        return {"ok": True, "message": "重复项已标记", "marked": marked}

    def consume_from_format(self) -> list[dict[str, Any]]:
        """读取格式识别器全部待识别与已识别记录的指纹集合。"""
        return [
            {"文件指纹": r.get("文件指纹", ""), "status": r.get("status", "")}
            for r in store.rows("format_detect")
        ]

    def retry_dedup(self, entry_id: int) -> dict[str, Any]:
        """查重失败重试：恢复为查重中。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "查重失败":
            return {"ok": False, "message": "批次不存在或未失败"}
        entry["status"] = "查重中"
        entry["pending"] = True
        entry["abnormal"] = False
        return {"ok": True, "message": "查重已恢复进行中"}

    def report_dup_metrics(self, entry_id: int) -> dict[str, Any]:
        """把查重结果上报管线编排，供编排统计拦截量。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "批次不存在"}
        orch_rows = store.rows("pipeline_orch")
        orch_rows.append({
            "id": max((int(r.get("id", 0)) for r in orch_rows), default=0) + 1,
            "任务标识": f"ORCH-DEDUP-{entry_id}",
            "处理阶段": "查重",
            "输入批次": entry.get("查重批次", ""),
            "输出批次": f"{entry.get('查重批次', '')}-deduped",
            "编排状态": "去重完成",
            "status": "已完成",
            "pending": False,
            "abnormal": False,
        })
        return {"ok": True, "message": "查重结果已上报编排"}
