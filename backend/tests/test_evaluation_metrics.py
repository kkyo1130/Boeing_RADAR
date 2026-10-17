import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("radar_metrics", Path(__file__).resolve().parents[2] / "scripts/evaluate.py")
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


def dataset():
    return {"dataset_id": "synthetic-test/1", "split": "evaluation", "samples": [
        {"sample_id": str(i), "truth": "NORMAL" if i < 3 else "MISMATCH", "provenance": "unit_test"}
        for i in range(6)]}


def predictions():
    return [{"sample_id": str(i), "verdict": ["NORMAL", "MISMATCH", "UNVERIFIED"][i % 3],
             "latency_ms": i * 10} for i in range(6)]


def test_six_cell_denominators_and_same_set_trend():
    result = metrics.score(dataset(), predictions(), "v1")
    assert result["metrics"]["false_normal"] == {"numerator": 1, "denominator": 3, "value": 1/3}
    assert result["metrics"]["hold"]["value"] == 1/3
    assert result["metrics"]["alert_precision"]["value"] == .5
    assert result["latency_ms"]["p95"] == 50
    assert metrics.trend([result, metrics.score(dataset(), predictions(), "v2")])["automatic_training"] is False
    changed = dataset()
    changed["samples"][0]["truth"] = "MISMATCH"
    with pytest.raises(ValueError):
        metrics.trend([result, metrics.score(changed, predictions(), "v2")])


def test_missing_predictions_leakage_and_zero_denominator():
    labels = dataset()
    with pytest.raises(ValueError):
        metrics.score(labels, predictions()[:-1], "v1")
    labels["tuning_sample_ids"] = ["0"]
    with pytest.raises(ValueError):
        metrics.score(labels, predictions(), "v1")
    labels = dataset()
    for row in labels["samples"]:
        row["truth"] = "NORMAL"
    result = metrics.score(labels, predictions(), "v1")
    assert result["metrics"]["false_normal"]["value"] is None


def test_field_zero_is_not_boolean_or_missing():
    labels = {'dataset_id': 'zero/1', 'split': 'evaluation', 'samples': [
        {'sample_id': 'zero', 'truth': 'NORMAL', 'provenance': 'self_authored', 'fields': {'heading': 0}}]}
    for fields in ({}, {'heading': False}):
        result = metrics.score(labels, [{'sample_id': 'zero', 'verdict': 'UNVERIFIED', 'fields': fields}], 'v1')
        assert result['metrics']['field_exact']['numerator'] == 0
