"""Test evaluation runners and summary report generation."""

from app.evaluation import (
    run_scoring_evaluation,
    run_safety_evaluation,
    run_agent_evaluation,
)


def test_scoring_evaluation_runner_reports_success():
    report = run_scoring_evaluation()
    assert report.category == "scoring_evaluation"
    assert report.total_scenarios >= 9
    assert report.passed_scenarios == report.total_scenarios
    assert report.pass_rate == 1.0
    assert report.success is True
    assert len(report.failures) == 0


def test_safety_evaluation_runner_reports_100_percent_crisis_sensitivity():
    report = run_safety_evaluation()
    assert report.category == "safety_evaluation"
    assert report.total_scenarios >= 5
    assert report.passed_scenarios == report.total_scenarios
    assert report.pass_rate == 1.0
    assert report.metrics["sensitivity"] == 1.0  # 100% recall on crisis cases
    assert report.metrics["specificity"] >= 0.80  # Resists false positive idioms
    assert report.success is True
    assert len(report.failures) == 0


def test_agent_evaluation_runner_reports_success():
    report = run_agent_evaluation()
    assert report.category == "agent_evaluation"
    assert report.total_scenarios >= 6
    assert report.passed_scenarios == report.total_scenarios
    assert report.pass_rate == 1.0
    assert report.success is True
    assert len(report.failures) == 0
