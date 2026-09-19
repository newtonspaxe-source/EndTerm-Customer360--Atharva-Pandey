import json
from pathlib import Path
from typing import Any


class ScenarioEvaluator:

    def __init__(self, dataset_root: str = "."):
        self.dataset_root = Path(dataset_root)

    def load_ground_truth(self, scenario_id: str) -> dict[str, Any]:

        path = self.dataset_root / scenario_id / "ground_truth.json"

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_final(
        self,
        scenario_id: str,
        life_event,
        decision,
        execution,
        late_events: int,
    ) -> dict[str, Any]:

        ground_truth = self.load_ground_truth(scenario_id)

        checkpoints = ground_truth.get("checkpoints", [])

        # Final checkpoint is the strongest expected state/action.
        final_checkpoint = checkpoints[-1] if checkpoints else {}

        expected_state = final_checkpoint.get(
            "expected_inferred_state"
        )

        expected_action = final_checkpoint.get(
            "expected_action"
        )

        expected_action_subtype = final_checkpoint.get(
            "expected_action_subtype"
        )

        expected_hitl_status = final_checkpoint.get(
            "expected_hitl_status"
        )

        result = {
            "scenario_id": scenario_id,

            "expected_state": expected_state,
            "predicted_state": life_event.inferred_state,
            "state_pass": (
                life_event.inferred_state == expected_state
            ),

            "expected_action": expected_action,
            "predicted_action": decision.action,
            "action_pass": (
                decision.action == expected_action
            ),

            "expected_action_subtype": expected_action_subtype,
            "predicted_action_subtype": decision.action_subtype,
            "action_subtype_pass": (
                expected_action_subtype is None
                or decision.action_subtype == expected_action_subtype
            ),

            "expected_hitl_status": expected_hitl_status,
            "predicted_hitl_status": decision.hitl_status,

            "confidence": life_event.confidence,
            "confidence_band": life_event.confidence_band,

            "execution_status": execution.execution_status,

            "late_events": late_events,
        }

        return result

    def evaluate_checkpoints(
        self,
        scenario_id: str,
    ) -> list[dict[str, Any]]:

        ground_truth = self.load_ground_truth(scenario_id)

        results = []

        for checkpoint in ground_truth.get("checkpoints", []):

            results.append(
                {
                    "as_of_time": checkpoint.get("as_of_time"),

                    "expected_state": checkpoint.get(
                        "expected_inferred_state"
                    ),

                    "expected_confidence_band": checkpoint.get(
                        "expected_confidence_band"
                    ),

                    "expected_action": checkpoint.get(
                        "expected_action"
                    ),

                    "expected_action_subtype": checkpoint.get(
                        "expected_action_subtype"
                    ),

                    "expected_hitl_status": checkpoint.get(
                        "expected_hitl_status"
                    ),

                    "notes": checkpoint.get("notes", ""),
                }
            )

        return results

    def evaluate_red_herring_checks(
        self,
        scenario_id: str,
    ) -> list[dict[str, Any]]:

        ground_truth = self.load_ground_truth(scenario_id)

        results = []

        for check in ground_truth.get(
            "false_positive_checks",
            []
        ):

            results.append(
                {
                    "event_id": check.get("event_id"),

                    "must_not_trigger_action": check.get(
                        "must_not_trigger_action",
                        []
                    ),

                    "window_hours": check.get(
                        "window_hours"
                    ),

                    "notes": check.get(
                        "notes",
                        ""
                    ),
                }
            )

        return results

    def evaluate_run(self, scenario_id: str, inferred_path: str, final_result: dict[str, Any], late_events: int) -> dict[str, Any]:
        gt = self.load_ground_truth(scenario_id)
        rows=[]
        path=Path(inferred_path)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip(): rows.append(json.loads(line))
        checkpoints=gt.get("checkpoints", [])
        from datetime import datetime
        def nearest(cp):
            if not rows: return None
            target=cp.get("as_of_time")
            if not target: return rows[-1]
            t=datetime.fromisoformat(target.replace("Z","+00:00"))
            return min(rows,key=lambda r: abs(datetime.fromisoformat(r["as_of_time"].replace("Z","+00:00"))-t))
        scores=[]
        for cp in checkpoints:
            r=nearest(cp)
            scores.append({
                "as_of_time":cp.get("as_of_time"), "predicted":r,
                "state_pass":bool(r and r.get("inferred_state")==cp.get("expected_inferred_state")),
                "action_pass":bool(r and r.get("action")==cp.get("expected_action")),
                "subtype_pass":bool(r and (cp.get("expected_action_subtype") is None or r.get("action_subtype")==cp.get("expected_action_subtype"))),
                "hitl_pass":bool(r and (cp.get("expected_hitl_status") is None or r.get("hitl_status")==cp.get("expected_hitl_status"))),
            })
        return {"scenario_id":scenario_id,"checkpoint_results":scores,"inference_count":len(rows),"late_events":late_events,
                "final":self.evaluate_final(scenario_id, final_result["life_event"], final_result["decision"], final_result["execution"], late_events)}

    def print_final_result(
        self,
        result: dict[str, Any]
    ):

        print("\n" + "=" * 70)
        print(
            f"EVALUATION — {result['scenario_id']}"
        )
        print("=" * 70)

        print(
            f"Expected state       : "
            f"{result['expected_state']}"
        )

        print(
            f"Predicted state      : "
            f"{result['predicted_state']}"
        )

        print(
            f"State result         : "
            f"{'PASS' if result['state_pass'] else 'FAIL'}"
        )

        print()

        print(
            f"Expected action      : "
            f"{result['expected_action']}"
        )

        print(
            f"Predicted action     : "
            f"{result['predicted_action']}"
        )

        print(
            f"Action result        : "
            f"{'PASS' if result['action_pass'] else 'FAIL'}"
        )

        print()

        print(
            f"Expected subtype     : "
            f"{result['expected_action_subtype']}"
        )

        print(
            f"Predicted subtype    : "
            f"{result['predicted_action_subtype']}"
        )

        print(
            f"Subtype result       : "
            f"{'PASS' if result['action_subtype_pass'] else 'FAIL'}"
        )

        print()

        print(
            f"Expected HITL        : "
            f"{result['expected_hitl_status']}"
        )

        print(
            f"Predicted HITL       : "
            f"{result['predicted_hitl_status']}"
        )

        print()

        print(
            f"Confidence           : "
            f"{result['confidence']:.2f}"
        )

        print(
            f"Confidence band      : "
            f"{result['confidence_band']}"
        )

        print(
            f"Execution            : "
            f"{result['execution_status']}"
        )

        print(
            f"Late events detected : "
            f"{result['late_events']}"
        )

        print("=" * 70)