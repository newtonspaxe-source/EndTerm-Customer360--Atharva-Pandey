from typing import Literal

from pydantic import BaseModel, Field

from agents import AgentFinding
from synthesis import CorrelatedSignal
from life_event import LifeEventResult


class ConflictResult(BaseModel):
    conflict_detected: bool

    conflict_type: str

    conflicting_signals: list[str] = Field(
        default_factory=list
    )

    explanation: str


class DebateResult(BaseModel):
    customer_id: str

    conflict_detected: bool

    resolution_status: Literal[
        "not_required",
        "resolved",
        "unresolved"
    ]

    resolved_state: str

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    reasoning: str

    participating_agents: list[str] = Field(
        default_factory=list
    )


class ConflictDetectionAgent:

    def __init__(self):
        self.name = "conflict_detection_agent"

    def detect(
        self,
        findings: list[AgentFinding],
        signals: list[CorrelatedSignal]
    ) -> ConflictResult:

        signal_names = [
            signal.signal
            for signal in signals
        ]

        # -----------------------------------------------------
        # Strong conflicting high-level states
        # -----------------------------------------------------

        has_churn = any(
            "churn" in name
            for name in signal_names
        )

        has_growth = any(
            "growth" in name
            for name in signal_names
        )

        has_fraud = any(
            "fraud" in name
            for name in signal_names
        )

        has_support = any(
            "support" in name
            for name in signal_names
        )

        # -----------------------------------------------------
        # Detect contradictory signals
        # -----------------------------------------------------

        if has_churn and has_growth:

            return ConflictResult(
                conflict_detected=True,
                conflict_type="churn_vs_growth",
                conflicting_signals=[
                    "churn_risk",
                    "wealth_growth_or_windfall"
                ],
                explanation=(
                    "Signals indicate both relationship "
                    "disengagement and positive financial activity."
                )
            )

        if has_fraud and has_support:

            return ConflictResult(
                conflict_detected=True,
                conflict_type="fraud_vs_legitimate_support",
                conflicting_signals=[
                    "potential_fraud_or_takeover",
                    "support_activity"
                ],
                explanation=(
                    "Potential risk signals coexist with "
                    "legitimate customer-support activity."
                )
            )

        # -----------------------------------------------------
        # Compare specialist recommendations
        # -----------------------------------------------------

        recommendations = [
            finding.recommendation.lower()
            for finding in findings
        ]

        if (
            any("fraud" in recommendation
                for recommendation in recommendations)
            and
            any(
                "support" in recommendation
                or "normal" in recommendation
                for recommendation in recommendations
            )
        ):

            return ConflictResult(
                conflict_detected=True,
                conflict_type="specialist_disagreement",
                conflicting_signals=recommendations,
                explanation=(
                    "Specialist agents produced materially "
                    "different interpretations of the customer activity."
                )
            )

        return ConflictResult(
            conflict_detected=False,
            conflict_type="none",
            conflicting_signals=[],
            explanation=(
                "No material conflict was detected between "
                "the available specialist and synthesis signals."
            )
        )


class DebateAgent:

    def __init__(self):
        self.name = "debate_agent"

    def resolve(
        self,
        customer_id: str,
        conflict: ConflictResult,
        life_event: LifeEventResult,
        findings: list[AgentFinding],
        signals: list[CorrelatedSignal]
    ) -> DebateResult:

        # -----------------------------------------------------
        # No conflict
        # -----------------------------------------------------

        if not conflict.conflict_detected:

            return DebateResult(
                customer_id=customer_id,
                conflict_detected=False,
                resolution_status="not_required",
                resolved_state=life_event.inferred_state,
                confidence=life_event.confidence,
                reasoning=(
                    "No material disagreement was detected, "
                    "so the existing life-event inference is retained."
                ),
                participating_agents=[]
            )

        # -----------------------------------------------------
        # Resolve using strongest evidence
        # -----------------------------------------------------

        evidence_count = {}

        for signal in signals:

            evidence_count[signal.signal] = (
                len(signal.event_ids)
            )

        strongest_signal = None

        if evidence_count:

            strongest_signal = max(
                evidence_count,
                key=evidence_count.get
            )

        # -----------------------------------------------------
        # Preserve an already strongly supported inference
        # -----------------------------------------------------

        if life_event.confidence >= 0.80:

            return DebateResult(
                customer_id=customer_id,
                conflict_detected=True,
                resolution_status="resolved",
                resolved_state=life_event.inferred_state,
                confidence=max(
                    0.75,
                    life_event.confidence
                ),
                reasoning=(
                    "Debate resolved the conflict by retaining "
                    "the life-event hypothesis with the strongest "
                    "cross-domain evidence and highest confidence."
                ),
                participating_agents=[
                    finding.agent_name
                    for finding in findings
                ]
            )

        # -----------------------------------------------------
        # Unresolved conflict
        # -----------------------------------------------------

        return DebateResult(
            customer_id=customer_id,
            conflict_detected=True,
            resolution_status="unresolved",
            resolved_state=life_event.inferred_state,
            confidence=life_event.confidence,
            reasoning=(
                "The available evidence is insufficient to "
                "resolve the disagreement with high confidence. "
                "Human review should be considered."
            ),
            participating_agents=[
                finding.agent_name
                for finding in findings
            ]
        )