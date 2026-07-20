from typing import cast

from icml_2026_repro.online_trace import build_claim_2_evidence


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
