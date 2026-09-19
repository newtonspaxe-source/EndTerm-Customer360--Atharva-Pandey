from pydantic import BaseModel, Field
from typing import Literal

from decision import CustomerDecision
from offer import OfferRecommendation


class ActionDraft(BaseModel):
    customer_id: str
    draft_id: str
    agent_name: str

    action: str
    action_subtype: str

    message: str
    rationale: str

    risk_flags: list[str] = Field(default_factory=list)

    draft_status: Literal[
        "draft",
        "revised",
        "final"
    ] = "draft"


class RoundRobinDraftingAgent:

    def __init__(self):
        self.name = "round_robin_drafting_agent"

    def _create_message(
        self,
        decision: CustomerDecision,
        offer: OfferRecommendation
    ) -> str:

        action_subtype = decision.action_subtype

        if action_subtype == "childcare_savings_or_insurance_plan":

            return (
                "We can help review financial planning options that may support your family's changing needs."
            )

        elif action_subtype == "medical_hardship_payment_plan":

            return (
                "We can help review available payment-support options "
                "and discuss the assistance available to you."
            )

        elif action_subtype == "customer_retention_review":

            return (
                "We value your relationship with us. A specialist "
                "can review your recent experience and available "
                "support options with you."
            )

        elif action_subtype == "financial_support_review":

            return (
                "A specialist can review the support options available "
                "for your current situation."
            )

        elif action_subtype == "fraud_review":

            return (
                "A specialist needs to review recent account activity "
                "before any further action is taken."
            )

        else:

            return (
                "A specialist can review the options available "
                "for your current situation."
            )

    def generate_drafts(
        self,
        life_event,
        decision: CustomerDecision,
        offer: OfferRecommendation
    ) -> list[ActionDraft]:

        if offer.eligibility_status == "not_eligible":
            return []

        base_message = self._create_message(
            decision,
            offer
        )

        drafts = []

        drafts.append(
            ActionDraft(
                customer_id=decision.customer_id,
                draft_id="draft_001",
                agent_name="customer_support_agent",
                action=decision.action,
                action_subtype=decision.action_subtype,
                message=base_message,
                rationale=decision.rationale,
                risk_flags=decision.risk_flags.copy(),
                draft_status="draft"
            )
        )

        drafts.append(
            ActionDraft(
                customer_id=decision.customer_id,
                draft_id="draft_002",
                agent_name="relationship_manager_agent",
                action=decision.action,
                action_subtype=decision.action_subtype,
                message=base_message,
                rationale=decision.rationale,
                risk_flags=decision.risk_flags.copy(),
                draft_status="draft"
            )
        )

        drafts.append(
            ActionDraft(
                customer_id=decision.customer_id,
                draft_id="draft_003",
                agent_name="customer_experience_agent",
                action=decision.action,
                action_subtype=decision.action_subtype,
                message=base_message,
                rationale=decision.rationale,
                risk_flags=decision.risk_flags.copy(),
                draft_status="draft"
            )
        )

        return drafts

    def round_robin(self,drafts):
        revised_drafts = []
        for i, draft in enumerate(drafts):
            if i == 0:
                draft.draft_status = "draft"
            else:
                draft.message = (
                    draft.message
                    + " We will keep the communication focused "
                      "on the support options available to you."
                )
                draft.draft_status = "revised"
            revised_drafts.append(draft)
        return revised_drafts