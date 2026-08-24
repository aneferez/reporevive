from __future__ import annotations

from evaluation.run_eval import evaluate


def test_evaluation_scenarios_all_pass():
    report = evaluate()
    assert report.total >= 25, "PRD requires at least 25 documented scenarios"
    failed = [r.id for r in report.results if not r.passed]
    assert not failed, f"failing scenarios: {failed}"
    assert report.pass_rate == 1.0
