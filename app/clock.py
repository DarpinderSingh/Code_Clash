from datetime import datetime, timezone
from typing import Protocol


class ClockProtocol(Protocol):
    def now_utc(self) -> datetime:
        ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


_system_clock = SystemClock()


def get_clock() -> SystemClock:
    return _system_clock


def now_utc() -> datetime:
    return get_clock().now_utc()
