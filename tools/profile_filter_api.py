#!/usr/bin/env python3
"""Profile API latency for filter-driven transaction queries.

This script simulates the filter change patterns that a user triggers when
narrowing the transactions view (date range, merchant, category, amount).
Each filter combination fires a /transactions request; the script measures
response latency across a set of representative filter scenarios.

Use this to measure the effectiveness of the S1-3 debounce improvement and
to establish baselines for assessing DB/index tuning (S2-1 gate).

Output files follow the required naming convention:
    <batch>-<yyyymmddThhmmssZ>-filter-api.<artifact>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FilterScenario:
    name: str
    params: dict[str, Any]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * p
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (rank - lower)


def build_ssl_context(base_url: str, insecure: bool) -> ssl.SSLContext | None:
    from urllib.parse import urlsplit

    if urlsplit(base_url).scheme != "https":
        return None
    if insecure:
        return ssl._create_unverified_context()
    return ssl.create_default_context()


def make_transactions_request(
    base_url: str,
    timeout_seconds: float,
    ssl_context: ssl.SSLContext | None,
    api_token: str,
    unlock_token: str | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    query = urlencode({k: v for k, v in params.items() if v is not None})
    path = f"/transactions?{query}" if query else "/transactions"
    headers: dict[str, str] = {"X-API-Key": api_token}
    if unlock_token:
        headers["X-App-Unlock-Token"] = unlock_token
    req = Request(url=f"{base_url}{path}", method="GET", headers=headers)
    start = time.perf_counter()
    status_code: int | None = None
    ok = False
    error: str | None = None
    payload_size = 0
    try:
        with urlopen(req, timeout=timeout_seconds, context=ssl_context) as response:
            payload = response.read()
            status_code = response.status
            payload_size = len(payload)
            ok = 200 <= status_code < 300
    except HTTPError as exc:
        status_code = exc.code
        error = f"http_error:{exc.code}"
        try:
            payload_size = len(exc.read())
        except Exception:
            payload_size = 0
    except URLError as exc:
        error = f"url_error:{exc.reason}"
    except Exception as exc:
        error = f"request_error:{exc}"
    duration_ms = (time.perf_counter() - start) * 1000.0
    return {
        "path": path,
        "status_code": status_code,
        "ok": ok,
        "duration_ms": round(duration_ms, 3),
        "payload_bytes": payload_size,
        "error": error,
    }


def fetch_auth_status(
    base_url: str,
    timeout_seconds: float,
    ssl_context: ssl.SSLContext | None,
    api_token: str,
    unlock_token: str | None,
) -> dict[str, Any]:
    headers: dict[str, str] = {"X-API-Key": api_token}
    if unlock_token:
        headers["X-App-Unlock-Token"] = unlock_token
    req = Request(url=f"{base_url}/auth/status", method="GET", headers=headers)
    try:
        with urlopen(req, timeout=timeout_seconds, context=ssl_context) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"/auth/status failed: status={exc.code} body={message}") from exc


def unlock_with_pin(
    base_url: str,
    timeout_seconds: float,
    ssl_context: ssl.SSLContext | None,
    api_token: str,
    pin: str,
) -> str:
    headers = {"X-API-Key": api_token, "Content-Type": "application/json"}
    body = json.dumps({"pin": pin}).encode("utf-8")
    req = Request(url=f"{base_url}/auth/unlock", method="POST", headers=headers, data=body)
    try:
        with urlopen(req, timeout=timeout_seconds, context=ssl_context) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"/auth/unlock failed: status={exc.code} body={message}") from exc
    token = payload.get("unlock_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Unlock response did not include unlock_token")
    return token


def build_filter_scenarios(now: datetime) -> list[FilterScenario]:
    """Return representative filter combinations to benchmark.

    These mirror real user filter patterns: no-filter baseline, date-bounded,
    merchant search, category, amount range, and a combined multi-filter query.
    """
    month = f"{now.year:04d}-{now.month:02d}"
    month_start = f"{month}-01"
    month_end = f"{month}-28"  # safe across all months
    base = {"limit": 50, "offset": 0, "sort_by": "date", "sort_order": "desc"}
    return [
        FilterScenario(
            name="no_filter",
            params={**base},
        ),
        FilterScenario(
            name="date_range_current_month",
            params={**base, "date_from": month_start, "date_to": month_end},
        ),
        FilterScenario(
            name="merchant_search",
            params={**base, "merchant": "coffee"},
        ),
        FilterScenario(
            name="amount_min_filter",
            params={**base, "amount_min": 50},
        ),
        FilterScenario(
            name="amount_range_filter",
            params={**base, "amount_min": 10, "amount_max": 200},
        ),
        FilterScenario(
            name="combined_date_merchant",
            params={**base, "date_from": month_start, "date_to": month_end, "merchant": "store"},
        ),
    ]


def run_scenarios(
    *,
    scenarios: list[FilterScenario],
    runs: int,
    base_url: str,
    timeout_seconds: float,
    ssl_context: ssl.SSLContext | None,
    api_token: str,
    unlock_token: str | None,
) -> list[dict[str, Any]]:
    all_samples: list[dict[str, Any]] = []
    for run_idx in range(runs):
        run_started_at = datetime.now(timezone.utc).isoformat()
        for scenario in scenarios:
            result = make_transactions_request(
                base_url=base_url,
                timeout_seconds=timeout_seconds,
                ssl_context=ssl_context,
                api_token=api_token,
                unlock_token=unlock_token,
                params=scenario.params,
            )
            result["scenario"] = scenario.name
            result["run_index"] = run_idx
            result["run_started_at_utc"] = run_started_at
            all_samples.append(result)
    return all_samples


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for s in samples:
        by_scenario.setdefault(s["scenario"], []).append(s)

    scenario_summary: dict[str, dict[str, Any]] = {}
    for scenario, sc_samples in by_scenario.items():
        durations = [s["duration_ms"] for s in sc_samples]
        failures = [s for s in sc_samples if not s["ok"]]
        scenario_summary[scenario] = {
            "runs": len(durations),
            "failures": len(failures),
            "latency_ms": {
                "min": round(min(durations), 3),
                "max": round(max(durations), 3),
                "mean": round(sum(durations) / len(durations), 3),
                "p50": round(percentile(durations, 0.50), 3),
                "p95": round(percentile(durations, 0.95), 3),
            },
        }

    return {"scenarios": scenario_summary}


def write_outputs(
    output_dir: Path,
    base_name: str,
    raw_payload: dict[str, Any],
    summary_payload: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_json_path = output_dir / f"{base_name}.raw.json"
    summary_json_path = output_dir / f"{base_name}.summary.json"
    summary_csv_path = output_dir / f"{base_name}.summary.csv"

    raw_json_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
    summary_json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    with summary_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["scenario", "runs", "failures", "min_ms", "p50_ms", "mean_ms", "p95_ms", "max_ms"]
        )
        for scenario, values in summary_payload["scenarios"].items():
            lat = values["latency_ms"]
            writer.writerow(
                [
                    scenario,
                    values["runs"],
                    values["failures"],
                    lat["min"],
                    lat["p50"],
                    lat["mean"],
                    lat["p95"],
                    lat["max"],
                ]
            )

    return {
        "raw_json": raw_json_path,
        "summary_json": summary_json_path,
        "summary_csv": summary_csv_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile API latency for filter-driven transaction queries."
    )
    parser.add_argument(
        "--batch",
        default=os.environ.get("GODZILLA_PROFILE_BATCH", "s1"),
        help=(
            "Batch label used in output file names, e.g. 'baseline', 's1', 's2' "
            "(default: %(default)s). Output files use the convention "
            "<batch>-<yyyymmddThhmmssZ>-filter-api.<artifact>."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GODZILLA_PROFILE_BASE_URL", "http://127.0.0.1:8787"),
        help="API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--api-token",
        default=os.environ.get("GODZILLA_API_TOKEN"),
        help="API token. Defaults to GODZILLA_API_TOKEN env var.",
    )
    parser.add_argument(
        "--unlock-token",
        default=os.environ.get("GODZILLA_UNLOCK_TOKEN"),
        help="Optional unlock token for locked app sessions.",
    )
    parser.add_argument(
        "--pin",
        default=os.environ.get("GODZILLA_PIN"),
        help="Optional PIN used to call /auth/unlock when locked.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=8,
        help="Number of repeated runs per filter scenario (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Per-request timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--output-dir",
        default="trace/perf",
        help="Output directory for profile files (default: %(default)s).",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        default=True,
        help="Disable TLS certificate verification for HTTPS URLs (default: enabled).",
    )
    parser.add_argument(
        "--secure",
        dest="insecure",
        action="store_false",
        help="Enable TLS certificate verification.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.api_token:
        print("Missing API token. Set GODZILLA_API_TOKEN or pass --api-token.", file=sys.stderr)
        return 2
    if args.runs < 1:
        print("--runs must be >= 1", file=sys.stderr)
        return 2

    ssl_context = build_ssl_context(args.base_url, args.insecure)
    unlock_token = args.unlock_token

    try:
        auth_status = fetch_auth_status(
            base_url=args.base_url,
            timeout_seconds=args.timeout_seconds,
            ssl_context=ssl_context,
            api_token=args.api_token,
            unlock_token=unlock_token,
        )
    except Exception as exc:
        print(f"Failed to fetch auth status: {exc}", file=sys.stderr)
        return 1

    if bool(auth_status.get("locked")):
        if args.pin:
            try:
                unlock_token = unlock_with_pin(
                    base_url=args.base_url,
                    timeout_seconds=args.timeout_seconds,
                    ssl_context=ssl_context,
                    api_token=args.api_token,
                    pin=args.pin,
                )
            except Exception as exc:
                print(f"Failed to unlock with PIN: {exc}", file=sys.stderr)
                return 1
        elif unlock_token:
            pass
        else:
            print(
                "App is locked. Provide --pin or --unlock-token.",
                file=sys.stderr,
            )
            return 1

    started_at = datetime.now(timezone.utc)
    scenarios = build_filter_scenarios(started_at)

    samples = run_scenarios(
        scenarios=scenarios,
        runs=args.runs,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
        ssl_context=ssl_context,
        api_token=args.api_token,
        unlock_token=unlock_token,
    )

    summary = summarize(samples)
    batch = re.sub(r"[^a-z0-9_-]", "", args.batch.lower()) or "batch"
    base_name = f"{batch}-{started_at.strftime('%Y%m%dT%H%M%SZ')}-filter-api"
    raw_payload = {
        "generated_at_utc": started_at.isoformat(),
        "base_url": args.base_url,
        "runs_per_scenario": args.runs,
        "scenarios": [s.name for s in scenarios],
        "auth_status": {
            "pin_configured": auth_status.get("pin_configured"),
            "setup_required": auth_status.get("setup_required"),
            "locked": auth_status.get("locked"),
            "dev_bypass_enabled": auth_status.get("dev_bypass_enabled"),
            "auto_lock_minutes": auth_status.get("auto_lock_minutes"),
            "tls_enabled": (auth_status.get("tls") or {}).get("enabled"),
        },
        "samples": samples,
    }

    output_paths = write_outputs(Path(args.output_dir), base_name, raw_payload, summary)
    print(json.dumps({k: str(v) for k, v in output_paths.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
