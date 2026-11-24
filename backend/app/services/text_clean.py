"""文本清洗器领域服务：清洗OCR文本的乱码与噪声，控制字符损耗率。
数据链路位置：质量层，消费版面重建器产出的结构文本，产出干净的清洗
文本，供文档分类器与语种检测器消费。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class TextCleanService(BaseModuleService):
    MODULE = "text_clean"
    ENTITY = "清洗结果"
    OPERATION_TERM = "清洗"
    LIST_FIELDS = ["文件指纹", "清洗规则集", "乱码标记", "清洗产出", "字符损耗率"]
    REQUIRED_FIELDS = ["文件指纹", "清洗规则集", "乱码标记"]
    STATUS_ORDER = ["待清洗", "已清洗", "清洗异常"]
    ACTION_RULES = {"执行清洗": "已清洗", "重试清洗": "清洗异常"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：文本清洗与下游派发 ----
    NOISE_CHARS = ("", "□", "\ufffd")

    def run_clean(self, entry_id: int) -> dict[str, Any]:
        """执行清洗：去除乱码字符，计算字符损耗率。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待清洗":
            return {"ok": False, "message": "记录不存在或不在待清洗"}
        raw = str(entry.get("清洗产出", "") or "样例文本\ufffd待清洗内容")
        noise = sum(raw.count(c) for c in self.NOISE_CHARS)
        cleaned = "".join(c for c in raw if c not in self.NOISE_CHARS)
        entry["乱码标记"] = str(noise)
        entry["清洗产出"] = cleaned
        entry["字符损耗率"] = f"{(noise / max(len(raw), 1)):.4f}"
        entry["status"] = "已清洗"
        entry["pending"] = False
        return {"ok": True, "message": "清洗完成", "noise": noise, "chars": len(cleaned)}

    def dispatch_to_classify(self, entry_id: int) -> dict[str, Any]:
        """把已清洗文本推送给文档分类器生成分类任务。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已清洗":
            return {"ok": False, "message": "记录不存在或未完成清洗"}
        rows = store.rows("doc_classify")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "文件指纹": entry.get("文件指纹", ""),
            "分类体系": "中图法",
            "类别编码": "",
            "分类置信度": "0",
            "多类标记": "",
            "status": "待分类",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给文档分类器"}

    def dispatch_to_lang(self, entry_id: int) -> dict[str, Any]:
        """把已清洗文本推送给语种检测器生成检测任务。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已清洗":
            return {"ok": False, "message": "记录不存在或未完成清洗"}
        rows = store.rows("lang_detect")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "文件指纹": entry.get("文件指纹", ""),
            "主语种": "",
            "混合语种": "",
            "检测置信度": "0",
            "编码转换": "UTF-8",
            "status": "待检测",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给语种检测器"}

    def consume_from_layout(self, fingerprint: str) -> dict[str, Any]:
        """读取版面重建器中该指纹的版面块数与阅读顺序。"""
        row = next(
            (r for r in store.rows("layout_rebuild") if r.get("文件指纹") == fingerprint), None
        )
        if row is None:
            return {"ok": False, "message": "版面结构不存在", "blocks": 0}
        return {
            "ok": True,
            "message": "已读取版面结构",
            "blocks": int(row.get("版面块数", 0) or 0),
            "order": row.get("阅读顺序", ""),
        }

    def flag_anomaly(self, entry_id: int, reason: str) -> dict[str, Any]:
        """清洗异常：标记异常并写阶段重试记录。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "记录不存在"}
        entry["status"] = "清洗异常"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-TC-{entry_id}",
            "失败阶段": "清洗",
            "重试策略": "规则降级重试",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"清洗已标记异常: {reason}"}
