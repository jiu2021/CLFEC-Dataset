import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval.eval import calculate_metrics


def edit(start, end, replacement, error_type="Word_Error"):
    return {
        "start": start,
        "end": end,
        "candidate_word": replacement,
        "error_type": error_type,
    }


def assert_metrics(row, counts):
    tp, fp, fn = counts
    assert (row["true_positive"], row["false_positive"], row["false_negative"]) == counts
    assert row["precision"] == pytest.approx(tp / (tp + fp) if tp + fp else 0.0)
    assert row["recall"] == pytest.approx(tp / (tp + fn) if tp + fn else 0.0)
    f1_denominator = 2 * tp + fp + fn
    assert row["f1_score"] == pytest.approx(2 * tp / f1_denominator if f1_denominator else 0.0)


FIRST = edit(0, 3, "alpha")
SECOND = edit(8, 10, "beta")
WRONG = edit(8, 10, "gamma")


@pytest.mark.parametrize(
    ("predicted", "gold", "detection", "correction"),
    [
        pytest.param([FIRST], [FIRST], (1, 0, 0), (1, 0, 0), id="correct"),
        pytest.param([WRONG], [SECOND], (1, 0, 0), (0, 1, 1), id="wrong-replacement"),
        pytest.param(
            [FIRST, WRONG], [FIRST, SECOND], (2, 0, 0), (1, 1, 1), id="mixed-replacements"
        ),
        pytest.param([], [FIRST], (0, 0, 1), (0, 0, 1), id="no-predictions"),
        pytest.param([FIRST], [], (0, 1, 0), (0, 1, 0), id="no-gold-edits"),
    ],
)
def test_strict_metrics(predicted, gold, detection, correction):
    report = calculate_metrics({1: predicted}, {1: gold})
    assert_metrics(report["detection"], detection)
    assert_metrics(report["correction"], correction)


@pytest.mark.parametrize(
    ("match_mode", "start", "end", "replacement", "threshold", "detection", "correction"),
    [
        ("strict", 4, 8, "alpha", 0.5, (0, 1, 1), (0, 1, 1)),
        ("loose", 4, 8, "alpha", 0.5, (1, 0, 0), (1, 0, 0)),
        ("loose", 4, 8, "wrong", 0.5, (1, 0, 0), (0, 1, 1)),
        ("loose", 4, 8, "wrong", 0.51, (0, 1, 1), (0, 1, 1)),
        ("loose", 6, 10, "alpha", 0.0, (0, 1, 1), (0, 1, 1)),
    ],
    ids=["strict-partial", "exactly-half", "half-wrong", "below-threshold", "touching-only"],
)
def test_span_matching_boundaries(match_mode, start, end, replacement, threshold, detection, correction):
    report = calculate_metrics(
        {1: [edit(start, end, replacement)]},
        {1: [edit(2, 6, "alpha")]},
        match_mode=match_mode,
        overlap_threshold=threshold,
    )
    assert_metrics(report["detection"], detection)
    assert_metrics(report["correction"], correction)


@pytest.mark.parametrize(
    ("predicted", "correction"),
    [([WRONG, SECOND], (0, 2, 1)), ([SECOND, WRONG], (1, 1, 0))],
    ids=["wrong-first", "correct-first"],
)
def test_first_matching_prediction_consumes_gold_once(predicted, correction):
    report = calculate_metrics({1: predicted}, {1: [SECOND]})
    assert_metrics(report["detection"], (1, 1, 0))
    assert_metrics(report["correction"], correction)


def test_id_filter_preserves_detection_recall_by_error_type():
    gold_fact = edit(8, 10, "beta", "Fact_Error")
    missed_word = edit(12, 15, "delta")
    report = calculate_metrics(
        {1: [FIRST, WRONG], 2: [FIRST], 3: [FIRST]},
        {1: [FIRST, gold_fact, missed_word], 2: [FIRST]},
        id_filter={1},
    )
    assert_metrics(report["detection"], (2, 0, 1))
    assert_metrics(report["correction"], (1, 1, 2))
    assert report["recall_by_error_type"]["Word_Error"] == {
        "gold_total": 2, "matched": 1, "recall": 0.5,
    }
    assert report["recall_by_error_type"]["Fact_Error"] == {
        "gold_total": 1, "matched": 1, "recall": 1.0,
    }


def test_empty_evaluation_cohort():
    report = calculate_metrics({}, {})
    for metric in ("detection", "correction"):
        assert_metrics(report[metric], (0, 0, 0))


def test_cli_scores_both_matching_modes(tmp_path):
    gold = tmp_path / "gold.json"
    pred = tmp_path / "pred.json"
    for path, edits in ((gold, [FIRST, SECOND]), (pred, [FIRST, WRONG])):
        row = {"id": "example", "type": "gec_only", "input_text": "0123456789", "cors": edits}
        path.write_text(json.dumps([row]), encoding="utf-8")

    evaluator = Path(__file__).resolve().parents[1] / "eval" / "eval.py"
    output = tmp_path / "reports"
    subprocess.run(
        [sys.executable, "-X", "utf8", str(evaluator), "--gold", str(gold), "--pred", str(pred),
         "--mode", "both", "--output-dir", str(output)],
        check=True,
        capture_output=True,
    )

    report = json.loads(next(output.glob("*.json")).read_text(encoding="utf-8"))
    assert [case["match_mode"] for case in report["results"]] == ["strict", "loose"]
    for case in report["results"]:
        for metrics in (case["overall"], case["by_sample_type"]["gec_only"]):
            assert_metrics(metrics["detection"], (2, 0, 0))
            assert_metrics(metrics["correction"], (1, 1, 1))
