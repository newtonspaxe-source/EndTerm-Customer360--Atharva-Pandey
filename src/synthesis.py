from pydantic import BaseModel, Field
from typing import Literal

from state import CustomerState
from agents import AgentFinding


# ============================================================
# OUTPUT SCHEMA
# ============================================================

class CorrelatedSignal(BaseModel):
    """
    Higher-level signal produced by the Synthesis / Correlation
    layer after combining specialist-agent findings.
    """

    signal: str

    strength: Literal[
        "weak",
        "moderate",
        "strong"
    ]

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    supporting_agents: list[str] = Field(
        default_factory=list
    )

    evidence: list[str] = Field(
        default_factory=list
    )

    event_ids: list[str] = Field(
        default_factory=list
    )


# ============================================================
# SYNTHESIS AGENT
# ============================================================

class SynthesisAgent:
    """
    Correlates findings from specialist agents.

    Specialist agents:
        - Usage Agent
        - Support Agent
        - Transaction Agent
        - KYC / Compliance Agent

    The Synthesis Agent does NOT make the final life-event
    decision.

    Its job is to transform multiple low-level specialist
    findings into higher-level cross-domain signals.

    Example:

        Support Agent
              +
        Transaction Agent
              +
        Usage Agent
              ↓
        Cross-domain financial distress
    """

    def __init__(self):
        self.name = "synthesis_agent"

    # ========================================================
    # MAIN ANALYSIS FUNCTION
    # ========================================================

    def analyze(
        self,
        state: CustomerState,
        findings: list[AgentFinding],
        events: list,
    ) -> list[CorrelatedSignal]:

        signals: list[CorrelatedSignal] = []

        # ----------------------------------------------------
        # 1. Create lookup map for specialist findings
        # ----------------------------------------------------

        finding_map = {
            finding.agent_name: finding
            for finding in findings
        }

        usage = finding_map.get(
            "usage_agent"
        )

        support = finding_map.get(
            "support_agent"
        )

        transaction = finding_map.get(
            "transaction_agent"
        )

        kyc = finding_map.get(
            "kyc_compliance_agent"
        )

        # ----------------------------------------------------
        # 2. Helper functions
        # ----------------------------------------------------

        def has_finding(
            finding: AgentFinding | None
        ) -> bool:

            return finding is not None

        def has_evidence(
            finding: AgentFinding | None
        ) -> bool:

            return (
                finding is not None
                and len(finding.evidence) > 0
            )

        def get_event_ids(
            finding: AgentFinding | None,
            limit: int = 10
        ) -> list[str]:

            if finding is None:
                return []

            return list(
                dict.fromkeys(
                    finding.event_ids
                )
            )[:limit]

        def add_event_ids(
            *agent_findings: AgentFinding | None,
            limit: int = 20
        ) -> list[str]:

            """
            Combine event IDs from multiple specialist
            findings while removing duplicates.
            """

            ids = []

            for finding in agent_findings:

                if finding is None:
                    continue

                ids.extend(
                    finding.event_ids
                )

            return list(
                dict.fromkeys(ids)
            )[:limit]

        # ====================================================
        # 3. CROSS-DOMAIN FINANCIAL DISTRESS
        # ====================================================
        #
        # We require evidence from multiple independent
        # specialist domains.
        #
        # This prevents a single normal transaction from
        # becoming a financial-distress conclusion.
        # ====================================================

        distress_agents = []

        support_distress = False
        transaction_distress = False
        usage_distress = False

        if support is not None:
            support_text = " ".join(support.evidence).lower()

            distress_keywords = [
                "hardship",
                "medical",
                "hospital",
                "income reduction",
                "income loss",
                "payment difficulty",
                "unable to pay",
                "financial difficulty",
                "financial distress",
                "overdue",
                "delinquent",
            ]

            support_distress = any(
                keyword in support_text
                for keyword in distress_keywords
            )

        if transaction is not None:
            transaction_text = " ".join(transaction.evidence).lower()

            transaction_distress_keywords = [
                "large withdrawal",
                "savings drawdown",
                "balance decline",
                "unusual withdrawal",
                "financial hardship",
                "payment difficulty",
            ]

            transaction_distress = any(
                keyword in transaction_text
                for keyword in transaction_distress_keywords
            )

        if usage is not None:
            usage_text = " ".join(usage.evidence).lower()

            usage_distress_keywords = [
                "hardship",
                "loan",
                "income",
                "payment difficulty",
                "financial difficulty",
            ]

            usage_distress = any(
                keyword in usage_text
                for keyword in usage_distress_keywords
            )

        if support_distress:
            distress_agents.append("support_agent")

        if transaction_distress:
            distress_agents.append("transaction_agent")

        if usage_distress:
            distress_agents.append("usage_agent")
        if len(distress_agents) >= 2:

            evidence = []

            for agent_name in distress_agents:

                finding = finding_map[
                    agent_name
                ]

                for item in finding.evidence[:3]:

                    evidence.append(
                        f"{agent_name}: {item}"
                    )

            # ----------------------------------------------
            # Strength
            # ----------------------------------------------

            if len(distress_agents) >= 3:

                strength = "strong"
                confidence = 0.85

            else:

                strength = "moderate"
                confidence = 0.75

            # ----------------------------------------------
            # Event IDs come from specialist findings
            # ----------------------------------------------

            event_ids = add_event_ids(
                support,
                transaction,
                usage,
                limit=20
            )

            signals.append(
                CorrelatedSignal(
                    signal=(
                        "cross_domain_financial_distress"
                    ),
                    strength=strength,
                    confidence=confidence,
                    supporting_agents=(
                        distress_agents
                    ),
                    evidence=evidence,
                    event_ids=event_ids,
                )
            )

        # ====================================================
        # 4. CUSTOMER PROFILE TRANSITION
        # ====================================================
        #
        # KYC changes can indicate:
        #
        # - new child
        # - marriage
        # - relocation
        # - other profile changes
        #
        # The Life Event Agent will interpret the exact
        # meaning later.
        # ====================================================

        kyc_active = (
            kyc is not None 
            and kyc.signal_type != "no_kyc_signal"
            and len(kyc.event_ids) > 0
        )


        if kyc_active:
            signals.append(
                CorrelatedSignal(
                    signal="customer_profile_transition",
                    strength="moderate",
                    confidence=0.75,
                    supporting_agents=["kyc_compliance_agent"],
                    evidence=kyc.evidence[:5],
                    event_ids=get_event_ids(kyc, limit=10),
                )
            )

        # ====================================================
        # 5. DIGITAL ENGAGEMENT ACTIVITY
        # ====================================================

        if has_evidence(usage):

            signals.append(
                CorrelatedSignal(
                    signal=(
                        "digital_engagement_activity"
                    ),
                    strength="moderate",
                    confidence=0.65,
                    supporting_agents=[
                        "usage_agent"
                    ],
                    evidence=usage.evidence[:5],
                    event_ids=get_event_ids(
                        usage,
                        limit=10
                    ),
                )
            )

        # ====================================================
        # 6. FINANCIAL ACTIVITY CHANGE
        # ====================================================

        if has_evidence(transaction):

            signals.append(
                CorrelatedSignal(
                    signal=(
                        "financial_activity_change"
                    ),
                    strength="moderate",
                    confidence=0.65,
                    supporting_agents=[
                        "transaction_agent"
                    ],
                    evidence=transaction.evidence[:5],
                    event_ids=get_event_ids(
                        transaction,
                        limit=10
                    ),
                )
            )

        # ====================================================
        # 7. SUPPORT FRICTION
        # ====================================================

        if( 
            has_evidence(support)
            and support.signal_type == "support_friction"
        ):

            signals.append(
                CorrelatedSignal(
                    signal="support_friction",
                    strength="moderate",
                    confidence=0.70,
                    supporting_agents=[
                        "support_agent"
                    ],
                    evidence=support.evidence[:5],
                    event_ids=get_event_ids(
                        support,
                        limit=10
                    ),
                )
            )

        # ====================================================
        # 8. TEMPORAL ACTIVITY CONTEXT
        # ====================================================
        #
        # This does NOT make a life-event inference.
        #
        # It simply tells the next layer that a complete
        # customer timeline is available.
        # ====================================================

        if events:

            temporal_event_ids = []

            for event in events:

                # Support both:
                #   dict events
                #   Pydantic Event objects
                #
                # This prevents failures if main.py supplies
                # either representation.

                if isinstance(event, dict):

                    event_id = event.get(
                        "event_id"
                    )

                else:

                    event_id = getattr(
                        event,
                        "event_id",
                        None
                    )

                if event_id:

                    temporal_event_ids.append(
                        event_id
                    )

            signals.append(
                CorrelatedSignal(
                    signal=(
                        "temporal_activity_context"
                    ),
                    strength="weak",
                    confidence=0.60,
                    supporting_agents=[],
                    evidence=[
                        (
                            f"Observed {len(events)} "
                            "total events in the "
                            "customer timeline."
                        )
                    ],
                    event_ids=(
                        temporal_event_ids[:20]
                    ),
                )
            )

        # ====================================================
        # 9. RETURN ALL CORRELATED SIGNALS
        # ====================================================

        return signals