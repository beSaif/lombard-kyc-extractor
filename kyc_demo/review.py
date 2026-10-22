"""The human step: field decisions, a four-eyes sign-off, and an append-only audit log.

The model proposes and the rules route, but a compliance officer decides. Every action is one line in
runs/audit.jsonl, and every line carries the sha256 of the line before it, so editing or deleting a past
entry breaks the chain and verify() says where. What the file was (document hashes, extractor, prompt
version) is recorded with each sign-off, so a decision can be traced to the exact bytes and model behind it.

Rules a reviewer cannot skip:
- a value the system could not verify (unverified, dropped, or a required field it never found) must be
  accepted or corrected by eye before the file can be approved
- a file with flags needs a note on approval: why the flags do not stand in the way
- approval takes two different reviewers (four eyes); one rejection or request for information closes it

Identity is self-declared here (a name typed in the UI); a bank would take it from its single sign-on.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .validate import REQUIRED

FIELD_ACTIONS = {"accept", "correct", "reject"}
DECISIONS = {"approve", "reject", "request_info"}
NEEDS_EYES = {"unverified", "dropped"}
CLOSED = {"approved", "rejected", "info_requested"}
GENESIS = "0" * 64


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def entries(self, run_id: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
        return [r for r in rows if run_id is None or r.get("run_id") == run_id]

    def append(self, entry: dict) -> dict:
        with self.lock:
            rows = self.entries()
            entry = {"seq": len(rows) + 1, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     **entry, "prev": rows[-1]["hash"] if rows else GENESIS}
            entry["hash"] = _hash(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            return entry

    def verify(self) -> dict:
        """Walk the chain. Any edited, reordered or deleted line shows up as the first entry that breaks it."""
        prev, rows = GENESIS, self.entries()
        for i, r in enumerate(rows, start=1):
            if r.get("seq") != i or r.get("prev") != prev or _hash(r) != r.get("hash"):
                return {"ok": False, "entries": len(rows), "broken_at": i}
            prev = r["hash"]
        return {"ok": True, "entries": len(rows), "head": prev}


def review_state(result: dict, entries: list[dict]) -> dict:
    """Where the review of one run stands, rebuilt from its audit entries."""
    fields, approvals, closing = {}, [], None
    for e in entries:
        if e["kind"] == "field":
            fields[f"{e['doc']}.{e['field']}"] = e
        elif e["kind"] == "decision":
            if e["decision"] == "approve":
                approvals.append(e)
            else:
                closing = e
    needs = {f"{d}.{f}": ev["status"] for d, fs in (result.get("evidence") or {}).items()
             for f, ev in fs.items() if ev["status"] in NEEDS_EYES}
    for d, values in (result.get("fields") or {}).items():
        for f in REQUIRED.get(d, []) if values is not None else []:
            if (values.get(f) or {}).get("value") is None and f"{d}.{f}" not in needs:
                needs[f"{d}.{f}"] = "missing"
    approved_by = list(dict.fromkeys(a["reviewer"] for a in approvals))
    status = ({"reject": "rejected", "request_info": "info_requested"}[closing["decision"]] if closing
              else "approved" if len(approved_by) >= 2 else "awaiting_second_approval" if approved_by else "open")
    return {"status": status, "approved_by": approved_by, "fields": fields, "needs_eyes": needs,
            "pending": [k for k in needs if k not in fields],
            "rejected_fields": [k for k, e in fields.items() if e["action"] == "reject"], "entries": entries}


def refuse_field(state: dict, action: str, value: str | None) -> str | None:
    """Why a field action is not allowed, or None."""
    if state["status"] in CLOSED:
        return f"the review is closed ({state['status']})"
    if action not in FIELD_ACTIONS:
        return f"unknown action {action!r}"
    if action == "correct" and not (value or "").strip():
        return "a correction needs the corrected value"
    return None


def refuse_decision(state: dict, result: dict, reviewer: str, decision: str, note: str | None) -> str | None:
    """Why a sign-off is not allowed, or None."""
    if state["status"] in CLOSED:
        return f"the review is closed ({state['status']})"
    if decision not in DECISIONS:
        return f"unknown decision {decision!r}"
    if decision != "approve":
        return None if (note or "").strip() else "say why: a rejection or request for information needs a note"
    if state["pending"]:
        return "check these by eye first (accept or correct): " + ", ".join(state["pending"])
    if state["rejected_fields"]:
        return "rejected values cannot be approved; correct them or reject the file: " + ", ".join(state["rejected_fields"])
    if reviewer in state["approved_by"]:
        return "four eyes: the second approval must come from a different reviewer"
    if result.get("flags") and not (note or "").strip():
        return "the file has flags: say in a note why they do not stand in the way"
    return None


def provenance(result: dict) -> dict:
    """What the decision was about: the exact documents, model and prompt behind the values."""
    prompt = next((s["data"] for s in result.get("steps", []) if s["kind"] == "prompt"), {})
    return {"documents": {s["doc"]: s["data"].get("sha256") for s in result.get("steps", []) if s["kind"] == "load"},
            "extractor": result.get("extractor"), "second": result.get("second"),
            "prompt_version": prompt.get("prompt_version"), "decision_routed": result.get("decision"),
            "flags": [f["code"] for f in result.get("flags", [])]}


def corrections(log: AuditLog, results: dict[str, dict]) -> list[dict]:
    """Reviewer corrections next to what the model said: labelled data from real use, for the next eval."""
    out = []
    for e in log.entries():
        if e["kind"] != "field" or e["action"] != "correct" or e["run_id"] not in results:
            continue
        r = results[e["run_id"]]
        got = ((r.get("fields") or {}).get(e["doc"]) or {}).get(e["field"]) or {}
        out.append({"run_id": e["run_id"], "case": r.get("case"), "tier": r.get("tier"),
                    "extractor": r.get("extractor"), "doc": e["doc"], "field": e["field"],
                    "model_value": got.get("value"), "model_quote": got.get("quote"),
                    "evidence": ((r.get("evidence") or {}).get(e["doc"]) or {}).get(e["field"], {}).get("status"),
                    "corrected_value": e["value"], "reviewer": e["reviewer"], "at": e["at"]})
    return out
