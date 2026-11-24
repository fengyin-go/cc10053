"""领域服务注册表：通用资源路由按模块 key 分派到独立业务服务。"""
from __future__ import annotations

from app.services.base import BaseModuleService
from app.services.doc_source import DocSourceService
from app.services.file_ingest import FileIngestService
from app.services.format_detect import FormatDetectService
from app.services.ocr_extract import OcrExtractService
from app.services.layout_rebuild import LayoutRebuildService
from app.services.text_clean import TextCleanService
from app.services.meta_catalog import MetaCatalogService
from app.services.doc_classify import DocClassifyService
from app.services.lang_detect import LangDetectService
from app.services.dup_document import DupDocumentService
from app.services.archive_store import ArchiveStoreService
from app.services.fulltext_index import FulltextIndexService
from app.services.search_service import SearchServiceService
from app.services.pipeline_orch import PipelineOrchService
from app.services.stage_retry import StageRetryService
from app.services.quality_gate import QualityGateService
from app.services.catalog_review import CatalogReviewService
from app.services.export_bundle import ExportBundleService
from app.services.ingest_metrics import IngestMetricsService
from app.services.retention_policy import RetentionPolicyService

SERVICES: dict[str, BaseModuleService] = {
    "doc_source": DocSourceService(),
    "file_ingest": FileIngestService(),
    "format_detect": FormatDetectService(),
    "ocr_extract": OcrExtractService(),
    "layout_rebuild": LayoutRebuildService(),
    "text_clean": TextCleanService(),
    "meta_catalog": MetaCatalogService(),
    "doc_classify": DocClassifyService(),
    "lang_detect": LangDetectService(),
    "dup_document": DupDocumentService(),
    "archive_store": ArchiveStoreService(),
    "fulltext_index": FulltextIndexService(),
    "search_service": SearchServiceService(),
    "pipeline_orch": PipelineOrchService(),
    "stage_retry": StageRetryService(),
    "quality_gate": QualityGateService(),
    "catalog_review": CatalogReviewService(),
    "export_bundle": ExportBundleService(),
    "ingest_metrics": IngestMetricsService(),
    "retention_policy": RetentionPolicyService(),
}


def service_for(module: str) -> BaseModuleService | None:
    return SERVICES.get(module)
