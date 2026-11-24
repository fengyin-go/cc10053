"""文档分类器领域服务：按体系对文档进行自动分类，管理分类置信度与多类标记。
数据链路位置：分类层，消费文本清洗器产出的清洗文本，产出带类别编码的
分类结果，置信不足时流转到编目复核队列。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class DocClassifyService(BaseModuleService):
    MODULE = "doc_classify"
    ENTITY = "分类结果"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["文件指纹", "分类体系", "类别编码", "分类置信度", "多类标记"]
    REQUIRED_FIELDS = ["文件指纹", "分类体系", "类别编码"]
    STATUS_ORDER = ["待分类", "已分类", "置信不足"]
    ACTION_RULES = {"执行分类": "已分类", "转人工": "置信不足"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：自动分类与人工流转 ----

    CONF_THRESHOLD = 0.85
    CATEGORY_HINTS = {"报告": "F2", "通知": "G4", "纪要": "C9", "方案": "B1"}

    def run_classify(self, entry_id: int) -> dict[str, Any]:
        """执行分类：按指纹关键词推断类别编码与置信度。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待分类":
            return {"ok": False, "message": "记录不存在或不在待分类"}
        fingerprint = str(entry.get("文件指纹", ""))
        code, confidence = "Z5", "0.72"
        for hint, cat in self.CATEGORY_HINTS.items():
            if hint in fingerprint:
                code, confidence = cat, "0.92"
                break
        entry["类别编码"] = code
        entry["分类置信度"] = confidence
        entry["status"] = "已分类" if float(confidence) >= self.CONF_THRESHOLD else "置信不足"
        entry["pending"] = entry["status"] == "置信不足"
        return {"ok": True, "message": "分类完成", "code": code, "confidence": confidence}

    def route_low_confidence(self, entry_id: int) -> dict[str, Any]:
        """置信不足转人工：写入编目复核队列。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "置信不足":
            return {"ok": False, "message": "记录不存在或置信充足"}
        rows = store.rows("catalog_review")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "记录编号": f"DC-{entry_id}",
            "编目条目": f"分类复核 {entry.get('文件指纹', '')}",
            "复核结论": f"置信度 {entry.get('分类置信度', '0')} 低于阈值",
            "复核角色": "分类复核员",
            "复核时间": datetime.now(timezone.utc).isoformat(),
            "status": "待复核",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已转人工复核"}

    def consume_from_clean(self, fingerprint: str) -> dict[str, Any]:
        """读取清洗结果中该指纹的清洗产出与损耗率。"""
        row = next(
            (r for r in store.rows("text_clean") if r.get("文件指纹") == fingerprint), None
        )
        if row is None:
            return {"ok": False, "message": "清洗结果不存在", "chars": 0}
        return {
            "ok": True,
            "message": "已读取清洗结果",
            "chars": len(str(row.get("清洗产出", ""))),
            "loss_rate": row.get("字符损耗率", "0"),
        }

    def push_to_catalog(self, entry_id: int) -> dict[str, Any]:
        """把已分类结果作为编目线索推送给元数据编目器。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已分类":
            return {"ok": False, "message": "记录不存在或未完成分类"}
        rows = store.rows("meta_catalog")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "条目标识": f"CAT-{entry.get('文件指纹', '')}",
            "文档标题": f"分类文档 {entry.get('文件指纹', '')}",
            "作者机构": "分类体系提取",
            "成文日期": datetime.now(timezone.utc).date().isoformat(),
            "编目等级": "三级",
            "status": "待编目",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给编目器"}

    def multi_label_stats(self) -> dict[str, int]:
        """统计多类标记分布，供管线编排消费。"""
        stats: dict[str, int] = {}
        for row in store.rows(self.MODULE):
            label = str(row.get("多类标记", "") or "单类")
            stats[label] = stats.get(label, 0) + 1
        return stats
