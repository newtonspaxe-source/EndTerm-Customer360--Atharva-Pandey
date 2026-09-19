from pathlib import Path
from datetime import datetime, timezone
import json


class CLIHITL:
    """Real human checkpoint: approve, reject, or modify."""
    def __init__(self, audit_path: str = "outputs/hitl_audit.jsonl"):
        self.audit_path = Path(audit_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def review(self, decision, draft_message: str, context: dict | None = None):
        print("\n" + "=" * 70)
        print("                 HUMAN-IN-THE-LOOP REVIEW")
        print("=" * 70)
        print(f"Customer        : {decision.customer_id}")
        print(f"Inferred state  : {decision.inferred_state}")
        print(f"Confidence      : {decision.confidence:.2f} ({decision.confidence_band})")
        print(f"Action          : {decision.action}")
        print(f"Subtype         : {decision.action_subtype}")
        print(f"Reason          : {decision.rationale}")
        print(f"\nProposed message:\n{draft_message}")
        print("\n[A] Approve   [R] Reject   [M] Modify")

        choice = input("Your decision: ").strip().lower()

        if choice == "a":
            status = "human_approved"
            final_message = draft_message
        elif choice == "r":
            status = "human_rejected"
            final_message = draft_message
        elif choice == "m":
            status = "human_modified"
            final_message = input("Enter modified message: ").strip()
        else:
            print("Invalid choice. Treating as rejected.")
            status = "human_rejected"
            final_message = draft_message

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": decision.customer_id,
            "action": decision.action,
            "action_subtype": decision.action_subtype,
            "status": status,
            "original_message": draft_message,
            "final_message": final_message,
            "context_shown_to_human": context or {},
        }

        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        return status, final_message
