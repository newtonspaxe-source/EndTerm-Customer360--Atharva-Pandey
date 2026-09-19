import json
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv("api.env")

from langchain_google_genai import ChatGoogleGenerativeAI
from governance import mask_pii

from state import CustomerState
from agents import AgentFinding
from synthesis import CorrelatedSignal


class LifeEventResult(BaseModel):
    customer_id: str
    inferred_state: str
    confidence_band: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    reasoning_summary: str
    alternative_hypotheses: list[str] = Field(default_factory=list)


class LifeEventAgent:

    def __init__(self):
        self.name = "life_event_agent"

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            temperature=0,
        )

        self.structured_llm = self.llm.with_structured_output(
            LifeEventResult
        )

    # ============================================================
    # MAIN ANALYSIS
    # ============================================================

    def analyze(
        self,
        state: CustomerState,
        findings: list[AgentFinding],
        signals: list[CorrelatedSignal],
        evidence: dict,
        memory_context: dict | None = None,
    ) -> LifeEventResult:

        specialist_context = [
            finding.model_dump()
            for finding in findings
        ]

        correlation_context = [
            signal.model_dump()
            for signal in signals
        ]

        state_context = state.summary()

        memory_context = memory_context or {}
        episodic_context = memory_context.get("episodic", [])
        semantic_context = memory_context.get("semantic", {})

        evidence_context = {
            category: items[:15]
            for category, items in evidence.items()
        }

        memory_prompt = f"""
RELEVANT MEMORY (use only when relevant; never treat memory as current evidence):
Episodic: {mask_pii(json.dumps(episodic_context[:5], default=str))}
Semantic policy: {mask_pii(json.dumps(semantic_context.get("rules", [])[:6], default=str))}
"""

        prompt = f"""
You are the Life-Event Inference Agent in a Customer 360
multi-agent banking system.

{memory_prompt}
Your job is to infer the customer's current significant state
from MULTI-DOMAIN evidence and TEMPORAL behaviour.

Do NOT infer a major state from a single transaction.

Important rules:

1. Combine evidence from multiple domains.
2. Consider temporal changes in behaviour.
3. Distinguish genuine life events from red herrings.
4. A large transaction alone is NOT fraud.
5. A single support complaint alone is NOT churn.
6. A single search alone is NOT enough to infer a life event.
7. KYC changes are strong evidence when actually present.
8. Explicit medical/hospital evidence may support medical hardship.
9. Explicit child/dependent/daycare/baby evidence may support
   a new-child life event.
10. Repeated outbound transfers combined with support friction
    and declining engagement may support churn risk.
11. Do not invent facts that are not present in the evidence.
12. Explain alternative hypotheses when appropriate.

Allowed inferred states include:

- no_significant_event
- new_child_life_event
- marriage_or_relationship_change
- job_change_or_promotion
- job_loss_or_income_disruption
- medical_hardship
- financial_distress_general
- relocation
- retirement_transition
- wealth_growth_or_windfall
- potential_fraud_or_takeover
- elder_vulnerability_or_scam_risk
- churn_risk
- small_business_cashflow_event

CUSTOMER STATE:
{json.dumps(state_context, indent=2)}

SPECIALIST FINDINGS:
{json.dumps(specialist_context, indent=2)}

CORRELATED SIGNALS:
{json.dumps(correlation_context, indent=2)}

EXTRACTED EVIDENCE:
{json.dumps(evidence_context, indent=2)}

Return the most defensible current customer state.
"""

        # ========================================================
        # TRY LLM FIRST
        # ========================================================

        try:

            result = self.structured_llm.invoke(prompt)

            print("[LIFE EVENT] Gemini inference used.")

            return result

        except Exception as exc:

            error_text = str(exc).lower()

            quota_error = (
                "429" in str(exc)
                or "resource_exhausted" in error_text
                or "quota" in error_text
                or "rate limit" in error_text
                or "ratelimit" in error_text
            )

            if quota_error:
                print(
                    "[LIFE EVENT FALLBACK] "
                    "Gemini quota unavailable. "
                    "Using deterministic evidence inference."
                )
            else:
                print(
                    "[LIFE EVENT FALLBACK] "
                    f"Gemini unavailable ({type(exc).__name__}). "
                    "Using deterministic evidence inference."
                )

            return self._deterministic_fallback(
                state=state,
                findings=findings,
                signals=signals,
                evidence=evidence,
            )
    # ============================================================
    # DETERMINISTIC FALLBACK
    # ============================================================

    def _deterministic_fallback(
        self,
        state: CustomerState,
        findings: list[AgentFinding],
        signals: list[CorrelatedSignal],
        evidence: dict,
        memory_context: dict | None = None,
    ) -> LifeEventResult:

        events = [e.model_dump() if hasattr(e, "model_dump") else e for e in state.all_events]

        # --------------------------------------------------------
        # Convert every event into searchable text
        # --------------------------------------------------------

        event_records = []

        for event in events:

            payload = event.get("payload", {})

            text = " ".join(
                [
                    str(event.get("source_system", "")),
                    str(event.get("event_type", "")),
                    json.dumps(payload),
                ]
            ).lower()

            event_records.append(
                {
                    "event": event,
                    "text": text,
                }
            )

        # --------------------------------------------------------
        # Helper
        # --------------------------------------------------------

        def matching_events(keywords):

            matches = []

            for record in event_records:

                matched_keyword = None

                for keyword in keywords:

                    if keyword.lower() in record["text"]:
                        matched_keyword = keyword
                        break

                if matched_keyword:

                    matches.append(
                        (
                            record["event"],
                            matched_keyword,
                        )
                    )

            return matches

        # ========================================================
        # MEDICAL
        # ========================================================

        medical_keywords = [
            "hospital",
            "medical",
            "pharmacy",
            "clinic",
            "doctor",
            "health",
            "hardship",
            "disability",
            "income reduction",
            "medical bill",
            "hospital bill",
            "payment plan",
        ]

        medical_matches = matching_events(
            medical_keywords
        )

        medical_score = 0

        medical_score += min(
            len(medical_matches) * 2,
            12,
        )

        # ========================================================
        # NEW CHILD
        # ========================================================

        child_keywords = [
            "baby",
            "newborn",
            "child",
            "daycare",
            "maternity",
            "parent",
            "nursery",
            "formula",
            "diaper",
            "baby monitor",
            "education savings",
        ]

        child_matches = matching_events(
            child_keywords
        )

        child_score = 0

        child_score += min(
            len(child_matches) * 2,
            10,
        )

        # Strong KYC evidence
        for event in events:

            if event.get("source_system") != "loan_kyc":
                continue

            if event.get("event_type") == "dependents_change":

                payload = event.get("payload", {})

                old_value = payload.get("old_value")
                new_value = payload.get("new_value")

                try:

                    if (
                        old_value is not None
                        and new_value is not None
                        and int(new_value) > int(old_value)
                    ):
                        child_score += 6

                except (ValueError, TypeError):
                    pass

        # ========================================================
        # CHURN
        # ========================================================

        churn_keywords = [
            "international transaction fee",
            "fee wasn't disclosed",
            "fee was not disclosed",
            "refund this",
            "cannot be waived",
            "cannot waive",
            "denied",
            "close account",
            "competitor",
            "other bank",
            "rival bank",
            "transfer out",
        ]

        churn_matches = matching_events(
            churn_keywords
        )

        churn_score = 0

        churn_score += min(
            len(churn_matches) * 3,
            12,
        )

        # --------------------------------------------------------
        # Outbound transfers
        # --------------------------------------------------------

        outbound_events = [
            event
            for event in events
            if event.get("event_type") == "outbound_transfer"
        ]

        if len(outbound_events) >= 2:
            churn_score += 5

        if len(outbound_events) >= 3:
            churn_score += 3

        # --------------------------------------------------------
        # Standing instruction cancellations
        # --------------------------------------------------------

        cancelled_instructions = 0

        for event in events:

            if event.get("event_type") != "standing_instruction":
                continue

            text = json.dumps(
                event.get("payload", {})
            ).lower()

            cancellation_words = [
                "cancel",
                "cancelled",
                "canceled",
                "terminate",
                "terminated",
                "stop",
                "stopped",
                "disable",
                "disabled",
            ]

            if any(
                word in text
                for word in cancellation_words
            ):
                cancelled_instructions += 1

        if cancelled_instructions >= 1:
            churn_score += 4

        if cancelled_instructions >= 2:
            churn_score += 3

        # ========================================================
        # DIGITAL ENGAGEMENT DROP
        # ========================================================

        usage_events = [
            event
            for event in events
            if event.get("source_system") == "web_app_events"
        ]

        if usage_events:

            usage_events = sorted(
                usage_events,
                key=lambda x: x.get("event_time", "")
            )

            last_time = usage_events[-1].get(
                "event_time"
            )

            try:

                from datetime import datetime

                last_dt = datetime.fromisoformat(
                    last_time.replace("Z", "+00:00")
                )

                recent_start = (
                    last_dt - timedelta(days=14)
                )

                previous_start = (
                    last_dt - timedelta(days=28)
                )

                recent_count = 0
                previous_count = 0

                for event in usage_events:

                    event_time = event.get(
                        "event_time"
                    )

                    dt = datetime.fromisoformat(
                        event_time.replace("Z", "+00:00")
                    )

                    if dt >= recent_start:
                        recent_count += 1

                    elif dt >= previous_start:
                        previous_count += 1

                if (
                    previous_count > 0
                    and recent_count < previous_count * 0.5
                ):
                    churn_score += 4

            except Exception:
                pass

        # ========================================================
        # FINANCIAL DISTRESS
        # ========================================================

        distress_keywords = [
            "hardship",
            "unable to pay",
            "payment difficulty",
            "financial difficulty",
            "financial distress",
            "income loss",
            "income reduction",
            "overdue",
            "delinquent",
        ]

        distress_matches = matching_events(
            distress_keywords
        )

        distress_score = min(
            len(distress_matches) * 2,
            10,
        )

        # ========================================================
        # FRAUD
        # ========================================================

        fraud_keywords = [
            "takeover",
            "unauthorized",
            "stolen",
            "fraud",
            "suspicious login",
            "unknown device",
            "credential",
        ]

        fraud_matches = matching_events(
            fraud_keywords
        )

        fraud_score = min(
            len(fraud_matches) * 3,
            12,
        )

        # IMPORTANT:
        # Large transactions alone do NOT increase fraud score.

        # ========================================================
        # SELECT STATE
        # ========================================================

        candidate_scores = {
            "new_child_life_event": child_score,
            "medical_hardship": medical_score,
            "churn_risk": churn_score,
            "financial_distress_general": distress_score,
            "potential_fraud_or_takeover": fraud_score,
        }

        # --------------------------------------------------------
        # Priority rules for strong specific evidence
        # --------------------------------------------------------

        if child_score >= 6:

            selected_state = "new_child_life_event"

        elif medical_score >= 6:

            selected_state = "medical_hardship"

        elif churn_score >= 7:

            selected_state = "churn_risk"

        elif fraud_score >= 6:

            selected_state = "potential_fraud_or_takeover"

        elif distress_score >= 6:

            selected_state = "financial_distress_general"

        else:

            selected_state = "no_significant_event"

        selected_score = candidate_scores.get(
            selected_state,
            0,
        )

        # Carry forward a previously established customer state when the current
        # window becomes temporarily sparse. This is the episodic-memory path.
        prior_state = None
        prior_conf = 0.0
        for rec in (memory_context or {}).get("episodic", []):
            if rec.get("inferred_state") and rec.get("inferred_state") != "no_significant_event":
                prior_state = rec.get("inferred_state")
                prior_conf = float(rec.get("confidence", 0.0) or 0.0)
                break
        if selected_state == "no_significant_event" and prior_state and prior_conf >= 0.80:
            selected_state = prior_state
            selected_score = max(selected_score, 5)

        # ========================================================
        # CONFIDENCE
        # ========================================================

        if selected_score >= 12:

            confidence = 0.95

        elif selected_score >= 9:

            confidence = 0.92

        elif selected_score >= 7:

            confidence = 0.88

        elif selected_score >= 6:

            confidence = 0.82

        else:

            confidence = 0.55

        if confidence >= 0.85:

            confidence_band = "high"

        elif confidence >= 0.65:

            confidence_band = "medium"

        else:

            confidence_band = "low"

        # ========================================================
        # BUILD EVIDENCE
        # ========================================================

        selected_evidence = []

        def add_matches(
            matches,
            label,
            maximum=4,
        ):

            for event, keyword in matches[:maximum]:

                selected_evidence.append(
                    f"{label}: matched '{keyword}' "
                    f"in event {event.get('event_id')} "
                    f"({event.get('event_type')})."
                )

        if selected_state == "new_child_life_event":

            add_matches(
                child_matches,
                "Family/child evidence",
            )

            for event in events:

                if (
                    event.get("source_system")
                    == "loan_kyc"
                    and event.get("event_type")
                    == "dependents_change"
                ):

                    selected_evidence.append(
                        f"KYC dependent change detected "
                        f"in event {event.get('event_id')}."
                    )

        elif selected_state == "medical_hardship":

            add_matches(
                medical_matches,
                "Medical/hardship evidence",
            )

        elif selected_state == "churn_risk":

            add_matches(
                churn_matches,
                "Customer-friction evidence",
            )

            if len(outbound_events) >= 2:

                amounts = []

                for event in outbound_events:

                    amount = event.get(
                        "payload",
                        {}
                    ).get("amount")

                    if isinstance(
                        amount,
                        (int, float),
                    ):
                        amounts.append(
                            float(amount)
                        )

                total = sum(amounts)

                selected_evidence.append(
                    f"{len(outbound_events)} outbound "
                    f"transfers detected, totaling "
                    f"{total:.2f}."
                )

            if cancelled_instructions:

                selected_evidence.append(
                    f"{cancelled_instructions} standing "
                    f"instruction cancellation/stop "
                    f"signals detected."
                )

        elif selected_state == "financial_distress_general":

            add_matches(
                distress_matches,
                "Financial-distress evidence",
            )

        elif selected_state == "potential_fraud_or_takeover":

            add_matches(
                fraud_matches,
                "Fraud-risk evidence",
            )

        # Fallback evidence
        if not selected_evidence:

            selected_evidence.append(
                "No sufficiently strong multi-domain "
                "evidence was detected."
            )

        # ========================================================
        # ALTERNATIVE HYPOTHESES
        # ========================================================

        alternatives = []

        ranked = sorted(
            candidate_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for state_name, score in ranked:

            if (
                state_name != selected_state
                and score >= 5
            ):

                alternatives.append(
                    state_name
                )

        if not alternatives:

            alternatives.append(
                "no_significant_event"
                if selected_state != "no_significant_event"
                else "insufficient_evidence"
            )

        # ========================================================
        # REASONING
        # ========================================================

        reasoning = (
            f"Deterministic fallback selected "
            f"'{selected_state}' using multi-domain "
            f"evidence. Candidate scores were: "
            f"{candidate_scores}."
        )

        print(
            f"[LIFE EVENT FALLBACK] "
            f"Selected state: {selected_state} "
            f"(confidence={confidence:.2f})"
        )

        return LifeEventResult(
            customer_id=state.customer_id,
            inferred_state=selected_state,
            confidence_band=confidence_band,
            confidence=confidence,
            evidence=selected_evidence[:8],
            reasoning_summary=reasoning,
            alternative_hypotheses=alternatives[:3],
        )