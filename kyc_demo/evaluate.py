"""Score extractors against truth.json, per quality tier, and compare them.

What is measured, and why:
- field accuracy          share of truth values extracted correctly (normalised comparison)
- defect recall           planted defects whose flag was raised, with a 95% Wilson interval: with 19 defects,
                          19/19 only shows recall is probably above 83%
- defects not flagged     the expensive error, as a count. A file can still reach manual review for another
                          reason (a missing field), but then the reviewer is not told what is wrong
- right check             defects raised by the check meant to catch them (truth's expected_checks), not by
                          another check that happens to use the same flag code
- defect precision        defect flags that were real
- missed-defect files     files with a defect routed to the quick pre-filled queue. Read it next to
                          straight-through: a system that flags everything scores 0 here and saves nothing
- trap false alarms       harmless variations (Av./Avenue, missing middle name) wrongly flagged
- straight-through rate   clean files that reached the pre-filled queue. This is the time saved
- errors                  files whose run crashed. They are left out of every other metric, so watch this
- seconds and $ per file

Four suites, reported apart: "standard" (case_NNN) shows the system works; "hard" (hard_NNN) is built to
break it; "blind" (blind_NNN) was written by someone who never saw the rules, tables or prompt; "real"
(real_NNN) is public specimen passports, passport only. Each case is scored at its own review date
(truth.json as_of). A blind case may name its own traps, with the flag each one must not raise
(truth.json trap_guards).
"""

import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from .normalise import same
from .pipeline import run_case

DEFECT_CODES = {"PASSPORT_EXPIRED", "MRZ_CHECK_FAILED", "MRZ_VISUAL_MISMATCH", "NAME_MISMATCH", "ADDRESS_MISMATCH",
                "DOB_MISMATCH", "NATIONALITY_MISMATCH", "PROOF_OF_ADDRESS_TOO_OLD", "SUSPICIOUS_INSTRUCTIONS",
                "THIRD_PARTY_OWNER", "FORM_A_UNSIGNED", "IMPLAUSIBLE_DATE"}
TRAP_GUARDS = {"NAME_NO_MIDDLE": "NAME_MISMATCH", "NAME_SURNAME_FIRST": "NAME_MISMATCH",
               "NAME_NO_ACCENT": "NAME_MISMATCH", "ADDR_ABBREVIATED": "ADDRESS_MISMATCH",
               "ADDR_CITY_ALIAS": "ADDRESS_MISMATCH", "ADDR_NUMBER_FIRST": "ADDRESS_MISMATCH",
               "POA_NEAR_LIMIT": "PROOF_OF_ADDRESS_TOO_OLD", "PASSPORT_EXPIRES_SOON": "PASSPORT_EXPIRED",
               "POA_AT_LIMIT": "PROOF_OF_ADDRESS_TOO_OLD", "PASSPORT_EXPIRES_TODAY": "PASSPORT_EXPIRED",
               "UNSEEN_NATIONALITY": "NATIONALITY_MISMATCH", "UNSEEN_CITY_ALIAS": "ADDRESS_MISMATCH"}
SUITE_PREFIX = {"standard": "case_", "hard": "hard_", "blind": "blind_", "real": "real_"}
CRITICAL_FIELDS = {"passport.surname", "passport.given_names", "passport.date_of_birth", "passport.document_number",
                   "passport.expiry_date", "form_a.beneficial_owner_name", "form_a.beneficial_owner_date_of_birth",
                   "form_a.beneficial_owner_nationality", "form_a.beneficial_owner_address",
                   "proof_of_address.name", "proof_of_address.address", "proof_of_address.issue_date"}
# Committed, so anyone can check comparison.md. KYC_RESULTS points elsewhere for runs that must not mix with
# these (results/linux: the standard and hard suites as rendered off macOS).
RESULTS = Path(os.getenv("KYC_RESULTS") or Path(__file__).resolve().parent.parent / "results" / "eval")


def case_dirs(cases: Path, tier: str, limit: int | None = None, suite: str = "standard") -> list[Path]:
    dirs = sorted(p for p in (cases / tier).glob(f"{SUITE_PREFIX[suite]}*") if (p / "truth.json").exists())
    return dirs[:limit] if limit else dirs


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% interval for a proportion k/n. Unlike k/n alone it says how little 19/19 proves."""
    if not n:
        return None
    p, d = k / n, 1 + z * z / n
    centre, half = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)


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
        "trap_guards": truth.get("trap_guards", {}),
        "layouts": truth["layouts"], "decision": result["decision"], "raised": sorted(raised),
        "expected": sorted(expected), "expected_checks": truth.get("expected_checks", []),
        "failed_checks": sorted(c["name"] for c in result["checks"] if c["passed"] is False), "fields": fields,
        "evidence": {d: {f: e["status"] for f, e in ev.items()} for d, ev in result["evidence"].items()},
        "totals": result["totals"],
    }


def run_eval(cases: Path, spec: str, tiers: list[str], as_of: date | None = None, limit: int | None = None,
             workers: int = 1, second: str | None = None, reader: str = "auto", progress=print,
             suite: str = "standard") -> dict:
    """Run and score every case. as_of overrides each case's own review date (truth.json); leave it None."""
    from .extract import make_extractor
    ex = make_extractor(spec)
    sec = make_extractor(second) if second else None
    out, dates = {}, set()
    for tier in tiers:
        dirs = case_dirs(cases, tier, limit, suite)

        def one(d: Path) -> dict:
            truth = json.loads((d / "truth.json").read_text())
            review = as_of or date.fromisoformat(truth["as_of"])
            dates.add(review.isoformat())
            try:
                r = run_case(d, ex, review, reader=reader, second=sec)
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
    report = {"extractor": name, "suite": suite, "as_of": ", ".join(sorted(dates)), "platform": platform_name(),
              "tiers": {t: summarise(rs) for t, rs in out.items()}, "cases": out}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{slug(name)}{'' if suite == 'standard' else '.' + suite}.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False))
    return report


def platform_name() -> str:
    """Where a report was made. The standard and hard suites render differently on macOS (Bradley Hand) and
    elsewhere (Kalam), and Tesseract versions read differently, so a number is only comparable on its platform."""
    try:
        tess = subprocess.run(["tesseract", "--version"], capture_output=True, text=True).stdout.split()[1]
    except (OSError, IndexError):
        tess = "?"
    return f"{'macOS' if sys.platform == 'darwin' else sys.platform}, tesseract {tess}"


def slug(name: str) -> str:
    return name.replace(":", "_").replace("@", "__").replace("/", "_").replace("+", "--").replace("#", "_")


def summarise(rows: list[dict]) -> dict:
    errors = sum("error" in r for r in rows)
    rows = [r for r in rows if "error" not in r]
    if not rows:
        return {"errors": errors} if errors else {}
    field_hits = defaultdict(lambda: [0, 0])
    for r in rows:
        for k, v in r["fields"].items():
            field_hits[k][0] += v["ok"]
            field_hits[k][1] += 1
    tp = fp = fn = 0
    right = [0, 0]
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
        for check in r.get("expected_checks") or []:
            right[0] += check in r.get("failed_checks", [])
            right[1] += 1
        for trap in r["traps"]:
            guard = (r.get("trap_guards") or {}).get(trap) or TRAP_GUARDS.get(trap)
            if guard and guard not in expected:
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
        "defect_recall_ci": wilson(tp, tp + fn),
        "defect_recall_n": [tp, tp + fn],
        "defects_not_flagged": fn,
        "right_check_rate": ratio(*right),
        "defect_precision": ratio(tp, tp + fp),
        "missed_defect_files": missed_files,
        "missed_defect_files_ci": wilson(missed_files, sum(1 for r in rows if r["expected"])),
        "defect_files": sum(1 for r in rows if r["expected"]),
        "errors": errors,
        "straight_through_rate": ratio(straight, clean_files),
        "straight_through_ci": wilson(straight, clean_files),
        "clean_files": clean_files,
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


METRICS = [("files", "Files", "n"), ("field_accuracy", "Field accuracy", "%"), ("critical_field_accuracy", "Critical-field accuracy", "%"),
           ("defect_recall", "Defect recall (95% interval)", "recall"),
           ("defects_not_flagged", "Defects not flagged", "n"),
           ("right_check_rate", "Defects caught by the right check", "%"),
           ("defect_precision", "Defect precision", "%"),
           ("missed_defect_files", "Defect files sent to the quick queue", "n"),
           ("straight_through_rate", "Straight-through (clean files, 95% interval)", "stp"),
           ("trap_false_alarm_rate", "Trap false-alarm rate", "%"),
           ("process_flags_per_file", "Process flags per file", "n"), ("errors", "Errors", "n"),
           ("seconds_per_file", "Model seconds per file", "n"), ("cost_per_file_usd", "$ per file", "$")]


def _fmt(summary: dict, key: str, kind: str) -> str:
    v = summary.get(key)
    if v is None:
        return "-"
    if kind in ("recall", "stp"):
        lo, hi = summary.get("defect_recall_ci" if kind == "recall" else "straight_through_ci") or (None, None)
        return f"{v:.0%} ({lo:.0%}-{hi:.0%})" if lo is not None else f"{v:.0%}"
    return f"{v:.0%}" if kind == "%" else f"${v:.4f}" if kind == "$" else str(v)


def comparison_markdown(reports: list[dict]) -> str:
    lines = ["# Extractor comparison", "",
             "Synthetic files. The standard suite shows the system working; the hard suite is built to break it "
             "(defects inside traps, thresholds at their edge, one-digit changes, new injection wordings, Form A "
             "cases the standard suite lacks, and held-out names and places the normaliser was never tuned on). "
             "The blind suite was written by someone who never saw the rules, tables or prompt, and is scored once, "
             "on code frozen before it existed. `oracle` is not a model: it reads the true values from truth.json, "
             "so its column is the ceiling OCR, grounding and the rules put on every model. "
             "Intervals are 95% Wilson intervals: with this few cases, 100% is not a proof.", ""]
    for suite in ("standard", "hard", "blind", "real"):
        group = [r for r in reports if r.get("suite", "standard") == suite]
        for tier in [t for t in ("clean", "scan", "photo", "real") if any(t in r["tiers"] for r in group)]:
            rs = [r for r in group if r["tiers"].get(tier)]
            lines += [f"## {suite} suite, {tier}", "",
                      "| Metric | " + " | ".join(f"`{r['extractor']}`" for r in rs) + " |",
                      "| --- |" + " --- |" * len(rs)]
            for key, label, kind in METRICS:
                lines.append(f"| {label} | " + " | ".join(_fmt(r["tiers"][tier], key, kind) for r in rs) + " |")
            # Reports from before this field existed were all made on macOS (see README).
            lines.append("| Run on | " + " | ".join(r.get("platform", "macOS") for r in rs) + " |")
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
