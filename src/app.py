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

# app.py is:
# <project_root>/src/app.py
#
# Therefore parent.parent = project root.

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = BASE_DIR / "outputs"
MEMORY_DIR = BASE_DIR / "memory"


# ============================================================
# FILE DISCOVERY
# ============================================================

def find_latest_file(pattern):
    if not OUTPUT_DIR.exists():
        return None

    files = list(OUTPUT_DIR.glob(pattern))

    if not files:
        return None

    return max(files, key=lambda p: p.stat().st_mtime)


def find_latest_trace_dir():
    if not OUTPUT_DIR.exists():
        return None

    dirs = list(OUTPUT_DIR.glob("scenario_*_traces"))

    if not dirs:
        return None

    return max(dirs, key=lambda p: p.stat().st_mtime)


def find_latest_trace():
    trace_dir = find_latest_trace_dir()

    if trace_dir is None or not trace_dir.exists():
        return None

    files = list(trace_dir.glob("*.jsonl"))

    if not files:
        return None

    return max(files, key=lambda p: p.stat().st_mtime)


# Automatically detect latest scenario artifacts
EVALUATION_FILE = find_latest_file(
    "scenario_*_evaluation.json"
)

INFERRED_FILE = find_latest_file(
    "scenario_*_inferred_events.jsonl"
)

TRACE_DIR = find_latest_trace_dir()
TRACE_FILE = find_latest_trace()


# ============================================================
# FILE LOADERS
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


# ============================================================
# RECURSIVE VALUE SEARCH
# ============================================================

def find_value_recursive(obj, keys):
    """
    Recursively search dictionaries/lists for the first
    non-null value matching one of the requested keys.
    """

    if isinstance(obj, dict):

        # First check the current dictionary
        for key in keys:

            if key in obj and obj[key] is not None:

                value = obj[key]

                # Avoid returning empty containers
                if value != "" and value != [] and value != {}:
                    return value

        # Then search nested objects
        for value in obj.values():

            result = find_value_recursive(
                value,
                keys
            )

            if result is not None:
                return result

    elif isinstance(obj, list):

        for item in obj:

            result = find_value_recursive(
                item,
                keys
            )

            if result is not None:
                return result

    return None


def find_all_values_recursive(obj, keys):
    """
    Find all values associated with matching keys.
    Useful for evaluation/HITL information.
    """

    results = []

    if isinstance(obj, dict):

        for key, value in obj.items():

            if key in keys and value is not None:

                results.append(value)

            results.extend(
                find_all_values_recursive(
                    value,
                    keys
                )
            )

    elif isinstance(obj, list):

        for item in obj:

            results.extend(
                find_all_values_recursive(
                    item,
                    keys
                )
            )

    return results


# ============================================================
# SCENARIO DETECTION
# ============================================================

def get_scenario_name():

    candidates = [
        EVALUATION_FILE,
        INFERRED_FILE,
        TRACE_DIR,
    ]

    for path in candidates:

        if path is None:
            continue

        name = path.name

        match = re.search(
            r"(scenario_[^_]+)",
            name
        )

        if match:
            return match.group(1)

        # For scenario_03_traces
        match = re.search(
            r"(scenario_.+?)_traces",
            name
        )

        if match:
            return match.group(1)

    return "Unknown"


# ============================================================
# LOAD DATA
# ============================================================

evaluation = load_json(
    EVALUATION_FILE
)

inferred_events = load_jsonl(
    INFERRED_FILE
)

trace_records = load_jsonl(
    TRACE_FILE
)

scenario = get_scenario_name()


# ============================================================
# CUSTOMER ID
# ============================================================

def detect_customer_id():

    # 1. Try memory filename
    if MEMORY_DIR.exists():

        memory_files = list(
            MEMORY_DIR.glob("*_episodic.jsonl")
        )

        if memory_files:

            latest_memory = max(
                memory_files,
                key=lambda p: p.stat().st_mtime
            )

            match = re.match(
                r"(CUST_[^_]+)_episodic",
                latest_memory.stem
            )

            if match:
                return match.group(1)

    # 2. Try inferred events
    for event in reversed(inferred_events):

        customer_id = find_value_recursive(
            event,
            [
                "customer_id",
                "customerId",
                "customer"
            ]
        )

        if isinstance(customer_id, str):
            return customer_id

    # 3. Try evaluation
    customer_id = find_value_recursive(
        evaluation,
        [
            "customer_id",
            "customerId"
        ]
    )

    if customer_id:
        return str(customer_id)

    return "Unknown"


customer_id = detect_customer_id()


# ============================================================
# LATEST INFERENCE
# ============================================================

latest_inference = (
    inferred_events[-1]
    if inferred_events
    else {}
)


# ============================================================
# MAIN INFERENCE VALUES
# ============================================================

# ============================================================
# MAIN INFERENCE VALUES
# ============================================================
# The inferred-events JSONL has a fixed schema:
# as_of_time, inferred_state, confidence_band, action,
# action_subtype, hitl_status, evidence, source_event_ids.

if latest_inference:
    latest_timestamp = latest_inference.get(
        "as_of_time",
        "N/A"
    )

    life_phase = latest_inference.get(
        "inferred_state",
        "N/A"
    )

    confidence = latest_inference.get(
        "confidence_band",
        "N/A"
    )

    action = latest_inference.get(
        "action",
        "N/A"
    )

    action_subtype = latest_inference.get(
        "action_subtype",
        "N/A"
    )

    inference_hitl_status = latest_inference.get(
        "hitl_status",
        "N/A"
    )
else:
    latest_timestamp = "N/A"
    life_phase = "N/A"
    confidence = "N/A"
    action = "N/A"
    action_subtype = "N/A"
    inference_hitl_status = "N/A"

# ============================================================
# EVIDENCE
# ============================================================

evidence = find_value_recursive(
    latest_inference,
    [
        "evidence",
        "supporting_evidence",
        "evidence_items"
    ]
)

if evidence is None:
    evidence = []


# ============================================================
# SOURCE EVENT IDS
# ============================================================

source_event_ids = find_value_recursive(
    latest_inference,
    [
        "source_event_ids",
        "event_ids",
        "source_events"
    ]
)

if source_event_ids is None:
    source_event_ids = []


# ============================================================
# HITL / EXECUTION
# ============================================================

hitl_status = find_value_recursive(
    evaluation,
    [
        "hitl_status",
        "human_decision",
        "hitl_decision",
        "human_review_status",
        "approval_status"
    ]
)

execution_status = find_value_recursive(
    evaluation,
    [
        "execution_status",
        "execution_result",
        "execution_state"
    ]
)

# Search inference artifact if evaluation doesn't contain it
if hitl_status is None:

    hitl_status = find_value_recursive(
        latest_inference,
        [
            "hitl_status",
            "human_decision",
            "hitl_decision",
            "human_review_status",
            "approval_status"
        ]
    )

if execution_status is None:

    execution_status = find_value_recursive(
        latest_inference,
        [
            "execution_status",
            "execution_result",
            "execution_state"
        ]
    )


hitl_status = (
    hitl_status
    if hitl_status is not None
    else "Unknown"
)

execution_status = (
    execution_status
    if execution_status is not None
    else "Unknown"
)


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_confidence(value):

    if value is None:
        return "N/A"

    try:

        value = float(value)

        return f"{value:.2f}"

    except (TypeError, ValueError):

        return str(value)


def format_value(value):

    if value is None:
        return "N/A"

    if isinstance(value, bool):
        return "Yes" if value else "No"

    return str(value)


# ============================================================
# HEADER
# ============================================================

st.title(
    "🤖 Agentic Customer 360"
)

st.caption(
    "Proactive Intervention Desk — "
    "Multi-Agent Customer Intelligence"
)

st.info(
    f"Detected scenario: **{scenario}** | "
    f"Customer: **{customer_id}**"
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Dashboard Controls")

    if st.button("🔄 Refresh"):

        st.rerun()

    st.divider()

    st.subheader(
        "Detected Artifacts"
    )

    st.write(
        "Evaluation:",
        EVALUATION_FILE.name
        if EVALUATION_FILE
        else "Not found"
    )

    st.write(
        "Inferred events:",
        INFERRED_FILE.name
        if INFERRED_FILE
        else "Not found"
    )

    st.write(
        "Trace:",
        TRACE_FILE.name
        if TRACE_FILE
        else "Not found"
    )


# ============================================================
# SYSTEM STATUS
# ============================================================

st.subheader(
    "System Status"
)

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

    late_events = find_value_recursive(
        evaluation,
        [
            "late_events",
            "late_event_count",
            "num_late_events"
        ]
    )

    if late_events is None:
        late_events = 0

    st.metric(
        "Late Events",
        str(late_events)
    )

with col4:

    st.metric(
        "Trace Records",
        len(trace_records)
    )


# ============================================================
# CURRENT CUSTOMER STATE
# ============================================================

st.subheader(
    "Current Customer State"
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Life Phase / Inferred State",
        str(life_phase)
    )

with c2:
    st.metric(
        "Confidence",
        str(confidence)
    )

with c3:
    st.metric(
        "Current Action",
        str(action)
    )

with c4:
    st.metric(
        "HITL Status",
        str(inference_hitl_status)
    )

st.caption(
    f"Latest inference timestamp: {latest_timestamp}"
)

st.caption(
    f"Action subtype: {action_subtype}"
)


# ============================================================
# INFERENCE CHECKPOINTS
# ============================================================

st.subheader(
    "Inference Checkpoints"
)

if inferred_events:
    rows = []

    for i, event in enumerate(
        inferred_events,
        start=1
    ):
        rows.append(
            {
                "Checkpoint": i,
                "Timestamp": event.get(
                    "as_of_time",
                    "N/A"
                ),
                "State": event.get(
                    "inferred_state",
                    "N/A"
                ),
                "Confidence": event.get(
                    "confidence_band",
                    "N/A"
                ),
                "Action": event.get(
                    "action",
                    "N/A"
                ),
                "Action Subtype": event.get(
                    "action_subtype",
                    "N/A"
                ),
                "HITL": event.get(
                    "hitl_status",
                    "N/A"
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

st.subheader(
    "Latest Inference"
)

if latest_inference:

    with st.expander(
        "View latest inference details",
        expanded=True
    ):

        st.json(
            latest_inference
        )

else:

    st.info(
        "No inference record available."
    )


# ============================================================
# EVIDENCE
# ============================================================

st.subheader(
    "Evidence"
)

if isinstance(evidence, list) and evidence:

    for item in evidence:

        if isinstance(item, dict):

            text = (
                item.get("description")
                or item.get("text")
                or item.get("reason")
                or item.get("evidence")
                or str(item)
            )

            st.write(
                f"• {text}"
            )

        else:

            st.write(
                f"• {item}"
            )

elif isinstance(evidence, str):

    st.write(
        f"• {evidence}"
    )

else:

    st.info(
        "No evidence available."
    )


# ============================================================
# SOURCE EVENT IDS
# ============================================================

st.subheader(
    "Source Event IDs"
)

if source_event_ids:

    if isinstance(
        source_event_ids,
        list
    ):

        st.code(
            ", ".join(
                map(
                    str,
                    source_event_ids
                )
            )
        )

    else:

        st.code(
            str(source_event_ids)
        )

else:

    st.info(
        "No source event IDs available."
    )


# ============================================================
# MULTI-AGENT PIPELINE
# ============================================================

st.subheader(
    "Multi-Agent Pipeline"
)

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

for i, stage in enumerate(
    pipeline,
    start=1
):

    st.write(
        f"**{i}.** {stage}"
    )


# ============================================================
# MULTI-AGENT DRAFTING
# ============================================================

st.subheader(
    "Multi-Agent Drafting / Critique"
)

trace_text = json.dumps(
    trace_records
).lower()

round_robin_found = (
    "round-robin" in trace_text
    or "round_robin" in trace_text
    or "draft_001" in trace_text
    or "draft_002" in trace_text
    or "draft_003" in trace_text
)

if round_robin_found:

    st.success(
        "Round-robin multi-agent drafting detected in trace."
    )

else:

    st.info(
        "Round-robin drafting evidence "
        "not detected in the latest trace."
    )


# ============================================================
# HITL
# ============================================================

st.subheader(
    "Human-in-the-Loop"
)

h1, h2 = st.columns(2)

with h1:

    st.metric(
        "HITL Status",
        format_value(hitl_status)
    )

with h2:

    st.metric(
        "Execution",
        format_value(execution_status)
    )


# ============================================================
# TRACEABILITY
# ============================================================

st.subheader(
    "Traceability"
)

if TRACE_FILE:

    st.success(
        f"Trace artifact detected: "
        f"`{TRACE_FILE.name}`"
    )

    with st.expander(
        "View latest trace records"
    ):

        if trace_records:

            # Latest records first
            st.json(
                trace_records[-20:]
            )

        else:

            st.info(
                "Trace file exists but "
                "contains no readable records."
            )

else:

    st.warning(
        "Trace artifact not found."
    )


# ============================================================
# EVALUATION
# ============================================================

st.subheader(
    "Evaluation"
)

if evaluation:

    # Try to expose important evaluation values
    # without assuming one exact JSON structure.

    final_eval = evaluation.get(
        "final",
        {}
    )

    expected_state = final_eval.get(
        "expected_state",
        "N/A"
    )

    predicted_state = final_eval.get(
        "predicted_state",
        "N/A"
    )

    expected_action = final_eval.get(
        "expected_action",
        "N/A"
    )

    predicted_action = final_eval.get(
        "predicted_action",
        "N/A"
    )

    state_pass = final_eval.get(
        "state_pass",
        False
    )

    action_pass = final_eval.get(
        "action_pass",
        False
    )

    final_confidence = final_eval.get(
        "confidence",
        "N/A"
    )

    final_confidence_band = final_eval.get(
        "confidence_band",
        "N/A"
    )

    final_execution_status = final_eval.get(
        "execution_status",
        "N/A"
    )

    ec1, ec2, ec3 = st.columns(3)

    with ec1:

        st.metric(
            "Predicted State",
            format_value(
                predicted_state
            )
        )

    with ec2:

        st.metric(
            "Predicted Action",
            format_value(
                predicted_action
            )
        )

    with ec3:

        if state_pass is not None:

            st.metric(
                "State Check",
                "PASS"
                if state_pass
                else "FAIL"
            )
        elif action_pass is not None:

            st.metric(
                "Action Check",
                "PASS"
                if action_pass
                else "FAIL"
            )

        else:

            st.metric(
                "Evaluation",
                "Available"
            )
    ec4, ec5, ec6 = st.columns(3)

    with ec4:
        st.metric(
            "Final Confidence",
            str(final_confidence)
        )

    with ec5:
        st.metric(
            "Confidence Band",
            str(final_confidence_band)
        )

    with ec6:
        st.metric(
            "Execution",
            str(final_execution_status)
        )
    with st.expander(
        "View complete evaluation report"
    ):

        st.json(
            evaluation
        )

else:

    st.warning(
        "Evaluation file not found."
    )


# ============================================================
# CUSTOMER MEMORY
# ============================================================

st.subheader(
    "Customer Memory"
)

if MEMORY_DIR.exists():

    memory_files = list(
        MEMORY_DIR.glob(
            "*_episodic.jsonl"
        )
    )

    if memory_files:

        # Prefer the memory file matching
        # the currently detected customer.
        matching_files = [
            p
            for p in memory_files
            if customer_id in p.name
        ]

        if matching_files:

            memory_file = max(
                matching_files,
                key=lambda p: p.stat().st_mtime
            )

        else:

            memory_file = max(
                memory_files,
                key=lambda p: p.stat().st_mtime
            )

        memory_records = load_jsonl(
            memory_file
        )

        st.caption(
            f"Memory file: `{memory_file.name}`"
        )

        st.write(
            f"Memory records: "
            f"**{len(memory_records)}**"
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
                "Memory file is empty."
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
# ARTIFACT SUMMARY
# ============================================================

st.divider()

st.subheader(
    "Artifact Summary"
)

artifact_col1, artifact_col2, artifact_col3 = st.columns(3)

with artifact_col1:

    st.write(
        "Evaluation artifact"
    )

    st.write(
        "✅ Available"
        if EVALUATION_FILE
        else "❌ Missing"
    )

with artifact_col2:

    st.write(
        "Inferred-events artifact"
    )

    st.write(
        "✅ Available"
        if INFERRED_FILE
        else "❌ Missing"
    )

with artifact_col3:

    st.write(
        "Trace artifact"
    )

    st.write(
        "✅ Available"
        if TRACE_FILE
        else "❌ Missing"
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Agentic Customer 360 • "
    "Proactive Intervention Desk"
)
