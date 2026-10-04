import copy
import base64
import json
import unittest

from guardian_gate import BUDGETS, REQUIRED, evaluate
from rc_gate import assert_jobs_green, select_latest_successful_run


def clean_report():
    return {"suites": [{"specs": [
        {"title": f"Journey @guardian-{journey}", "tests": [{
            "projectName": project, "expectedStatus": "passed", "status": "expected",
            "results": [{"status": "passed", "attachments": [
                {"name": f"guardian-metric:{metric}", "body": base64.b64encode(
                    json.dumps({"metric": metric, "durationMs": 100}).encode()).decode()}
                for metric in BUDGETS.get(journey, {})
            ]}],
        }]}
        for project, journeys in REQUIRED.items() for journey in journeys
    ]}]}


class GuardianGateTests(unittest.TestCase):
    def test_complete_report_is_ready(self):
        self.assertEqual(evaluate(clean_report())["gate"], "READY")

    def test_missing_or_empty_suite_blocks(self):
        self.assertEqual(evaluate({})["gate"], "BLOCKED")
        report = clean_report()
        report["suites"][0]["specs"].pop()
        self.assertEqual(evaluate(report)["gate"], "BLOCKED")

    def test_skip_timeout_expected_failure_and_no_results_block(self):
        for change in ({"results": []}, {"results": [{"status": "skipped"}]},
                       {"results": [{"status": "timedOut"}]}, {"expectedStatus": "failed"}):
            with self.subTest(change=change):
                report = clean_report()
                report["suites"][0]["specs"][0]["tests"][0].update(change)
                self.assertEqual(evaluate(report)["gate"], "BLOCKED")

    def test_retry_is_warning(self):
        report = clean_report()
        test = report["suites"][0]["specs"][0]["tests"][0]
        test.update(status="flaky", results=[{"status": "failed"}, test["results"][0]])
        self.assertEqual(evaluate(report)["gate"], "WARNING")

    def test_missing_invalid_or_slow_timings_block(self):
        for attachments in ([], [{"name": "guardian-metric:lobby-ready", "body": "invalid!"}],
                            [{"name": "guardian-metric:lobby-ready", "body": base64.b64encode(
                                json.dumps({"metric": "lobby-ready", "durationMs": 6000}).encode()).decode()}]):
            report = clean_report()
            spec = next(s for s in report["suites"][0]["specs"] if s["title"].endswith("@guardian-join"))
            spec["tests"][0]["results"][0]["attachments"] = attachments
            self.assertEqual(evaluate(report)["gate"], "BLOCKED")

    def test_runner_error_and_duplicate_block(self):
        report = clean_report()
        report["errors"] = [{"message": "setup failed"}]
        self.assertEqual(evaluate(report)["gate"], "BLOCKED")
        report = clean_report()
        report["suites"][0]["specs"].append(copy.deepcopy(report["suites"][0]["specs"][0]))
        self.assertEqual(evaluate(report)["gate"], "BLOCKED")

    def test_newer_failed_or_running_ci_cannot_use_old_green(self):
        older = {"name": "frontend-ci", "id": 1, "run_attempt": 4,
                 "status": "completed", "conclusion": "success"}
        for status, conclusion in (("completed", "failure"), ("in_progress", None)):
            newer = dict(older, id=2, run_attempt=1, status=status, conclusion=conclusion)
            with self.assertRaises(RuntimeError):
                select_latest_successful_run([older, newer], "frontend-ci")

    def test_missing_or_skipped_ci_jobs_block(self):
        for jobs in ([], [{"name": "build", "conclusion": "skipped"}]):
            with self.assertRaises(RuntimeError):
                assert_jobs_green(jobs, "frontend-ci")


if __name__ == "__main__":
    unittest.main()
