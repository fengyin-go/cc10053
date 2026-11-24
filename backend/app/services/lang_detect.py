"""语种检测器领域服务：检测文档语种并规划编码转换，管理混合语种识别。
数据链路位置：语言层，消费文本清洗器产出的清洗文本，产出主语种与编码
转换计划，供全文索引器确定分词策略。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class LangDetectService(BaseModuleService):
    MODULE = "lang_detect"
    ENTITY = "语种记录"
    OPERATION_TERM = "转换"
    LIST_FIELDS = ["文件指纹", "主语种", "混合语种", "检测置信度", "编码转换"]
    REQUIRED_FIELDS = ["文件指纹", "主语种", "混合语种"]
    STATUS_ORDER = ["已检测", "待检测", "检测失败"]
    ACTION_RULES = {"执行检测": "已检测", "重试检测": "检测失败"}
    NEGATIVE_ACTIONS = []

    # ---- 业务扩展：语种检测与编码转换 ----
    ENCODE_PLAN = {"中文": "UTF-8", "英文": "UTF-8", "日文": "SHIFT-JIS", "俄文": "UTF-8"}

    def run_detect(self, entry_id: int) -> dict[str, Any]:
        """执行检测：判定主语种、混合语种与编码转换计划。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "待检测":
            return {"ok": False, "message": "记录不存在或不在待检测"}
        fingerprint = str(entry.get("文件指纹", ""))
        main_lang = "中文" if "z" not in fingerprint.lower() else "英文"
        mixed = "无"
        for lang in ("英文", "日文"):
            if lang[:1] in fingerprint:
                mixed = lang
                break
        entry["主语种"] = main_lang
        entry["混合语种"] = mixed
        entry["检测置信度"] = "0.95" if mixed == "无" else "0.87"
        entry["编码转换"] = self.ENCODE_PLAN.get(main_lang, "UTF-8")
        entry["status"] = "已检测"
        entry["pending"] = False
        return {"ok": True, "message": "检测完成", "main": main_lang, "mixed": mixed}

    def consume_from_clean(self, fingerprint: str) -> dict[str, Any]:
        """读取清洗结果中该指纹的清洗产出长度。"""
        row = next(
            (r for r in store.rows("text_clean") if r.get("文件指纹") == fingerprint), None
        )
        if row is None:
            return {"ok": False, "message": "清洗结果不存在", "chars": 0}
        return {
            "ok": True,
            "message": "已读取清洗结果",
            "chars": len(str(row.get("清洗产出", ""))),
            "rule_set": row.get("清洗规则集", ""),
        }

    def push_to_index(self, entry_id: int) -> dict[str, Any]:
        """把已检测语种记录推送给全文索引器确定分词策略。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已检测":
            return {"ok": False, "message": "记录不存在或未完成检测"}
        rows = store.rows("fulltext_index")
        rows.append({
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "分片标识": f"SHARD-{entry.get('文件指纹', '')}",
            "索引词数": 0,
            "文档数": 1,
            "分片状态": "构建中",
            "合并水位": "0",
            "status": "构建中",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": "已推送给全文索引器"}

    def fail_detect(self, entry_id: int, reason: str) -> dict[str, Any]:
        """检测失败：写阶段重试记录等待重试。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "记录不存在"}
        entry["status"] = "检测失败"
        entry["abnormal"] = True
        retry_rows = store.rows("stage_retry")
        retry_rows.append({
            "id": max((int(r.get("id", 0)) for r in retry_rows), default=0) + 1,
            "重试编号": f"RT-LD-{entry_id}",
            "失败阶段": "语种检测",
            "重试策略": "编码探测重试",
            "重试次数": 1,
            "恢复状态": "待重试",
            "status": "待重试",
            "pending": True,
            "abnormal": False,
        })
        return {"ok": True, "message": f"检测已标记失败: {reason}"}

    def stats_by_lang(self) -> dict[str, int]:
        """按主语种统计检测记录数量。"""
        stats: dict[str, int] = {}
        for row in store.rows(self.MODULE):
            lang = str(row.get("主语种", "") or "未检测")
            stats[lang] = stats.get(lang, 0) + 1
        return stats
