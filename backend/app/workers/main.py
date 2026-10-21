"""Idle worker process scaffold; it does not execute workflows."""

import signal
import threading
import time


def main() -> None:
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.wait(timeout=1):
        pass


if __name__ == "__main__":
    main()
