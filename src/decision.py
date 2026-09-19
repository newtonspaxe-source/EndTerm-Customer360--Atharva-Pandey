from typing import Literal
from pydantic import BaseModel, Field

from life_event import LifeEventResult


class CustomerDecision(BaseModel):
    customer_id: str

    inferred_state: str

    confidence_band: Literal[
        "low",
        "medium",
        "high"
    ]

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    action: Literal[
        "no_action",
        "proactive_retention_outreach",
        "relationship_manager_escalation",
        "personalized_offer",
        "support_intervention",
        "compliance_fraud_hold"
    ]

    action_subtype: str

    rationale: str

    evidence: list[str] = Field(
        default_factory=list
    )

    risk_flags: list[str] = Field(
        default_factory=list
    )

    requires_human_review: bool = False

    hitl_status: Literal[
        "auto_approved",
        "escalated",
        "human_approved",
        "human_rejected",
        "human_modified"
    ] = "auto_approved"
class DecisionAgent:

    def __init__(self):
        self.name = "decision_agent"

    def decide(
        self,
        life_event: LifeEventResult,
    ) -> CustomerDecision:

        state = life_event.inferred_state

        # ====================================================
        # MEDICAL HARDSHIP
        # ====================================================

        if state == "medical_hardship":

            return CustomerDecision(
                customer_id=life_event.customer_id,

                inferred_state=state,

                confidence_band=(
                    life_event.confidence_band
                ),

                confidence=life_event.confidence,

                action="support_intervention",

                action_subtype=(
                    "medical_hardship_payment_plan"
                ),

                rationale=(
                    "Customer shows multi-signal evidence "
                    "of medical hardship, including explicit "
                    "hospitalization, income reduction, and "
                    "a request for payment-plan assistance."
                ),

                evidence=life_event.evidence,

                risk_flags=[],

                requires_human_review=True,

                hitl_status="escalated",
            )

        # ====================================================
        # CHURN
        # ====================================================

        if state == "churn_risk":

            return CustomerDecision(
                customer_id=life_event.customer_id,

                inferred_state=state,

                confidence_band=(
                    life_event.confidence_band
                ),

                confidence=life_event.confidence,

                action=(
                    "proactive_retention_outreach"
                ),

                action_subtype=(
                    "customer_retention_review"
                ),

                rationale=(
                    "Customer behaviour indicates "
                    "potential relationship disengagement."
                ),

                evidence=life_event.evidence,

                risk_flags=["potential_churn"],

                requires_human_review=False,

                hitl_status="auto_approved",
            )

        # ====================================================
        # NEW CHILD
        # ====================================================

        if state == "new_child_life_event":

            return CustomerDecision(
                customer_id=life_event.customer_id,

                inferred_state=state,

                confidence_band=(
                    life_event.confidence_band
                ),

                confidence=life_event.confidence,

                action="personalized_offer",

                action_subtype=(
                    "childcare_savings_or_insurance_plan"
                ),

                rationale=(
                    "Customer activity indicates a "
                    "significant family-life transition."
                ),

                evidence=life_event.evidence,

                risk_flags=[],

                requires_human_review=False,

                hitl_status="escalated",
            )

        # ====================================================
        # FRAUD
        # ====================================================

        if state == "potential_fraud_or_takeover":

            return CustomerDecision(
                customer_id=life_event.customer_id,

                inferred_state=state,

                confidence_band=(
                    life_event.confidence_band
                ),

                confidence=life_event.confidence,

                action="compliance_fraud_hold",

                action_subtype=(
                    "fraud_review"
                ),

                rationale=(
                    "Potential fraud or account-takeover "
                    "signals require compliance review."
                ),

                evidence=life_event.evidence,

                risk_flags=[
                    "potential_fraud"
                ],

                requires_human_review=True,

                hitl_status="escalated",
            )

        # ====================================================
        # GENERIC FINANCIAL DISTRESS
        # ====================================================

        if state == "financial_distress_general":

            return CustomerDecision(
                customer_id=life_event.customer_id,

                inferred_state=state,

                confidence_band=(
                    life_event.confidence_band
                ),

                confidence=life_event.confidence,

                action="support_intervention",

                action_subtype=(
                    "financial_support_review"
                ),

                rationale=(
                    "Multiple signals indicate potential "
                    "financial difficulty."
                ),

                evidence=life_event.evidence,

                risk_flags=[
                    "financial_distress"
                ],

                requires_human_review=False,

                hitl_status="auto_approved",
            )

        # ====================================================
        # DEFAULT
        # ====================================================

        return CustomerDecision(
            customer_id=life_event.customer_id,

            inferred_state=state,

            confidence_band=(
                life_event.confidence_band
            ),

            confidence=life_event.confidence,

            action="no_action",

            action_subtype="monitor",

            rationale=(
                "No sufficiently actionable life-event "
                "state was identified."
            ),

            evidence=life_event.evidence,

            risk_flags=[],

            requires_human_review=False,

            hitl_status="auto_approved",
        )