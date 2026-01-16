"""
FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

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
    allow_origins=[
        "http://localhost:3000",  # React 开发服务器
        "http://localhost:5173",  # Vite 开发服务器
    ],
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
    print("✅ FastAPI 服务器启动成功")
    print("📖 API 文档: http://localhost:8000/docs")


# 健康检查
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "翻译系统运行中"}
