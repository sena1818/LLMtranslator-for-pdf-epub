#!/usr/bin/env python3
"""
Web 翻译系统启动脚本
"""
import os
import socket
import sys

from src.utils.config_loader import get_config


def is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("❌ 当前 Python 环境缺少 `uvicorn`")
        print("💡 请先在你激活的环境里安装依赖:")
        print("   python -m pip install -r requirements.txt")
        sys.exit(1)

    config = get_config()
    port = int(os.getenv("TRANSLATION_SERVER_PORT", str(config.server_port)))
    reload_enabled = os.getenv(
        "TRANSLATION_SERVER_RELOAD",
        "1" if config.server_reload else "0",
    ) != "0"

    if not is_port_available(port):
        print(f"❌ 端口 {port} 已被占用")
        print(f"💡 可先结束旧进程，或改用: TRANSLATION_SERVER_PORT={port + 1} python run_server.py")
        sys.exit(1)

    print("🚀 启动 Web 翻译系统...")
    print(f"📖 API 文档将在: http://localhost:{port}/docs")
    print(f"🌐 Web 界面将在: http://localhost:{port} (前端构建后)")
    if os.getenv("TRANSLATION_INLINE_WORKER", "1") == "0":
        print("⏸️  当前已禁用内联 worker，请另开终端运行: python run_worker.py")
    else:
        print("🎯 当前会同时启动内联 worker；如需独立 worker，请设置 TRANSLATION_INLINE_WORKER=0")
    if reload_enabled:
        print("🔄 当前启用开发热重载，仅建议在改代码时使用")
    else:
        print("🧱 当前关闭热重载，更适合长时间翻译任务")
    print()

    run_kwargs = {
        "app": "src.api.app:app",
        "host": "0.0.0.0",
        "port": port,
    }
    if reload_enabled:
        run_kwargs["reload"] = True
        run_kwargs["reload_dirs"] = config.server_reload_dirs

    uvicorn.run(**run_kwargs)
