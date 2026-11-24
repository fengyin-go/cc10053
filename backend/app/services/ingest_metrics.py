"""采集处理量指标领域服务：统计采集-抽取-归档的量级健康度，管理波动检测。
数据链路位置：观测层，消费各处理阶段上报的量级数据，产出量级快照与
波动结论，供断流告警与管线编排决策消费。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class IngestMetricsService(BaseModuleService):
    MODULE = "ingest_metrics"
    ENTITY = "量级快照"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["统计时间", "文档源", "采集量", "抽取量", "归档量"]
    REQUIRED_FIELDS = ["统计时间", "文档源", "采集量"]
    STATUS_ORDER = ["正常", "量级波动", "断流"]
    ACTION_RULES = {"查看趋势": "量级波动", "忽略波动": "断流"}
    NEGATIVE_ACTIONS = ["忽略波动"]

    # ---- 业务扩展：量级统计与波动检测 ----

    FLUCTUATION_RATIO = 0.4

    def take_snapshot(self, source_name: str) -> dict[str, Any]:
        """采集量级快照：汇总批次、抽取与归档量并写入快照。"""
        rows = store.rows(self.MODULE)
        ingest_total = sum(
            int(b.get("文件数量", 0) or 0)
            for b in store.rows("file_ingest")
            if b.get("文档源") == source_name
        )
        extract_total = sum(
            1 for r in store.rows("ocr_extract")
            if r.get("status") in ("已抽取", "抽取失败")
        )
        archive_total = sum(
            1 for r in store.rows("archive_store") if r.get("status") == "已归档"
        )
        snapshot = {
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "统计时间": datetime.now(timezone.utc).isoformat(),
            "文档源": source_name,
            "采集量": ingest_total,
            "抽取量": extract_total,
            "归档量": archive_total,
            "status": "正常",
            "pending": True,
            "abnormal": False,
        }
        rows.append(snapshot)
        return {"ok": True, "message": "快照已采集", "snapshot_id": snapshot["id"]}

    def detect_fluctuation(self) -> dict[str, Any]:
        """检测量级波动：对比最近两条快照的采集量差异。"""
        rows = sorted(
            store.rows(self.MODULE), key=lambda r: str(r.get("统计时间", ""))
        )
        if len(rows) < 2:
            return {"ok": False, "message": "快照不足无法对比"}
        prev, curr = rows[-2], rows[-1]
        prev_val = int(prev.get("采集量", 0) or 0)
        curr_val = int(curr.get("采集量", 0) or 0)
        base = max(prev_val, 1)
        ratio = abs(curr_val - prev_val) / base
        if curr_val == 0:
            curr["status"] = "断流"
            curr["abnormal"] = True
        elif ratio > self.FLUCTUATION_RATIO:
            curr["status"] = "量级波动"
            curr["abnormal"] = True
        return {
            "ok": True,
            "message": "波动检测完成",
            "ratio": round(ratio, 4),
            "status": curr.get("status", "正常"),
        }

    def consume_from_archive(self) -> dict[str, int]:
        """读取归档存储库的归档量作为快照来源。"""
        return {
            "archived": sum(1 for r in store.rows("archive_store") if r.get("status") == "已归档"),
            "failed": sum(1 for r in store.rows("archive_store") if r.get("status") == "归档失败"),
        }

    def trend_of_source(self, source_name: str) -> list[dict[str, Any]]:
        """输出指定文档源的量级趋势序列。"""
        return [
            {"统计时间": r.get("统计时间", ""), "采集量": r.get("采集量", 0)}
            for r in store.rows(self.MODULE)
            if r.get("文档源") == source_name
        ]

    def alert_pipeline(self) -> dict[str, Any]:
        """断流告警：通知管线编排暂停相关任务。"""
        broken = [r for r in store.rows(self.MODULE) if r.get("status") == "断流"]
        if not broken:
            return {"ok": False, "message": "无断流快照"}
        orch_rows = store.rows("pipeline_orch")
        for snap in broken:
            orch_rows.append({
                "id": max((int(r.get("id", 0)) for r in orch_rows), default=0) + 1,
                "任务标识": f"ORCH-ALERT-{snap.get('id')}",
                "处理阶段": "告警",
                "输入批次": str(snap.get("文档源", "")),
                "输出批次": "",
                "编排状态": "断流告警暂停",
                "status": "编排失败",
                "pending": True,
                "abnormal": True,
            })
        return {"ok": True, "message": "断流告警已通知编排", "broken": len(broken)}
