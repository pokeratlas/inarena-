"""Fail closed on missing journeys; a retry is a warning, never a clean release."""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
from pathlib import Path

DESKTOP = (
    "owner-session", "join", "owner-recovery", "owner-create", "profile",
    "owner-live", "cash-loop", "watchdog", "leave", "identity", "sit-out",
    "top-up", "queued-top-up", "cash-acceptance", "seven-max", "owner-lifecycle", "table-chat", "return", "owner-credit",
)
REQUIRED = {
    "guardian-desktop": DESKTOP,
    "guardian-mobile": ("join", "owner-create", "owner-live", "owner-lifecycle", "table-chat", "return", "owner-credit"),
}
BUDGETS = json.loads((Path(__file__).resolve().parents[1] /
                     "frontend/e2e-fullstack/guardian-budgets.json").read_text())


def evaluate(report: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    evidence: dict[str, str] = {}
    measurements: list[dict] = []

    def visit(suite: dict) -> None:
        for spec in suite.get("specs", []):
            tags = [word.removeprefix("@guardian-") for word in spec["title"].split()
                    if word.startswith("@guardian-")]
            for test in spec.get("tests", []):
                project = test.get("projectName", "")
                key = f"{project}/{tags[0] if len(tags) == 1 else spec['title']}"
                if key in evidence:
                    blockers.append(f"Duplicate journey: {key}")
                results = test.get("results", [])
                if len(tags) == 1:
                    measured = {}
                    for attachment in (results[-1].get("attachments", []) if results else []):
                        if not attachment.get("name", "").startswith("guardian-metric:"):
                            continue
                        try:
                            value = json.loads(base64.b64decode(attachment["body"], validate=True))
                            metric = value["metric"]
                            duration = value["durationMs"]
                            if (not isinstance(duration, (int, float)) or isinstance(duration, bool)
                                    or not math.isfinite(duration) or duration < 0 or metric in measured):
                                raise ValueError("invalid or duplicate duration")
                            measured[metric] = duration
                        except (ValueError, KeyError, TypeError):
                            blockers.append(f"Invalid measurement: {key}")
                    for metric, budget in BUDGETS.get(tags[0], {}).items():
                        duration = measured.get(metric)
                        measurements.append({"journey": key, "metric": metric,
                                             "duration_ms": duration, "budget_ms": budget})
                        if duration is None:
                            blockers.append(f"Missing timing: {key}/{metric}")
                        elif duration > budget:
                            blockers.append(f"Timing exceeds {budget}ms: {key}/{metric} ({duration}ms)")
                statuses = [result.get("status") for result in results]
                if (test.get("expectedStatus") != "passed" or not statuses
                        or statuses[-1] != "passed" or test.get("status") not in {"expected", "flaky"}):
                    evidence[key] = "BLOCKED"
                    blockers.append(f"Failed, skipped or incomplete journey: {key}")
                elif len(statuses) > 1 or test.get("status") == "flaky":
                    evidence[key] = "WARNING"
                    warnings.append(f"Passed only after retry: {key}")
                else:
                    evidence[key] = "READY"
        for child in suite.get("suites", []):
            visit(child)

    for suite in report.get("suites", []):
        visit(suite)
    for project, journeys in REQUIRED.items():
        for journey in journeys:
            key = f"{project}/{journey}"
            if key not in evidence:
                blockers.append(f"Missing required journey: {key}")
    if report.get("errors"):
        blockers.append("Playwright reported a runner/setup error")
    return {
        "gate": "BLOCKED" if blockers else "WARNING" if warnings else "READY",
        "blockers": blockers, "warnings": warnings, "journeys": evidence,
        "measurements": measurements,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(Path(args.report).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        result = {"gate": "BLOCKED", "blockers": [f"Report unavailable or invalid: {error}"],
                  "warnings": [], "journeys": {}}
    result.update(product="INARENA Product Guardian v1", candidate_sha=args.sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary = f"## Product Guardian: {result['gate']}\n\nCommit: `{args.sha}`\n\n"
    summary += "\n".join(f"- {message}" for message in result["blockers"] + result["warnings"])
    summary += "\n\n| Journey | Result |\n| --- | --- |\n"
    summary += "\n".join(f"| {key} | {value} |" for key, value in sorted(result["journeys"].items()))
    summary += "\n\n| Journey / timing | Measured ms | Budget ms |\n| --- | --- | --- |\n"
    summary += "\n".join(f"| {m['journey']}/{m['metric']} | {m['duration_ms']} | {m['budget_ms']} |"
                         for m in result.get("measurements", []))
    output.with_suffix(".md").write_text(summary + "\n", encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")
    print(f"Product Guardian: {result['gate']}")
    # WARNING also prevents automatic release; investigate and rerun cleanly.
    return 0 if result["gate"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
