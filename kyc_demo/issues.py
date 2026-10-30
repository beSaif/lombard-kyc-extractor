"""Where on the page each reason for a manual review is: the client-facing view of a finished run.

A flag says what failed ("Passport date of birth = Form A date of birth: '1985-03-12' vs '1985-12-03'").
A reviewer then has to find those values on the documents. This turns every flag into regions: the page and
box of each value the failed check read, taken from the run's own evidence (the box its quote was found in),
plus the signature band and the instruction-like text, which the checks locate themselves.

Built from result.json alone, so it works on any finished run. A value with no box (not extracted, or its
quote not found on the page) still gets a region, without a box: the UI shows the whole page and says so.
"""

import re

from .pipeline import DOC_TYPES

PASSPORT_NAME = ("passport.surname", "passport.given_names")
MRZ = ("passport.mrz_line1", "passport.mrz_line2")
# The values each check compares: the ones a reviewer has to look at when it fails or cannot run.
CHECK_FIELDS = {
    "passport.mrz_format": MRZ,
    "passport.mrz_check_digits": MRZ,
    "passport.not_expired": ("passport.expiry_date",),
    "cross.name_passport_partner": (*PASSPORT_NAME, "form_a.contracting_partner"),
    "cross.name_passport_bill": (*PASSPORT_NAME, "proof_of_address.name"),
    "cross.name_passport_form_a": (*PASSPORT_NAME, "form_a.beneficial_owner_name"),
    "form_a.owner_is_client": ("form_a.contracting_partner", "form_a.beneficial_owner_name"),
    "cross.dob": ("passport.date_of_birth", "form_a.beneficial_owner_date_of_birth"),
    "cross.nationality": ("passport.nationality", "form_a.beneficial_owner_nationality"),
    "cross.address": ("form_a.beneficial_owner_address", "proof_of_address.address"),
    "poa.age": ("proof_of_address.issue_date",),
}
FIELD_LABEL = {
    "surname": "Surname", "given_names": "Given names", "nationality": "Nationality",
    "date_of_birth": "Date of birth", "sex": "Sex", "document_number": "Passport number",
    "expiry_date": "Expiry date", "mrz_line1": "MRZ line 1", "mrz_line2": "MRZ line 2",
    "contracting_partner": "Contracting partner", "beneficial_owner_name": "Beneficial owner",
    "beneficial_owner_date_of_birth": "Beneficial owner's date of birth",
    "beneficial_owner_nationality": "Beneficial owner's nationality",
    "beneficial_owner_address": "Beneficial owner's address", "name": "Name on the bill", "address": "Address",
    "issue_date": "Issue date", "issuer": "Issuer",
}
# Plain words for the client view; the flag code and the check's own message are kept next to them.
TITLE = {
    "PASSPORT_EXPIRED": "The passport has expired",
    "MRZ_CHECK_FAILED": "The passport's machine-readable zone does not add up",
    "MRZ_VISUAL_MISMATCH": "The machine-readable zone disagrees with the printed page",
    "NAME_MISMATCH": "A name does not match the passport",
    "ADDRESS_MISMATCH": "The addresses do not match",
    "DOB_MISMATCH": "The dates of birth do not match",
    "NATIONALITY_MISMATCH": "The nationalities do not match",
    "PROOF_OF_ADDRESS_TOO_OLD": "The proof of address is too old",
    "IMPLAUSIBLE_DATE": "The proof of address is dated in the future",
    "SUSPICIOUS_INSTRUCTIONS": "The document contains text addressed to an AI system",
    "THIRD_PARTY_OWNER": "Someone else is named as beneficial owner",
    "FORM_A_UNSIGNED": "Form A is not signed",
    "EVIDENCE_NOT_FOUND": "Values to check by eye",
    "EVIDENCE_OUT_OF_PLACE": "Values read from the wrong part of the page",
    "MISSING_FIELD": "A required value could not be read",
    "MISSING_DOCUMENT": "A document is missing",
    "MODEL_DISAGREEMENT": "Two models read different values",
    "CHECK_SKIPPED": "A check could not run",
}


def _pages(steps: list[dict]) -> dict[str, list[dict]]:
    """Each document's page images, as the pipeline read them (the boxes are fractions of these)."""
    out: dict[str, dict[int, str]] = {}
    for s in steps:
        if s.get("kind") == "read" and s.get("doc") and s["data"].get("image"):
            out.setdefault(s["doc"], {})[s["data"].get("page", 1)] = s["data"]["image"]
    return {doc: [{"page": n, "image": img} for n, img in sorted(pages.items())] for doc, pages in out.items()}


def _field_region(result: dict, key: str, note: str | None = None) -> dict:
    doc, field = key.split(".", 1)
    ev = (result.get("evidence") or {}).get(doc, {}).get(field)
    fv = ((result.get("fields") or {}).get(doc) or {}).get(field) or {}
    region = {"doc": doc, "field": field, "label": FIELD_LABEL.get(field, field), "page": fv.get("page") or 1,
              "bbox": None, "value": fv.get("value"), "status": None, "note": note, "exact": False}
    if ev:
        region.update(page=ev.get("page") or region["page"], status=ev["status"], value=ev.get("value"),
                      note=note or ev.get("why"))
        if ev.get("bbox"):
            # A quote that was not found still has the closest window OCR had: show it, marked as a guess.
            region.update(bbox=ev["bbox"], exact=ev.get("method") != "not_found")
            if not region["exact"]:
                region["note"] = (note or "") + ("; " if note else "") + "the box is only the closest text on the page"
    elif region["value"] is None:
        region["note"] = note or "not read from the document"
    return region


def _named_fields(detail: str, known) -> list[str]:
    """'disagree on: date_of_birth, surname' -> ['date_of_birth', 'surname'], keeping only real field names."""
    body = detail.split(":", 1)[1] if ":" in detail else ""
    return [f for f in (x.strip() for x in body.split(",")) if f in known]


def _regions(result: dict, check: dict) -> list[dict]:
    name, inputs = check["name"], check.get("inputs") or {}
    doc = name.split(".", 1)[0]
    if name.endswith(".present"):
        return []
    if name == "form_a.signed":
        if inputs.get("bbox"):
            return [{"doc": "form_a", "field": None, "label": "Signature", "page": inputs.get("page", 1),
                     "bbox": inputs["bbox"], "value": None, "status": None, "exact": True,
                     "note": f"the band above '{inputs.get('label')}' where the signature goes"}]
        return [{"doc": "form_a", "field": None, "label": "Signature", "page": 1, "bbox": None, "value": None,
                 "status": None, "exact": False, "note": "the signature line was not found"}]
    if name.endswith(".injection"):
        where = inputs.get("where")
        text = inputs.get("regex_match") or inputs.get("model_report")
        return [{"doc": doc, "field": None, "label": "Instruction-like text", "page": (where or {}).get("page") or 1,
                 "bbox": (where or {}).get("bbox"), "value": text, "status": None, "exact": bool(where),
                 "note": None if where else "the text was not found in the OCR words"}]
    if name.endswith((".evidence", ".evidence_place")):
        wanted = {"out_of_place"} if name.endswith("_place") else {"unverified", "dropped"}
        evidence = (result.get("evidence") or {}).get(doc, {})
        return [_field_region(result, f"{doc}.{f}") for f, e in evidence.items() if e["status"] in wanted]
    if name.endswith(".required"):
        values = (result.get("fields") or {}).get(doc) or {}
        return [_field_region(result, f"{doc}.{f}", "not read from the document")
                for f in inputs.get("required", []) if (values.get(f) or {}).get("value") is None]
    if name.endswith(".cross_model"):
        return [_field_region(result, f"{doc}.{f}", f"first model {row['primary']!r}, second {row['second']!r}")
                for f, row in (inputs.get("fields") or {}).items() if not row.get("agree")]
    if name == "passport.mrz_vs_visual":
        diffs = _named_fields(check["detail"], FIELD_LABEL)
        printed, mrz = inputs.get("printed") or {}, inputs.get("mrz") or {}
        return [_field_region(result, f"passport.{f}", f"printed {printed.get(f)!r}, MRZ says {mrz.get(f)!r}")
                for f in diffs] + [_field_region(result, k) for k in MRZ]
    return [_field_region(result, k) for k in CHECK_FIELDS.get(name, ())]


def _merge(regions: list[dict]) -> list[dict]:
    """One crop per box: both MRZ lines are the same zone, and the same quote can stand for two fields."""
    out: list[dict] = []
    for r in regions:
        where = (r["doc"], r["page"], r["bbox"])
        same = next((o for o in out if r["bbox"] and (o["doc"], o["page"], o["bbox"]) == where), None)
        if same is None:
            out.append(dict(r))
            continue
        same["label"] += f" + {r['label']}"
        same["value"] = " / ".join(v for v in (same["value"], r["value"]) if v) or None
        if r["note"] and r["note"] != same["note"]:
            same["note"] = "; ".join(n for n in (same["note"], r["note"]) if n)
    return out


def locate_issues(result: dict) -> dict:
    """Every flag of a run with the regions to look at, and each document's pages to show them on."""
    checks = {c["name"]: c for c in result.get("checks", [])}
    issues = []
    for i, flag in enumerate(result.get("flags", [])):
        check = checks.get(flag["check"], {"name": flag["check"], "detail": "", "inputs": {}})
        regions = _merge([r for r in _regions(result, check) if r["doc"] in DOC_TYPES])
        issues.append({"id": i, "code": flag["code"], "severity": flag["severity"], "check": flag["check"],
                       "title": TITLE.get(flag["code"], flag["code"]), "message": flag["message"],
                       "missing_doc": check["name"].split(".")[0] if check["name"].endswith(".present") else None,
                       "regions": regions})
    return {"run_id": result.get("run_id"), "decision": result.get("decision"), "issues": issues,
            "pages": _pages(result.get("steps", []))}
