"""
Consumer runner — starts all Kafka consumers as asyncio tasks.
Entry point: python -m kafka.consumers.runner
"""
import asyncio
import signal
import sys

from core.logging import configure_logging, get_logger
from kafka.consumers import ml_scorer, graph_sync, alert_dispatcher, snowflake_writer

log = get_logger(__name__)

_shutdown = asyncio.Event()


def _handle_signal(sig):
    log.info("Shutdown signal received", signal=sig.name)
    _shutdown.set()


async def main() -> None:
    configure_logging()
    log.info("Starting all Kafka consumers")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s))

    tasks = [
        asyncio.create_task(ml_scorer.run(), name="ml_scorer"),
        asyncio.create_task(graph_sync.run(), name="graph_sync"),
        asyncio.create_task(alert_dispatcher.run(), name="alert_dispatcher"),
        asyncio.create_task(snowflake_writer.run(), name="snowflake_writer"),
    ]

    await _shutdown.wait()
    log.info("Cancelling consumer tasks")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("All consumers stopped")


if __name__ == "__main__":
    asyncio.run(main())
