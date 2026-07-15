# 可观测性（Langfuse）

翻译系统经 LangChain 回调把每次 Agent 调用（分析员 / 翻译员 / 审校员）与逐块 token 消耗
上报到 [Langfuse](https://langfuse.com)。默认**关闭**，开关在配置，缺 SDK 或密钥时自动降级为无操作，
不影响翻译主流程。

## 启用

1. 安装依赖（已在 `requirements.txt` / `pyproject.toml`）：`pip install langfuse langchain`。
2. 配置开关 `config/config.yaml`：

   ```yaml
   observability:
     langfuse:
       enabled: true
   ```

3. 设置环境变量（**密钥不写入配置文件**）：

   ```bash
   export LANGFUSE_PUBLIC_KEY=pk-...
   export LANGFUSE_SECRET_KEY=sk-...
   export LANGFUSE_HOST=https://cloud.langfuse.com   # 自部署则填自己的地址
   ```

4. 跑一次翻译，Langfuse UI 中即可看到完整调用链与每个块的 token 消耗。

## 生效条件

`enabled: true` **且**具备 `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` 才真正接入；
任一缺失都降级为无操作并打印 warning。判定逻辑见 `src/infrastructure/observability/langfuse_tracing.py`
（`build_langfuse_callbacks` / `langfuse_settings`）。回调在 `ChatModelFactory` 中一次性挂到三个角色模型上，
经 LangChain 回调链自动下沉到每次调用。

## 与评测的关系

评测（`translator-eval`）用一个独立的本地回调 `UsageMetadataCollector` 采集 token，
**不依赖 Langfuse 服务**也能拿到 token/成本数据；Langfuse 开启时二者并存，互不影响。
