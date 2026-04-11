# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在此代码库中工作的指导。

## 请总是使用中文来回复

---

## 📚 项目概览

这是一个**基于大语言模型的哲学/文学文本翻译系统**，专为英文 → 中文翻译设计，擅长处理后现代哲学、理论文学等复杂文本（Nick Land CCRU 著作、Reza Negarestani 的 Cyclonopedia 等）。

**核心特性**：
- 🚀 异步并发处理（最高支持 10 个并发请求）
- 🧩 章节感知分块（按标题树规划 chunk，避免跨章节漂移）
- 📚 术语表注入约束（强制术语一致性）
- 🤝 三角色多 Agent 协作（分析员 → 翻译员 → 选择性审校员）
- 🛡️ 质量校验与选择性修复（仅对高风险块触发审校）
- 💾 Chunk 级 SQLite 缓存（支持中断后恢复式重跑）
- 🎨 智能格式化（自动清理 Pandoc/EPUB 转换残留）
- 🌗 双语对照导出（Markdown + 双栏 HTML）
- 🌐 Web 管理界面（React + FastAPI + SQLite 任务队列）

---

## 🏗️ 核心架构

### 翻译流水线

```
PDF/EPUB
  ↓ 文档转换器 (pandoc/marker)
  ↓ Markdown 文件
  ↓
章节感知分块器 (ChunkPlanner)
  ↓
文档分析 Agent（生成摘要/风格/术语提示）
  ↓
异步并发翻译 (DeepSeek V3, 10 并发)
  ├─ 术语表 + 全局上下文注入
  ├─ 质量校验 (TranslationValidator)
  └─ 选择性审校修复（仅高风险块）
  ↓
Chunk 缓存落盘 (SQLite)
  ↓
顺序输出管理器 (OutputManager)
  ↓
智能格式化 (MarkdownFormatter)
  ↓
最终翻译文件
```

### 七大核心组件

1. **ChunkPlanner** (`src/core/chunk_planner.py`) - 按 Markdown 标题树规划 chunk，产出稳定 `chunk_id`（SHA1 哈希）
2. **TranslationEngine** (`src/core/translator.py`) - 异步翻译引擎，含 Token Bucket 限流 + 指数退避重试 + 三角色 Agent
3. **TranslationValidator** (`src/core/validator.py`) - 检测未翻译英文、术语遗漏、Markdown 结构丢失
4. **TranslationCache** (`src/core/translation_cache.py`) - SQLite 缓存层，支持恢复式重跑
5. **OutputManager** (`src/core/output_manager.py`) - 顺序写入缓冲，解决异步乱序问题
6. **MarkdownFormatter** (`src/services/markdown_formatter.py`) - 清理 Pandoc 残留并修复排版
7. **TaskWorker** (`src/api/worker.py`) - Web 模式的后台任务队列处理器

---

## 📁 目录结构

```
LLMtranslator-for-pdf-epub/
├── translate.py                      # ⭐ CLI 主入口（完整翻译流程）
├── run_server.py                     # Web API 服务器启动器
├── run_worker.py                     # 独立任务 worker 启动器
├── requirements.txt                  # Python 依赖
│
├── src/
│   ├── core/                         # 核心翻译引擎
│   │   ├── translator.py             # TranslationEngine - 异步翻译核心
│   │   ├── chunk_planner.py          # ChunkPlanner - 章节感知分块器
│   │   ├── rate_limiter.py           # RateLimiter - Token Bucket 限流
│   │   ├── output_manager.py         # OutputManager - 顺序输出管理
│   │   ├── translation_cache.py      # TranslationCache - SQLite 缓存层
│   │   └── validator.py              # TranslationValidator - 质量检查器
│   │
│   ├── converters/
│   │   └── document_converter.py     # PDF/EPUB → Markdown 转换器
│   │
│   ├── services/
│   │   ├── markdown_formatter.py     # 智能 Markdown 格式化
│   │   ├── export_service.py         # HTML/双语导出服务
│   │   └── epub_artifact_cleaner.py  # Pandoc/EPUB 残留清理
│   │
│   ├── domain/models/
│   │   └── translation_models.py     # DocumentProfile、TranslationResult 数据类
│   │
│   ├── pipelines/
│   │   ├── translate/
│   │   │   └── document_translation_pipeline.py
│   │   └── postprocess/
│   │       └── result_postprocess_pipeline.py
│   │
│   ├── application/use_cases/
│   │   └── run_translation_pipeline.py   # CLI/Web 共用的翻译用例
│   │
│   ├── api/                          # Web API 层
│   │   ├── app.py                    # FastAPI 应用入口
│   │   ├── worker.py                 # TaskWorker - 任务队列处理器
│   │   ├── routes/
│   │   │   ├── translation.py        # 翻译任务 CRUD 端点
│   │   │   ├── glossary.py           # 术语表管理端点
│   │   │   └── files.py              # 文件上传/下载端点
│   │   ├── services/
│   │   │   ├── translation_service.py
│   │   │   └── glossary_service.py
│   │   ├── models/
│   │   │   ├── task.py               # TranslationTask 数据模型
│   │   │   └── glossary.py
│   │   └── database/
│   │       └── db.py                 # SQLite 数据库管理（任务队列）
│   │
│   └── utils/
│       └── config_loader.py          # 配置加载器（单例）
│
├── config/
│   ├── config.yaml                   # 主配置文件（并发数、API、分块参数）
│   └── artifact_rules.yaml           # Pandoc/EPUB 残留清理规则
│
├── data/
│   ├── glossaries/
│   │   ├── glossary.json             # 通用术语表（可自定义）
│   │   └── CPglossary.json           # Cyclonopedia 专用术语表（73 条）
│   ├── input/                        # CLI 输入文件目录
│   ├── output/                       # CLI 输出目录
│   ├── uploads/                      # Web 上传目录
│   ├── results/                      # Web 任务输出目录
│   └── translation_cache.db          # Chunk 级翻译缓存（SQLite）
│
├── BookTrans/                        # PDF/EPUB 待翻译文件（默认放置位置）
├── output_final/                     # 翻译完成的最终文件
├── frontend/                         # React 前端源码（Vite + TypeScript）
├── frontend_dist/                    # 前端构建产物（由后端静态托管）
├── scripts/
│   ├── smart_markdown_formatter.py   # 独立格式化工具
│   ├── longrun.sh                    # 后台启动 API + worker
│   └── run_tests.sh                  # 回归测试脚本
├── tests/                            # 单元测试（10 个文件）
├── logs/
│   └── translation.log               # 翻译详细日志
├── docs/                             # 详细使用文档
│   ├── 使用指南.md                   # 完整使用说明（CLI/Web）
│   ├── 本地运行.md                   # 快速上手步骤
│   ├── 格式化指南.md                 # Markdown 格式化工具说明
│   └── Web启动.md                    # Web 界面部署指南
└── .env                              # API 密钥（不提交 git）
```

---

## ⚡ 常用命令

### CLI 模式（单文件翻译）

```bash
# 基本用法（EPUB/PDF → 中文）
python translate.py BookTrans/book.epub -g data/glossaries/glossary.json

# 已有 Markdown，跳过格式转换
python translate.py data/input/book.md --skip-conversion

# 双语对照输出
python translate.py data/input/book.md --skip-conversion --bilingual

# 指定输出路径
python translate.py data/input/book.md -o output_final/result.md
```

### Web 模式（推荐长任务使用）

```bash
# 一键启动（后台 API + 独立 worker）
bash scripts/longrun.sh

# 仅启动 API（含内联 worker）
python run_server.py

# 关闭服务
kill $(cat logs/server.pid) $(cat logs/worker.pid)

# 访问界面：http://localhost:8000
# API 文档：http://localhost:8000/docs
```

### 开发模式

```bash
# 后端热重载
TRANSLATION_SERVER_RELOAD=1 python run_server.py

# 前端开发服务
cd frontend && npm run dev  # 访问 http://localhost:5173
```

### 测试

```bash
# 运行所有回归测试
bash scripts/run_tests.sh

# 含前端构建检查
bash scripts/run_tests.sh --with-frontend

# 仅 Python 单元测试
python3 -m unittest discover -s tests -v
```

### 缓存与进度管理

```bash
# 查看实时日志
tail -f logs/translation.log

# 中断后继续（系统自动命中缓存，只补跑未完成的 chunk）
python translate.py data/input/book.md --skip-conversion

# 强制全量重跑（删除翻译缓存）
rm data/translation_cache.db

# 检查失败的 chunk
grep "翻译失败\|failed" logs/translation.log

# Web 任务数据库重置
rm data/translation.db
```

---

## 🔑 环境变量配置

在项目根目录创建 `.env` 文件：

```bash
# 主 API（DeepSeek V3 via SiliconFlow）
SILICONFLOW_API_KEY=sk-your-key-here

# 备用 API（Google Gemini，可选）
GOOGLE_API_KEY=AIzaSy...
```

Web 服务器环境变量（可选）：

```bash
TRANSLATION_SERVER_PORT=8000      # 服务端口（默认 8000）
TRANSLATION_SERVER_RELOAD=1       # 热重载（开发用）
TRANSLATION_INLINE_WORKER=0       # 禁用内联 worker（搭配独立 worker 使用）
TRANSLATION_PREVENT_SLEEP=1       # 防止 Mac 休眠（longrun.sh 使用）
```

---

## 🔧 配置文件说明

`config/config.yaml` 主要参数：

```yaml
api:
  model: "deepseek-ai/DeepSeek-V3"
  translator:
    temperature: 0.3        # 翻译创造性（0=保守，1=创造）

concurrency:
  max_concurrent_requests: 10  # 并发数（遇 429 错误时降低）
  rate_limit_per_minute: 200   # API 速率限制

text_splitting:
  chunk_size: 3600             # 目标块大小（字符数）
  context_window: 1400         # 上下文窗口大小

quality:
  enable_qa_check: true        # 开启质量检查
  max_fix_attempts: 1          # 最大修复次数

multi_agent:
  enabled: true                # 开启三角色 Agent 协作
  analyst_max_chars: 12000     # 文档分析器最大采样字符数
```

---

## 🐛 常见问题排查

### API 速率限制（429 Too Many Requests）

降低并发：

```yaml
concurrency:
  max_concurrent_requests: 5
  rate_limit_per_minute: 100
```

### 翻译中断后如何继续

直接重新运行同一命令，系统会自动命中已完成 chunk 的缓存，只继续处理未完成部分：

```bash
python translate.py data/input/book.md --skip-conversion
```

### 图片路径失效

格式化时系统会自动将绝对路径修复为相对路径。若仍有问题，单独运行格式化：

```bash
python scripts/smart_markdown_formatter.py output_final/book_CN.md
```

### Web 端口被占用

```bash
TRANSLATION_SERVER_PORT=8001 bash scripts/longrun.sh
```

---

## 📖 术语表系统

### 格式规范

```json
{
  "English Term": "中文译名 (English Term)",
  "Hyperstition": "超虚构 (Hyperstition)",
  "War Machine": "战争机器 (War Machine)"
}
```

括号中保留英文原词，方便读者对照原文。

### 使用方式

1. 编辑 `data/glossaries/glossary.json`（通用）或创建专项术语表
2. CLI 指定：`python translate.py ... -g data/glossaries/my_terms.json`
3. Web 模式：在术语表管理页面直接导入 JSON

术语表会注入每个 chunk 的翻译 Prompt，TranslationValidator 会自动抽查前 25 条术语的一致性。

---

## 📊 性能基准

基于 Ccru.md 翻译测试（344 个块）：

| 指标 | 数值 |
|------|------|
| 并发数 | 10 |
| 总耗时 | ~25 分钟 |
| 平均速度 | 13.8 chunks/分钟 |
| 成功率 | 100% (344/344) |

**提速建议**：并发 20 + RPM 400 可将速度提升至 20+ chunks/分钟（需确认 API 配额上限）
