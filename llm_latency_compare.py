"""Compare LLM timings for the same set of recorded requests."""

import argparse
import csv
from dataclasses import dataclass
import json
from math import ceil, isclose, isfinite
from pathlib import Path


@dataclass(frozen=True)
class Sample:
    success: bool
    duration_ms: float
    ttft_ms: float | None


def nonnegative(value):
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError("expected a finite nonnegative number")
    return number


def nonnegative_int(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("expected a nonnegative integer")
    return number


def read_samples(path):
    samples = {}
    columns = {"request_id", "status", "duration_ms", "ttft_ms"}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames is None or set(reader.fieldnames) != columns or len(reader.fieldnames) != len(columns):
            raise ValueError("expected columns request_id,status,duration_ms,ttft_ms")
        for row in reader:
            location = f"line {reader.line_num}"
            if None in row or None in row.values():
                raise ValueError(f"{location}: expected four fields")
            key = row["request_id"]
            if not key or key.strip() != key or key in samples:
                raise ValueError(f"{location}: blank or duplicate request ID")
            status = row["status"]
            if status not in ("ok", "error"):
                raise ValueError(f"{location}: status must be ok or error")
            try:
                duration = nonnegative(row["duration_ms"])
                ttft = nonnegative(row["ttft_ms"]) if row["ttft_ms"] else None
            except ValueError as error:
                raise ValueError(f"{location}: invalid duration or time to first token") from error
            if ttft is not None and (status == "error" or ttft > duration):
                raise ValueError(f"{location}: time to first token requires success and cannot exceed total duration")
            samples[key] = Sample(status == "ok", duration, ttft)
    if not samples:
        raise ValueError("expected at least one request")
    return samples


def quantiles(values):
    ordered = sorted(values)
    if not ordered:
        return {"p50": None, "p95": None}
    return {f"p{p}": ordered[ceil(len(ordered) * p / 100) - 1] for p in (50, 95)}


def timing_summary(pairs):
    baseline = quantiles([first for first, _ in pairs])
    candidate = quantiles([second for _, second in pairs])
    return {"baseline": baseline, "candidate": candidate,
            "delta_p95": candidate["p95"] - baseline["p95"] if pairs else None}


def compare(baseline, candidate):
    if baseline.keys() != candidate.keys():
        raise ValueError("both files must contain exactly the same request IDs")
    pairs = [(sample, candidate[key]) for key, sample in baseline.items()
             if sample.success and candidate[key].success]
    durations = [(old.duration_ms, new.duration_ms) for old, new in pairs]
    ttft = [(old.ttft_ms, new.ttft_ms) for old, new in pairs
            if old.ttft_ms is not None and new.ttft_ms is not None]
    baseline_errors = sum(not sample.success for sample in baseline.values())
    candidate_errors = sum(not sample.success for sample in candidate.values())
    paired_successes = len(pairs)
    return {"requests": len(baseline), "paired_successes": paired_successes, "paired_ttft": len(ttft),
            "baseline_errors": baseline_errors, "candidate_errors": candidate_errors,
            "newly_failed_requests": len(baseline) - baseline_errors - paired_successes,
            "recovered_requests": len(candidate) - candidate_errors - paired_successes,
            "error_rate_change_pp": (candidate_errors - baseline_errors) * 100 / len(baseline),
            "duration_ms": timing_summary(durations), "ttft_ms": timing_summary(ttft)}


def exceeds(value, limit):
    return value > limit and not isclose(value, limit, rel_tol=0, abs_tol=1e-9)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--max-p95-regression-ms", type=nonnegative)
    parser.add_argument("--max-error-increase-pp", type=nonnegative)
    parser.add_argument(
        "--max-newly-failed-requests", type=nonnegative_int,
        help="limit requests that succeeded in the baseline and failed in the candidate",
    )
    args = parser.parse_args(argv)
    try:
        baseline = read_samples(args.baseline)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(f"baseline: {error}")
    try:
        candidate = read_samples(args.candidate)
        report = compare(baseline, candidate)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(f"candidate: {error}")

    failures = []
    p95_delta = report["duration_ms"]["delta_p95"]
    if args.max_p95_regression_ms is not None:
        if p95_delta is None:
            failures.append("p95_unavailable")
        elif exceeds(p95_delta, args.max_p95_regression_ms):
            failures.append("p95_regression")
    if args.max_error_increase_pp is not None and exceeds(report["error_rate_change_pp"], args.max_error_increase_pp):
        failures.append("error_rate_increase")
    if args.max_newly_failed_requests is not None and report["newly_failed_requests"] > args.max_newly_failed_requests:
        failures.append("newly_failed_requests")
    report["gate_failures"] = failures
    print(json.dumps(report, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
