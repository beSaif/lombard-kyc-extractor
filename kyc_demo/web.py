"""HTTP API for the learning UI (web/). Start with: python -m kyc_demo serve

A run executes in a background thread; the UI polls /api/runs/{id} and sees each step appear as it
finishes. /api/code returns the real source of any function a step names, so the UI always shows the code
that actually ran.
"""

import importlib
import inspect
import json
import subprocess
import threading
import time
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .evaluate import load_reports
from .extract import PRICES, make_extractor
from .pipeline import run_case
from .trace import Trace

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"
RUNS = ROOT / "runs" / "ui"
DIST = ROOT / "web" / "dist"
TIERS = ("clean", "scan", "photo")
OPENAI_MODELS = ["gpt-5.4-mini", "gpt-5.5", "gpt-4.1-mini", "gpt-5.4-nano"]
VISION_HINTS = ("vl", "llava", "gemma3", "vision", "minicpm-v", "llama3.2-vision")

app = FastAPI(title="KYC extractor (learning UI)")
RUNS.mkdir(parents=True, exist_ok=True)
CASES.mkdir(exist_ok=True)
JOBS: dict[str, dict] = {}


@app.get("/api/cases")
def cases():
    out = []
    for tier in TIERS:
        for d in sorted((CASES / tier).glob("case_*")):
            t = json.loads((d / "truth.json").read_text())
            out.append({"tier": tier, "case": d.name, "defects": t["defects"], "traps": t["traps"],
                        "layouts": t["layouts"], "files": sorted(p.name for p in d.iterdir() if p.name != "truth.json")})
    return out


@app.get("/api/cases/{tier}/{case}")
def case(tier: str, case: str):
    d = CASES / tier / case
    if not (d / "truth.json").exists():
        raise HTTPException(404)
    return {"truth": json.loads((d / "truth.json").read_text()),
            "files": sorted(p.name for p in d.iterdir() if p.name != "truth.json")}


@app.get("/api/preview/{tier}/{case}/{doc_type}")
def preview(tier: str, case: str, doc_type: str, w: int = 900):
    """First page of a case document as a JPEG (PDFs cannot be shown in an <img>)."""
    import cv2
    from fastapi.responses import Response
    from .read import find_file, load_pages
    path = find_file(CASES / tier / case, doc_type)
    if path is None:
        raise HTTPException(404)
    img = load_pages(path)[1][0]
    scale = min(1.0, w / img.shape[1])
    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return Response(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes(), media_type="image/jpeg")


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
    extractor: str = "openai:gpt-5.4-mini@both"
    second: str | None = None
    reader: str = "auto"
    as_of: str = "2026-10-21"


def _worker(run_id: str, req: RunRequest, trace: Trace):
    job = JOBS[run_id]
    try:
        result = run_case(CASES / req.tier / req.case, make_extractor(req.extractor), date.fromisoformat(req.as_of),
                          req.reader, make_extractor(req.second) if req.second else None, trace)
        truth = json.loads((CASES / req.tier / req.case / "truth.json").read_text())
        from .evaluate import score_case
        result["score"] = score_case(truth, result)
        result["run_id"] = run_id
        result["request"] = req.model_dump()
        (RUNS / run_id / "result.json").write_text(json.dumps(result, ensure_ascii=False, default=str))
        job.update(status="done", result=result)
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")
    job["finished"] = time.time()


@app.post("/api/runs")
def start_run(req: RunRequest):
    if not (CASES / req.tier / req.case / "truth.json").exists():
        raise HTTPException(404, "unknown case")
    make_extractor(req.extractor)  # fail fast on a bad spec
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    (RUNS / run_id).mkdir(parents=True)
    trace = Trace(RUNS / run_id, f"/artifacts/{run_id}")
    JOBS[run_id] = {"run_id": run_id, "status": "running", "request": req.model_dump(), "trace": trace,
                    "started": time.time()}
    threading.Thread(target=_worker, args=(run_id, req, trace), daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    job = JOBS.get(run_id)
    if job is None:
        f = RUNS / run_id / "result.json"
        if not f.exists():
            raise HTTPException(404)
        return {"run_id": run_id, "status": "done", "result": json.loads(f.read_text())}
    out = {k: v for k, v in job.items() if k != "trace"}
    out["steps"] = job["trace"].steps
    out["elapsed"] = round((job.get("finished") or time.time()) - job["started"], 1)
    return out


@app.get("/api/runs")
def list_runs():
    out = []
    for f in sorted(RUNS.glob("*/result.json"), reverse=True)[:100]:
        r = json.loads(f.read_text())
        out.append({"run_id": r["run_id"], "tier": r["tier"], "case": r["case"], "extractor": r["extractor"],
                    "second": r.get("second"), "decision": r["decision"], "flags": [x["code"] for x in r["flags"]],
                    "totals": r["totals"]})
    return out


@app.get("/api/code")
def code(ref: str):
    """Source of a function, method or class by dotted name, e.g. kyc_demo.read.ocr_page."""
    if not ref.startswith("kyc_demo."):
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
        lines, start = inspect.getsourcelines(obj)
        file = Path(inspect.getsourcefile(obj)).resolve().relative_to(ROOT)
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
        return FileResponse(DIST / "index.html")
