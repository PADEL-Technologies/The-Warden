class PingService:
    def format_latency(self, latency: float) -> str:
        return f"{latency * 1000:.0f} ms"
