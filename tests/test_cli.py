import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from llm_latency_compare import main


class LatencyTests(unittest.TestCase):
    def run_compare(self, before, after, *flags):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, rows in (("before", before), ("after", after)):
                (root / f"{name}.csv").write_text("request_id,status,duration_ms,ttft_ms\n" + rows, encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                try:
                    code = main([str(root / "before.csv"), str(root / "after.csv"), *flags])
                except SystemExit as problem:
                    code = problem.code
            return code, output.getvalue(), error.getvalue()

    def test_paired_samples_and_opt_in_gate(self):
        before = "a,ok,100,40\nb,ok,400,50\nc,ok,200,70\n"
        after = "c,ok,260,80\na,ok,140,\nb,error,560,\n"
        code, output, error = self.run_compare(before, after, "--max-p95-regression-ms", "59")
        self.assertEqual(code, 1, error)
        report = json.loads(output)
        self.assertEqual(report["paired_successes"], 2)
        self.assertEqual(report["paired_ttft"], 1)
        self.assertEqual(report["duration_ms"]["delta_p95"], 60)
        self.assertAlmostEqual(report["error_rate_change_pp"], 100 / 3)
        self.assertEqual(report["gate_failures"], ["p95_regression"])

    def test_gate_fails_when_there_are_no_successful_pairs(self):
        code, output, error = self.run_compare("a,error,10,\n", "a,ok,20,5\n", "--max-p95-regression-ms", "1")
        self.assertEqual(code, 1, error)
        self.assertIsNone(json.loads(output)["duration_ms"]["delta_p95"])

    def test_error_rate_gate_with_fractional_percentage_points(self):
        good = "a,ok,110,\nb,ok,100,\n"
        degraded = "a,ok,110,\nb,error,100,\n"
        code, output, error = self.run_compare(good, degraded, "--max-error-increase-pp", "49.5")
        self.assertEqual(code, 1, error)
        self.assertEqual(json.loads(output)["gate_failures"], ["error_rate_increase"])

    def test_mismatched_request_ids_and_invalid_timings_fail(self):
        for bad in ("b,ok,10,\n", "a,ok,10,12\n", "a,ok,inf,\n", "a,ok,10\n", "a,error,10,3\n"):
            self.assertEqual(self.run_compare("a,ok,10,\n", bad)[0], 2)
