"""格式识别器领域服务：识别文档格式并路由到对应解析分支，管理识别置信度。
数据链路位置：识别路由层，消费采集批次推送的文件指纹，产出带处理分支的
格式记录，供 OCR 抽取器按分支领取任务。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class FormatDetectService(BaseModuleService):
    MODULE = "format_detect"
    ENTITY = "格式记录"
    OPERATION_TERM = "解析"
    LIST_FIELDS = ["文件指纹", "识别格式", "置信度", "识别版本", "处理分支"]
    REQUIRED_FIELDS = ["文件指纹", "识别格式", "置信度"]
    STATUS_ORDER = ["已识别", "待识别", "识别失败"]
    ACTION_RULES = {"重新识别": "已识别", "转人工": "识别失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：格式识别与分支路由 ----

    def detect_format(self, entry_id: int) -> dict[str, Any]:
        """识别文件格式：按指纹后缀推断格式、置信度与处理分支。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": f"{self.ENTITY} {entry_id} 不存在"}
        fingerprint = str(entry.get("文件指纹", ""))
        matched_fmt, branch, confidence = "PDF", "pdf解析分支", "0.96"
        branch_map = {
            "PDF": "pdf解析分支", "OFD": "ofd解析分支", "扫描件": "ocr抽取分支",
            "DOCX": "docx解析分支", "XLSX": "表格解析分支",
        }
        for fmt, br in branch_map.items():
            if fmt.casefold() in fingerprint.casefold():
                matched_fmt, branch, confidence = fmt, br, "0.98"
                break
        entry["识别格式"] = matched_fmt
        entry["置信度"] = confidence
        entry["识别版本"] = "fmt-v2.1"
        entry["处理分支"] = branch
        entry["status"] = "已识别"
        entry["pending"] = False
        return {"ok": True, "message": "格式已识别", "branch": branch}

    def dispatch_to_ocr(self, entry_id: int) -> dict[str, Any]:
        """把扫描件分支的格式记录推送给 OCR 抽取器生成抽取任务。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("处理分支") != "ocr抽取分支":
            return {"ok": False, "message": "记录不存在或不属于OCR抽取分支"}
        rows = store.rows("ocr_extract")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "文件指纹": entry.get("文件指纹", ""),
            "抽取文本": "",
            "置信度均值": "0",
            "页码范围": "1-10",
            "抽取引擎版本": "ocr-v3",
            "status": "待抽取",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送OCR抽取队列"}

    def mark_manual(self, entry_id: int, reason: str) -> dict[str, Any]:
        """识别失败转人工：写入编目复核队列。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "记录不存在"}
        entry["status"] = "识别失败"
        entry["abnormal"] = True
        rows = store.rows("catalog_review")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "记录编号": f"FD-{entry_id}",
            "编目条目": f"格式识别 {entry.get('文件指纹', '')}",
            "复核结论": reason or "识别失败转人工复核",
            "复核角色": "格式复核员",
            "复核时间": datetime.now(timezone.utc).isoformat(),
            "status": "待复核",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已转人工复核"}

    def consume_from_ingest(self, batch_no: str) -> list[dict[str, Any]]:
        """读取采集批次中指定批次的完成状态与文件数量。"""
        return [
            dict(b) for b in store.rows("file_ingest")
            if b.get("批次编号") == batch_no and b.get("status") == "已完成"
        ]

    def stats_by_branch(self) -> dict[str, int]:
        """按处理分支统计识别记录数量，供管线编排消费。"""
        stats: dict[str, int] = {}
        for row in store.rows(self.MODULE):
            branch = str(row.get("处理分支", "") or "未路由")
            stats[branch] = stats.get(branch, 0) + 1
        return stats
