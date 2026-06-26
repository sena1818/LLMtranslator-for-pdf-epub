"""
FastAPI 应用入口
"""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/translation.log", encoding='utf-8')
    ]
)

from .routes import translation, glossary, files
from .database.db import Database
from .worker import TaskWorker
from ..utils.config_loader import get_config

# 创建应用
app = FastAPI(
    title="AI 翻译系统 API",
    description="后现代哲学文本翻译系统",
    version="1.0.0"
)

# CORS 配置 (允许前端调用)
# 注意: allow_origins=["*"] 与 allow_credentials=True 是非法组合，
# 浏览器会直接忽略带凭证的请求。本服务不依赖 cookie/凭证，
# 故关闭 credentials，保留通配来源以支持 ngrok 隧道分享。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(translation.router)
app.include_router(glossary.router)
app.include_router(files.router)

# 静态文件服务 (优先使用 Vite 最新构建产物)
frontend_build_dir = None
for candidate in [Path("frontend/dist"), Path("frontend_dist")]:
    if candidate.exists():
        frontend_build_dir = candidate
        break

if frontend_build_dir:
    app.mount("/", StaticFiles(directory=str(frontend_build_dir), html=True), name="frontend")


# 启动事件
@app.on_event("startup")
async def startup_event():
    """初始化数据库"""
    config = get_config()
    port = int(os.getenv("TRANSLATION_SERVER_PORT", str(config.server_port)))
    db = Database()
    await db.initialize()
    print("✅ 数据库初始化完成")

    inline_worker_enabled = os.getenv(
        "TRANSLATION_INLINE_WORKER",
        "1" if config.inline_worker_enabled else "0",
    ) != "0"

    if inline_worker_enabled:
        app.state.worker = TaskWorker()
        app.state.worker_task = asyncio.create_task(app.state.worker.run_forever())
        print("🎯 已启动内联任务 worker")
    else:
        app.state.worker = None
        app.state.worker_task = None
        print("⏸️  内联 worker 已禁用，请单独运行 run_worker.py")

    print("✅ FastAPI 服务器启动成功")
    print(f"📖 API 文档: http://localhost:{port}/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """优雅关闭内联 worker"""
    worker = getattr(app.state, "worker", None)
    worker_task = getattr(app.state, "worker_task", None)
    if worker:
        await worker.stop()
    if worker_task:
        await worker_task


# 健康检查
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "翻译系统运行中"}
