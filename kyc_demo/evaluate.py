"""Score a pipeline run against truth.json: field accuracy, flag precision/recall, routing accuracy."""

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from .normalise import address_key, name_key, text_key
from .pipeline import run_case

NAME_FIELDS = {"surname", "given_names", "contracting_partner", "beneficial_owner_name", "name"}
ADDRESS_FIELDS = {"beneficial_owner_address", "address"}


def same(field: str, got: str | None, want: str | None) -> bool:
    key = name_key if field in NAME_FIELDS else address_key if field in ADDRESS_FIELDS else text_key
    return got is not None and key(got) == key(want)


def evaluate(cases_dir: Path, extractor, as_of: date) -> dict:
    field_hits = defaultdict(lambda: [0, 0])  # "doc.field" -> [correct, total]
    tp = fp = fn = routed_ok = 0
    per_case = []
    for case in sorted(p for p in cases_dir.iterdir() if (p / "truth.json").exists()):
        truth = json.loads((case / "truth.json").read_text())
        result = run_case(case, extractor, as_of)
        for doc_type, fields in truth["fields"].items():
            got = result["fields"][doc_type] or {}
            for field, want in fields.items():
                ok = same(field, (got.get(field) or {}).get("value"), want)
                field_hits[f"{doc_type}.{field}"][0] += ok
                field_hits[f"{doc_type}.{field}"][1] += 1
        raised = {f["code"] for f in result["flags"]}
        expected = set(truth["expected_flags"])
        tp += len(raised & expected)
        fp += len(raised - expected)
        fn += len(expected - raised)
        want_route = "manual_review" if expected else "pre_filled_review"
        routed_ok += result["decision"] == want_route
        per_case.append({"case": case.name, "defect": truth["defect"], "layouts": truth["layouts"],
                         "decision": result["decision"], "expected": sorted(expected),
                         "raised": sorted(raised), "seconds": result["seconds"]})

    correct = sum(c for c, _ in field_hits.values())
    total = sum(t for _, t in field_hits.values())
    return {
        "extractor": extractor.name,
        "as_of": as_of.isoformat(),
        "cases": len(per_case),
        "field_accuracy": round(correct / total, 3) if total else None,
        "fields": {k: round(c / t, 3) for k, (c, t) in sorted(field_hits.items())},
        "flag_precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "flag_recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "routing_accuracy": round(routed_ok / len(per_case), 3) if per_case else None,
        "per_case": per_case,
    }


def to_markdown(r: dict) -> str:
    lines = [
        f"# Evaluation: {r['extractor']}",
        "",
        f"{r['cases']} synthetic client files, as of {r['as_of']}.",
        "",
        "| Metric | Value |", "| --- | --- |",
        f"| Field accuracy | {r['field_accuracy']:.1%} |",
        f"| Flag precision | {r['flag_precision'] if r['flag_precision'] is None else format(r['flag_precision'], '.1%')} |",
        f"| Flag recall | {r['flag_recall']:.1%} |",
        f"| Routing accuracy | {r['routing_accuracy']:.1%} |",
        "",
        "| Case | Planted defect | Layouts (Form A / bill) | Routed to | Flags raised |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in r["per_case"]:
        lines.append(f"| {c['case']} | {c['defect'] or 'none'} | {c['layouts']['form_a']} / "
                     f"{c['layouts']['proof_of_address']} | {c['decision']} | {', '.join(c['raised']) or '-'} |")
    lines += ["", "| Field | Accuracy |", "| --- | --- |"]
    lines += [f"| {k} | {v:.0%} |" for k, v in r["fields"].items()]
    return "\n".join(lines) + "\n"
