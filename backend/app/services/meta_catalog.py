"""元数据编目器领域服务：从文档内容与版面提取结构化元数据，管理编目等级。
数据链路位置：编目层，消费版面重建器与分类器产出的结构线索，产出带编目
等级的条目数据，供归档存储库与资料导出包消费。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class MetaCatalogService(BaseModuleService):
    MODULE = "meta_catalog"
    ENTITY = "编目条目"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["条目标识", "文档标题", "作者机构", "成文日期", "编目等级"]
    REQUIRED_FIELDS = ["条目标识", "文档标题", "作者机构"]
    STATUS_ORDER = ["待编目", "已编目", "编目冲突"]
    ACTION_RULES = {"执行编目": "已编目", "解决冲突": "编目冲突"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：编目执行与冲突处理 ----

    LEVEL_RULES = {"一级": 90, "二级": 75, "三级": 60}

    def run_catalog(self, entry_id: int) -> dict[str, Any]:
        """执行编目：按标题与作者机构完整度评定编目等级。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待编目":
            return {"ok": False, "message": "条目不存在或不在待编目"}
        score = 0
        if str(entry.get("文档标题", "")).strip():
            score += 45
        if str(entry.get("作者机构", "")).strip():
            score += 35
        if str(entry.get("成文日期", "")).strip():
            score += 20
        level = "一级" if score >= 90 else "二级" if score >= 60 else "三级"
        entry["编目等级"] = level
        entry["status"] = "已编目"
        entry["pending"] = False
        return {"ok": True, "message": "编目完成", "level": level, "score": score}

    def detect_conflict(self, entry_id: int) -> dict[str, Any]:
        """检测同标题条目冲突：发现重复标题写入复核队列。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "条目不存在"}
        title = entry.get("文档标题", "")
        conflicts = [
            r for r in store.rows(self.MODULE)
            if r.get("id") != entry.get("id") and r.get("文档标题") == title and r.get("status") == "已编目"
        ]
        if not conflicts:
            return {"ok": True, "message": "无冲突", "conflicts": 0}
        entry["status"] = "编目冲突"
        entry["abnormal"] = True
        rows = store.rows("catalog_review")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "记录编号": f"MC-{entry_id}",
            "编目条目": title,
            "复核结论": f"同标题冲突 {len(conflicts)} 条",
            "复核角色": "编目复核员",
            "复核时间": datetime.now(timezone.utc).isoformat(),
            "status": "待复核",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "发现编目冲突", "conflicts": len(conflicts)}

    def dispatch_to_archive(self, entry_id: int) -> dict[str, Any]:
        """把已编目条目推送给归档存储库生成归档任务。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已编目":
            return {"ok": False, "message": "条目不存在或未完成编目"}
        rows = store.rows("archive_store")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "归档标识": f"AR-{entry.get('条目标识', '')}",
            "文件指纹": "",
            "归档层级": f"L{entry.get('编目等级', '二级')[-1]}",
            "存储位置": f"layer{entry.get('编目等级', '二级')[-1]}/{entry.get('条目标识', '')}",
            "保留期限": "5年",
            "status": "待归档",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给归档存储库"}

    def consume_from_classify(self, fingerprint: str) -> dict[str, Any]:
        """读取分类器中该指纹的类别编码与置信度作为编目线索。"""
        row = next(
            (r for r in store.rows("doc_classify") if r.get("文件指纹") == fingerprint), None
        )
        if row is None:
            return {"ok": False, "message": "分类结果不存在", "category": ""}
        return {
            "ok": True,
            "message": "已读取分类结果",
            "category": row.get("类别编码", ""),
            "confidence": row.get("分类置信度", "0"),
        }

    def export_entries(self, level: str | None = None) -> list[dict[str, Any]]:
        """导出已编目条目列表，供资料导出包消费。"""
        rows = [
            dict(r) for r in store.rows(self.MODULE)
            if r.get("status") == "已编目"
        ]
        if level:
            rows = [r for r in rows if r.get("编目等级") == level]
        return rows
