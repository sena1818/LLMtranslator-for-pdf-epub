#!/usr/bin/env python3
"""
Web 翻译系统启动脚本
"""
import uvicorn

if __name__ == "__main__":
    print("🚀 启动 Web 翻译系统...")
    print("📖 API 文档将在: http://localhost:8000/docs")
    print("🌐 Web 界面将在: http://localhost:8000 (前端构建后)")
    print()

    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # 开发模式，代码修改自动重启
    )
