"""OCR抽取器领域服务：对扫描件执行文字识别抽取，产出带置信度的全文文本。
数据链路位置：抽取层，消费格式识别器路由来的扫描件指纹，把抽取文本交给
版面重建器重建结构，并同步抽取量到采集量指标。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class OcrExtractService(BaseModuleService):
    MODULE = "ocr_extract"
    ENTITY = "抽取结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["文件指纹", "抽取文本", "置信度均值", "页码范围", "抽取引擎版本"]
    REQUIRED_FIELDS = ["文件指纹", "抽取文本", "置信度均值"]
    STATUS_ORDER = ["待抽取", "已抽取", "抽取失败"]
    ACTION_RULES = {"执行抽取": "已抽取", "重试抽取": "抽取失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：OCR抽取与下游重建 ----

    def run_extract(self, entry_id: int) -> dict[str, Any]:
        """执行抽取：产出样例抽取文本与置信度均值，标记已抽取。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待抽取":
            return {"ok": False, "message": "记录不存在或不在待抽取"}
        text = entry.get("抽取文本", "")
        sampled = text if text else f"OCR识别文本 {entry.get('文件指纹', '')} 第1页内容样例"
        entry["抽取文本"] = sampled
        entry["置信度均值"] = "0.93"
        entry["抽取引擎版本"] = "ocr-v3.2"
        entry["status"] = "已抽取"
        entry["pending"] = False
        return {"ok": True, "message": "抽取完成", "chars": len(sampled)}

    def dispatch_to_layout(self, entry_id: int) -> dict[str, Any]:
        """把已抽取结果推送给版面重建器生成版面结构任务。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已抽取":
            return {"ok": False, "message": "记录不存在或未完成抽取"}
        rows = store.rows("layout_rebuild")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "文件指纹": entry.get("文件指纹", ""),
            "版面块数": 12,
            "阅读顺序": "标题-段落-表格",
            "表格块数": 2,
            "重建质量": "0.90",
            "status": "待重建",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给版面重建器"}

    def fail_extract(self, entry_id: int, reason: str) -> dict[str, Any]:
        """抽取失败：写阶段重试记录并标记异常。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "记录不存在"}
        entry["status"] = "抽取失败"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-OCR-{entry_id}",
            "失败阶段": "抽取",
            "重试策略": "引擎降级重试",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"抽取已标记失败: {reason}"}

    def consume_from_format(self, fingerprint: str) -> dict[str, Any]:
        """读取格式识别器中该指纹的识别分支与置信度。"""
        row = next(
            (r for r in store.rows("format_detect") if r.get("文件指纹") == fingerprint), None
        )
        if row is None:
            return {"ok": False, "message": "格式记录不存在", "branch": ""}
        return {
            "ok": True,
            "message": "已读取格式记录",
            "branch": row.get("处理分支", ""),
            "confidence": row.get("置信度", "0"),
        }

    def report_extract_metrics(self, entry_id: int) -> dict[str, Any]:
        """把抽取完成量上报采集量指标。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "记录不存在"}
        rows = store.rows("ingest_metrics")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "统计时间": datetime.now(timezone.utc).isoformat(),
            "文档源": "",
            "采集量": 0,
            "抽取量": 1,
            "归档量": 0,
            "status": "正常",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "抽取量已上报"}
