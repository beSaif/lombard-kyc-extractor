"""Score extractors against truth.json, per quality tier, and compare them.

What is measured, and why:
- field accuracy          share of truth values extracted correctly (normalised comparison)
- defect recall           planted defects that were flagged. Missing one is the expensive error
- defect precision        defect flags that were real
- missed-defect files     files with a defect routed to the quick pre-filled queue. The number that matters most
- trap false alarms       harmless variations (Av./Avenue, missing middle name) wrongly flagged
- straight-through rate   clean files that reached the pre-filled queue. This is the time saved
- seconds and $ per file
"""

import json
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from .normalise import same
from .pipeline import run_case

DEFECT_CODES = {"PASSPORT_EXPIRED", "MRZ_CHECK_FAILED", "MRZ_VISUAL_MISMATCH", "NAME_MISMATCH", "ADDRESS_MISMATCH",
                "DOB_MISMATCH", "NATIONALITY_MISMATCH", "PROOF_OF_ADDRESS_TOO_OLD", "SUSPICIOUS_INSTRUCTIONS"}
TRAP_GUARDS = {"NAME_NO_MIDDLE": "NAME_MISMATCH", "NAME_SURNAME_FIRST": "NAME_MISMATCH",
               "NAME_NO_ACCENT": "NAME_MISMATCH", "ADDR_ABBREVIATED": "ADDRESS_MISMATCH",
               "ADDR_CITY_ALIAS": "ADDRESS_MISMATCH", "ADDR_NUMBER_FIRST": "ADDRESS_MISMATCH",
               "POA_NEAR_LIMIT": "PROOF_OF_ADDRESS_TOO_OLD", "PASSPORT_EXPIRES_SOON": "PASSPORT_EXPIRED"}
CRITICAL_FIELDS = {"passport.surname", "passport.given_names", "passport.date_of_birth", "passport.document_number",
                   "passport.expiry_date", "form_a.beneficial_owner_name", "form_a.beneficial_owner_date_of_birth",
                   "form_a.beneficial_owner_nationality", "form_a.beneficial_owner_address",
                   "proof_of_address.name", "proof_of_address.address", "proof_of_address.issue_date"}
RESULTS = Path("runs/eval")


def case_dirs(cases: Path, tier: str, limit: int | None = None) -> list[Path]:
    dirs = sorted(p for p in (cases / tier).iterdir() if (p / "truth.json").exists())
    return dirs[:limit] if limit else dirs


def score_case(truth: dict, result: dict) -> dict:
    fields = {}
    for doc_type, values in truth["fields"].items():
        got = result["fields"][doc_type] or {}
        for name, want in values.items():
            value = (got.get(name) or {}).get("value")
            fields[f"{doc_type}.{name}"] = {"ok": same(name, value, want), "got": value, "want": want}
    raised = {f["code"] for f in result["flags"]}
    expected = set(truth["expected_flags"])
    return {
        "case": truth["case"], "tier": truth["tier"], "defects": truth["defects"], "traps": truth["traps"],
        "layouts": truth["layouts"], "decision": result["decision"], "raised": sorted(raised),
        "expected": sorted(expected), "fields": fields,
        "evidence": {d: {f: e["status"] for f, e in ev.items()} for d, ev in result["evidence"].items()},
        "totals": result["totals"],
    }


def run_eval(cases: Path, spec: str, tiers: list[str], as_of: date, limit: int | None = None,
             workers: int = 1, second: str | None = None, reader: str = "auto", progress=print) -> dict:
    from .extract import make_extractor
    ex = make_extractor(spec)
    sec = make_extractor(second) if second else None
    out = {}
    for tier in tiers:
        dirs = case_dirs(cases, tier, limit)

        def one(d: Path) -> dict:
            truth = json.loads((d / "truth.json").read_text())
            try:
                r = run_case(d, ex, as_of, reader=reader, second=sec)
            except Exception as e:  # one failed call must not sink a 90-file run
                progress(f"  {tier}/{d.name}: ERROR {e}")
                return {"case": d.name, "tier": tier, "error": str(e)}
            s = score_case(truth, r)
            progress(f"  {tier}/{d.name}: {s['decision']:17} raised={s['raised']} expected={s['expected']}")
            return s

        with ThreadPoolExecutor(max_workers=workers) as pool:
            out[tier] = list(pool.map(one, dirs))
    name = spec + (f"+{second}" if second else "") + (f"#{reader}" if reader != "auto" else "")
    if os.getenv("KYC_MODEL_INJECTION_DETECTOR", "on") == "off":
        name += "#regex-only-injection"
    report = {"extractor": name, "as_of": as_of.isoformat(), "tiers": {t: summarise(rs) for t, rs in out.items()},
              "cases": out}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{slug(name)}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report


def slug(name: str) -> str:
    return name.replace(":", "_").replace("@", "__").replace("/", "_").replace("+", "--").replace("#", "_")


def summarise(rows: list[dict]) -> dict:
    rows = [r for r in rows if "error" not in r]
    if not rows:
        return {}
    field_hits = defaultdict(lambda: [0, 0])
    for r in rows:
        for k, v in r["fields"].items():
            field_hits[k][0] += v["ok"]
            field_hits[k][1] += 1
    tp = fp = fn = 0
    per_defect = defaultdict(lambda: [0, 0])
    trap_hits = defaultdict(lambda: [0, 0])
    missed_files = clean_files = straight = routed_ok = 0
    process_flags = 0
    for r in rows:
        raised = set(r["raised"]) & DEFECT_CODES
        expected = set(r["expected"])
        tp += len(raised & expected)
        fp += len(raised - expected)
        fn += len(expected - raised)
        for code in expected:
            per_defect[code][0] += code in raised
            per_defect[code][1] += 1
        for trap in r["traps"]:
            guard = TRAP_GUARDS[trap]
            if guard not in expected:
                trap_hits[trap][0] += guard in raised
                trap_hits[trap][1] += 1
        process_flags += len(set(r["raised"]) - DEFECT_CODES)
        if expected:
            missed_files += r["decision"] == "pre_filled_review"
            routed_ok += r["decision"] == "manual_review"
        else:
            clean_files += 1
            straight += r["decision"] == "pre_filled_review"
            routed_ok += r["decision"] == "pre_filled_review"
    correct = sum(c for c, _ in field_hits.values())
    total = sum(t for _, t in field_hits.values())
    crit = [field_hits[k] for k in CRITICAL_FIELDS if k in field_hits]
    costs = [r["totals"]["cost_usd"] for r in rows if r["totals"].get("cost_usd") is not None]
    ratio = lambda a, b: round(a / b, 3) if b else None
    return {
        "files": len(rows),
        "field_accuracy": ratio(correct, total),
        "critical_field_accuracy": ratio(sum(c for c, _ in crit), sum(t for _, t in crit)),
        "defect_recall": ratio(tp, tp + fn),
        "defect_precision": ratio(tp, tp + fp),
        "missed_defect_files": missed_files,
        "defect_files": sum(1 for r in rows if r["expected"]),
        "straight_through_rate": ratio(straight, clean_files),
        "routing_accuracy": ratio(routed_ok, len(rows)),
        "trap_false_alarm_rate": ratio(sum(h for h, _ in trap_hits.values()), sum(n for _, n in trap_hits.values())),
        "process_flags_per_file": round(process_flags / len(rows), 2),
        # model latency as measured on the original call (a cache hit keeps it), plus OCR and rules time
        "seconds_per_file": round(sum(r["totals"].get("model_seconds") or 0 for r in rows) / len(rows), 2),
        "cost_per_file_usd": round(sum(costs) / len(costs), 5) if len(costs) == len(rows) else None,
        "fields": {k: ratio(c, t) for k, (c, t) in sorted(field_hits.items())},
        "per_defect": {k: ratio(h, n) for k, (h, n) in sorted(per_defect.items())},
        "per_trap": {k: ratio(h, n) for k, (h, n) in sorted(trap_hits.items())},
    }


METRICS = [("field_accuracy", "Field accuracy", "%"), ("critical_field_accuracy", "Critical-field accuracy", "%"),
           ("defect_recall", "Defect recall", "%"), ("defect_precision", "Defect precision", "%"),
           ("missed_defect_files", "Defect files sent to the quick queue", "n"),
           ("straight_through_rate", "Straight-through (clean files)", "%"),
           ("trap_false_alarm_rate", "Trap false-alarm rate", "%"),
           ("process_flags_per_file", "Process flags per file", "n"),
           ("seconds_per_file", "Model seconds per file", "n"), ("cost_per_file_usd", "$ per file", "$")]


def _fmt(v, kind):
    if v is None:
        return "-"
    return f"{v:.0%}" if kind == "%" else f"${v:.4f}" if kind == "$" else str(v)


def comparison_markdown(reports: list[dict]) -> str:
    tiers = [t for t in ("clean", "scan", "photo") if any(t in r["tiers"] for r in reports)]
    lines = ["# Extractor comparison", "", f"Synthetic files, review date {reports[0]['as_of']}.", ""]
    for tier in tiers:
        rs = [r for r in reports if r["tiers"].get(tier)]
        lines += [f"## {tier} ({rs[0]['tiers'][tier]['files']} files)", "",
                  "| Metric | " + " | ".join(f"`{r['extractor']}`" for r in rs) + " |",
                  "| --- |" + " --- |" * len(rs)]
        for key, label, kind in METRICS:
            lines.append(f"| {label} | " + " | ".join(_fmt(r["tiers"][tier].get(key), kind) for r in rs) + " |")
        lines.append("")
    return "\n".join(lines)


def load_reports() -> list[dict]:
    """Saved evals, with summaries recomputed from the per-case rows so metric changes need no re-run."""
    reports = []
    for p in sorted(RESULTS.glob("*.json")):
        r = json.loads(p.read_text())
        r["tiers"] = {t: summarise(rows) for t, rows in r["cases"].items()}
        reports.append(r)
    return reports
