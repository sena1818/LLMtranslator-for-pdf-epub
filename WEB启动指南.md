# 🌐 AI 翻译系统 Web 端启动指南

> 基于 FastAPI + React 的文本翻译系统

## 🚀 极简启动

### 1. 启动后端
```bash
# 根目录下
pip install -r requirements.txt
python run_server.py
```

### 2. 启动前端
```bash
# 前端目录下（frontend/）
cd frontend
npm install && npm run build
```
*(后端会自动托管构建后的前端页面，直接访问 http://localhost:8000 即可)*

---



###  用完如何关闭?
这是一个持续运行的 Web 服务。**如果你不再使用了，请务必关闭它**，否则它会在后台持续检查任务，消耗电量。
- **关闭方法**: 在运行 `run_server.py` 的终端窗口，按 `Ctrl + C` 即可终止。

---

## 🌍 分享给朋友 (内网穿透)

推荐使用 **ngrok** (最稳定):
```bash
# 终端 1
python run_server.py

# 终端 2
ngrok http 8000
```
复制生成的 `https://xxxx.ngrok-free.app` 发给朋友即可。

---

## 🛠️ 开发模式

如果需要修改代码并实时预览：

1. **后端**: `python run_server.py` (支持热重载)
2. **前端**: `cd frontend && npm run dev` (访问 http://localhost:5173)

---

## ❓ 常见问题

- **端口被占用**: 修改 `run_server.py` 中的 `port=8000`。
- **数据库重置**: 删除 `data/tasks.db` 后重启服务。
- **API 文档**: 访问 http://localhost:8000/docs
