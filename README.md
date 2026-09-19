# Agentic AI 360 — Proactive Intervention Desk

## Problem

Agentic AI 360 is a multi-agent Customer 360 system designed to continuously monitor customer activity, infer meaningful life events, maintain customer memory, and proactively recommend or execute bounded interventions.

The system processes heterogeneous customer events such as:

- Transactions
- Support interactions
- Digital usage
- KYC/compliance events

Instead of treating every event independently, specialist agents contribute structured findings to a shared per-customer state. A synthesis and life-event inference pipeline then determines whether a meaningful customer state has emerged.

---

## Key Objectives

The system is designed around the following requirements:

- Continuous multi-source event processing
- Working, episodic and semantic memory
- Event-time aware processing
- Late/out-of-order event handling
- Specialist agents with scoped responsibilities
- Shared per-customer state
- Agent-dependent and scheduled triggers
- Life-event inference
- Multi-agent drafting and refinement
- Deterministic guardrails
- Human-in-the-loop approval
- Full traceability and audit logging
- Citation/evidence-backed decisions
- Automated evaluation using inferred-event outputs

---

## Architecture

The system follows a multi-agent architecture based on:

1. Parallel specialist signal gathering
2. Shared customer state / blackboard
3. Scoped agent handoffs
4. Life-event synthesis
5. Conflict/debate resolution when required
6. Offer and eligibility evaluation
7. Round-robin action drafting
8. Critique/compliance refinement
9. Deterministic guardrails
10. Human-in-the-loop approval
11. Action or escalation execution

### Major Agents

- Transaction Agent
- Support Agent
- Usage Agent
- KYC/Compliance Agent
- Synthesis/Correlation Agent
- Life-Event Inference Agent
- Offer/Eligibility Agent
- Retention/Action Agent
- Critique/Compliance Refiner
- Escalation/Guardrail Layer

---

## Memory Architecture

### Working Memory

Stores the current customer state and recent context required during active processing.

### Episodic Memory

Stores customer-specific historical events and observations. Retrieval can be used to recover relevant historical context.

### Semantic Memory

Stores shared/domain-level information such as policies, rules and reusable knowledge.

### State Board

Specialist agents write structured findings to a shared per-customer state board. Agents exchange structured conclusions rather than unrestricted internal reasoning.

---

## Event Processing

The system distinguishes:

- Event time
- Ingestion time

This allows the pipeline to identify late-arriving events.

The replay pipeline also tracks:

- Accepted events
- Duplicate events
- Late events
- Total state events
- Inference checkpoints

---

## Multi-Agent Coordination

The architecture combines multiple coordination patterns:

### Parallel / Swarm-style Signal Gathering

Specialist agents independently analyse their scoped event types.

### Scoped Handoffs

Structured outputs are passed between specialized stages.

### Shared State / Blackboard

Agents contribute findings to a common customer state.

### Debate

When conflicting interpretations are detected, the architecture supports a debate/resolution stage.

### Round-Robin Drafting

Multiple specialized drafting agents sequentially refine the proposed customer-facing action.

### Critique-Refiner

Candidate actions are checked for policy, compliance, risk and cost before approval.

---

## Guardrails and HITL

Customer-facing or costly actions are not directly executed without passing deterministic safety checks.

High-risk actions are routed through a Human-in-the-Loop checkpoint.

The human reviewer can:

- Approve
- Reject
- Modify

The decision and resulting execution status are recorded in the audit trail.

---

## Explainability

Every major decision is associated with supporting evidence.

For example, a medical-hardship inference can reference relevant historical events containing signals such as hospital, pharmacy or health-related transaction context.

The system records:

- Evidence
- Source event IDs
- Agent findings
- Inference result
- Confidence
- Proposed action
- Risk flags
- HITL decision
- Execution status

---

## Observability and Traceability

The system records execution traces covering:

- Agent execution
- Tool calls
- Retrievals
- Intermediate structured findings
- Decisions
- Drafting
- Critique
- Guardrails
- HITL decisions
- Final execution

Trace artifacts are stored under:

`outputs/scenario_01_traces/`

---

## Evaluation

The system produces an inferred-event artifact containing:

- Inferred state
- Confidence
- Action
- Timestamp
- Action subtype
- HITL status
- Execution status

An automated evaluation harness compares the system output against scenario expectations.

Example evaluation dimensions include:

- State correctness
- Action correctness
- Action subtype correctness
- HITL correctness
- Confidence band
- Late-event handling

---

## Demonstrated Scenario

The included scenario processes:

- 375 historical events
- 116 live events
- 491 total state events
- 8 inference checkpoints
- 1 late event

The final demonstrated state is:

**Medical hardship**

with:

**support_intervention**

and:

**medical_hardship_payment_plan**

The system routes the customer-facing action through guardrails and HITL before execution.

---

## For UI

A Streamlit dashboard is included to visualize:

- Customer state
- Inference checkpoints
- Agent activity
- Evidence
- Final decision
- Round-robin drafting
- HITL status
- Traceability
- Evaluation results

Run:

```bash
streamlit run app.py
