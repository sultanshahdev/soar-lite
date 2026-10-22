"""Polling worker for persisted suspicious-IP investigations."""

import asyncio
import os
import signal
import threading

from app.config import get_settings
from app.connectors.abuseipdb import AbuseIPDBConnector
from app.persistence.database import SessionLocal
from app.workers.investigations import InvestigationProcessor


def main() -> None:
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    settings = get_settings()
    processor = InvestigationProcessor(
        SessionLocal,
        AbuseIPDBConnector(),
        worker_id=os.environ.get("HOSTNAME", "soar-lite-worker"),
        lease_seconds=settings.investigation_lease_seconds,
        max_attempts=settings.investigation_max_attempts,
        retry_base_seconds=settings.investigation_retry_base_seconds,
    )
    while not stop.is_set():
        processed = asyncio.run(processor.process_once())
        if not processed:
            stop.wait(timeout=settings.investigation_poll_seconds)


if __name__ == "__main__":
    main()
