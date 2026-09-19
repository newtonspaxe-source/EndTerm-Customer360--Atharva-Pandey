from typing import Literal

from pydantic import BaseModel, Field

from drafting import ActionDraft
from offer import OfferRecommendation


class CritiqueResult(BaseModel):
    draft_id: str
    agent_name: str

    status: Literal[
        "approved",
        "needs_revision",
        "rejected"
    ]

    compliance_flags: list[str] = Field(
        default_factory=list
    )

    issues: list[str] = Field(
        default_factory=list
    )

    revised_message: str | None = None

    explanation: str


class CritiqueComplianceAgent:

    def __init__(self):
        self.name = "critique_compliance_agent"

    def review(
        self,
        draft: ActionDraft,
        offer: OfferRecommendation
    ) -> CritiqueResult:

        issues = []
        flags = []

        message = draft.message.lower()

        # -----------------------------------------------------
        # Unsupported claims
        # -----------------------------------------------------

        risky_phrases = [
            "we know",
            "we detected",
            "we know exactly",
            "you are definitely",
            "you have definitely"
        ]

        for phrase in risky_phrases:

            if phrase in message:

                issues.append(
                    f"Unsupported certainty: '{phrase}'"
                )

        # -----------------------------------------------------
        # Sensitive inference protection
        # -----------------------------------------------------

        if "medical" in message:

            flags.append(
                "Sensitive medical context"
            )

            issues.append(
                "Customer-facing message should not "
                "explicitly reveal an inferred sensitive "
                "condition unless permitted."
            )

        # -----------------------------------------------------
        # Fraud protection
        # -----------------------------------------------------

        if "fraud" in message or "takeover" in message:

            flags.append(
                "Fraud-related communication"
            )

            issues.append(
                "Fraud-related internal signals should "
                "not automatically be exposed to the customer."
            )

        # -----------------------------------------------------
        # Manual review requirement
        # -----------------------------------------------------

        if offer.requires_human_review:

            flags.append(
                "Human review required"
            )

            issues.append(
                "Offer requires human approval before execution."
            )

        # -----------------------------------------------------
        # Decision
        # -----------------------------------------------------

        if offer.eligibility_status == "not_eligible":

            return CritiqueResult(
                draft_id=draft.draft_id,
                agent_name=self.name,
                status="rejected",
                compliance_flags=flags,
                issues=issues + [
                    "Offer is not eligible."
                ],
                revised_message=None,
                explanation=(
                    "Draft rejected because the associated "
                    "offer is not eligible."
                )
            )

        if offer.requires_human_review:

            return CritiqueResult(
                draft_id=draft.draft_id,
                agent_name=self.name,
                status="needs_revision",
                compliance_flags=flags,
                issues=issues,
                revised_message=(
                    "Please review the available support "
                    "options with a specialist before "
                    "taking further action."
                ),
                explanation=(
                    "Draft requires human review before "
                    "execution."
                )
            )

        if issues:

            return CritiqueResult(
                draft_id=draft.draft_id,
                agent_name=self.name,
                status="needs_revision",
                compliance_flags=flags,
                issues=issues,
                revised_message=(
                    "A specialist can review the available "
                    "support options with you."
                ),
                explanation=(
                    "Draft contains claims or content that "
                    "should be revised before customer contact."
                )
            )

        return CritiqueResult(
            draft_id=draft.draft_id,
            agent_name=self.name,
            status="approved",
            compliance_flags=flags,
            issues=[],
            revised_message=draft.message,
            explanation=(
                "Draft passed the current compliance and "
                "customer-communication checks."
            )
        )

    def review_drafts(
        self,
        # decision : CustomerDecision,
        drafts: list[ActionDraft],
        offer: OfferRecommendation
    ) -> list[CritiqueResult]:

        results = []

        for draft in drafts:

            result = self.review(
                draft,
                offer
            )

            results.append(result)

        return results