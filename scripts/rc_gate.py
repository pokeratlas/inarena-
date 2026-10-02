from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


REQUIRED_WORKFLOWS = ("backend-ci", "frontend-ci")


def api_get(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def workflow_runs(repo: str, sha: str, token: str) -> list[dict]:
    data = api_get(
        f"https://api.github.com/repos/{repo}/actions/runs"
        f"?head_sha={sha}&per_page=100",
        token,
    )
    return list(data.get("workflow_runs", []))


def workflow_jobs(repo: str, run_id: int, token: str) -> list[dict]:
    data = api_get(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
        f"?per_page=100",
        token,
    )
    return list(data.get("jobs", []))


def select_latest_successful_run(
    runs: list[dict],
    workflow_name: str,
) -> dict:
    matching = [
        run
        for run in runs
        if run.get("name") == workflow_name
        and run.get("status") == "completed"
    ]
    if not matching:
        raise RuntimeError(
            f"no completed {workflow_name} run found for requested SHA"
        )
    matching.sort(
        key=lambda run: run.get("run_attempt", 1),
        reverse=True,
    )
    run = matching[0]
    if run.get("conclusion") != "success":
        raise RuntimeError(
            f"{workflow_name} is not green: "
            f"{run.get('conclusion') or run.get('status')}"
        )
    return run


def assert_jobs_green(jobs: list[dict], workflow_name: str) -> list[str]:
    failures = [
        f"{job.get('name')}: {job.get('conclusion') or job.get('status')}"
        for job in jobs
        if job.get("conclusion") not in {"success", "skipped"}
    ]
    if failures:
        raise RuntimeError(
            f"{workflow_name} contains non-green jobs: "
            + ", ".join(failures)
        )
    return [str(job.get("name")) for job in jobs]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate INARENA release-candidate CI state",
    )
    parser.add_argument("--sha", required=True)
    parser.add_argument("--schema-version", required=True, type=int)
    parser.add_argument("--frontend-version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]

    runs = workflow_runs(repo, args.sha, token)
    verified: dict[str, dict] = {}

    for name in REQUIRED_WORKFLOWS:
        run = select_latest_successful_run(runs, name)
        jobs = workflow_jobs(repo, int(run["id"]), token)
        verified[name] = {
            "run_id": run["id"],
            "run_url": run["html_url"],
            "jobs": assert_jobs_green(jobs, name),
        }

    manifest = {
        "product": "INARENA",
        "candidate_sha": args.sha,
        "schema_version": args.schema_version,
        "frontend_version": args.frontend_version,
        "workflows": verified,
        "gate": "PASS",
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(manifest, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
