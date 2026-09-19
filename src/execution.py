from typing import Literal

from pydantic import BaseModel, Field

from guardrail import GuardrailResult
from drafting import ActionDraft


class ExecutionResult(BaseModel):
    customer_id: str

    execution_status: Literal[
        "executed",
        "pending_human_review",
        "blocked"
    ]

    action: str

    draft_id: str | None = None

    execution_message: str

    audit_record: dict = Field(
        default_factory=dict
    )


class ExecutionAgent:

    def __init__(self):
        self.name = "execution_agent"

    def execute(
        self,
        guardrail: GuardrailResult,
        drafts: list[ActionDraft]
    ) -> ExecutionResult:

        # -----------------------------------------------------
        # Blocked
        # -----------------------------------------------------

        if guardrail.decision == "blocked":

            return ExecutionResult(
                customer_id=guardrail.customer_id,
                execution_status="blocked",
                action="no_action",
                draft_id=None,
                execution_message=(
                    "Execution blocked by guardrails."
                ),
                audit_record={
                    "guardrail_decision": guardrail.decision,
                    "hitl_status": guardrail.hitl_status,
                    "reason": guardrail.reason
                }
            )

        # -----------------------------------------------------
        # Human review
        # -----------------------------------------------------

        if guardrail.decision == "requires_human_review":

            return ExecutionResult(
                customer_id=guardrail.customer_id,
                execution_status="pending_human_review",
                action="human_review",
                draft_id=None,
                execution_message=(
                    "Action has been escalated for human review "
                    "and has not been executed."
                ),
                audit_record={
                    "guardrail_decision": guardrail.decision,
                    "hitl_status": guardrail.hitl_status,
                    "reason": guardrail.reason,
                    "guardrail_flags": guardrail.guardrail_flags
                }
            )
        # -----------------------------------------------------
        # No-action is a legitimate terminal outcome.
        # Nothing needs to be executed.
        # -----------------------------------------------------

        if "no_action" in guardrail.guardrail_flags:

            return ExecutionResult(
                customer_id=guardrail.customer_id,
                execution_status="executed",
                action="no_action",
                draft_id=None,
                execution_message=(
                    "No customer-facing action required."
                ),
                audit_record={
                    "guardrail_decision": guardrail.decision,
                    "hitl_status": guardrail.hitl_status,
                    "reason": guardrail.reason,
                    "action": "no_action",
                }
            )
        # -----------------------------------------------------
        # Find selected draft
        # -----------------------------------------------------

        selected_draft = None

        for draft in drafts:

            if draft.draft_id == guardrail.selected_draft_id:

                selected_draft = draft
                break

        # -----------------------------------------------------
        # Safety fallback
        # -----------------------------------------------------

        if selected_draft is None:

            return ExecutionResult(
                customer_id=guardrail.customer_id,
                execution_status="blocked",
                action="no_action",
                draft_id=None,
                execution_message=(
                    "Execution blocked because the selected "
                    "draft could not be found."
                ),
                audit_record={
                    "guardrail_decision": guardrail.decision,
                    "error": "selected_draft_not_found"
                }
            )

        # -----------------------------------------------------
        # Execute
        # -----------------------------------------------------

        return ExecutionResult(
            customer_id=guardrail.customer_id,
            execution_status="executed",
            action=selected_draft.action,
            draft_id=selected_draft.draft_id,
            execution_message=(
                "Approved action is ready for execution."
            ),
            audit_record={
                "guardrail_decision": guardrail.decision,
                "hitl_status": guardrail.hitl_status,
                "selected_draft": selected_draft.draft_id,
                "action": selected_draft.action,
                "action_subtype": selected_draft.action_subtype
            }
        )