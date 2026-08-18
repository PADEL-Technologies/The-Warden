from typing import Protocol


class PingService(Protocol):
    def format_latency(self, latency: float) -> str: ...
