# LLM Latency Compare

[Português](README.pt-BR.md) · [Contributing](CONTRIBUTING.md)

Detect latency regressions when you change an LLM configuration. Compare the same recorded requests before and after a change. The tool runs offline with Python 3.11 or newer and requires only a pair of CSV files.

```sh
python3 -m llm_latency_compare examples/baseline.csv examples/candidate.csv \
  --max-p95-regression-ms 30 --max-error-increase-pp 10
```

Use UTF-8 CSV with `request_id,status,duration_ms,ttft_ms`. Every ID must appear exactly once in both files. Status is `ok` or `error`, and timings are finite nonnegative milliseconds. Leave `ttft_ms` blank for failures or when no streaming measurement was captured. Use the same workload and measurement protocol in both runs.

The latency report uses nearest-rank p50 and p95 on pairs that succeeded in both runs. Time to first token uses only pairs with that value measured twice. All attempts count toward the error-rate change in percentage points. The sample shows a p95 increase of 60 ms and one additional error. Both gates fail. Results omit request IDs and model output. [OpenTelemetry GenAI observability](https://opentelemetry.io/blog/2026/genai-observability/)

Exit status is `0` for a completed check with passing or absent gates, `1` for a gate failure, and `2` for invalid input. A requested p95 gate fails when no paired successes are available. `python -m pip install .` installs the `llm-latency-compare` command.

The report counts requests that went from success to failure (`newly_failed_requests`) and from failure to success (`recovered_requests`). The net error rate can stay flat when one request recovers and another starts failing. Use `--max-newly-failed-requests 0` to fail the check when any previously successful request starts failing.
