from typing import cast

from icml_2026_repro.online_trace import GROUND_TRUTH, build_claim_2_evidence

EXPECTED_GROUND_TRUTH = [
    "VALUE | Sheet1!A1 | 1",
    "VALUE | Sheet1!A2 | 2",
    "VALUE | Sheet1!A3 | 3",
    "VALUE | Sheet1!A4 | 4",
    "VALUE | Sheet1!A5 | 5",
]


def test_online_trace_covers_prediction_decisions_and_future_update(tmp_path):
    evidence = build_claim_2_evidence(tmp_path)
    summary = cast(dict[str, object], evidence["summary"])
    decisions = cast(list[dict[str, object]], evidence["decisions"])

    assert evidence["verdict"] == "verified"
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["predictions_after_user_actions"] is True
    assert summary["future_was_updated"] is True
    assert {decision["accepted"] for decision in decisions} == {True, False}


def test_online_trace_uses_exact_fixture_and_multi_action_acceptance(tmp_path):
    evidence = build_claim_2_evidence(tmp_path)
    decisions = cast(list[dict[str, object]], evidence["decisions"])
    accepted = next(decision for decision in decisions if decision["accepted"] is True)

    assert GROUND_TRUTH == EXPECTED_GROUND_TRUTH
    assert evidence["fixture"] == EXPECTED_GROUND_TRUTH
    assert len(cast(list[str], accepted["predicted_ops"])) >= 2


def test_online_trace_is_idempotent_in_existing_output_directory(tmp_path):
    sentinel = tmp_path / "caller-file.txt"
    sentinel.write_text("preserve me", encoding="utf-8")

    first = build_claim_2_evidence(tmp_path)
    second = build_claim_2_evidence(tmp_path)
    decisions = cast(list[dict[str, object]], second["decisions"])

    assert second == first
    assert len(decisions) == 2
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_online_trace_future_counts_use_uncapped_timeline_lengths(tmp_path):
    evidence = build_claim_2_evidence(tmp_path)
    decisions = cast(list[dict[str, object]], evidence["decisions"])
    accepted = next(decision for decision in decisions if decision["accepted"] is True)

    user_t = cast(int, accepted["user_t"])
    prediction_t = cast(int, accepted["t"])
    gt_len_before = cast(int, accepted["gt_len_before"])
    gt_len_after = cast(int, accepted["gt_len_after"])
    assert accepted["future_before_count"] == gt_len_before - user_t
    assert accepted["future_after_count"] == gt_len_after - prediction_t
    assert accepted["future_before_count"] != accepted["future_after_count"]
