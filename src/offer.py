from typing import Literal

from pydantic import BaseModel, Field

from life_event import LifeEventResult
from decision import CustomerDecision


class OfferRecommendation(BaseModel):
    customer_id: str

    inferred_state: str

    action: str

    offer_type: str

    eligibility_status: Literal[
        "eligible",
        "not_eligible",
        "manual_review"
    ]

    rationale: str

    conditions: list[str] = Field(
        default_factory=list
    )

    risk_flags: list[str] = Field(
        default_factory=list
    )

    requires_human_review: bool = False


class OfferEligibilityAgent:

    def __init__(self):
        self.name = "offer_eligibility_agent"

    def evaluate(
        self,
        life_event: LifeEventResult,
        decision: CustomerDecision
    ) -> OfferRecommendation:

        state = life_event.inferred_state

        # -----------------------------------------------------
        # Medical hardship
        # -----------------------------------------------------

        if state == "medical_hardship":

            return OfferRecommendation(
                customer_id=life_event.customer_id,
                inferred_state=state,
                action=decision.action,
                offer_type="medical_hardship_payment_support",
                eligibility_status="eligible",
                rationale=(
                    "The inferred medical hardship is supported "
                    "by multiple independent customer signals. "
                    "A payment-support intervention is aligned "
                    "with the selected customer action."
                ),
                conditions=[
                    "Verify applicable payment-support policy.",
                    "Confirm customer eligibility before execution.",
                    "Do not modify account terms without required approval."
                ],
                risk_flags=[],
                requires_human_review=False
            )

        # -----------------------------------------------------
        # New child
        # -----------------------------------------------------

        if state == "new_child_life_event":

            return OfferRecommendation(
                customer_id=life_event.customer_id,
                inferred_state=state,
                action=decision.action,
                offer_type="childcare_savings_or_insurance_plan",
                eligibility_status="eligible",
                rationale="Customer may benefit from family financial planning support following a new-child life event.",
                conditions=["human review before customer-facing action"],
                risk_flags=[],
                requires_human_review=True
            )

        # -----------------------------------------------------
        # Churn risk
        # -----------------------------------------------------

        if state == "churn_risk":

            return OfferRecommendation(
                customer_id=life_event.customer_id,
                inferred_state=state,
                action=decision.action,
                offer_type="retention_review",
                eligibility_status="eligible",
                rationale="Customer behaviour indicates potential relationship disengagement.",
                conditions=[],
                risk_flags=["potential_churn"],
                requires_human_review=False
            )

        # -----------------------------------------------------
        # Financial distress
        # -----------------------------------------------------

        if state == "financial_distress_general":

            return OfferRecommendation(
                customer_id=life_event.customer_id,
                inferred_state=state,
                action=decision.action,
                offer_type="financial_support_review",
                eligibility_status="manual_review",
                rationale=(
                    "Multiple signals indicate potential financial "
                    "difficulty, but additional policy checks are "
                    "required before selecting a specific support "
                    "option."
                ),
                conditions=[
                    "Review applicable financial-support policies.",
                    "Confirm eligibility before offering assistance."
                ],
                risk_flags=["financial_distress"],
                requires_human_review=True
            )

        # -----------------------------------------------------
        # Fraud
        # -----------------------------------------------------

        if state == "potential_fraud_or_takeover":

            return OfferRecommendation(
                customer_id=life_event.customer_id,
                inferred_state=state,
                action=decision.action,
                offer_type="no_customer_offer",
                eligibility_status="manual_review",
                rationale=(
                    "Potential fraud or account takeover requires "
                    "compliance review before any customer-facing "
                    "offer or action."
                ),
                conditions=[
                    "Compliance review required.",
                    "Do not automatically execute customer-facing actions."
                ],
                risk_flags=["potential_fraud"],
                requires_human_review=True
            )

        # -----------------------------------------------------
        # Default
        # -----------------------------------------------------

        return OfferRecommendation(
            customer_id=life_event.customer_id,
            inferred_state=state,
            action=decision.action,
            offer_type="none",
            eligibility_status="not_eligible",
            rationale=(
                "No predefined offer or eligibility rule "
                "matches the inferred customer state."
            ),
            conditions=[],
            risk_flags=[],
            requires_human_review=False
        )