# MCP Server（stdio）

把本翻译系统暴露为一个 [Model Context Protocol](https://modelcontextprotocol.io) 服务，
让 Claude Desktop 等 MCP 客户端把它当作可编排的**翻译能力节点**：短文本即时翻译、
提交长文档任务并轮询、管理术语表——全部无需打开 Web 界面。

工具处理器直接调用既有 service 层（`TranslationService` / `GlossaryService`），
不新增业务逻辑，因此与 Web 界面、后台 worker **共享同一份 SQLite 任务库和
`data/glossaries` 术语表存储**。

## 工具清单

| 工具 | 作用 |
| --- | --- |
| `translate_text` | 短文本同步翻译，立即返回译文（可选术语表约束） |
| `submit_document` | 提交长文档进入异步翻译队列，返回 `task_id` |
| `get_task_status` | 查询任务状态与进度 |
| `list_tasks` | 分页列出任务 |
| `cancel_task` | 取消 `pending` / `processing` 任务 |
| `export_result` | 取回结果（`mono` 单语 / `bilingual` 双语对照 Markdown） |
| `list_glossaries` | 列出术语表 |
| `get_glossary` | 查询单个术语表词条 |
| `create_glossary` | 新建术语表 |
| `modify_glossary_terms` | 增量增/删术语词条 |
| `update_glossary` | 全量替换术语表词条 |
| `delete_glossary` | 删除术语表 |

### 典型工作流

**短文本**：直接 `translate_text`。

**长文档**：`submit_document` → 轮询 `get_task_status` 直到 `completed` /
`partial_success` → `export_result` 取回 Markdown。文档内容二选一：纯文本 /
Markdown 用 `text` 直接传；PDF / EPUB 等二进制用 `content_base64` 传 base64 字节。

**取消语义**：`cancel_task` 只对 `pending` / `processing` 任务生效并置为
`cancelled`；对已进入终态的任务返回 `cancelled: false` 且不改变状态。取消一个
运行中的任务后，即使后台 worker 把该批次跑完，也不会把状态覆盖回 `completed`。

## 运行

MCP Server 走 **stdio** 传输——由客户端负责拉起进程，通常不需要手动启动。
本地调试可直接运行：

```bash
# 免安装（在仓库根目录运行，data/ 相对路径就地解析）
python -m src.interfaces.mcp.server

# 或安装为 console 命令后
pip install -e .
translator-mcp
```

翻译需要 LLM 密钥，请确保 `.env` 中已配置 `SILICONFLOW_API_KEY`（见
[快速开始](../README.md)）。术语表工具与任务查询不消耗 LLM。

## 在 Claude Desktop 中配置

编辑 Claude Desktop 的 `claude_desktop_config.json`
（macOS 路径：`~/Library/Application Support/Claude/claude_desktop_config.json`），
新增一个 MCP server：

```json
{
  "mcpServers": {
    "agentic-translator": {
      "command": "python",
      "args": ["-m", "src.interfaces.mcp.server"],
      "cwd": "/absolute/path/to/agentic-translator",
      "env": {
        "SILICONFLOW_API_KEY": "sk-your-key-here"
      }
    }
  }
}
```

- `cwd` 必须指向仓库根目录，服务内部的 `data/` 相对路径（任务库、上传、结果、
  术语表）都以此为基准。
- 已执行 `pip install -e .` 时，可把 `command` 换成 `translator-mcp` 并省略 `args`。
- 保存后重启 Claude Desktop，即可在对话中看到并调用上述 12 个工具。

## 测试

工具处理器经 service 层接缝测试（临时 SQLite + 注入符合引擎契约的
`FakeEngine`，不触碰真实 LLM），覆盖工具发现、术语约束、`submit → status →
export` 全流程、取消状态语义、术语表 CRUD 与存储互通：

```bash
pytest tests/test_mcp_server.py -q
```
