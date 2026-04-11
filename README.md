# AI 翻译系统

基于大语言模型的专业文本翻译系统，专为复杂的后现代哲学文本设计。支持 PDF/EPUB/Markdown 格式，提供术语表管理和智能格式化功能。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## ✨ 核心特性

- 🚀 **异步并发翻译** - 最高支持 10 个并发请求，速度提升 10 倍
- 🧩 **章节感知分块** - 按 Markdown 标题与结构块规划 chunk，减少跨章节漂移
- 🆔 **稳定 Chunk ID** - 每个 chunk 自带结构化元数据，便于缓存、恢复和调试
- 📚 **术语表约束** - 在 Prompt 中强制注入术语表，帮助保持术语一致
- 🛡️ **质量校验与选择性修复** - 自动检测未翻译英文、术语遗漏和 Markdown 结构问题，只对高风险块触发修复
- 🤝 **三角色多 Agent 协作** - 文档分析员先生成全局摘要和术语提示，主翻译员执行翻译，审校员只在高风险块介入
- ⚠️ **失败块保底输出** - 单个 chunk 失败时写入占位符，不阻塞整体产出
- 📝 **格式完整保留** - 保留 Markdown 标题、加粗、图片等所有格式
- 🎨 **智能格式化** - 自动清理 Pandoc 转换残留，优化书籍排版
- 🌐 **Web 管理界面** - React + FastAPI 构建的现代化 Web 界面
- 📚 **术语表管理** - 可视化管理翻译术语，支持导入导出
- 🌗 **双语对照导出** - 双语任务可导出 Markdown 与双栏 HTML

## 🚀 快速开始

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/你的用户名/translator.git
cd translator

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖（如果需要 Web 界面）
cd frontend
npm install
cd ..
```

### 配置 API 密钥

创建 `.env` 文件：

```bash
# DeepSeek API（推荐）
SILICONFLOW_API_KEY=your_api_key_here

# 或 Google Gemini API
GOOGLE_API_KEY=your_google_api_key
```

### 基础使用

```bash
# 翻译 Markdown 文件
python translate.py data/input/your_book.md

# 翻译 EPUB 文件
python translate.py BookTrans/your_book.epub

# 使用术语表翻译
python translate.py data/input/book.md -g data/glossaries/glossary.json

# 双语对照输出
python translate.py data/input/book.md --bilingual --skip-conversion
```

翻译结果将保存在 `data/output/` 目录。

### 运行测试

```bash
# 快速回归测试
bash scripts/run_tests.sh

# 包含前端构建检查
bash scripts/run_tests.sh --with-frontend

# 仅运行 Python 单元测试
python3 -m unittest discover -s tests -v
```

## 📖 详细文档

- [使用指南](docs/使用指南.md) - 完整的 CLI/Web 使用说明
- [本地运行](docs/本地运行.md) - 快速上手步骤
- [格式化指南](docs/格式化指南.md) - Markdown 格式化工具说明
- [Web 启动指南](docs/Web启动.md) - Web 界面部署与内网穿透
- [CLAUDE.md](CLAUDE.md) - 项目架构和技术细节（AI Agent 工作指导）

## 🎯 功能演示

### 命令行翻译

```bash
# 完整翻译流程
python translate.py BookTrans/Cyclonopedia.epub \
  -g data/glossaries/CPglossary.json \
  -o output_final/Cyclonopedia_CN.md
```

输出示例：
```
============================================================
🚀 翻译流水线启动
============================================================
📄 输入文件: input/Cyclonopedia.epub
🔄 开始格式转换...
📖 读取文件: data/temp/Cyclonopedia/Cyclonopedia.md
📚 加载术语表: 73 个词条
✂️ 文本分块完成: 150 个块
🚀 开始翻译...
✅ Chunk 0 完成 (1/150, 0.7%, 速度: 12.5 chunks/分钟)
...
🎨 开始格式化处理...
✅ 翻译完成!
⏱️  总耗时: 18.50 分钟
💾 输出文件: output/Cyclonopedia_CN.md
```

### Web 界面

启动 Web 服务器：

```bash
# 推荐：长任务模式（后台启动 API + 独立 worker + macOS 防休眠）
bash scripts/longrun.sh

# 仅启动后端（默认会带一个内联 worker）
python run_server.py

# 启动前端（新终端）
cd frontend
npm run dev
```

访问 http://localhost:5173/ 即可使用可视化界面。

如果你希望把 API 和执行器拆开运行：

```bash
# 终端 1：只启动 API
TRANSLATION_INLINE_WORKER=0 python run_server.py

# 终端 2：启动独立 worker
python run_worker.py

# 或直接启动多进程 worker 集群
python run_worker.py --processes 4 --parallel-tasks 2
```

长时间翻译任务更建议使用 `bash scripts/longrun.sh`。它会：
- 后台启动 API
- 后台启动独立 worker
- 将 PID 写入 `logs/server.pid` 和 `logs/worker.pid`
- 将日志写入 `logs/server.out` 和 `logs/worker.out`

如果你确实需要防止 Mac 休眠，再显式启用：

```bash
TRANSLATION_PREVENT_SLEEP=1 bash scripts/longrun.sh
```

## 🛠️ 核心架构

```
translator/
├── translate.py              # 主翻译脚本
├── src/
│   ├── core/                 # 核心翻译引擎
│   │   ├── translator.py     # 异步翻译引擎
│   │   ├── rate_limiter.py   # Token Bucket 速率限制
│   │   └── output_manager.py # 顺序输出管理
│   ├── converters/           # 文档转换器
│   │   └── document_converter.py
│   ├── services/             # 导出与格式化服务
│   │   ├── export_service.py
│   │   └── markdown_formatter.py
│   └── api/                  # Web API
│       ├── app.py            # FastAPI 应用
│       ├── routes/           # API 路由
│       ├── services/         # 业务逻辑
│       └── worker.py         # 队列 worker
├── run_worker.py             # 独立 worker 启动脚本
├── scripts/                  # 辅助工具
│   ├── smart_markdown_formatter.py  # 智能格式化
│   ├── async_translator.py          # 独立翻译器
│   └── fixpath.py                   # 路径修复
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/      # UI 组件
│   │   └── services/        # API 客户端
│   └── package.json
└── config/
    └── config.yaml          # 配置文件
```

## 🔧 配置说明

编辑 `config/config.yaml` 自定义配置：

```yaml
# API 配置
api:
  model: "deepseek-ai/DeepSeek-V3"
  translator:
    temperature: 0.3

concurrency:
  max_concurrent_requests: 10
  rate_limit_per_minute: 200

text_splitting:
  chunk_size: 2000
  chunk_overlap: 200
  context_window: 800

quality:
  enable_qa_check: true
  max_fix_attempts: 1
  untranslated_word_span: 12

worker:
  inline_enabled: true
  poll_interval_seconds: 2
  stale_after_seconds: 900
  max_parallel_tasks: 1
  processes: 1

multi_agent:
  enabled: true
  analyst_max_chars: 12000
  analyst_max_sections: 12
```

## 📊 翻译流程

```
输入文件 (PDF/EPUB/MD)
   ↓
文档转换 (Pandoc)
   ↓
章节感知分块 (2000 字/块)
   ↓
异步并发翻译 (10 并发)
   ├─ 文档分析员（摘要 / 风格 / 术语提示）
   ├─ Chunk 元数据 / 稳定 ID
   ├─ 术语表应用
   ├─ 主翻译员
   ├─ 质量校验 / 选择性修复
   ├─ 审校修复员（仅高风险块）
   ├─ Chunk 级缓存恢复
   ├─ 失败重试（指数退避）
   └─ 顺序输出管理
   ↓
智能格式化
   ├─ 块级结构解析
   ├─ 代码块保留
   ├─ Pandoc div / 目录 / 引用清理
   └─ 排版优化
   ↓
输出 Markdown 文件
```

## 💡 高级功能

### 术语表管理

创建 JSON 格式术语表：

```json
{
  "Hyperstition": "超虚构 (Hyperstition)",
  "War Machine": "战争机器 (War Machine)",
  "Rhizome": "根茎 (Rhizome)"
}
```

使用术语表：

```bash
python translate.py data/input/input.md -g data/glossaries/my_glossary.json
```

### Web 任务状态与队列

- API 负责创建任务并写入 SQLite 队列
- worker 负责认领 `pending` 任务并执行翻译
- 默认 `run_server.py` 会启一个内联 worker，单机开箱即用
- 生产或长任务场景推荐单独运行 `run_worker.py`
- `python run_worker.py --processes N --parallel-tasks M` 可直接横向扩到多进程，多进程之间通过数据库原子认领避免重复消费

- `pending`: 任务已创建，等待后台启动
- `processing`: 正在翻译
- `completed`: 全部 chunk 成功
- `partial_success`: 部分 chunk 失败，但结果文件已生成
- `failed`: 全部 chunk 失败或任务级错误

说明：
- Markdown 结果在 `completed` 和 `partial_success` 状态下都可下载
- 双栏 HTML 仅对双语任务开放

### 智能格式化

单独格式化已翻译文件：

```bash
python scripts/smart_markdown_formatter.py output/book_CN.md
```

功能：
- ✅ 保留代码块格式
- ✅ 按块处理标题、列表、Pandoc div 和段落
- ✅ 清理 Pandoc 残留标记
- ✅ 转换引用块和强调格式
- ✅ 修复图片路径
- ✅ 优化书籍排版

### 跳过格式化

如果需要原始翻译输出：

```bash
python translate.py input.md --skip-formatting
```

## 🌟 性能基准

基于 344 块文本的翻译测试（Ccru.md）：

| 指标 | 数值 |
|------|------|
| 并发数 | 10 |
| 总耗时 | ~25 分钟 |
| 平均速度 | 13.8 chunks/分钟 |
| 成功率 | 100% (344/344) |
| 单块平均时长 | 4.3 秒 |

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 🧪 测试

当前仓库已覆盖以下基础回归：

- 术语表创建、更新、导入接口
- 任务 `bilingual` 持久化
- 单语/双语导出约束
- 部分失败任务状态判定

运行命令：

```bash
bash scripts/run_tests.sh

# 如需包含前端构建
bash scripts/run_tests.sh --with-frontend

# 或仅运行单元测试
python3 -m unittest discover -s tests -v
```

## 📝 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM 框架
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [React](https://reactjs.org/) - 前端框架
- [Ant Design](https://ant.design/) - UI 组件库
- [DeepSeek](https://www.deepseek.com/) - 翻译模型提供商

## 📮 联系方式

- 问题反馈: [GitHub Issues](https://github.com/sena1818/translator/issues)
- 项目主页: [GitHub](https://github.com/sena1818/translator)

---

⭐ 如果这个项目对你有帮助，请给个 Star！
