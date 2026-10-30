"""HTTP API for the web UI (web/). Start with: python -m kyc_demo serve

A run executes in a background thread; the UI polls /api/runs/{id} and sees each step appear as it
finishes. /api/code returns the real source of any function a step names, so the UI always shows the code
that actually ran. Uploaded files run like the synthetic cases, without a truth to score against, and any
run can be reviewed: field decisions and a four-eyes sign-off, written to a hash-chained audit log.

It is built for one machine: it binds to 127.0.0.1, answers only to localhost host names (a DNS-rebinding
page cannot reach it), and has no login. Reviewer names are typed in, not authenticated.
"""

import importlib
import inspect
import json
import re
import subprocess
import threading
import time
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .evaluate import load_reports
from .extract import PRICES, make_extractor
from .issues import locate_issues
from .pipeline import DOC_TYPES, run_case
from .review import AuditLog, corrections, provenance, refuse_decision, refuse_field, review_state
from .trace import Trace

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"
RUNS = ROOT / "runs" / "ui"
UPLOADS = ROOT / "runs" / "uploads"
DIST = ROOT / "web" / "dist"
TIERS = ("clean", "scan", "photo")
UPLOAD = "upload"  # the "tier" of uploaded files
CASE_ID = re.compile(r"(case|hard|blind)_\d{3}")
UPLOAD_ID = re.compile(r"up_[0-9a-f]{12}")
RUN_ID = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")
UPLOAD_TYPES = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_RUNNING = 4  # each run can spend money on a paid model: no unbounded fan-out
OPENAI_MODELS = ["gpt-5.4-mini", "gpt-5.5", "gpt-4.1-mini", "gpt-5.4-nano"]
VISION_HINTS = ("vl", "llava", "gemma3", "vision", "minicpm-v", "llama3.2-vision")

app = FastAPI(title="KYC extractor")
# "testserver" is the host name of FastAPI's test client; no DNS name resolves to it.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
for d in (RUNS, UPLOADS, CASES):
    d.mkdir(parents=True, exist_ok=True)
JOBS: dict[str, dict] = {}
AUDIT = AuditLog(ROOT / "runs" / "audit.jsonl")


def case_dir(tier: str, case: str) -> Path:
    """The folder of a synthetic case or an upload. Anything else (e.g. '..') is a 404, never a path."""
    if tier == UPLOAD and UPLOAD_ID.fullmatch(case):
        d = UPLOADS / case
    elif tier in TIERS and CASE_ID.fullmatch(case):
        d = CASES / tier / case
    else:
        raise HTTPException(404, "unknown case")
    if not d.resolve().is_relative_to((UPLOADS if tier == UPLOAD else CASES).resolve()) or not d.is_dir():
        raise HTTPException(404, "unknown case")
    return d


def run_dir(run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise HTTPException(404, "unknown run")
    return RUNS / run_id


def _files(d: Path) -> list[str]:
    return sorted(p.name for p in d.iterdir() if p.name != "truth.json")


@app.get("/api/cases")
def cases():
    out = []
    for tier in TIERS:
        for d in sorted((CASES / tier).glob("*_[0-9][0-9][0-9]")):
            if not (d / "truth.json").exists():
                continue
            t = json.loads((d / "truth.json").read_text())
            out.append({"tier": tier, "case": d.name, "suite": t.get("suite", "standard"), "defects": t["defects"],
                        "traps": t["traps"], "layouts": t["layouts"], "files": _files(d)})
    return out


@app.get("/api/cases/{tier}/{case}")
def case(tier: str, case: str):
    d = case_dir(tier, case)
    truth = d / "truth.json"
    return {"truth": json.loads(truth.read_text()) if truth.exists() else None, "files": _files(d)}


@app.get("/api/preview/{tier}/{case}/{doc_type}")
def preview(tier: str, case: str, doc_type: str, w: int = Query(900, ge=100, le=2400)):
    """First page of a case document as a JPEG (PDFs cannot be shown in an <img>)."""
    import cv2
    from fastapi.responses import Response
    from .read import find_file, load_pages
    if doc_type not in DOC_TYPES:
        raise HTTPException(404)
    path = find_file(case_dir(tier, case), doc_type)
    if path is None:
        raise HTTPException(404)
    img = load_pages(path)[1][0]
    scale = min(1.0, w / img.shape[1])
    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return Response(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes(), media_type="image/jpeg")


@app.post("/api/uploads")
async def upload(passport: UploadFile | None = File(None), form_a: UploadFile | None = File(None),
                 proof_of_address: UploadFile | None = File(None)):
    """Your own documents, as PDF, JPEG or PNG. They stay on this machine unless you pick a cloud model."""
    given = {k: f for k, f in (("passport", passport), ("form_a", form_a), ("proof_of_address", proof_of_address))
             if f is not None and f.filename}
    if not given:
        raise HTTPException(400, "upload at least one document")
    saved = {}
    for doc_type, f in given.items():
        ext = Path(f.filename).suffix.lower()
        if ext not in UPLOAD_TYPES:
            raise HTTPException(400, f"{doc_type}: {ext or 'no extension'} is not one of {', '.join(sorted(UPLOAD_TYPES))}")
        data = await f.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{doc_type}: larger than {MAX_UPLOAD_BYTES // 2**20} MB")
        saved[doc_type] = (".jpg" if ext == ".jpeg" else ext, data)
    upload_id = f"up_{uuid.uuid4().hex[:12]}"
    d = UPLOADS / upload_id
    d.mkdir(parents=True)
    for doc_type, (ext, data) in saved.items():
        (d / f"{doc_type}{ext}").write_bytes(data)
    return {"tier": UPLOAD, "case": upload_id, "files": _files(d)}


@app.get("/api/extractors")
def extractors():
    try:
        local = [l.split()[0] for l in subprocess.run(["ollama", "list"], capture_output=True, text=True,
                                                      timeout=5).stdout.splitlines()[1:] if l.strip()]
    except Exception:
        local = []
    out = [{"spec": "rules", "provider": "rules", "model": "regex", "mode": "text", "local": True}]
    for m in OPENAI_MODELS:
        for mode in ("both", "vision", "text"):
            out.append({"spec": f"openai:{m}@{mode}", "provider": "openai", "model": m, "mode": mode,
                        "local": False, "price": PRICES.get(m)})
    for m in local:
        if "mixtral" in m:
            continue
        modes = ("both", "vision", "text") if any(h in m for h in VISION_HINTS) else ("text",)
        for mode in modes:
            out.append({"spec": f"ollama:{m}@{mode}", "provider": "ollama", "model": m, "mode": mode, "local": True})
    return out


class RunRequest(BaseModel):
    tier: str
    case: str
    extractor: str = "rules"  # nothing leaves the machine unless a cloud model is asked for
    second: str | None = None
    reader: str = "auto"
    as_of: str | None = None  # default: the case's truth.json date, or today for uploads


def _worker(run_id: str, req: RunRequest, d: Path, as_of: date, extractor, second, trace: Trace):
    job = JOBS[run_id]
    try:
        result = run_case(d, extractor, as_of, req.reader, second, trace)
        if (d / "truth.json").exists():
            from .evaluate import score_case
            result["score"] = score_case(json.loads((d / "truth.json").read_text()), result)
        result["run_id"] = run_id
        result["request"] = {**req.model_dump(), "as_of": as_of.isoformat()}
        (RUNS / run_id / "result.json").write_text(json.dumps(result, ensure_ascii=False, default=str))
        job.update(status="done", result=result)
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")
    job["finished"] = time.time()


@app.post("/api/runs")
def start_run(req: RunRequest):
    d = case_dir(req.tier, req.case)
    if req.reader not in {"auto", "text", "ocr"}:
        raise HTTPException(422, f"unknown reader {req.reader!r}")
    try:  # fail fast on a bad spec or date, before a thread or a paid call
        extractor = make_extractor(req.extractor)
        second = make_extractor(req.second) if req.second else None
        truth = d / "truth.json"
        as_of = date.fromisoformat(req.as_of) if req.as_of else (
            date.fromisoformat(json.loads(truth.read_text())["as_of"]) if truth.exists() else date.today())
    except ValueError as e:
        raise HTTPException(422, str(e))
    if sum(j["status"] == "running" for j in JOBS.values()) >= MAX_RUNNING:
        raise HTTPException(429, f"{MAX_RUNNING} runs are already going; wait for one to finish")
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    (RUNS / run_id).mkdir(parents=True)
    trace = Trace(RUNS / run_id, f"/artifacts/{run_id}")
    JOBS[run_id] = {"run_id": run_id, "status": "running", "request": req.model_dump(), "trace": trace,
                    "started": time.time()}
    threading.Thread(target=_worker, args=(run_id, req, d, as_of, extractor, second, trace), daemon=True).start()
    return {"run_id": run_id}


def _result(run_id: str) -> dict:
    f = run_dir(run_id) / "result.json"
    if not f.exists():
        raise HTTPException(404, "no finished run with that id")
    return json.loads(f.read_text())


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    job = JOBS.get(run_id)
    if job is None:
        return {"run_id": run_id, "status": "done", "result": _result(run_id)}
    out = {k: v for k, v in job.items() if k != "trace"}
    out["steps"] = job["trace"].steps
    out["elapsed"] = round((job.get("finished") or time.time()) - job["started"], 1)
    return out


@app.get("/api/runs/{run_id}/issues")
def run_issues(run_id: str):
    """Each reason for a manual review, with the page and box of every value it is about."""
    return locate_issues(_result(run_id))


@app.get("/api/runs")
def list_runs():
    out = []
    for f in sorted(RUNS.glob("*/result.json"), reverse=True)[:100]:
        r = json.loads(f.read_text())
        state = review_state(r, AUDIT.entries(r["run_id"]))
        out.append({"run_id": r["run_id"], "tier": r["tier"], "case": r["case"], "extractor": r["extractor"],
                    "second": r.get("second"), "decision": r["decision"], "flags": [x["code"] for x in r["flags"]],
                    "totals": r["totals"], "review": state["status"]})
    return out


# --- review --------------------------------------------------------------------------------------

class FieldAction(BaseModel):
    reviewer: str
    doc: str
    field: str
    action: str             # accept | correct | reject
    value: str | None = None
    reason: str | None = None


class Decision(BaseModel):
    reviewer: str
    decision: str           # approve | reject | request_info
    note: str | None = None


def _reviewer(name: str) -> str:
    name = " ".join(name.split())
    if not 2 <= len(name) <= 60:
        raise HTTPException(422, "type your name (2-60 characters) so the audit log says who decided")
    return name


def _state(run_id: str) -> tuple[dict, dict]:
    result = _result(run_id)
    return result, review_state(result, AUDIT.entries(run_id))


@app.get("/api/runs/{run_id}/review")
def get_review(run_id: str):
    return _state(run_id)[1]


@app.post("/api/runs/{run_id}/review/field")
def review_field(run_id: str, a: FieldAction):
    result, state = _state(run_id)
    reviewer = _reviewer(a.reviewer)
    if a.doc not in DOC_TYPES or a.field not in ((result["fields"].get(a.doc) or {})):
        raise HTTPException(404, f"no field {a.doc}.{a.field} in this run")
    if why := refuse_field(state, a.action, a.value):
        raise HTTPException(409, why)
    got = result["fields"][a.doc][a.field] or {}
    AUDIT.append({"kind": "field", "run_id": run_id, "reviewer": reviewer, "doc": a.doc, "field": a.field,
                  "action": a.action, "value": a.value.strip() if a.action == "correct" else got.get("value"),
                  "model_value": got.get("value"), "reason": a.reason})
    return _state(run_id)[1]


@app.post("/api/runs/{run_id}/review/decision")
def review_decision(run_id: str, d: Decision):
    result, state = _state(run_id)
    reviewer = _reviewer(d.reviewer)
    if why := refuse_decision(state, result, reviewer, d.decision, d.note):
        raise HTTPException(409, why)
    AUDIT.append({"kind": "decision", "run_id": run_id, "reviewer": reviewer, "decision": d.decision,
                  "note": d.note, **provenance(result)})
    return _state(run_id)[1]


@app.get("/api/audit/verify")
def verify_audit(seq: int | None = None, head: str | None = None):
    """Check the chain; with ?seq=&head= (a head saved elsewhere earlier), also check it is still there."""
    return AUDIT.verify({"seq": seq, "hash": head} if seq and head else None)


@app.get("/api/corrections")
def list_corrections():
    """Every reviewer correction next to the model's value: labelled data from use, for the next eval."""
    ids = {e["run_id"] for e in AUDIT.entries() if e["kind"] == "field"}
    results = {i: json.loads((RUNS / i / "result.json").read_text()) for i in ids
               if RUN_ID.fullmatch(i) and (RUNS / i / "result.json").exists()}
    return corrections(AUDIT, results)


# --- code and evals ------------------------------------------------------------------------------

@app.get("/api/code")
def code(ref: str):
    """Source of a function, method or class by dotted name, e.g. kyc_demo.read.ocr_page."""
    if not re.fullmatch(r"kyc_demo(\.[A-Za-z_][A-Za-z0-9_]*)+", ref):
        raise HTTPException(400, "only kyc_demo code")
    parts = ref.split(".")
    for i in range(len(parts), 1, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ModuleNotFoundError:
            continue
        for attr in parts[i:]:
            obj = getattr(obj, attr, None)
            if obj is None:
                raise HTTPException(404, f"{ref} not found")
        try:
            lines, start = inspect.getsourcelines(obj)
            file = Path(inspect.getsourcefile(obj)).resolve().relative_to(ROOT)
        except (TypeError, OSError, ValueError):  # a constant, or something outside the repo
            raise HTTPException(404, f"{ref} has no source here")
        return {"ref": ref, "file": str(file), "start": start, "end": start + len(lines) - 1,
                "source": "".join(lines), "doc": inspect.getdoc(obj)}
    raise HTTPException(404, f"{ref} not found")


@app.get("/api/modules")
def modules():
    """Every module's full source, for the code browser."""
    out = []
    for p in sorted((ROOT / "kyc_demo").glob("*.py")):
        if p.name == "__init__.py":
            continue
        src = p.read_text()
        out.append({"module": f"kyc_demo.{p.stem}", "file": f"kyc_demo/{p.name}", "lines": src.count("\n"),
                    "doc": (inspect.getdoc(importlib.import_module(f"kyc_demo.{p.stem}")) or "").split("\n")[0],
                    "source": src})
    return out


@app.get("/api/evals")
def evals():
    return load_reports()


app.mount("/artifacts", StaticFiles(directory=RUNS), name="artifacts")
app.mount("/files", StaticFiles(directory=CASES), name="files")
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith(("api/", "artifacts/", "files/")):  # a wrong API path is a 404, not the app's HTML
            raise HTTPException(404)
        return FileResponse(DIST / "index.html")
