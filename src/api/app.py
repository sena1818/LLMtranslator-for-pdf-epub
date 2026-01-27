"""
FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
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

# 创建应用
app = FastAPI(
    title="AI 翻译系统 API",
    description="后现代哲学文本翻译系统",
    version="1.0.0"
)

# CORS 配置 (允许前端调用)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（包括 ngrok 隧道）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(translation.router)
app.include_router(glossary.router)
app.include_router(files.router)

# 静态文件服务 (前端构建产物)
if Path("frontend_dist").exists():
    app.mount("/", StaticFiles(directory="frontend_dist", html=True), name="frontend")


# 启动事件
@app.on_event("startup")
async def startup_event():
    """初始化数据库"""
    db = Database()
    await db.initialize()
    print("✅ 数据库初始化完成")
    
    # 重置中断的任务
    from .services.translation_service import TranslationService
    service = TranslationService()
    reset_count = await service.reset_interrupted_tasks()
    if reset_count > 0:
        print(f"⚠️  重置了 {reset_count} 个因服务器重启而中断的任务")
    print("✅ FastAPI 服务器启动成功")
    print("📖 API 文档: http://localhost:8000/docs")


# 健康检查
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "翻译系统运行中"}
