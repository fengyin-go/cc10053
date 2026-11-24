<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">文档资料自动归集与数字化采集平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向多类型文档资料的自动采集、格式识别、OCR抽取、编目归档与全文检索平台</span>
        <span class="head-user">当前值班：数据工程组</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
const navItems = [{ label: "运营概览", path: "/" }, { label: "文档源注册", path: "/doc_source" }, { label: "文件采集器", path: "/file_ingest" }, { label: "格式识别器", path: "/format_detect" }, { label: "OCR抽取器", path: "/ocr_extract" }, { label: "版面重建器", path: "/layout_rebuild" }, { label: "文本清洗器", path: "/text_clean" }, { label: "元数据编目器", path: "/meta_catalog" }, { label: "文档分类器", path: "/doc_classify" }, { label: "语种检测器", path: "/lang_detect" }, { label: "重复文档检测", path: "/dup_document" }, { label: "归档存储库", path: "/archive_store" }, { label: "全文索引器", path: "/fulltext_index" }, { label: "检索查询服务", path: "/search_service" }, { label: "处理管线编排", path: "/pipeline_orch" }, { label: "阶段重试器", path: "/stage_retry" }, { label: "处理质量闸", path: "/quality_gate" }, { label: "编目复核队列", path: "/catalog_review" }, { label: "资料导出包", path: "/export_bundle" }, { label: "采集处理量指标", path: "/ingest_metrics" }, { label: "保留清理策略", path: "/retention_policy" }]
</script>
