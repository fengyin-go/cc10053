"""版面重建器领域服务：把抽取结果重建为结构化版面，恢复阅读顺序与表格结构。
数据链路位置：结构化层，消费 OCR 抽取器产出的抽取文本，产出带阅读顺序的
版面结构数据，供文本清洗器与元数据编目器消费。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class LayoutRebuildService(BaseModuleService):
    MODULE = "layout_rebuild"
    ENTITY = "版面结构"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["文件指纹", "版面块数", "阅读顺序", "表格块数", "重建质量"]
    REQUIRED_FIELDS = ["文件指纹", "版面块数", "阅读顺序"]
    STATUS_ORDER = ["待重建", "已重建", "重建失败"]
    ACTION_RULES = {"执行重建": "已重建", "重试重建": "重建失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：版面重建与下游派发 ----

    def run_rebuild(self, entry_id: int) -> dict[str, Any]:
        """执行重建：计算版面块数、表格块数与重建质量。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待重建":
            return {"ok": False, "message": "记录不存在或不在待重建"}
        blocks = int(entry.get("版面块数", 0) or 0) or 12
        entry["版面块数"] = blocks
        entry["表格块数"] = max(blocks // 6, 1)
        entry["重建质量"] = "0.91"
        entry["status"] = "已重建"
        entry["pending"] = False
        return {"ok": True, "message": "版面已重建", "blocks": blocks}

    def dispatch_to_clean(self, entry_id: int) -> dict[str, Any]:
        """把已重建版面推送给文本清洗器生成清洗任务。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已重建":
            return {"ok": False, "message": "记录不存在或未完成重建"}
        rows = store.rows("text_clean")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "文件指纹": entry.get("文件指纹", ""),
            "清洗规则集": "基础去噪规则集",
            "乱码标记": "0",
            "清洗产出": "",
            "字符损耗率": "0.02",
            "status": "待清洗",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给文本清洗器"}

    def dispatch_to_catalog(self, entry_id: int) -> dict[str, Any]:
        """从版面结构提取元数据线索，写入元数据编目器。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已重建":
            return {"ok": False, "message": "记录不存在或未完成重建"}
        rows = store.rows("meta_catalog")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "条目标识": f"CAT-{entry.get('文件指纹', '')}",
            "文档标题": f"文档 {entry.get('文件指纹', '')}",
            "作者机构": "版面首块提取",
            "成文日期": datetime.now(timezone.utc).date().isoformat(),
            "编目等级": "二级",
            "status": "待编目",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "元数据线索已写入编目器"}

    def consume_from_ocr(self, fingerprint: str) -> dict[str, Any]:
        """读取 OCR 抽取器中该指纹的抽取文本与置信度。"""
        row = next(
            (r for r in store.rows("ocr_extract") if r.get("文件指纹") == fingerprint), None
        )
        if row is None:
            return {"ok": False, "message": "抽取结果不存在", "chars": 0}
        return {
            "ok": True,
            "message": "已读取抽取结果",
            "chars": len(str(row.get("抽取文本", ""))),
            "confidence": row.get("置信度均值", "0"),
        }

    def fail_rebuild(self, entry_id: int, reason: str) -> dict[str, Any]:
        """重建失败：写阶段重试记录等待断点恢复。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "记录不存在"}
        entry["status"] = "重建失败"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-LR-{entry_id}",
            "失败阶段": "版面重建",
            "重试策略": "顺序模型重试",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"重建已标记失败: {reason}"}
