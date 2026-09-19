from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from models import Event


class CustomerState(BaseModel):
    """
    Deterministic Customer 360 state.

    This is the shared working state that later agents will read from.
    It does NOT perform life-event inference.
    """

    customer_id: str

    # ---------------------------------------------------------
    # Timeline
    # ---------------------------------------------------------

    last_event_time: datetime | None = None
    last_ingestion_time: datetime | None = None

    # ---------------------------------------------------------
    # Event statistics
    # ---------------------------------------------------------

    total_events: int = 0

    events_by_source: dict[str, int] = Field(default_factory=dict)
    events_by_type: dict[str, int] = Field(default_factory=dict)
    
    # ---------------------------------------------------------
    # Account-level information
    # ---------------------------------------------------------

    latest_balances: dict[str, float] = Field(default_factory=dict)
    balance_event_times: dict[str, datetime] = Field(default_factory=dict)
    transaction_counts: dict[str, int] = Field(default_factory=dict)
    transaction_amounts: dict[str, float] = Field(default_factory=dict)

    # ---------------------------------------------------------
    # Support activity
    # ---------------------------------------------------------

    support_tickets_created: int = 0
    support_tickets_resolved: int = 0
    support_calls: int = 0

    # ---------------------------------------------------------
    # Digital / usage activity
    # ---------------------------------------------------------

    web_logins: int = 0
    web_searches: int = 0
    web_features_used: int = 0
    web_sessions: int = 0

    # ---------------------------------------------------------
    # KYC / profile changes
    # ---------------------------------------------------------

    kyc_updates: int = 0
    profile_changes: list[dict[str, Any]] = Field(default_factory=list)

    # ---------------------------------------------------------
    # Recent events
    # ---------------------------------------------------------

    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    all_events: list[Event] = Field(default_factory=list)
    max_recent_events: int = 20

    # =========================================================
    # UPDATE STATE
    # =========================================================

    def update(self, event: Event) -> None:
        """
        Apply one event to the Customer State Board.
        """

        # -----------------------------------------------------
        # 1. Basic event statistics
        # -----------------------------------------------------

        self.total_events += 1

        self.events_by_source[event.source_system] = (
            self.events_by_source.get(event.source_system, 0) + 1
        )

        self.events_by_type[event.event_type] = (
            self.events_by_type.get(event.event_type, 0) + 1
        )

        # -----------------------------------------------------
        # 2. Timeline
        # -----------------------------------------------------

        if (
            self.last_event_time is None
            or event.event_time > self.last_event_time
        ):
            self.last_event_time = event.event_time

        if (
            self.last_ingestion_time is None
            or event.ingestion_time > self.last_ingestion_time
        ):
            self.last_ingestion_time = event.ingestion_time

        # -----------------------------------------------------
        # 3. Transaction information
        # -----------------------------------------------------

        transaction_sources = {
            "card_payments",
            "instant_payments",
            "ach_wire",
            "core_banking_ledger",
            "trading_brokerage",
        }

        if event.source_system in transaction_sources:

            amount = event.payload.get("amount")

            if isinstance(amount, (int, float)):

                self.transaction_amounts[event.source_system] = (
                    self.transaction_amounts.get(
                        event.source_system,
                        0.0
                    )
                    + float(amount)
                )

            self.transaction_counts[event.source_system] = (
                self.transaction_counts.get(
                    event.source_system,
                    0
                )
                + 1
            )

        # -----------------------------------------------------
        # 4. Core banking balance
        # -----------------------------------------------------

        if event.source_system == "core_banking_ledger":
            balance_after = event.payload.get("balance_after")

            if (event.account_id is not None and isinstance(balance_after, (int, float))):
                previous_time = self.balance_event_times.get(event.account_id)
               # Only update the balance if this event is newer
                # according to EVENT TIME.
                if (previous_time is None or event.event_time >= previous_time):
                    self.latest_balances[event.account_id] = float(balance_after)
                    self.balance_event_times[event.account_id] = event.event_time
        # -----------------------------------------------------
        # 5. Support activity
        # -----------------------------------------------------

        if event.source_system == "support_logs":

            if event.event_type == "ticket_created":
                self.support_tickets_created += 1

            elif event.event_type == "ticket_resolved":
                self.support_tickets_resolved += 1

            elif event.event_type == "call_transcript":
                self.support_calls += 1

        # -----------------------------------------------------
        # 6. Web / application activity
        # -----------------------------------------------------

        if event.source_system == "web_app_events":

            if event.event_type == "login":
                self.web_logins += 1

            elif event.event_type == "search_query":
                self.web_searches += 1

            elif event.event_type == "feature_used":
                self.web_features_used += 1

            elif event.event_type == "session_duration":
                self.web_sessions += 1

        # -----------------------------------------------------
        # 7. KYC / profile changes
        # -----------------------------------------------------

        if event.source_system == "loan_kyc":

            if event.event_type in {
                "kyc_update",
                "address_change",
                "marital_status_change",
                "dependents_change",
            }:

                self.kyc_updates += 1

                self.profile_changes.append(
                    {
                        "event_id": event.event_id,
                        "event_time": event.event_time.isoformat(),
                        "event_type": event.event_type,
                        "payload": event.payload,
                    }
                )

        # -----------------------------------------------------
        # 8. Full event history
# -----------------------------------------------------

        self.all_events.append(event)
            # {
            #     "event_id": event.event_id,
            #     "event_time": event.event_time.isoformat(),
            #     "ingestion_time": event.ingestion_time.isoformat(),
            #     "source_system": event.source_system,
            #     "event_type": event.event_type,
            #     "account_id": event.account_id,
            #     "payload": event.payload,
            # }


# -----------------------------------------------------
# 9. Recent-event memory
# -----------------------------------------------------

        self.recent_events.append(
            {
                "event_id": event.event_id,
                "event_time": event.event_time.isoformat(),
                "ingestion_time": event.ingestion_time.isoformat(),
                "source_system": event.source_system,
                "event_type": event.event_type,
                "account_id": event.account_id,
                "payload": event.payload,
            }
        )

# Keep only the most recent N events.
        if len(self.recent_events) > self.max_recent_events:

            self.recent_events = self.recent_events[
                -self.max_recent_events:
            ]

    # =========================================================
    # SUMMARY
    # =========================================================

    def summary(self) -> dict[str, Any]:

        return {
            "customer_id": self.customer_id,

            "last_event_time": (
                self.last_event_time.isoformat()
                if self.last_event_time
                else None
            ),

            "last_ingestion_time": (
                self.last_ingestion_time.isoformat()
                if self.last_ingestion_time
                else None
            ),

            "total_events": self.total_events,

            "events_by_source": self.events_by_source,

            "events_by_type": self.events_by_type,

            "latest_balances": self.latest_balances,

            "balance_event_time": {
                account: timestamp.isoformat()
                for account, timestamp
                in self.balance_event_times.items()
            },

            "transaction_counts": self.transaction_counts,

            "transaction_amounts": self.transaction_amounts,

            "support": {
                "tickets_created": self.support_tickets_created,
                "tickets_resolved": self.support_tickets_resolved,
                "calls": self.support_calls,
            },

            "web_activity": {
                "logins": self.web_logins,
                "searches": self.web_searches,
                "features_used": self.web_features_used,
                "sessions": self.web_sessions,
            },

            "kyc_updates": self.kyc_updates,

            "recent_events_count": len(self.recent_events),
        }