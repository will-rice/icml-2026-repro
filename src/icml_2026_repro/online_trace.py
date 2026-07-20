"""Run a deterministic online evaluation trace with the official NAPE evaluator."""

import json
from pathlib import Path
from typing import Optional, Union, cast

from next_action_pred_eval.core.operation import Operation
from next_action_pred_eval.core.symbolic import symbolic_to_operations
from next_action_pred_eval.evaluation import (
    HEURISTIC_STEPS_SAVED,
    ISolver,
    Orchestrator,
    PredictionResult,
)
from next_action_pred_eval.evaluation.stride import StrideConfig, StrideMode

from icml_2026_repro.audit import GITHUB_REVISION

GROUND_TRUTH = [
    "VALUE | Sheet1!A1 | 1",
    "VALUE | Sheet1!A2 | 2",
    "VALUE | Sheet1!A2 | 2",
    "VALUE | Sheet1!A3 | 3",
    "VALUE | Sheet1!A4 | 4",
]

SCRIPTED_RESPONSES = [
    [GROUND_TRUTH[1]],
    ["VALUE | Sheet1!A4 | 999"],
    [],
]


class ScriptedSolver(ISolver):
    """Return a fixed symbolic prediction on each call."""

    def __init__(self, responses: list[list[str]]) -> None:
        self.responses = responses
        self.response_index = 0

    def predict(
        self,
        previous_actions: list[Union[Operation, str]],
        workbook_state: Optional[dict[str, object]] = None,
        context: Optional[dict[str, object]] = None,
    ) -> PredictionResult:
        """Return the next scripted response as parsed NAPE operations."""
        del previous_actions, workbook_state, context
        if self.response_index >= len(self.responses):
            raise RuntimeError("scripted solver responses exhausted")
        predicted_symbolic = self.responses[self.response_index]
        self.response_index += 1
        return PredictionResult(
            predicted_operations=symbolic_to_operations(predicted_symbolic),
            predicted_symbolic=predicted_symbolic,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            metadata={"solver": "scripted"},
        )

    def reset(self) -> None:
        """Restart the scripted response sequence."""
        self.response_index = 0


def _read_timeline(path: Path) -> list[dict[str, object]]:
    """Parse the official recorder timeline JSONL."""
    events: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as timeline_file:
        for line_number, line in enumerate(timeline_file, start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"invalid timeline event at line {line_number}") from error
            if not isinstance(event, dict):
                raise RuntimeError(f"timeline event at line {line_number} is not an object")
            events.append(event)
    return events


def build_claim_2_evidence(output_dir: Path) -> dict[str, object]:
    """Build evidence for the online evaluation transitions in Claim 2."""
    output_dir.mkdir(parents=True, exist_ok=True)
    orchestrator = Orchestrator(
        solver=ScriptedSolver(SCRIPTED_RESPONSES),
        stride_config=StrideConfig(mode=StrideMode.FIXED_INTERVAL, interval=1),
        acceptance_heuristics=[HEURISTIC_STEPS_SAVED],
        output_dir=output_dir,
    )
    orchestrator.run_experiment(
        cast(list[Union[Operation, str]], GROUND_TRUTH),
        experiment_name="claim-2-fixture",
        online_mode=True,
    )

    timeline_path = output_dir / "timeline.jsonl"
    if not timeline_path.exists():
        raise RuntimeError("official evaluator did not write timeline.jsonl")
    events = _read_timeline(timeline_path)

    decisions: list[dict[str, object]] = []
    last_user_event: Optional[dict[str, object]] = None
    for event in events:
        event_type = event.get("event")
        if event_type == "user_step":
            last_user_event = event
            continue
        if event_type != "prediction":
            continue
        if last_user_event is None or event.get("user_step") != last_user_event.get("user_step"):
            raise RuntimeError("prediction was not recorded after its user action")

        predicted_ops = event.get("predicted_ops")
        future_head = event.get("future_head")
        accepted = event.get("accepted")
        future_before_count = last_user_event.get("future_len")
        if not isinstance(predicted_ops, list) or not predicted_ops:
            raise RuntimeError("online trace has an empty non-empty prediction transition")
        if not isinstance(future_head, list) or not isinstance(accepted, bool):
            raise RuntimeError("online trace prediction event has an invalid schema")
        if not isinstance(future_before_count, int):
            raise RuntimeError("online trace user event has no future count")
        if accepted and not all(
            isinstance(event.get(field), int) for field in ("gt_len_before", "gt_len_after")
        ):
            raise RuntimeError("accepted prediction has no recorded ground-truth update")

        decisions.append(
            {
                "prediction_index": event.get("prediction_index"),
                "user_step": event.get("user_step"),
                "t": event.get("t"),
                "accepted": accepted,
                "predicted_ops": cast(list[str], predicted_ops),
                "future_before_count": future_before_count,
                "future_after_count": len(future_head),
                "gt_len_before": event.get("gt_len_before"),
                "gt_len_after": event.get("gt_len_after"),
            }
        )

    accepted_decisions = [decision for decision in decisions if decision["accepted"] is True]
    rejected_decisions = [decision for decision in decisions if decision["accepted"] is False]
    future_updates = [
        decision
        for decision in accepted_decisions
        if decision["future_before_count"] != decision["future_after_count"]
    ]
    if not accepted_decisions or not rejected_decisions:
        raise RuntimeError("online trace did not record both accepted and rejected predictions")
    if not future_updates:
        raise RuntimeError("online trace did not record an accepted future update")

    return {
        "source_revision": GITHUB_REVISION,
        "fixture": GROUND_TRUTH,
        "decisions": decisions,
        "summary": {
            "predictions": len(decisions),
            "accepted": len(accepted_decisions),
            "rejected": len(rejected_decisions),
            "predictions_after_user_actions": True,
            "future_was_updated": True,
        },
        "verdict": "verified",
    }
