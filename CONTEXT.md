# CONTEXT.md

本项目的领域语言词汇表。所有代码、issue、文档命名以此为准。

## 术语表

| 术语 | 英文/代码名 | 定义 |
|------|------------|------|
| 块 | Chunk | 章节感知切分出的翻译最小单元，携带稳定 chunk_id 与结构元数据。翻译、质检、缓存、修复都以块为粒度。 |
| 文档画像 | DocumentProfile | 分析员对整本文档产出的全局摘要、风格与术语提示，注入每个块的翻译 Prompt。 |
| 术语表 | Glossary | 英文术语 → 中文译名的 JSON 映射，翻译时强制注入 Prompt 并由质检校验一致性。 |
| 分析员 | Analyst | 翻译前读全文、产出文档画像的 Agent 角色。 |
| 翻译员 | Translator | 执行块翻译的主 Agent 角色。 |
| 审校员 | Reviewer / Checker | 只对质检不通过的高风险块介入修复的 Agent 角色。 |
| 质检报告 | QualityReport | 单块翻译的校验结果：未翻译残留、术语遗漏、Markdown 结构问题。 |
| 修复 | Repair | 审校员对高风险块的一次性重译尝试。区别于"重试"（Retry，指 API 调用失败的指数退避）。 |
| 编排引擎 | Engine | 多 Agent 流程的编排实现，取值 `langgraph`（默认，文档级 StateGraph）或 `native`（手写 asyncio，过渡期保留）。见 ADR-0001。 |
| 顺序输出 | Ordered Output | 块并发乱序完成、但按原文顺序流式写盘的保证，由 OutputManager 提供。 |
| 翻译缓存 | TranslationCache | chunk 级 SQLite 缓存，键含模型名、术语表、Prompt 版本与文档画像指纹；承担断点恢复职责。 |
| 双语对照 | Bilingual | 原文（引用块）+ 译文交替输出的模式，可导出 Markdown 与双栏 HTML。 |
| 占位符 | Placeholder | 块翻译最终失败时写入的标记文本，保证整体产出不被单块阻塞。 |
| 可观测 | Observability / Langfuse | 经 LangChain 回调把 Agent 调用链与逐块 token 上报 Langfuse 的能力，配置开关、可降级为无操作。见 docs/observability.md。 |
| 裁判 | Judge | LLM-as-judge 评测中给译文打分的模型角色，用异源强模型（Gemini），避免与选手同源偏好。 |
| 对照组 / 变体 | Comparison / Variant | 评测中只拨动一个开关的两两对照（引擎、多 Agent 开关、术语表有无），每个取值为一个变体。 |
| 译法一致率 | Consistency Rate | 术语表外重复短语每次是否译成同一中文的比率，作为是否立项 RAG 翻译记忆的量化门槛（0.90）。见 ADR-0002。 |
