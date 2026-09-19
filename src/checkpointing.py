import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from datetime import datetime


class InferredEvent(BaseModel):
    as_of_time: datetime
    inferred_state: str
    confidence_band: str
    action: str
    action_subtype: str | None = None
    hitl_status: str
    notes: str = ""
    evidence: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    decision_trace_id: str | None = None


class InferredEventWriter:
    """Append-only, machine-readable decision history."""
    def __init__(self, path: str = "outputs/inferred_events.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, item: InferredEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(item.model_dump_json() + "\n")

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


class DecisionCheckpoint:
    """
    Prevents excessive LLM calls while still making the system ambient.
    An inference is requested when:
      - a high-value trigger event arrives,
      - enough events have accumulated,
      - or the caller explicitly forces a checkpoint.
    """
    TRIGGER_TYPES = {
        "ticket_created",
        "ticket_resolved",
        "call_transcript",
        "kyc_update",
        "address_change",
        "marital_status_change",
        "dependents_change",
        "loan_application",
        "loan_disbursed",
    }

    KEYWORDS = (
        "hospital", "medical", "hardship", "daycare", "baby",
        "education", "competitor", "close account", "income",
        "payment plan", "insurance", "retirement", "promotion",
        "mortgage", "relocation",
    )

    def __init__(self, min_events_between_inference: int = 8):
        self.min_events_between_inference = min_events_between_inference
        self.events_since_last = 0

    def observe(self, event, agent_findings=None) -> bool:
        self.events_since_last += 1

        payload = event.payload or {}
        text = " ".join(
            str(payload.get(k, ""))
            for k in ("search_text", "raw_text", "merchant_name", "counterparty_name",
                      "transaction_type", "feature_or_page")
        ).lower()

        if event.event_type in self.TRIGGER_TYPES:
            return True

        # Agent-dependent trigger: multiple specialist domains independently
        # report meaningful signals for the same customer.
        if agent_findings:
            meaningful = [f for f in agent_findings if getattr(f, "confidence", 0) >= 0.70 and getattr(f, "signal_type", "") not in {"no_usage_signal", "no_support_signal", "no_transaction_signal", "no_kyc_signal"}]
            if len({getattr(f, "agent_name", "") for f in meaningful}) >= 2:
                return True

        if any(k in text for k in self.KEYWORDS):
            return True

        if self.events_since_last >= self.min_events_between_inference:
            return True

        return False

    def mark_inferred(self) -> None:
        self.events_since_last = 0
