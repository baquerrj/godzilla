#!/usr/bin/env python3
"""Profile UI first-load latency by timing tab-specific API call groups.

This script measures the backend request sets that each tab issues on first load.
It writes both raw samples and summarized metrics to JSON/CSV files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class EndpointCall:
    name: str
    path: str
    method: str = "GET"
    body: dict[str, Any] | None = None


def month_bounds(now: datetime) -> tuple[str, str, str]:
    month = f"{now.year:04d}-{now.month:02d}"
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=now.tzinfo)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=now.tzinfo)
    this_month = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
    last_day = (next_month - this_month).days
    start = f"{month}-01"
    end = f"{month}-{last_day:02d}"
    return month, start, end


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
    low_val = sorted_values[lower]
    high_val = sorted_values[upper]
    return low_val + (high_val - low_val) * (rank - lower)


def build_context(base_url: str, insecure: bool) -> ssl.SSLContext | None:
    if urlsplit(base_url).scheme != "https":
        return None
    if insecure:
        return ssl._create_unverified_context()
    return ssl.create_default_context()


def make_request(
    base_url: str,
    timeout_seconds: float,
    ssl_context: ssl.SSLContext | None,
    api_token: str,
    unlock_token: str | None,
    call: EndpointCall,
) -> dict[str, Any]:
    headers = {
        "X-API-Key": api_token,
    }
    if unlock_token:
        headers["X-App-Unlock-Token"] = unlock_token

    body_bytes: bytes | None = None
    if call.body is not None:
        body_bytes = json.dumps(call.body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        url=f"{base_url}{call.path}",
        method=call.method,
        headers=headers,
        data=body_bytes,
    )

    start = time.perf_counter()
    status_code: int | None = None
    ok = False
    error: str | None = None
    payload_size = 0
    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl_context) as response:
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
    except Exception as exc:  # pragma: no cover - defensive fallback
        error = f"request_error:{exc}"
    duration_ms = (time.perf_counter() - start) * 1000.0
    return {
        "endpoint_name": call.name,
        "path": call.path,
        "method": call.method,
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
    result = make_request(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        ssl_context=ssl_context,
        api_token=api_token,
        unlock_token=unlock_token,
        call=EndpointCall(name="auth_status", path="/auth/status"),
    )
    if not result["ok"]:
        raise RuntimeError(
            f"/auth/status failed: status={result['status_code']} error={result['error']}"
        )

    headers = {"X-API-Key": api_token}
    if unlock_token:
        headers["X-App-Unlock-Token"] = unlock_token
    request = Request(url=f"{base_url}/auth/status", method="GET", headers=headers)
    with urlopen(request, timeout=timeout_seconds, context=ssl_context) as response:
        return json.loads(response.read().decode("utf-8"))


def unlock_with_pin(
    base_url: str,
    timeout_seconds: float,
    ssl_context: ssl.SSLContext | None,
    api_token: str,
    pin: str,
) -> str:
    headers = {
        "X-API-Key": api_token,
        "Content-Type": "application/json",
    }
    body = json.dumps({"pin": pin}).encode("utf-8")
    request = Request(
        url=f"{base_url}/auth/unlock",
        method="POST",
        headers=headers,
        data=body,
    )
    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl_context) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"/auth/unlock failed: status={exc.code} body={message}") from exc
    token = payload.get("unlock_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Unlock response did not include unlock_token")
    return token


def build_scenarios(now: datetime) -> dict[str, list[EndpointCall]]:
    month, month_start, month_end = month_bounds(now)
    overview_calls = [
        EndpointCall(name="app.getAccounts", path="/accounts"),
        EndpointCall(name="app.getCategories", path="/categories"),
        EndpointCall(name="syncState.getSyncState", path="/sync-state"),
        EndpointCall(name="conflictQueue.getConflicts", path="/conflicts?status=open"),
        EndpointCall(name="accountsTable.getAccounts", path="/accounts"),
        EndpointCall(name="balancesTable.getBalances", path="/balances?limit=100"),
    ]
    transactions_calls = [
        EndpointCall(
            name="transactionsTable.getTransactions",
            path=f"/transactions?{urlencode({'limit': 50, 'offset': 0, 'sort_by': 'date', 'sort_order': 'desc'})}",
        )
    ]
    reports_calls = [
        EndpointCall(name="budgetPanel.getBudgets", path=f"/budgets?{urlencode({'month': month})}"),
        EndpointCall(
            name="reportsPanel.getMonthlyOverview",
            path=f"/reports/monthly-overview?{urlencode({'month': month})}",
        ),
        EndpointCall(
            name="reportsPanel.getCashFlow",
            path=f"/reports/cash-flow?{urlencode({'start': month_start, 'end': month_end})}",
        ),
        EndpointCall(
            name="reportsPanel.getNetWorth",
            path=f"/reports/net-worth?{urlencode({'start': month_start, 'end': month_end})}",
        ),
    ]
    data_calls = [
        EndpointCall(name="settingsPanel.getSettings", path="/settings"),
        EndpointCall(name="exportPanel.getSettings", path="/settings"),
    ]
    return {
        "overview_first_load": overview_calls,
        "transactions_first_load": transactions_calls,
        "reports_first_load": reports_calls,
        "data_first_load": data_calls,
    }


def run_scenario(
    *,
    scenario_name: str,
    calls: list[EndpointCall],
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
        with ThreadPoolExecutor(max_workers=max(1, len(calls))) as pool:
            futures = [
                pool.submit(
                    make_request,
                    base_url,
                    timeout_seconds,
                    ssl_context,
                    api_token,
                    unlock_token,
                    call,
                )
                for call in calls
            ]
            results: list[dict[str, Any]] = []
            for future in as_completed(futures):
                results.append(future.result())
        group_duration_ms = max((entry["duration_ms"] for entry in results), default=0.0)
        for entry in results:
            entry["scenario"] = scenario_name
            entry["run_index"] = run_idx
            entry["run_started_at_utc"] = run_started_at
            entry["group_duration_ms"] = round(group_duration_ms, 3)
            all_samples.append(entry)
    return all_samples


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    by_endpoint: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sample in samples:
        by_scenario.setdefault(sample["scenario"], []).append(sample)
        by_endpoint.setdefault((sample["scenario"], sample["endpoint_name"]), []).append(sample)

    scenario_summary: dict[str, dict[str, Any]] = {}
    for scenario, scenario_samples in by_scenario.items():
        grouped_by_run: dict[int, list[dict[str, Any]]] = {}
        for entry in scenario_samples:
            grouped_by_run.setdefault(int(entry["run_index"]), []).append(entry)
        run_latencies = [
            max(item["duration_ms"] for item in run_entries)
            for _, run_entries in sorted(grouped_by_run.items(), key=lambda kv: kv[0])
        ]
        scenario_summary[scenario] = {
            "runs": len(run_latencies),
            "latency_ms": {
                "min": round(min(run_latencies), 3),
                "max": round(max(run_latencies), 3),
                "mean": round(sum(run_latencies) / len(run_latencies), 3),
                "p50": round(percentile(run_latencies, 0.50), 3),
                "p95": round(percentile(run_latencies, 0.95), 3),
            },
        }

    endpoint_summary: dict[str, dict[str, Any]] = {}
    for (scenario, endpoint_name), endpoint_samples in by_endpoint.items():
        key = f"{scenario}:{endpoint_name}"
        durations = [entry["duration_ms"] for entry in endpoint_samples]
        failures = [entry for entry in endpoint_samples if not entry["ok"]]
        endpoint_summary[key] = {
            "scenario": scenario,
            "endpoint_name": endpoint_name,
            "calls": len(endpoint_samples),
            "failures": len(failures),
            "latency_ms": {
                "min": round(min(durations), 3),
                "max": round(max(durations), 3),
                "mean": round(sum(durations) / len(durations), 3),
                "p50": round(percentile(durations, 0.50), 3),
                "p95": round(percentile(durations, 0.95), 3),
            },
        }

    return {
        "scenarios": scenario_summary,
        "endpoints": endpoint_summary,
    }


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
    endpoint_csv_path = output_dir / f"{base_name}.endpoints.csv"

    raw_json_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
    summary_json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    with summary_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "runs", "min_ms", "p50_ms", "mean_ms", "p95_ms", "max_ms"])
        for scenario, values in summary_payload["scenarios"].items():
            latency = values["latency_ms"]
            writer.writerow(
                [
                    scenario,
                    values["runs"],
                    latency["min"],
                    latency["p50"],
                    latency["mean"],
                    latency["p95"],
                    latency["max"],
                ]
            )

    with endpoint_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scenario",
                "endpoint_name",
                "calls",
                "failures",
                "min_ms",
                "p50_ms",
                "mean_ms",
                "p95_ms",
                "max_ms",
            ]
        )
        for _, values in summary_payload["endpoints"].items():
            latency = values["latency_ms"]
            writer.writerow(
                [
                    values["scenario"],
                    values["endpoint_name"],
                    values["calls"],
                    values["failures"],
                    latency["min"],
                    latency["p50"],
                    latency["mean"],
                    latency["p95"],
                    latency["max"],
                ]
            )

    return {
        "raw_json": raw_json_path,
        "summary_json": summary_json_path,
        "summary_csv": summary_csv_path,
        "endpoint_csv": endpoint_csv_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile first-load API latency by tab.")
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
        help="Number of repeated runs per scenario (default: %(default)s).",
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

    ssl_context = build_context(args.base_url, args.insecure)
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
                "App is locked. Provide --pin or --unlock-token, or set GODZILLA_AUTH_DEV_BYPASS=1 "
                "for a dedicated profiling sidecar.",
                file=sys.stderr,
            )
            return 1

    started_at = datetime.now(timezone.utc)
    scenarios = build_scenarios(started_at)
    samples: list[dict[str, Any]] = []
    for scenario_name, calls in scenarios.items():
        samples.extend(
            run_scenario(
                scenario_name=scenario_name,
                calls=calls,
                runs=args.runs,
                base_url=args.base_url,
                timeout_seconds=args.timeout_seconds,
                ssl_context=ssl_context,
                api_token=args.api_token,
                unlock_token=unlock_token,
            )
        )

    summary = summarize(samples)
    base_name = f"first-load-latency-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    raw_payload = {
        "generated_at_utc": started_at.isoformat(),
        "base_url": args.base_url,
        "runs_per_scenario": args.runs,
        "scenarios": list(scenarios.keys()),
        "calls_by_scenario": {
            scenario: [call.__dict__ for call in calls]
            for scenario, calls in scenarios.items()
        },
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
