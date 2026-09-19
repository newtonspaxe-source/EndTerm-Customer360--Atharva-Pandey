from pathlib import Path
import json
import re
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Agentic Customer 360",
    page_icon="🤖",
    layout="wide",
)


# ============================================================
# PROJECT PATHS
# ============================================================

# app.py is inside: <project_root>/src/
# Therefore parent.parent = project root
BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = BASE_DIR / "outputs"
MEMORY_DIR = BASE_DIR / "memory"


# ============================================================
# FILE DISCOVERY
# ============================================================

def find_latest_file(pattern):
    """Return the most recently modified file matching pattern."""
    if not OUTPUT_DIR.exists():
        return None

    files = list(OUTPUT_DIR.glob(pattern))

    if not files:
        return None

    return max(files, key=lambda p: p.stat().st_mtime)


def find_latest_trace_dir():
    """Return the most recently modified scenario trace directory."""
    if not OUTPUT_DIR.exists():
        return None

    dirs = list(OUTPUT_DIR.glob("scenario_*_traces"))

    if not dirs:
        return None

    return max(dirs, key=lambda p: p.stat().st_mtime)


def find_latest_trace():
    """Return the most recently modified trace JSONL."""
    trace_dir = find_latest_trace_dir()

    if trace_dir is None or not trace_dir.exists():
        return None

    files = list(trace_dir.glob("*.jsonl"))

    if not files:
        return None

    return max(files, key=lambda p: p.stat().st_mtime)


EVALUATION_FILE = find_latest_file("scenario_*_evaluation.json")
INFERRED_FILE = find_latest_file("scenario_*_inferred_events.jsonl")
TRACE_DIR = find_latest_trace_dir()


# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    if path is None or not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_jsonl(path):
    if path is None or not path.exists():
        return []

    records = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    except Exception:
        return []

    return records


def scenario_from_path(path):
    """Extract scenario name from artifact filename."""
    if path is None:
        return "Unknown"

    match = re.search(r"(scenario_[^_]+)", path.name)

    if match:
        return match.group(1)

    return "Unknown"


def get_nested(data, *keys, default=None):
    """Safely retrieve nested dictionary values."""
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


# ============================================================
# LOAD ARTIFACTS
# ============================================================

evaluation = load_json(EVALUATION_FILE)
inferred_events = load_jsonl(INFERRED_FILE)
trace_file = find_latest_trace()
trace_records = load_jsonl(trace_file)


# ============================================================
# SCENARIO
# ============================================================

scenario = "Unknown"

if EVALUATION_FILE:
    scenario = scenario_from_path(EVALUATION_FILE)

elif INFERRED_FILE:
    scenario = scenario_from_path(INFERRED_FILE)

elif TRACE_DIR:
    scenario = TRACE_DIR.name.replace("_traces", "")


# ============================================================
# CUSTOMER ID
# ============================================================

customer_id = "Unknown"

# Try memory files first
if MEMORY_DIR.exists():
    memory_files = list(MEMORY_DIR.glob("*_episodic.jsonl"))

    if memory_files:
        latest_memory = max(
            memory_files,
            key=lambda p: p.stat().st_mtime
        )

        customer_id = latest_memory.stem.replace(
            "_episodic",
            ""
        )


# Try inferred events if customer ID wasn't found
if customer_id == "Unknown" and inferred_events:

    for event in reversed(inferred_events):

        possible_id = (
            event.get("customer_id")
            or event.get("customerId")
            or get_nested(event, "customer", "customer_id")
        )

        if possible_id:
            customer_id = possible_id
            break


# ============================================================
# HEADER
# ============================================================

st.title("🤖 Agentic Customer 360")
st.caption(
    "Proactive Intervention Desk — Multi-Agent Customer Intelligence"
)

st.info(
    f"Detected scenario: **{scenario}**  |  "
    f"Customer: **{customer_id}**"
)


# ============================================================
# DASHBOARD CONTROLS
# ============================================================

with st.sidebar:

    st.header("Dashboard Controls")

    auto_refresh = st.checkbox(
        "Auto refresh",
        value=False
    )

    if st.button("🔄 Refresh now"):
        st.rerun()

    st.divider()

    st.subheader("Detected Artifacts")

    st.write(
        f"Evaluation: "
        f"`{EVALUATION_FILE.name if EVALUATION_FILE else 'Not found'}`"
    )

    st.write(
        f"Inferred events: "
        f"`{INFERRED_FILE.name if INFERRED_FILE else 'Not found'}`"
    )

    st.write(
        f"Trace: "
        f"`{trace_file.name if trace_file else 'Not found'}`"
    )


# ============================================================
# SYSTEM STATUS
# ============================================================

st.subheader("System Status")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Backend",
        "main.py"
    )

with col2:
    st.metric(
        "Inference Checkpoints",
        len(inferred_events)
    )

with col3:
    late_events = 0

    if evaluation:
        late_events = (
            evaluation.get("late_events")
            or evaluation.get("metrics", {}).get("late_events")
            or 0
        )

    st.metric(
        "Late Events",
        late_events
    )

with col4:
    st.metric(
        "Trace Records",
        len(trace_records)
    )


# ============================================================
# CURRENT CUSTOMER STATE
# ============================================================

st.subheader("Current Customer State")

latest_inference = (
    inferred_events[-1]
    if inferred_events
    else {}
)

life_phase = (
    latest_inference.get("inferred_state")
    or latest_inference.get("life_phase")
    or latest_inference.get("state")
    or "Unknown"
)

confidence = (
    latest_inference.get("confidence")
    or latest_inference.get("state_confidence")
)

action = (
    latest_inference.get("action")
    or latest_inference.get("recommended_action")
    or "Unknown"
)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "Life Phase / Inferred State",
        str(life_phase)
    )

with c2:
    st.metric(
        "Confidence",
        f"{confidence:.2f}"
        if isinstance(confidence, (int, float))
        else "N/A"
    )

with c3:
    st.metric(
        "Final Action",
        str(action)
    )


# ============================================================
# INFERENCE CHECKPOINTS
# ============================================================

st.subheader("Inference Checkpoints")

if inferred_events:

    rows = []

    for i, event in enumerate(inferred_events, start=1):

        rows.append(
            {
                "Checkpoint": i,
                "Timestamp": (
                    event.get("timestamp")
                    or event.get("event_time")
                    or event.get("checkpoint_time")
                    or ""
                ),
                "State": (
                    event.get("inferred_state")
                    or event.get("life_phase")
                    or event.get("state")
                    or ""
                ),
                "Confidence": event.get("confidence", ""),
                "Action": (
                    event.get("action")
                    or event.get("recommended_action")
                    or ""
                ),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True
    )

else:
    st.warning(
        "No inferred-events file found."
    )


# ============================================================
# LATEST INFERENCE
# ============================================================

if latest_inference:

    st.subheader("Latest Inference")

    with st.expander(
        "View latest inference details",
        expanded=True
    ):
        st.json(latest_inference)


# ============================================================
# EVIDENCE
# ============================================================

st.subheader("Evidence")

evidence = (
    latest_inference.get("evidence")
    or latest_inference.get("supporting_evidence")
    or []
)

if isinstance(evidence, list) and evidence:

    for item in evidence:
        if isinstance(item, dict):

            text = (
                item.get("description")
                or item.get("text")
                or item.get("reason")
                or str(item)
            )

            st.write(f"• {text}")

        else:
            st.write(f"• {item}")

else:
    st.write("No evidence available.")


# ============================================================
# SOURCE EVENTS
# ============================================================

st.subheader("Source Event IDs")

source_ids = (
    latest_inference.get("source_event_ids")
    or latest_inference.get("event_ids")
    or []
)

if source_ids:
    st.code(", ".join(map(str, source_ids)))
else:
    st.write("No source event IDs available.")


# ============================================================
# AGENT PIPELINE
# ============================================================

st.subheader("Multi-Agent Pipeline")

pipeline = [
    "Event Stream / Trigger Router",
    "Usage Agent",
    "Support / Sentiment Agent",
    "Transaction / Billing Agent",
    "KYC / Compliance Agent",
    "Per-Customer State Board",
    "Synthesis / Correlation Agent",
    "Life-Event Inference Agent",
    "Conflict / Ambiguity Debate",
    "Offer / Eligibility Agent",
    "Retention / Action Agent",
    "Critique / Compliance Refiner",
    "HITL Approval",
    "Action / Escalation Execution",
]

for i, stage in enumerate(pipeline, start=1):

    st.write(
        f"**{i}.** {stage}"
    )


# ============================================================
# ROUND-ROBIN / MULTI-AGENT DRAFTING
# ============================================================

st.subheader("Multi-Agent Drafting / Critique")

round_robin_found = False

for record in trace_records:

    text = str(record).lower()

    if (
        "round-robin" in text
        or "draft_001" in text
        or "draft_002" in text
        or "draft_003" in text
    ):
        round_robin_found = True
        break


if round_robin_found:

    st.success(
        "Round-robin multi-agent drafting detected in trace."
    )

else:

    st.info(
        "Round-robin drafting evidence not detected in the latest trace."
    )


# ============================================================
# HITL
# ============================================================

st.subheader("Human-in-the-Loop")

hitl_status = "Unknown"
execution_status = "Unknown"

if evaluation:

    hitl_status = (
        evaluation.get("hitl_status")
        or evaluation.get("human_decision")
        or evaluation.get("hitl", {}).get("status")
        or "Unknown"
    )

    execution_status = (
        evaluation.get("execution_status")
        or evaluation.get("execution", {}).get("status")
        or "Unknown"
    )

elif latest_inference:

    hitl_status = (
        latest_inference.get("hitl_status")
        or latest_inference.get("human_decision")
        or "Unknown"
    )

    execution_status = (
        latest_inference.get("execution_status")
        or "Unknown"
    )


h1, h2 = st.columns(2)

with h1:
    st.metric(
        "HITL Status",
        str(hitl_status)
    )

with h2:
    st.metric(
        "Execution",
        str(execution_status)
    )


# ============================================================
# TRACEABILITY
# ============================================================

st.subheader("Traceability")

if trace_file:

    st.success(
        f"Trace artifact detected: `{trace_file.name}`"
    )

    with st.expander(
        "View latest trace records"
    ):

        # Show only a reasonable amount in UI
        display_records = trace_records[-20:]

        if display_records:
            st.json(display_records)

        else:
            st.info("Trace file exists but contains no readable JSONL records.")

else:

    st.warning(
        "Trace artifact not found."
    )


# ============================================================
# EVALUATION
# ============================================================

st.subheader("Evaluation")

if evaluation:

    # Show important evaluation information first

    metrics = evaluation.get("metrics", {})

    if isinstance(metrics, dict) and metrics:

        st.write("### Evaluation Metrics")

        metric_cols = st.columns(
            min(len(metrics), 4)
        )

        for col, (key, value) in zip(
            metric_cols,
            metrics.items()
        ):

            with col:
                st.metric(
                    key.replace("_", " ").title(),
                    str(value)
                )

    with st.expander(
        "View complete evaluation report"
    ):
        st.json(evaluation)

else:

    st.warning(
        "Evaluation file not found."
    )


# ============================================================
# MEMORY
# ============================================================

st.subheader("Customer Memory")

if MEMORY_DIR.exists():

    memory_files = list(
        MEMORY_DIR.glob("*_episodic.jsonl")
    )

    if memory_files:

        latest_memory_file = max(
            memory_files,
            key=lambda p: p.stat().st_mtime
        )

        memory_records = load_jsonl(
            latest_memory_file
        )

        st.caption(
            f"Memory file: `{latest_memory_file.name}`"
        )

        st.write(
            f"Memory records: **{len(memory_records)}**"
        )

        if memory_records:

            with st.expander(
                "View latest memory records"
            ):
                st.json(
                    memory_records[-10:]
                )

    else:

        st.info(
            "No episodic memory file found."
        )

else:

    st.info(
        "Memory directory not found."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Agentic Customer 360 • Proactive Intervention Desk"
)


# ============================================================
# OPTIONAL AUTO REFRESH
# ============================================================

if auto_refresh:

    import time

    time.sleep(5)
    st.rerun()