# 文档资料自动归集与数字化采集平台

面向多类型文档资料的自动采集、格式识别、OCR抽取、编目归档与全文检索平台

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/WorkbenchView.vue|tsx  全部模块共享工作台
│   ├── src/data/modules.ts              18个业务模块配置
│   ├── src/api/              统一请求封装
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/resource.py  通用查询/导出/登记/动作接口
│   ├── app/services/<key>.py    每个模块独立领域逻辑
│   ├── app/services/base.py     共享服务骨架
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8023/api/health`

### 前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认监听 `http://127.0.0.1:5203/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8023`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 文档源注册 | `doc_source` | 文档源 | 源标识、源名称、源类型 |
| 文件采集器 | `file_ingest` | 采集批次 | 批次编号、文档源、文件数量 |
| 格式识别器 | `format_detect` | 格式记录 | 文件指纹、识别格式、置信度 |
| OCR抽取器 | `ocr_extract` | 抽取结果 | 文件指纹、抽取文本、置信度均值 |
| 版面重建器 | `layout_rebuild` | 版面结构 | 文件指纹、版面块数、阅读顺序 |
| 文本清洗器 | `text_clean` | 清洗结果 | 文件指纹、清洗规则集、乱码标记 |
| 元数据编目器 | `meta_catalog` | 编目条目 | 条目标识、文档标题、作者机构 |
| 文档分类器 | `doc_classify` | 分类结果 | 文件指纹、分类体系、类别编码 |
| 语种检测器 | `lang_detect` | 语种记录 | 文件指纹、主语种、混合语种 |
| 重复文档检测 | `dup_document` | 查重结果 | 查重批次、候选组数、相似文档对 |
| 归档存储库 | `archive_store` | 归档条目 | 归档标识、文件指纹、归档层级 |
| 全文索引器 | `fulltext_index` | 索引分片 | 分片标识、索引词数、文档数 |
| 检索查询服务 | `search_service` | 查询记录 | 查询标识、查询词、命中文档数 |
| 处理管线编排 | `pipeline_orch` | 管线任务 | 任务标识、处理阶段、输入批次 |
| 阶段重试器 | `stage_retry` | 重试记录 | 重试编号、失败阶段、重试策略 |
| 处理质量闸 | `quality_gate` | 质量结果 | 检查批次、处理阶段、检查项数 |
| 编目复核队列 | `catalog_review` | 复核记录 | 记录编号、编目条目、复核结论 |
| 资料导出包 | `export_bundle` | 导出任务 | 任务名称、编目范围、导出格式 |
| 采集处理量指标 | `ingest_metrics` | 量级快照 | 统计时间、文档源、采集量 |
| 保留清理策略 | `retention_policy` | 保留规则 | 规则名称、归档层级、保留期限 |

## 约定

- 全部模块共享`frontend/src/views/WorkbenchView.vue|tsx`和一套资源路由。
- 每个模块仍保留独立`backend/app/services/<模块>.py`；纯前端保留
  `frontend/src/domain/<模块>.ts`，用于承载真实业务差异并维持36题位容量。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

领域：数据工程
子方向：数据采集、爬虫与RPA
