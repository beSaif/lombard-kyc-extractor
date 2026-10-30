"""The API's guard rails and the review workflow, end to end on an uploaded file with the rules extractor."""

import json
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from kyc_demo import web
from kyc_demo.issues import locate_issues
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

        issues = self.client.get(f"/api/runs/{run_id}/issues").json()
        self.assertEqual([i["code"] for i in issues["issues"]], [f["code"] for f in result["flags"]])
        self.assertEqual(set(issues["pages"]), {"passport", "form_a", "proof_of_address"})
        for region in (r for i in issues["issues"] for r in i["regions"]):
            if region["bbox"]:
                self.assertTrue(all(0 <= v <= 1 for v in region["bbox"]), region)
        self.assertEqual(self.client.get("/api/runs/20260101-000000-abcdef/issues").status_code, 404)

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


class IssueTests(unittest.TestCase):
    """Each flag points at the values its check read, on the page and in the box where they were found."""

    def result(self, flags, checks, evidence):
        return {"run_id": "r", "decision": "manual_review", "flags": flags, "checks": checks, "evidence": evidence,
                "fields": {"passport": {"date_of_birth": {"value": "1985-03-12", "quote": "12.03.1985", "page": 1}},
                           "form_a": {"beneficial_owner_date_of_birth": {"value": "1985-12-03", "quote": "x", "page": 1}},
                           "proof_of_address": None},
                "steps": [{"kind": "read", "doc": "passport", "data": {"page": 1, "image": "/artifacts/r/p.jpg"}}]}

    def test_a_cross_document_flag_points_at_both_values(self):
        box = [0.1, 0.2, 0.3, 0.25]
        out = locate_issues(self.result(
            [{"code": "DOB_MISMATCH", "severity": "high", "message": "m", "check": "cross.dob"},
             {"code": "MISSING_DOCUMENT", "severity": "high", "message": "m", "check": "proof_of_address.present"}],
            [{"name": "cross.dob", "detail": "", "inputs": {}},
             {"name": "proof_of_address.present", "detail": "document missing", "inputs": {}}],
            {"passport": {"date_of_birth": {"bbox": box, "page": 1, "method": "exact", "status": "verified",
                                            "value": "1985-03-12"}},
             "form_a": {"beneficial_owner_date_of_birth": {"bbox": [0.5, 0.5, 0.6, 0.52], "page": 1,
                                                           "method": "not_found", "status": "unverified",
                                                           "value": "1985-12-03", "why": "best match 60"}}}))
        dob, missing = out["issues"]
        self.assertEqual([(r["doc"], r["field"], r["exact"]) for r in dob["regions"]],
                         [("passport", "date_of_birth", True), ("form_a", "beneficial_owner_date_of_birth", False)])
        self.assertEqual(dob["regions"][0]["bbox"], box)
        self.assertIn("closest text", dob["regions"][1]["note"])  # a guess is never shown as a find
        self.assertEqual((missing["missing_doc"], missing["regions"]), ("proof_of_address", []))
        self.assertEqual(out["pages"], {"passport": [{"page": 1, "image": "/artifacts/r/p.jpg"}]})

    def test_signature_and_injection_point_at_where_the_check_looked(self):
        out = locate_issues(self.result(
            [{"code": "FORM_A_UNSIGNED", "severity": "high", "message": "m", "check": "form_a.signed"},
             {"code": "SUSPICIOUS_INSTRUCTIONS", "severity": "high", "message": "m", "check": "form_a.injection"}],
            [{"name": "form_a.signed", "detail": "", "inputs": {"page": 1, "bbox": [0.5, 0.8, 0.9, 0.84],
                                                                "label": "Signature", "ink": 0.0}},
             {"name": "form_a.injection", "detail": "", "inputs": {"regex_match": "ignore previous instructions",
                                                                   "where": {"page": 1, "bbox": [0.1, 0.9, 0.6, 0.92]}}}],
            {}))
        sig, inj = (i["regions"][0] for i in out["issues"])
        self.assertEqual((sig["bbox"], sig["exact"]), ([0.5, 0.8, 0.9, 0.84], True))
        self.assertEqual((inj["bbox"], inj["value"]), ([0.1, 0.9, 0.6, 0.92], "ignore previous instructions"))


if __name__ == "__main__":
    unittest.main()
