# AGENTS.md

本文件为 Codex 等 AI Agent 提供在此代码库中工作的指导。内容与 CLAUDE.md 保持同步。

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
│   │   ├── translation_cache.py      # TranslationCache - SQLite 缓存层
│   │   └── validator.py              # TranslationValidator - 质量检查器
│   │
│   ├── converters/
│   │   └── document_converter.py     # PDF/EPUB → Markdown 转换器
│   │
│   ├── services/
│   │   ├── result_renderer.py        # CLI/Web 共用结果渲染器
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
│   │   │   ├── task.py
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
└── docs/                             # 详细使用文档
    ├── 使用指南.md
    ├── 本地运行.md
    ├── 格式化指南.md
    └── Web启动.md
```

---

## ⚡ 常用命令

### CLI 模式

```bash
# 基本用法（EPUB/PDF → 中文）
python translate.py BookTrans/book.epub -g data/glossaries/glossary.json

# 已有 Markdown，跳过格式转换
python translate.py data/input/book.md --skip-conversion

# 双语对照输出
python translate.py data/input/book.md --skip-conversion --bilingual
```

### Web 模式

```bash
# 一键启动（后台 API + 独立 worker）
bash scripts/longrun.sh

# 关闭服务
kill $(cat logs/server.pid) $(cat logs/worker.pid)
```

### 测试

```bash
bash scripts/run_tests.sh
python3 -m unittest discover -s tests -v
```

### 缓存管理

```bash
# 中断后继续（自动命中缓存，只补跑未完成的 chunk）
python translate.py data/input/book.md --skip-conversion

# 强制全量重跑
rm data/translation_cache.db
```

---

## 🔑 环境变量配置

```bash
# .env 文件
SILICONFLOW_API_KEY=sk-your-key-here
GOOGLE_API_KEY=AIzaSy...  # 可选，Google Gemini
```

---

## 🐛 常见问题排查

### API 速率限制（429 Too Many Requests）

```yaml
# config/config.yaml
concurrency:
  max_concurrent_requests: 5
  rate_limit_per_minute: 100
```

### 翻译中断后恢复

直接重新运行同一命令，缓存自动生效。

### 检查失败块

```bash
grep "翻译失败\|failed" logs/translation.log
```

---

## 📖 术语表系统

```json
{
  "Hyperstition": "超虚构 (Hyperstition)",
  "War Machine": "战争机器 (War Machine)"
}
```

CLI 使用：`python translate.py ... -g data/glossaries/my_terms.json`

---

## 📊 性能基准

| 指标 | 数值 |
|------|------|
| 并发数 | 10 |
| 总耗时 | ~25 分钟 (344 块) |
| 平均速度 | 13.8 chunks/分钟 |
| 成功率 | 100% |
