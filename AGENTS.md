# AGENTS.md

本文件为 Codex (Codex.ai/code) 提供在此代码库中工作的指导。

## 请总是使用中文来回复

---

## 📚 项目概览

这是一个**基于大语言模型的哲学文本翻译系统**，专门用于将复杂的后现代哲学文本（Nick Land 的 CCRU 著作、Reza Negarestani 的 Cyclonopedia 等）从英文翻译成中文。

**核心特性**：
- 🚀 异步并发处理（最高支持 10 个并发请求）
- 📚 术语表注入与约束
- ⚠️ 失败块占位符输出
- 🌗 双语 Markdown / HTML 导出
- 📝 Markdown 格式完整保留

---

## 🏗️ 核心架构

### 翻译流水线

```
PDF/EPUB
  ↓
文档转换器 (marker/pandoc)
  ↓
Markdown 文件
  ↓
文本分块器 (2000 字符/块)
  ↓
异步并发翻译 (DeepSeek V3)
  ↓
顺序输出管理器
  ↓
智能格式化
  ↓
最终翻译文件
```

### 五大核心组件

1. **文本分块器** - 智能切割长文本，传递上下文（前一块最后 500 字符）
2. **异步翻译引擎** - 并发处理 + Token Bucket 速率限制 + 指数退避重试
3. **Prompt + 术语表约束** - 将术语表和上文语境注入模型请求
4. **顺序输出管理器** - 解决异步乱序问题，保证顺序写入
5. **智能格式化器** - 清理 Pandoc 残留并修复 Markdown 排版

---

## 📁 目录结构

```
translator/
├── src/
│   ├── core/
│   │   ├── translator.py           # 核心翻译引擎
│   │   ├── rate_limiter.py         # Token Bucket 速率限制器
│   │   └── output_manager.py       # 顺序输出管理器
│   ├── converters/
│   │   └── document_converter.py   # PDF/EPUB → Markdown 转换器
│   └── utils/
│       └── config_loader.py        # 配置加载器
├── config/
│   └── config.yaml                 # 主配置文件（并发数、API 设置等）
├── data/
│   ├── glossaries/                 # 术语表文件夹
│   │   ├── glossary.json           # 通用术语表
│   │   └── CPglossary.json         # Cyclonopedia 专用术语表（73 个术语）
│   └── temp/                       # 临时文件（文档转换中间产物等）
├── input/                          # 待翻译源文件（历史目录）
├── output_final/                   # 翻译完成的输出文件
├── marker_output/                  # EPUB/PDF 提取的资源（图片等）
├── logs/                           # 运行日志
│   └── translation.log             # 翻译详细日志
├── tests/                          # unittest 回归测试
├── translate.py                    # ⭐ 主入口脚本（完整流程）
├── .env                            # API 密钥配置
└── requirements.txt                # Python 依赖（待生成）
```

---

## ⚡ 常用命令

### 完整翻译流程（PDF/EPUB → 中文翻译）

```bash
# 基本用法（自动转换 + 翻译）
python translate.py input.pdf -o output.md -g data/glossaries/glossary.json

# 跳过转换（已有 Markdown）
python translate.py input.md -o output.md --skip-conversion
```

### 配置修改

所有配置在 `config/config.yaml` 中修改：

```yaml
# 并发控制
concurrency:
  max_concurrent_requests: 10    # 最大并发数
  rate_limit_per_minute: 200     # API 速率限制

# LLM 设置
api:
  model: "deepseek-ai/DeepSeek-V3"
  translator:
    temperature: 0.3             # 翻译创造性（0-1）
```

### 日志与重跑

```bash
# 当前主流程中断后会从头重新运行
python translate.py input.md -o output.md --skip-conversion

# 查看实时日志
tail -f logs/translation.log
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

---

## 🐛 常见问题排查

### API 速率限制错误 (429 Too Many Requests)

修改 `config/config.yaml`：

```yaml
concurrency:
  max_concurrent_requests: 5     # 降低并发（从 10 → 5）
  rate_limit_per_minute: 100     # 降低速率（从 200 → 100）
```

### 翻译在某个索引处卡住

系统会自动为失败块写入占位符，不会阻塞流程。请直接查看输出文件中的失败占位符和主日志：

```bash
grep "翻译失败" logs/translation.log
```

### 图片路径失效

运行旧版路径修复工具（待集成到主流程）：

```bash
python scripts/fixpath.py
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

### 使用方式

1. 编辑 `data/glossaries/glossary.json`
2. 运行翻译时指定：`-g data/glossaries/glossary.json`
3. 当前主流程会将术语表直接注入 Prompt，输出后建议人工抽查关键术语

---

## 🚀 快速开始

```bash
# 1. 配置环境
echo "SILICONFLOW_API_KEY=sk-your-key" > .env

# 2. 安装依赖
pip install -r requirements.txt  # 文件待生成

# 3. 运行翻译（PDF → 中文）
python translate.py BookTrans/Cyclonopedia.epub \
  -o output_final/Cyclonopedia_CN.md \
  -g data/glossaries/CPglossary.json

# 4. 监控日志
tail -f logs/translation.log
```

---

## 📊 性能基准

基于 Ccru.md 翻译测试（344 个块）：

- **并发数**: 10
- **总耗时**: ~25 分钟
- **平均速度**: 13.8 chunks/分钟
- **成功率**: 100% (344/344)

**优化建议**：并发 20 + RPM 400 可将速度提升至 20+ chunks/分钟
