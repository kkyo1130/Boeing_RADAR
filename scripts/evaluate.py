"""Score labelled, versioned offline predictions; never tune a model automatically."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def score(dataset, predictions, model_version):
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Explicit model version required")
    if not dataset.get("dataset_id") or dataset.get("split") not in ("tuning", "evaluation"):
        raise ValueError("dataset_id and tuning/evaluation split required")
    samples = dataset["samples"]
    ids = [s["sample_id"] for s in samples]
    if len(set(ids)) != len(ids) or not samples:
        raise ValueError("dataset must be nonempty with unique sample IDs")
    if any(not s.get("provenance") or s["truth"] not in ("NORMAL", "MISMATCH") for s in samples):
        raise ValueError("Every label needs provenance and NORMAL/MISMATCH truth")
    training = set(dataset.get("training_sample_ids", []))
    tuning = set(dataset.get("tuning_sample_ids", []))
    if set(ids) & training or dataset["split"] == "evaluation" and set(ids) & tuning:
        raise ValueError("Training/tuning leakage into evaluation")
    by_id = {p["sample_id"]: p for p in predictions}
    if len(by_id) != len(predictions) or set(by_id) != set(ids):
        raise ValueError("Predictions must cover exactly the fixed dataset once")
    counts = {truth: {v: 0 for v in ("NORMAL", "MISMATCH", "UNVERIFIED")}
              for truth in ("NORMAL", "MISMATCH")}
    failures, latencies = [], []
    field_total = field_correct = transcript_total = transcript_correct = 0
    for sample in samples:
        prediction = by_id[sample["sample_id"]]
        verdict = prediction["verdict"]
        if verdict not in counts[sample["truth"]]:
            raise ValueError("Unsupported verdict")
        counts[sample["truth"]][verdict] += 1
        if verdict != sample["truth"]:
            failures.append({"sample_id": sample["sample_id"], "truth": sample["truth"],
                             "verdict": verdict, "condition": sample.get("condition")})
        latency = prediction.get("latency_ms")
        if latency is not None:
            if isinstance(latency, bool) or not isinstance(latency, (float, int)) or not math.isfinite(latency) or latency < 0:
                raise ValueError("latency_ms must be finite nonnegative, or null")
            latencies.append(latency)
        for name, value in sample.get("fields", {}).items():
            field_total += 1
            actual = prediction.get("fields", {}).get(name)
            field_correct += name in prediction.get("fields", {}) and type(actual) is type(value) and actual == value
        if "transcript" in sample:
            transcript_total += 1
            transcript_correct += prediction.get("transcript") == sample["transcript"]
    a, b, c = (counts["NORMAL"][v] for v in ("NORMAL", "MISMATCH", "UNVERIFIED"))
    d, e, f = (counts["MISMATCH"][v] for v in ("NORMAL", "MISMATCH", "UNVERIFIED"))
    def rate(numerator, denominator):
        return {"numerator": numerator, "denominator": denominator,
                "value": numerator / denominator if denominator else None}
    latencies.sort()
    canonical = json.dumps(dataset, sort_keys=True, separators=(',', ':')).encode()
    return {"schema_version": "radar-evaluation/1", "dataset_id": dataset["dataset_id"],
        "dataset_sha256": hashlib.sha256(canonical).hexdigest(), "split": dataset["split"],
        "model_version": model_version, "sample_count": len(samples), "confusion": counts,
        "metrics": {"detection": rate(e, d+e+f), "false_normal": rate(d, d+e+f),
            "false_positive": rate(b, a+b+c), "alert_precision": rate(e, b+e),
            "hold": rate(c+f, a+b+c+d+e+f), "error_hold": rate(f, d+e+f),
            "field_exact": rate(field_correct, field_total),
            "transcript_exact": rate(transcript_correct, transcript_total)},
        "latency_ms": {"measured_count": len(latencies),
            "mean": sum(latencies)/len(latencies) if latencies else None,
            "p95": latencies[math.ceil(.95*len(latencies))-1] if latencies else None,
            "max": max(latencies) if latencies else None},
        "failures": failures, "limitations": "Finite labelled samples; zero observed failures do not imply zero risk. Model scores are not accuracy."}


def trend(reports):
    if len(reports) < 2 or len({r["dataset_sha256"] for r in reports}) != 1:
        raise ValueError("Compare at least two versions on the identical dataset")
    if len({r["model_version"] for r in reports}) != len(reports):
        raise ValueError("Model versions must differ")
    return {"dataset_sha256": reports[0]["dataset_sha256"], "versions": reports,
            "automatic_training": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--model-version")
    parser.add_argument("--compare", type=Path, nargs='+')
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.compare:
        result = trend([json.loads(p.read_text()) for p in args.compare])
    else:
        if not all((args.dataset, args.predictions, args.model_version)):
            parser.error("Scoring requires dataset, predictions and model-version")
        result = score(json.loads(args.dataset.read_text()), json.loads(args.predictions.read_text()), args.model_version)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


if __name__ == "__main__":
    main()
