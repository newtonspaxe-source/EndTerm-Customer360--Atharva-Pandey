from typing import Literal
from pydantic import BaseModel, Field


class GuardrailResult(BaseModel):
    customer_id: str
    decision: Literal[
        "approved_for_execution",
        "requires_human_review",
        "blocked",
    ]
    hitl_status: Literal[
        "auto_approved",
        "escalated",
        "human_approved",
        "human_rejected",
        "human_modified",
    ]
    selected_draft_id: str | None = None
    reason: str
    guardrail_flags: list[str] = Field(default_factory=list)


class GuardrailHITLAgent:
    """
    Deterministic safety boundary. The LLM cannot bypass these checks.
    """
    HARD_STOP_TERMS = {
        "lawsuit",
        "legal action",
        "attorney",
        "sue us",
    }

    def __init__(self):
        self.name = "guardrail_hitl_agent"

    def evaluate(self, decision, offer, critique_results, drafts=None):
        # Hard-stop based on evidence/message content.
        texts = [decision.rationale]
        for draft in (drafts or []):
            texts.append(draft.message)

        combined = " ".join(texts).lower()
        matched = [term for term in self.HARD_STOP_TERMS if term in combined]

        if matched:
            return GuardrailResult(
                customer_id=decision.customer_id,
                decision="blocked",
                hitl_status="escalated",
                selected_draft_id=None,
                reason="Hard-stop legal-risk guardrail triggered.",
                guardrail_flags=["legal_threat:" + x for x in matched],
            )
        # -----------------------------------------------------------
        #  NO-ACTION PATH
        # -----------------------------------------------------------
        # No-action is a valid bounded outcome.
        # If the system decides to take no customer-facing action,
        # offer eligibility must not block the decision.

        if decision.action == "no_action":
            return GuardrailResult(
                customer_id=decision.customer_id,
                decision="approved_for_execution",
                hitl_status="auto_approved",
                selected_draft_id=None,
                reason="No action selected; no customer-facing action will be executed.",
                guardrail_flags=["no_action"],
            )
        if offer.eligibility_status == "not_eligible":
            return GuardrailResult(
                customer_id=decision.customer_id,
                decision="blocked",
                hitl_status="auto_approved",
                reason="Offer is not eligible.",
                guardrail_flags=["offer_not_eligible"],
            )

        if offer.requires_human_review or decision.requires_human_review:
            return GuardrailResult(
                customer_id=decision.customer_id,
                decision="requires_human_review",
                hitl_status="escalated",
                selected_draft_id=None,
                reason="Policy requires human approval before customer-facing or costly action.",
                guardrail_flags=["human_review_required"],
            )

        approved = [
            r for r in critique_results
            if r.status == "approved"
        ]

        if not approved:
            return GuardrailResult(
                customer_id=decision.customer_id,
                decision="requires_human_review",
                hitl_status="escalated",
                selected_draft_id=None,
                reason="No compliant draft is available.",
                guardrail_flags=["no_compliant_draft"],
            )

        return GuardrailResult(
            customer_id=decision.customer_id,
            decision="approved_for_execution",
            hitl_status="auto_approved",
            selected_draft_id=approved[0].draft_id,
            reason="Passed deterministic guardrails and compliance review.",
        )
