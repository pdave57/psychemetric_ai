"""Evaluation package for PsychemetreAI / Agent Bleu.

Exposes evaluation metrics, scoring benchmarks, safety screening suites,
and agent orchestrator verification harnesses.
"""

from app.evaluation.evaluation_metrics import (
    cronbach_alpha,
    split_half_reliability,
    standard_error_of_measurement,
    item_total_correlations,
    mean_absolute_error,
    dimension_coverage_rate,
    completion_rate,
    safety_confusion_matrix,
    safety_sensitivity,
    safety_specificity,
    safety_f1_score,
    numeric_consistency_score,
    diagnostic_claim_absence_score,
    rag_citation_coverage,
    EvaluationReport,
)

from app.evaluation.scoring_tests import run_scoring_evaluation
from app.evaluation.safety_tests import run_safety_evaluation
from app.evaluation.agent_tests import run_agent_evaluation

__all__ = [
    "cronbach_alpha",
    "split_half_reliability",
    "standard_error_of_measurement",
    "item_total_correlations",
    "mean_absolute_error",
    "dimension_coverage_rate",
    "completion_rate",
    "safety_confusion_matrix",
    "safety_sensitivity",
    "safety_specificity",
    "safety_f1_score",
    "numeric_consistency_score",
    "diagnostic_claim_absence_score",
    "rag_citation_coverage",
    "EvaluationReport",
    "run_scoring_evaluation",
    "run_safety_evaluation",
    "run_agent_evaluation",
]
