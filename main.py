import argparse
import json
from pathlib import Path

from models import Event
from state import CustomerState
from stream import EventStream
from router import TriggerRouter
from agents import SpecialistAgents
from synthesis import SynthesisAgent
from evidence import EvidenceExtractor
from life_event import LifeEventAgent
from debate import ConflictDetectionAgent, DebateAgent
from decision import DecisionAgent
from offer import OfferEligibilityAgent
from drafting import RoundRobinDraftingAgent
from critique import CritiqueComplianceAgent
from guardrail import GuardrailHITLAgent
from execution import ExecutionAgent

from checkpointing import DecisionCheckpoint, InferredEvent, InferredEventWriter
from memory import CustomerMemory
from trace import TraceLogger
from hitl import CLIHITL
from evaluation import ScenarioEvaluator


BASE_DIR = Path(".")


# ============================================================
# DATA LOADING
# ============================================================

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path):
    events = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(
                    Event.model_validate(json.loads(line))
                )

    return events


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_separator(title):
    print("\n" + "=" * 75)
    print(title)
    print("=" * 75)


def print_decision(
    life_event,
    decision,
    offer,
    drafts,
    critique_results,
    guardrail_result,
    execution_result,
):
    print_separator("CUSTOMER 360 DECISION")

    print(f"Customer          : {life_event.customer_id}")
    print(f"Inferred state    : {life_event.inferred_state}")
    print(
        f"Confidence        : "
        f"{life_event.confidence:.2f} "
        f"({life_event.confidence_band})"
    )

    print(f"Action            : {decision.action}")
    print(f"Action subtype    : {decision.action_subtype}")

    print(
        f"Offer             : "
        f"{offer.offer_type}"
    )

    print(
        f"Eligibility       : "
        f"{offer.eligibility_status}"
    )

    print(
        f"Decision HITL     : "
        f"{decision.hitl_status}"
    )

    print(
        f"Guardrail         : "
        f"{guardrail_result.decision}"
    )

    print(
        f"Guardrail HITL    : "
        f"{guardrail_result.hitl_status}"
    )

    print(
        f"Execution         : "
        f"{execution_result.execution_status}"
    )

    print(
        f"Risk flags        : "
        f"{', '.join(decision.risk_flags) if decision.risk_flags else 'None'}"
    )

    print("\nEvidence:")

    for evidence in life_event.evidence[:8]:
        print(f"  - {evidence}")

    print("\nDrafts:")

    for draft in drafts:
        print(
            f"  {draft.draft_id} | "
            f"{draft.agent_name} | "
            f"{draft.draft_status}"
        )

    print("\nCritique:")

    for critique in critique_results:
        print(
            f"  {critique.draft_id} | "
            f"{critique.status}"
        )

        if critique.compliance_flags:
            print(
                f"      flags: "
                f"{', '.join(critique.compliance_flags)}"
            )


# ============================================================
# MAIN SCENARIO RUNNER
# ============================================================

def run_scenario(
    scenario_id: str,
    interactive_hitl: bool = False,
    checkpoint_interval: int = 20,
):

    scenario_dir = BASE_DIR / scenario_id

    if not scenario_dir.exists():
        raise FileNotFoundError(
            f"Scenario not found: {scenario_dir}"
        )

    print_separator(f"RUNNING {scenario_id}")

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    history_events = load_jsonl(
        scenario_dir / "history_seed.jsonl"
    )

    live_events = load_jsonl(
        scenario_dir / "live_stream.jsonl"
    )

    replay_config = load_json(
        scenario_dir / "replay_config.json"
    )

    all_dataset_events = (
        history_events + live_events
    )

    customer_ids = {
        event.customer_id
        for event in all_dataset_events
    }

    if len(customer_ids) != 1:
        raise ValueError(
            f"Expected one customer, found {customer_ids}"
        )

    customer_id = next(iter(customer_ids))

    print(f"Customer ID       : {customer_id}")
    print(
        f"Historical events : {len(history_events)}"
    )
    print(
        f"Live events       : {len(live_events)}"
    )

    print(
        f"Replay start      : "
        f"{replay_config.get('simulated_start')}"
    )

    print(
        f"Replay end        : "
        f"{replay_config.get('simulated_end')}"
    )

    # --------------------------------------------------------
    # CORE STATE
    # --------------------------------------------------------

    state = CustomerState(
        customer_id=customer_id
    )

    stream = EventStream()
    router = TriggerRouter()

    # --------------------------------------------------------
    # AGENTS
    # --------------------------------------------------------

    specialists = SpecialistAgents()
    synthesis_agent = SynthesisAgent()
    life_event_agent = LifeEventAgent()

    conflict_agent = ConflictDetectionAgent()
    debate_agent = DebateAgent()

    decision_agent = DecisionAgent()
    offer_agent = OfferEligibilityAgent()

    drafting_agent = RoundRobinDraftingAgent()
    critique_agent = CritiqueComplianceAgent()

    guardrail_agent = GuardrailHITLAgent()
    execution_agent = ExecutionAgent()

    # --------------------------------------------------------
    # NEW INFRASTRUCTURE
    # --------------------------------------------------------

    checkpoint_engine = DecisionCheckpoint(
        min_events_between_inference=checkpoint_interval
    )

    inferred_event_writer = InferredEventWriter(
        path=f"outputs/{scenario_id}_inferred_events.jsonl"
    )

    # Start fresh for this scenario
    inferred_event_writer.clear()

    memory = CustomerMemory(
        customer_id=customer_id
    )

    memory.seed_semantic_policy()

    tracer = TraceLogger(
        root=f"outputs/{scenario_id}_traces"
    )

    hitl = CLIHITL(
        audit_path=f"outputs/{scenario_id}_hitl_audit.jsonl"
    )

    # --------------------------------------------------------
    # HISTORICAL STATE
    # --------------------------------------------------------

    print_separator("HISTORICAL STATE RECONSTRUCTION")

    history_events.sort(
        key=lambda event: event.event_time
    )

    for event in history_events:
        state.update(event)

    print(
        f"Historical events applied: "
        f"{len(history_events)}"
    )

    print(
        f"State event count       : "
        f"{state.total_events}"
    )

    # --------------------------------------------------------
    # LIVE STREAM
    # --------------------------------------------------------

    print_separator("LIVE EVENT STREAM")

    live_events.sort(
        key=lambda event: event.ingestion_time
    )

    accepted = 0
    duplicates = 0
    late_events = 0
    accepted_live_events = []

    def rebuild_state_for_event_time():
        nonlocal state
        rebuilt = CustomerState(customer_id=customer_id)
        for ev in sorted(history_events + accepted_live_events, key=lambda x: x.event_time):
            rebuilt.update(ev)
        state = rebuilt

    last_pipeline_result = None
    inference_count = 0

    # --------------------------------------------------------
    # PIPELINE FUNCTION
    # --------------------------------------------------------

    def run_inference(as_of_event: Event):

        nonlocal inference_count
        nonlocal last_pipeline_result

        inference_count += 1

        tracer.log(
            "checkpoint",
            "inference_triggered",
            {
                "event_id": as_of_event.event_id,
                "event_time": str(
                    as_of_event.event_time
                ),
                "inference_number": inference_count,
            },
        )

        print_separator(
            f"INFERENCE CHECKPOINT #{inference_count}"
        )

        print(
            f"As-of event       : "
            f"{as_of_event.event_id}"
        )

        print(
            f"As-of event time   : "
            f"{as_of_event.event_time}"
        )

        # ----------------------------------------------------
        # MEMORY RETRIEVAL
        # ----------------------------------------------------

        memory_query = " ".join(str(e.payload.get(k, "")) for e in state.all_events[-20:] for k in ("raw_text", "search_text", "merchant_name", "feature_or_page", "transaction_type"))
        episodic_memory = memory.retrieve_episodic(query=memory_query, limit=5)
        semantic_memory = memory.retrieve_semantic(query=memory_query)

        tracer.log(
            "memory",
            "retrieved",
            {
                "episodic_count": len(
                    episodic_memory
                ),
                "semantic_rules": len(
                    semantic_memory.get("rules", [])
                ),
            },
        )

        # ----------------------------------------------------
        # SPECIALIST AGENTS
        # ----------------------------------------------------

        with tracer.span(
            "specialists",
            "specialist_analysis"
        ):

            findings = specialists.run(
                state,
                state.all_events
            )

        print("\nSPECIALIST FINDINGS")

        for finding in findings:
            print(
                f"  {finding.agent_name:<28} "
                f"{finding.signal_type:<25} "
                f"{finding.confidence:.2f}"
            )

        tracer.log(
            "specialists",
            "findings",
            [
                finding.model_dump()
                for finding in findings
            ],
        )

        # ----------------------------------------------------
        # SYNTHESIS
        # ----------------------------------------------------

        with tracer.span(
            "synthesis",
            "signal_correlation"
        ):

            signals = synthesis_agent.analyze(
                state = state,
                findings = findings,
                events  = state.all_events
            )

        print("\nCORRELATED SIGNALS")

        for signal in signals:
            print(
                f"  {signal.signal:<30} "
                f"{signal.confidence:.2f}"
            )

        tracer.log(
            "synthesis",
            "correlated_signals",
            [
                signal.model_dump()
                for signal in signals
            ],
        )

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        with tracer.span(
            "evidence",
            "evidence_extraction"
        ):

            evidence_extractor = EvidenceExtractor(
                state
            )

            evidence = evidence_extractor.extract()

        tracer.log(
            "evidence",
            "extracted",
            evidence,
        )

        # ----------------------------------------------------
        # LIFE EVENT INFERENCE
        # ----------------------------------------------------

        with tracer.span(
            "life_event",
            "inference"
        ):

            life_event = life_event_agent.analyze(
                state=state,
                findings=findings,
                signals=signals,
                evidence=evidence,
                memory_context={"episodic": episodic_memory, "semantic": semantic_memory},
            )

        print("\nLIFE-EVENT INFERENCE")

        print(
            f"  State      : "
            f"{life_event.inferred_state}"
        )

        print(
            f"  Confidence : "
            f"{life_event.confidence:.2f}"
        )

        print(
            f"  Band       : "
            f"{life_event.confidence_band}"
        )

        tracer.log(
            "life_event",
            "inference_result",
            life_event.model_dump(),
        )

        # ----------------------------------------------------
        # CONFLICT DETECTION
        # ----------------------------------------------------

        with tracer.span(
            "conflict",
            "conflict_detection"
        ):

            conflict = conflict_agent.detect(
                findings,
                signals
            )

        print("\nCONFLICT DETECTION")

        print(
            f"  Conflict detected : "
            f"{conflict.conflict_detected}"
        )

        if conflict.conflict_detected:

            print(
                f"  Conflict type     : "
                f"{conflict.conflict_type}"
            )

        tracer.log(
            "conflict",
            "detection",
            conflict.model_dump(),
        )

        # ----------------------------------------------------
        # DEBATE
        # ----------------------------------------------------

        with tracer.span(
            "debate",
            "resolution"
        ):

            debate_result = debate_agent.resolve(
                customer_id=customer_id,
                conflict=conflict,
                life_event=life_event,
                findings=findings,
                signals=signals,
            )

        print("\nDEBATE")

        print(
            f"  Status : "
            f"{debate_result.resolution_status}"
        )

        print(
            f"  State  : "
            f"{debate_result.resolved_state}"
        )

        tracer.log(
            "debate",
            "resolution",
            debate_result.model_dump(),
        )

        # ----------------------------------------------------
        # DECISION
        # ----------------------------------------------------

        with tracer.span(
            "decision",
            "decision_generation"
        ):

            decision = decision_agent.decide(
                life_event
            )

        # If debate remains unresolved,
        # force human review rather than pretending
        # the system is certain.
        if debate_result.resolution_status == "unresolved":

            decision.requires_human_review = True
            decision.hitl_status = "escalated"

            if "unresolved_agent_conflict" not in decision.risk_flags:
                decision.risk_flags.append(
                    "unresolved_agent_conflict"
                )

        print("\nDECISION")

        print(
            f"  Action   : "
            f"{decision.action}"
        )

        print(
            f"  Subtype  : "
            f"{decision.action_subtype}"
        )

        print(
            f"  HITL     : "
            f"{decision.hitl_status}"
        )

        tracer.log(
            "decision",
            "decision_result",
            decision.model_dump(),
        )

        # ----------------------------------------------------
        # OFFER ELIGIBILITY
        # ----------------------------------------------------

        with tracer.span(
            "offer",
            "eligibility"
        ):

            offer = offer_agent.evaluate(
                life_event,
                decision
            )

        print("\nOFFER ELIGIBILITY")

        print(
            f"  Offer      : "
            f"{offer.offer_type}"
        )

        print(
            f"  Eligibility: "
            f"{offer.eligibility_status}"
        )

        tracer.log(
            "offer",
            "eligibility_result",
            offer.model_dump(),
        )

        # ----------------------------------------------------
        # ROUND-ROBIN DRAFTING
        # ----------------------------------------------------

        with tracer.span(
            "drafting",
            "draft_generation"
        ):

            drafts = drafting_agent.generate_drafts(
                life_event,
                decision,
                offer
            )

            drafts = drafting_agent.round_robin(
                drafts
            )

        print("\nROUND-ROBIN DRAFTING")

        for draft in drafts:
            print(
                f"  {draft.draft_id} | "
                f"{draft.agent_name} | "
                f"{draft.draft_status}"
            )

        tracer.log(
            "drafting",
            "drafts",
            [
                draft.model_dump()
                for draft in drafts
            ],
        )

        # ----------------------------------------------------
        # CRITIQUE / COMPLIANCE
        # ----------------------------------------------------

        with tracer.span(
            "critique",
            "compliance_review"
        ):

            critique_results = (
                critique_agent.review_drafts(drafts,offer)
            )

        print("\nCRITIQUE / COMPLIANCE")

        for result in critique_results:
            print(
                f"  {result.draft_id} | "
                f"{result.status}"
            )

        tracer.log(
            "critique",
            "results",
            [
                result.model_dump()
                for result in critique_results
            ],
        )

        # ----------------------------------------------------
        # GUARDRAIL
        # ----------------------------------------------------

        with tracer.span(
            "guardrail",
            "guardrail_evaluation"
        ):

            guardrail_result = guardrail_agent.evaluate(
                decision=decision,
                offer=offer,
                critique_results=critique_results,
                drafts=drafts,
            )

        print("\nGUARDRAIL")

        print(
            f"  Decision : "
            f"{guardrail_result.decision}"
        )

        print(
            f"  HITL     : "
            f"{guardrail_result.hitl_status}"
        )

        print(
            f"  Reason   : "
            f"{guardrail_result.reason}"
        )

        tracer.log(
            "guardrail",
            "result",
            guardrail_result.model_dump(),
        )

        # ----------------------------------------------------
        # REAL HUMAN-IN-THE-LOOP
        # ----------------------------------------------------

        final_draft_message = ""

        if guardrail_result.selected_draft_id:

            selected = next(
                (
                    draft
                    for draft in drafts
                    if draft.draft_id
                    == guardrail_result.selected_draft_id
                ),
                None,
            )

            if selected:
                final_draft_message = selected.message

        if (
            interactive_hitl
            and guardrail_result.decision
            == "requires_human_review"
        ):

            print("\n>>> HUMAN REVIEW REQUIRED")

            hitl_status, modified_message = hitl.review(
                decision,
                final_draft_message,
                context={"evidence": life_event.evidence[:10], "memory": episodic_memory[:5], "policy_rules": semantic_memory.get("rules", [])[:6], "guardrail": guardrail_result.model_dump()},
            )

            guardrail_result.hitl_status = hitl_status

            if hitl_status == "human_rejected":

                guardrail_result.decision = "blocked"

            elif hitl_status in {"human_approved","human_modified",}:
                guardrail_result.decision = ("approved_for_execution")
                # -------------------------------------------------
                # HITL approved the action, so select the draft
                # that was shown to the human.
                # -------------------------------------------------
                if guardrail_result.selected_draft_id is None:
                    if drafts:
                        guardrail_result.selected_draft_id = (drafts[0].draft_id)
                # -------------------------------------------------
                # If human modified the message, update the actual
                # draft that will be executed.
                # -------------------------------------------------
                if modified_message:
                    final_draft_message = modified_message
                    for draft in drafts:

                        if (draft.draft_id== guardrail_result.selected_draft_id):
                            draft.message = modified_message
                            draft.draft_status = "human_modified"
                            break
        # ----------------------------------------------------
        # EXECUTION
        # ----------------------------------------------------

        with tracer.span(
            "execution",
            "action_execution"
        ):

            execution_result = execution_agent.execute(
                # decision=decision,
                guardrail=guardrail_result,
                drafts=drafts,
            )

        print("\nEXECUTION")

        print(
            f"  Status : "
            f"{execution_result.execution_status}"
        )

        tracer.log(
            "execution",
            "result",
            execution_result.model_dump(),
        )

        # ----------------------------------------------------
        # WRITE INFERRED EVENT
        # ----------------------------------------------------

        inferred_event = InferredEvent(
            as_of_time=as_of_event.event_time,
            inferred_state=life_event.inferred_state,
            confidence_band=life_event.confidence_band,
            action=decision.action,
            action_subtype=decision.action_subtype,
            hitl_status=guardrail_result.hitl_status,
            notes=life_event.reasoning_summary,
            evidence=life_event.evidence[:10],
            source_event_ids=[e.event_id for e in state.all_events[-20:] if e.event_time <= as_of_event.event_time][-20:],
            memory_refs=[str(x.get("timestamp")) for x in episodic_memory[:5]],
            decision_trace_id=tracer.trace_id,
        )

        inferred_event_writer.write(
            inferred_event
        )

        # ----------------------------------------------------
        # EPISODIC MEMORY
        # ----------------------------------------------------

        memory.write_episode(
            inferred_state=life_event.inferred_state,
            action=decision.action,
            confidence=life_event.confidence,
            evidence=life_event.evidence,
            event_ids=[e.event_id for e in state.all_events[-20:]],
            outcome=execution_result.execution_status,
        )

        tracer.log(
            "memory",
            "episode_written",
            {
                "state": life_event.inferred_state,
                "action": decision.action,
            },
        )

        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        print_decision(
            life_event,
            decision,
            offer,
            drafts,
            critique_results,
            guardrail_result,
            execution_result,
        )

        last_pipeline_result = {
            "life_event": life_event,
            "decision": decision,
            "offer": offer,
            "drafts": drafts,
            "critique_results": critique_results,
            "guardrail": guardrail_result,
            "execution": execution_result,
        }

        return last_pipeline_result

    # ========================================================
    # PROCESS LIVE EVENTS
    # ========================================================

    for event in live_events:

        stream_result = stream.process(event)

        # --------------------------------------------
        # DUPLICATE
        # --------------------------------------------

        if stream_result["status"] == "duplicate":

            duplicates += 1

            tracer.log(
                "stream",
                "duplicate_event",
                {
                    "event_id": event.event_id
                },
            )

            continue

        accepted += 1

        # --------------------------------------------
        # LATE EVENT
        # --------------------------------------------

        if stream_result["is_late"]:

            late_events += 1

            print(
                f"[LATE EVENT] "
                f"event_time={event.event_time} "
                f"ingestion_time={event.ingestion_time}"
            )

            tracer.log(
                "stream",
                "late_event",
                {
                    "event_id": event.event_id,
                    "event_time": str(
                        event.event_time
                    ),
                    "ingestion_time": str(
                        event.ingestion_time
                    ),
                },
            )

        # --------------------------------------------
        # UPDATE STATE (event-time correct)
        # --------------------------------------------

        accepted_live_events.append(event)
        if stream_result["is_late"]:
            rebuild_state_for_event_time()
        else:
            state.update(event)

        # --------------------------------------------
        # ROUTER
        # --------------------------------------------

        route = router.route(event)

        print(
            f"[{event.event_time}] "
            f"{event.event_type:<25} "
            f"→ {route['target']}"
        )

        tracer.log(
            "router",
            "event_routed",
            {
                "event_id": event.event_id,
                "source": event.source_system,
                "event_type": event.event_type,
                "target": route["target"],
            },
        )

        # --------------------------------------------
        # CHECKPOINT TRIGGER
        # --------------------------------------------

        should_infer = checkpoint_engine.observe(
            event
        )

        if should_infer:

            checkpoint_engine.mark_inferred()

            run_inference(event)

    # ========================================================
    # FINAL INFERENCE
    # ========================================================

    # Always perform one final inference after the
    # complete live stream. This guarantees a terminal
    # decision even if the final events did not trigger
    # the checkpoint policy.

    if accepted > 0:

        final_event = max(
            live_events,
            key=lambda event: event.event_time
        )

        print_separator(
            "FINAL TERMINAL INFERENCE"
        )

        run_inference(
            final_event
        )

    # ========================================================
    # AUTOMATED EVALUATION ARTIFACT
    # ========================================================
    if (scenario_dir / "ground_truth.json").exists() and last_pipeline_result is not None:
        evaluator = ScenarioEvaluator(dataset_root=str(BASE_DIR))
        evaluation = evaluator.evaluate_run(
            scenario_id=scenario_id,
            inferred_path=f"outputs/{scenario_id}_inferred_events.jsonl",
            final_result=last_pipeline_result,
            late_events=late_events,
        )
        eval_path = Path(f"outputs/{scenario_id}_evaluation.json")
        eval_path.parent.mkdir(parents=True, exist_ok=True)
        eval_path.write_text(json.dumps(evaluation, indent=2, default=str), encoding="utf-8")
        print(f"Evaluation report    : {eval_path}")

    # ========================================================
    # STREAM SUMMARY
    # ========================================================

    print_separator("STREAM SUMMARY")

    print(
        f"Accepted events       : {accepted}"
    )

    print(
        f"Duplicate events      : {duplicates}"
    )

    print(
        f"Late events           : {late_events}"
    )

    print(
        f"Total state events    : "
        f"{state.total_events}"
    )

    print(
        f"Inference checkpoints : "
        f"{inference_count}"
    )

    print(
        f"Trace file            : "
        f"{tracer.path}"
    )

    print(
        f"Inferred events file  : "
        f"outputs/{scenario_id}_inferred_events.jsonl"
    )

    print(
        f"Memory file           : "
        f"memory/{customer_id}_episodic.jsonl"
    )

    return last_pipeline_result


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Customer 360 Multi-Agent System"
    )

    parser.add_argument(
        "--scenario",
        default="all",
        help="scenario_01, scenario_02, scenario_03, or all",
    )

    parser.add_argument(
        "--interactive-hitl",
        action="store_true",
        help="Enable real CLI human approval/rejection/modification",
    )

    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=20,
        help="Minimum events between automatic inference checkpoints",
    )

    args = parser.parse_args()

    if args.scenario == "all":

        scenarios = [
            "scenario_01",
            "scenario_02",
            "scenario_03",
        ]

    else:

        scenarios = [
            args.scenario
        ]

    for scenario_id in scenarios:

        run_scenario(
            scenario_id=scenario_id,
            interactive_hitl=args.interactive_hitl,
            checkpoint_interval=args.checkpoint_interval,
        )


if __name__ == "__main__":
    main()