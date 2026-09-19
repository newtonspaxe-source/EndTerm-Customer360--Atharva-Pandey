import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone


class TraceLogger:
    """Append-only structured trace for observability and audit."""
    def __init__(self, root: str = "outputs/traces"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.trace_id = uuid.uuid4().hex[:12]
        self.path = self.root / f"{self.trace_id}.jsonl"

    def log(self, stage: str, event: str, data=None):
        record = {
            "trace_id": self.trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "event": event,
            "data": data or {},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def span(self, stage: str, name: str):
        return TraceSpan(self, stage, name)


class TraceSpan:
    def __init__(self, tracer: TraceLogger, stage: str, name: str):
        self.tracer = tracer
        self.stage = stage
        self.name = name
        self.start = None

    def __enter__(self):
        self.start = time.perf_counter()
        self.tracer.log(self.stage, self.name + "_start")
        return self

    def __exit__(self, exc_type, exc, tb):
        latency_ms = (time.perf_counter() - self.start) * 1000
        self.tracer.log(
            self.stage,
            self.name + "_end",
            {
                "latency_ms": round(latency_ms, 2),
                "error": str(exc) if exc else None,
            },
        )
