"""The API's guard rails and the review workflow, end to end on an uploaded file with the rules extractor."""

import json
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from kyc_demo import web
from kyc_demo.review import AuditLog
from kyc_demo.synth import generate


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.saved = (web.CASES, web.RUNS, web.UPLOADS, web.AUDIT)
        web.CASES, web.RUNS, web.UPLOADS = root / "cases", root / "runs", root / "uploads"
        web.RUNS.mkdir()
        web.UPLOADS.mkdir()
        web.AUDIT = AuditLog(root / "audit.jsonl")
        generate(web.CASES, date(2026, 10, 21), n=1, tiers=("clean",))
        (root / "secret").mkdir()
        (root / "secret" / "passport.png").write_bytes(b"not for you")
        cls.client = TestClient(web.app)

    @classmethod
    def tearDownClass(cls):
        web.CASES, web.RUNS, web.UPLOADS, web.AUDIT = cls.saved
        cls.tmp.cleanup()

    def wait(self, run_id: str) -> dict:
        for _ in range(600):
            r = self.client.get(f"/api/runs/{run_id}").json()
            if r["status"] != "running":
                return r
            time.sleep(0.1)
        self.fail("run did not finish")

    def test_paths_outside_the_cases_are_not_reachable(self):
        for url in ["/api/preview/%2E%2E/secret/passport", "/api/cases/%2E%2E/secret", "/api/preview/clean/case_001/x",
                    "/api/cases/upload/%2E%2E", "/api/cases/upload/up_000000000000", "/api/runs/..%2F..%2Fsecret/review"]:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        r = self.client.post("/api/runs", json={"tier": "..", "case": "secret"})
        self.assertEqual(r.status_code, 404)

    def test_other_host_names_are_refused(self):
        self.assertEqual(self.client.get("/api/cases", headers={"host": "evil.example"}).status_code, 400)

    def test_bad_requests_fail_before_a_run_starts(self):
        for body in [{"second": "bogus:x@y"}, {"as_of": "nope"}, {"reader": "magic"}, {"extractor": "nope:x"}]:
            r = self.client.post("/api/runs", json={"tier": "clean", "case": "case_001", **body})
            self.assertEqual(r.status_code, 422, body)
        self.assertEqual(self.client.get("/api/preview/clean/case_001/passport?w=0").status_code, 422)

    def test_upload_run_review_and_four_eyes(self):
        src = web.CASES / "clean" / "case_001"
        files = {d: (f"{d}.pdf", (src / f"{d}.pdf").read_bytes(), "application/pdf")
                 for d in ("passport", "form_a", "proof_of_address")}
        self.assertEqual(self.client.post("/api/uploads", files={"passport": ("x.exe", b"MZ", "application/octet-stream")}).status_code, 400)
        up = self.client.post("/api/uploads", files=files).json()
        self.assertEqual(up["tier"], "upload")

        run = self.wait(self.client.post("/api/runs", json={"tier": "upload", "case": up["case"]}).json()["run_id"])
        self.assertEqual(run["status"], "done", run.get("error"))
        result, run_id = run["result"], run["result"]["run_id"]
        self.assertNotIn("score", result)  # an upload has no truth to score against

        review = self.client.get(f"/api/runs/{run_id}/review").json()
        self.assertEqual(review["status"], "open")
        approve = lambda who, note="flags checked by eye": self.client.post(
            f"/api/runs/{run_id}/review/decision", json={"reviewer": who, "decision": "approve", "note": note})
        if review["pending"]:  # the rules baseline leaves unverified values: they block approval
            r = approve("Alice Reviewer")
            self.assertEqual(r.status_code, 409)
            self.assertIn("check these by eye", r.json()["detail"])
            for key in review["pending"]:
                doc, field = key.split(".", 1)
                r = self.client.post(f"/api/runs/{run_id}/review/field", json={
                    "reviewer": "Alice Reviewer", "doc": doc, "field": field, "action": "correct", "value": "checked"})
                self.assertEqual(r.status_code, 200, r.text)

        self.assertEqual(approve("Alice Reviewer").json()["status"], "awaiting_second_approval")
        r = approve("Alice Reviewer")
        self.assertEqual(r.status_code, 409)
        self.assertIn("four eyes", r.json()["detail"])
        state = approve("Bob Second").json()
        self.assertEqual((state["status"], state["approved_by"]), ("approved", ["Alice Reviewer", "Bob Second"]))
        decision = state["entries"][-1]
        self.assertEqual(set(decision["documents"]), {"passport", "form_a", "proof_of_address"})
        self.assertEqual(approve("Carol Third").status_code, 409)  # closed

        head = self.client.get("/api/audit/verify").json()
        self.assertTrue(head["ok"])
        lines = web.AUDIT.path.read_text().splitlines()
        # Cutting the last line off leaves a valid chain: only the head saved elsewhere shows it.
        web.AUDIT.path.write_text("\n".join(lines[:-1]) + "\n")
        self.assertTrue(self.client.get("/api/audit/verify").json()["ok"])
        cut = self.client.get("/api/audit/verify", params={"seq": head["seq"], "head": head["head"]}).json()
        self.assertFalse(cut["ok"])
        self.assertIn("cut off", cut["why"])
        web.AUDIT.path.write_text("\n".join(lines) + "\n")
        first = json.loads(lines[0])
        first["reviewer"] = "Mallory"
        web.AUDIT.path.write_text("\n".join([json.dumps(first, sort_keys=True), *lines[1:]]) + "\n")
        self.assertEqual(self.client.get("/api/audit/verify").json(), {"ok": False, "entries": len(lines), "broken_at": 1})


if __name__ == "__main__":
    unittest.main()
