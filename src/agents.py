from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from models import Event
from state import CustomerState
from tools import windowed_usage, support_ticket_retrieval, transaction_baseline, kyc_lookup
from governance import authorize


# ============================================================
# 1. COMMON FINDING SCHEMA
# ============================================================

class AgentFinding(BaseModel):
    agent_name: str
    customer_id: str

    signal_type: str
    severity: Literal["low", "medium", "high"]

    evidence: list[str] = Field(default_factory=list)

    event_ids: list[str] = Field(default_factory=list)

    confidence: float = Field(ge=0.0, le=1.0)

    recommendation: str
    tools_used: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)


# ============================================================
# 2. BASE AGENT
# ============================================================

class BaseAgent:

    def __init__(self, name: str):
        self.name = name

    def finding(
        self,
        customer_id: str,
        signal_type: str,
        severity: str,
        evidence: list[str],
        event_ids: list[str],
        confidence: float,
        recommendation: str,
        tools_used: list[str] | None = None,
        data_sources: list[str] | None = None,
    ) -> AgentFinding:

        defaults = {
            "usage_agent": (["windowed_usage", "trend_detection", "anomaly_scoring"], ["web_app_events"]),
            "support_agent": (["ticket_retrieval", "sentiment_analysis", "urgency_detection"], ["support_logs"]),
            "transaction_agent": (["transaction_query", "anomaly_scoring", "historical_baseline"], list(TransactionAgent.TRANSACTION_SOURCES)),
            "kyc_compliance_agent": (["kyc_lookup", "sanctions_lookup", "compliance_rules"], ["loan_kyc"]),
        }
        if tools_used is None or data_sources is None:
            dt, ds = defaults.get(self.name, ([], []))
            tools_used = tools_used or dt
            data_sources = data_sources or ds

        return AgentFinding(
            agent_name=self.name,
            customer_id=customer_id,
            signal_type=signal_type,
            severity=severity,
            evidence=evidence,
            event_ids=event_ids,
            confidence=confidence,
            recommendation=recommendation,
            tools_used=tools_used or [],
            data_sources=data_sources or [],
        )


# ============================================================
# 3. USAGE AGENT
# ============================================================

class UsageAgent(BaseAgent):

    def __init__(self):
        super().__init__("usage_agent")

    def analyze(
        self,
        state: CustomerState,
        events: list[Event],
    ) -> AgentFinding:

        usage_events = [e for e in events if authorize(self.name, e.source_system)]
        usage_window = windowed_usage(usage_events, days=14)

        if not usage_events:
            return self.finding(
                state.customer_id,
                "no_usage_signal",
                "low",
                ["No web/app events available."],
                [],
                0.20,
                "No usage-based action."
            )

        logins = 0
        searches = 0
        features = 0
        sessions = 0

        for event in usage_events:

            if event.event_type == "login":
                logins += 1

            elif event.event_type == "search_query":
                searches += 1

            elif event.event_type == "feature_used":
                features += 1

            elif event.event_type == "session_duration":
                sessions += 1

        evidence = [
            f"Observed {logins} login events.",
            f"Observed {searches} search events.",
            f"Observed {features} feature-use events.",
            f"Observed {sessions} session events.",
        ]

        # Look for recent inactivity.
        latest_usage_time = max(
            e.event_time for e in usage_events
        )

        recent_cutoff = latest_usage_time - timedelta(days=14)

        recent_usage = [
            e for e in usage_events
            if e.event_time >= recent_cutoff
        ]

        if len(recent_usage) == 0:

            return self.finding(
                state.customer_id,
                "usage_decline",
                "medium",
                evidence + [
                    "No usage events observed in the recent 14-day window."
                ],
                [],
                0.70,
                "Consider checking for digital disengagement."
            )

        return self.finding(
            state.customer_id,
            "usage_activity",
            "low",
            evidence + [
                f"{len(recent_usage)} usage events observed "
                "in the recent 14-day window."
            ],
            [e.event_id for e in usage_events[-10:]],
            0.60,
            "Continue monitoring usage behaviour."
        )


# ============================================================
# 4. SUPPORT AGENT
# ============================================================

class SupportAgent(BaseAgent):

    def __init__(self):
        super().__init__("support_agent")

    def analyze(
        self,
        state: CustomerState,
        events: list[Event],
    ) -> AgentFinding:

        support_events = support_ticket_retrieval([e for e in events if authorize(self.name, e.source_system)])

        if not support_events:
            return self.finding(
                state.customer_id,
                "no_support_signal",
                "low",
                ["No support events available."],
                [],
                0.20,
                "No support intervention."
            )

        tickets = [
            e for e in support_events
            if e.event_type == "ticket_created"
        ]

        calls = [
            e for e in support_events
            if e.event_type == "call_transcript"
        ]

        unresolved = []

        for event in tickets:

            resolution_status = event.payload.get(
                "resolution_status"
            )

            if resolution_status not in {
                "resolved",
                "closed",
            }:
                unresolved.append(event)

        evidence = [
            f"Observed {len(tickets)} support tickets.",
            f"Observed {len(calls)} support calls.",
            f"Observed {len(unresolved)} potentially unresolved tickets.",
        ]

        # Inspect support text for clear distress/friction signals.
        keywords = [
            "problem",
            "issue",
            "urgent",
            "help",
            "fee",
            "charged",
            "denied",
            "cannot",
            "unable",
        ]

        matched_events = []

        for event in support_events:

            raw_text = str(
                event.payload.get("raw_text", "")
            ).lower()

            if any(word in raw_text for word in keywords):
                matched_events.append(event)

        if matched_events:

            evidence.append(
                f"{len(matched_events)} support events contain "
                "potential issue/friction signals."
            )

            return self.finding(
                state.customer_id,
                "support_friction",
                "medium",
                evidence,
                [e.event_id for e in matched_events],
                0.75,
                "Review support friction together with other customer signals."
            )

        return self.finding(
            state.customer_id,
            "support_activity",
            "low",
            evidence,
            [e.event_id for e in support_events[-10:]],
            0.55,
            "Continue monitoring support interactions."
        )


# ============================================================
# 5. TRANSACTION AGENT
# ============================================================

class TransactionAgent(BaseAgent):

    TRANSACTION_SOURCES = {
        "card_payments",
        "instant_payments",
        "ach_wire",
        "core_banking_ledger",
        "trading_brokerage",
    }

    def __init__(self):
        super().__init__("transaction_agent")

    def analyze(
        self,
        state: CustomerState,
        events: list[Event],
    ) -> AgentFinding:

        transaction_events = [e for e in events if authorize(self.name, e.source_system)]
        transaction_summary = transaction_baseline(transaction_events)

        if not transaction_events:
            return self.finding(
                state.customer_id,
                "no_transaction_signal",
                "low",
                ["No transaction events available."],
                [],
                0.20,
                "No transaction action."
            )

        total_events = len(transaction_events)

        total_amount = 0.0

        declines = []
        refunds = []
        international = []

        for event in transaction_events:

            amount = event.payload.get("amount", 0)

            try:
                total_amount += float(amount)
            except (TypeError, ValueError):
                pass

            if event.event_type in {
                "decline",
                "payment_declined",
            }:
                declines.append(event)

            if event.event_type == "refund":
                refunds.append(event)

            if event.payload.get("is_international") is True:
                international.append(event)

        evidence = [
            f"Observed {total_events} transaction events.",
            f"Aggregate transaction amount field: {total_amount:.2f}.",
            f"Observed {len(declines)} decline events.",
            f"Observed {len(refunds)} refund events.",
            f"Observed {len(international)} international card events.",
        ]

        # We deliberately do NOT call every large transaction fraud.
        # The agent only reports a transaction signal.
        if declines:

            evidence.append(
                "Transaction declines require contextual review."
            )

            return self.finding(
                state.customer_id,
                "transaction_friction",
                "medium",
                evidence,
                [e.event_id for e in declines],
                0.70,
                "Correlate transaction friction with support and usage signals."
            )

        return self.finding(
            state.customer_id,
            "transaction_activity",
            "low",
            evidence,
            [e.event_id for e in transaction_events[-10:]],
            0.60,
            "Continue monitoring transaction behaviour."
        )


# ============================================================
# 6. KYC / COMPLIANCE AGENT
# ============================================================

class KYCComplianceAgent(BaseAgent):

    def __init__(self):
        super().__init__("kyc_compliance_agent")

    def analyze(
        self,
        state: CustomerState,
        events: list[Event],
    ) -> AgentFinding:

        kyc_events = kyc_lookup([e for e in events if authorize(self.name, e.source_system)])

        if not kyc_events:
            return self.finding(
                state.customer_id,
                "no_kyc_signal",
                "low",
                ["No KYC/compliance events available."],
                [],
                0.20,
                "No KYC action."
            )

        profile_changes = []

        for event in kyc_events:

            if event.event_type in {
                "address_change",
                "marital_status_change",
                "dependents_change",
            }:
                profile_changes.append(event)

        loan_events = [
            e for e in kyc_events
            if e.event_type in {
                "loan_application",
                "loan_disbursed",
            }
        ]

        evidence = [
            f"Observed {len(kyc_events)} KYC/loan events.",
            f"Observed {len(profile_changes)} profile changes.",
            f"Observed {len(loan_events)} loan-related events.",
        ]

        if profile_changes:

            evidence.append(
                "Customer profile information changed."
            )

            return self.finding(
                state.customer_id,
                "profile_change",
                "medium",
                evidence,
                [e.event_id for e in profile_changes],
                0.85,
                "Make updated customer profile available to downstream inference."
            )

        return self.finding(
            state.customer_id,
            "kyc_activity",
            "low",
            evidence,
            [e.event_id for e in kyc_events[-10:]],
            0.60,
            "Continue monitoring KYC/compliance events."
        )


# ============================================================
# 7. SPECIALIST AGENT MANAGER
# ============================================================

class SpecialistAgents:

    def __init__(self):

        self.usage = UsageAgent()
        self.support = SupportAgent()
        self.transaction = TransactionAgent()
        self.kyc = KYCComplianceAgent()

    def run(
        self,
        state: CustomerState,
        events: list[Event],
    ) -> list[AgentFinding]:

        findings = [
            self.usage.analyze(state, events),
            self.support.analyze(state, events),
            self.transaction.analyze(state, events),
            self.kyc.analyze(state, events),
        ]

        return findings