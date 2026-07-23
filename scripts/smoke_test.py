#!/usr/bin/env python3
"""Post-deploy smoke test: confirms a running HealMatrix stack is actually up.

Unlike the pytest suite (which runs against an in-memory MongoDB and never
touches a real deployment), this hits real HTTP endpoints on a stack that has
already been started — by `docker compose up`, by Render, or by any other
target — and reports pass/fail per check with a nonzero exit code on any
failure, so it is safe to wire into a CI/CD deploy job as a gate.

Stdlib-only (urllib), deliberately: a smoke test that needs its own dependency
install is one more thing that can fail before it has told you anything.

Usage
-----
    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url https://healmatrix-api.onrender.com
    python scripts/smoke_test.py --frontend-url https://healmatrix.vercel.app
    python scripts/smoke_test.py --strict   # a degraded /health/ready also fails the run
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _get(url: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "healmatrix-smoke-test"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed http(s) URLs only
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def check_liveness(base_url: str, timeout: float) -> CheckResult:
    status, body = _get(f"{base_url}/health", timeout)
    if status != 200:
        return CheckResult("liveness (/health)", False, f"HTTP {status}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return CheckResult("liveness (/health)", False, "response was not valid JSON")
    if payload.get("status") != "alive":
        return CheckResult("liveness (/health)", False, f"unexpected body: {payload}")
    return CheckResult("liveness (/health)", True, f"version {payload.get('version', '?')}")


def check_readiness(base_url: str, timeout: float, strict: bool) -> CheckResult:
    status, body = _get(f"{base_url}/health/ready", timeout)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return CheckResult("readiness (/health/ready)", False, "response was not valid JSON")

    dependencies = payload.get("dependencies", {})
    detail = ", ".join(f"{name}={state}" for name, state in dependencies.items()) or "no dependency detail returned"

    if status == 200:
        return CheckResult("readiness (/health/ready)", True, detail)
    if status == 503:
        # A degraded Gemini configuration is expected and fine (every agent has a
        # deterministic fallback per docs/04_agent_design.md); MongoDB being down
        # is not. Only fail non-strict runs on the dependency that actually matters.
        mongodb_down = dependencies.get("mongodb") != "up"
        ok = not (strict or mongodb_down)
        return CheckResult("readiness (/health/ready)", ok, f"degraded — {detail}")
    return CheckResult("readiness (/health/ready)", False, f"HTTP {status}")


def check_docs(base_url: str, timeout: float) -> CheckResult:
    status, _ = _get(f"{base_url}/docs", timeout)
    if status != 200:
        return CheckResult("API docs (/docs)", False, f"HTTP {status}")
    return CheckResult("API docs (/docs)", True, "reachable")


def check_openapi(base_url: str, timeout: float) -> CheckResult:
    status, body = _get(f"{base_url}/openapi.json", timeout)
    if status != 200:
        return CheckResult("OpenAPI schema", False, f"HTTP {status}")
    try:
        schema = json.loads(body)
    except json.JSONDecodeError:
        return CheckResult("OpenAPI schema", False, "response was not valid JSON")
    paths = schema.get("paths", {})
    if not paths:
        return CheckResult("OpenAPI schema", False, "schema has no routes registered")
    return CheckResult("OpenAPI schema", True, f"{len(paths)} routes registered")


def check_frontend(frontend_url: str, timeout: float) -> CheckResult:
    status, body = _get(frontend_url, timeout)
    if status != 200:
        return CheckResult("frontend", False, f"HTTP {status}")
    if b"<div id=\"root\"" not in body and b"<div id='root'" not in body:
        return CheckResult("frontend", False, "response did not look like the built SPA shell")
    return CheckResult("frontend", True, "reachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL (no trailing slash)")
    parser.add_argument("--frontend-url", default=None, help="Optional frontend URL to also check")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds")
    parser.add_argument(
        "--strict", action="store_true",
        help="Fail the run if /health/ready reports 'degraded' for any reason, including a missing GOOGLE_API_KEY",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    checks = [
        check_liveness(base_url, args.timeout),
        check_readiness(base_url, args.timeout, args.strict),
        check_docs(base_url, args.timeout),
        check_openapi(base_url, args.timeout),
    ]
    if args.frontend_url:
        checks.append(check_frontend(args.frontend_url.rstrip("/"), args.timeout))

    print(f"HealMatrix smoke test — {base_url}\n")
    all_ok = True
    for check in checks:
        icon = "PASS" if check.ok else "FAIL"
        print(f"  [{icon}] {check.name}: {check.detail}")
        all_ok = all_ok and check.ok

    print()
    if all_ok:
        print("All checks passed.")
        return 0

    print("One or more checks failed — this deployment is not healthy.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
