#!/usr/bin/env python3
"""
独立翻译 worker 启动脚本
"""
import argparse
import asyncio
import logging
import multiprocessing
import signal
import sys
from contextlib import suppress

from src.api.worker import TaskWorker
from src.utils.config_loader import get_config


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/translation.log", encoding="utf-8"),
        ],
    )


async def run_single_worker(worker_name: str, parallel_tasks: int):
    worker = TaskWorker(worker_name=worker_name, max_parallel_tasks=parallel_tasks)
    try:
        await worker.run_forever()
    finally:
        await worker.stop()


def worker_entry(worker_name: str, parallel_tasks: int):
    configure_logging()
    print(f"🎯 启动独立翻译 worker: {worker_name} (任务并发={parallel_tasks})")
    asyncio.run(run_single_worker(worker_name, parallel_tasks))


def main():
    config = get_config()
    parser = argparse.ArgumentParser(description="启动独立翻译 worker")
    parser.add_argument(
        "--processes",
        type=int,
        default=config.worker_processes,
        help="启动多少个 worker 进程",
    )
    parser.add_argument(
        "--parallel-tasks",
        type=int,
        default=config.worker_max_parallel_tasks,
        help="每个 worker 进程同时处理多少个翻译任务",
    )
    args = parser.parse_args()

    configure_logging()
    print(
        "🎯 启动独立翻译 worker 集群..."
        f" 进程数={args.processes}, 每进程任务并发={args.parallel_tasks}"
    )

    if args.processes <= 1:
        asyncio.run(run_single_worker("worker-1", args.parallel_tasks))
        return

    processes: list[multiprocessing.Process] = []

    def shutdown_handler(signum, frame):
        print("\n⏹️  正在关闭 worker 集群...")
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    for index in range(args.processes):
        process = multiprocessing.Process(
            target=worker_entry,
            args=(f"worker-{index + 1}", args.parallel_tasks),
            daemon=False,
        )
        process.start()
        processes.append(process)

    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        shutdown_handler(signal.SIGINT, None)
    finally:
        for process in processes:
            with suppress(Exception):
                if process.is_alive():
                    process.terminate()
                process.join(timeout=5)


if __name__ == "__main__":
    main()
