# AI 翻译系统

基于大语言模型的专业文本翻译系统，专为复杂的后现代哲学文本设计。支持 PDF/EPUB/Markdown 格式，提供术语表管理和智能格式化功能。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## ✨ 核心特性

- 🚀 **异步并发翻译** - 最高支持 10 个并发请求，速度提升 10 倍
- 🔍 **术语一致性检查** - 自动验证专业术语翻译准确性
- 🔧 **质量自动修复** - 智能检测并修正翻译质量问题
- 💾 **断点续传** - 支持中断恢复，不怕意外中断
- 📝 **格式完整保留** - 保留 Markdown 标题、加粗、图片等所有格式
- 🎨 **智能格式化** - 自动清理 Pandoc 转换残留，优化书籍排版
- 🌐 **Web 管理界面** - React + FastAPI 构建的现代化 Web 界面
- 📚 **术语表管理** - 可视化管理翻译术语，支持导入导出

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
python translate.py input/your_book.md

# 翻译 EPUB 文件
python translate.py BookTrans/your_book.epub

# 使用术语表翻译
python translate.py input/book.md -g glossary.json
```

翻译结果将保存在 `data/output/` 目录。

## 📖 详细文档

- [翻译系统使用指南](翻译系统使用指南.md) - 完整的使用说明
- [格式化工具使用指南](格式化工具使用指南.md) - Markdown 格式化工具文档
- [本地运行指南](本地运行指南.md) - Web 界面部署指南
- [CLAUDE.md](CLAUDE.md) - 项目架构和技术细节

## 🎯 功能演示

### 命令行翻译

```bash
# 完整翻译流程
python translate.py input/Cyclonopedia.epub \
  -g CPglossary.json \
  -o output/Cyclonopedia_CN.md
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
# 启动后端
python run_server.py

# 启动前端（新终端）
cd frontend
npm run dev
```

访问 http://localhost:5173/ 即可使用可视化界面。

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
│   └── api/                  # Web API
│       ├── app.py            # FastAPI 应用
│       ├── routes/           # API 路由
│       └── services/         # 业务逻辑
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
# 翻译引擎
translator:
  model: "deepseek-ai/DeepSeek-V3"
  temperature: 0.3
  max_concurrent: 10      # 最大并发数
  chunk_size: 2000        # 每块大小

# API 配置
api:
  rate_limit: 200         # 每分钟请求数
  timeout: 60             # 超时时间（秒）
```

## 📊 翻译流程

```
输入文件 (PDF/EPUB/MD)
   ↓
文档转换 (Pandoc)
   ↓
文本智能分块 (2000 字/块)
   ↓
异步并发翻译 (10 并发)
   ├─ 术语表应用
   ├─ 质量检查
   └─ 自动修复
   ↓
智能格式化
   ├─ 代码块保护
   ├─ 目录清理
   ├─ 引用块转换
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
python translate.py input.md -g my_glossary.json
```

### 智能格式化

单独格式化已翻译文件：

```bash
python scripts/smart_markdown_formatter.py output/book_CN.md
```

功能：
- ✅ 保留代码块格式
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

## 📝 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM 框架
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [React](https://reactjs.org/) - 前端框架
- [Ant Design](https://ant.design/) - UI 组件库
- [DeepSeek](https://www.deepseek.com/) - 翻译模型提供商

## 📮 联系方式

- 问题反馈: [GitHub Issues](https://github.com/你的用户名/translator/issues)
- 项目主页: [GitHub](https://github.com/你的用户名/translator)

---

⭐ 如果这个项目对你有帮助，请给个 Star！
