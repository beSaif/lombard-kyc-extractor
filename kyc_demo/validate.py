"""Deterministic checks on extracted data. The model proposes; these rules decide what a human must look at.

Every check is recorded, passed or failed, with the inputs it compared, so a reviewer (or the UI) can see
why a file was routed the way it was. A failed check raises its flag code.
"""

import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from pydantic import BaseModel

from .ground import locate, locate_in_mrz
from .mrz import parse_td3, transliterate
from .normalise import address_key, names_match, parse_date, strip_accents, text_key
from .read import Document
from .schemas import FieldValue

REQUIRED = {
    "passport": ["surname", "given_names", "nationality", "date_of_birth", "document_number",
                 "expiry_date", "mrz_line1", "mrz_line2"],
    "form_a": ["beneficial_owner_name", "beneficial_owner_date_of_birth",
               "beneficial_owner_nationality", "beneficial_owner_address"],
    "proof_of_address": ["name", "address", "issue_date"],
}
DATE_FIELDS = {"date_of_birth", "expiry_date", "beneficial_owner_date_of_birth", "issue_date"}
MAX_PROOF_AGE_DAYS = 90  # assumed bank policy: proof of address under three months old
INJECTION_PATTERNS = re.compile("|".join([
    r"ignor\w*\s+(?:\w+\s+){0,3}(?:instructions|anweisungen|istruzioni)",
    r"(?:mark|marquez|markiere)\s+(?:this|the|ce|diesen)\s+(?:client|kunden)",
    r"(?:automated|automatisierte|automatis[ée]s)\s+(?:systems?|systeme|syst[èe]mes)",
    r"\bAI\s+(?:reviewer|system|model)",
    r"set all checks to passed|already approved by compliance|system prompt",
]), re.IGNORECASE)


@dataclass
class Check:
    name: str                  # e.g. "passport.mrz_check_digits"
    label: str                 # what was checked, in words
    passed: bool | None        # None: skipped because an input is missing
    detail: str
    flag: str | None = None    # code raised when it fails
    severity: str = "high"
    inputs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _v(data: BaseModel | None, name: str) -> str | None:
    return getattr(data, name).value if data is not None else None


# --- per document ------------------------------------------------------------------------------

def ground_fields(doc_type: str, data: BaseModel, doc: Document) -> dict:
    """Locate every quote on the page and give each value an evidence status:

    verified      the quote was found in the OCR words (exact or fuzzy) or in the MRZ pass
    unverified    not found, e.g. handwriting OCR could not read. Kept, but a human must check it
                  unless another document corroborates it (see corroborate)
    dropped       the quote contradicts the value (says another date): the model is inconsistent
    """
    evidence = {}
    for name in type(data).model_fields:
        fv: FieldValue = getattr(data, name)
        if fv.value is None:
            continue
        m = locate(fv.quote, doc.pages)
        if m.method == "not_found" and doc_type == "passport":
            m = locate_in_mrz(name, fv.value, doc.pages) or m
        ev = {**m.to_dict(), "status": "verified" if m.method != "not_found" else "unverified", "value": fv.value}
        if name in DATE_FIELDS and parse_date(fv.quote) and parse_date(fv.quote).isoformat() != fv.value:
            ev["status"], ev["why"] = "dropped", f"quote {fv.quote!r} does not say {fv.value}"
            fv.value = None
        elif m.method == "not_found":
            ev["why"] = f"best match on the page scored {m.score} (< 85)"
        evidence[name] = ev
    return evidence


# Which passing check lets a verified value vouch for an unverified one: (supporting side, supported side).
PASSPORT_NAME = [("passport", "surname"), ("passport", "given_names")]
CORROBORATION = {
    "passport.mrz_vs_visual": ([("passport", "mrz_line1"), ("passport", "mrz_line2")],
                               [("passport", f) for f in ("document_number", "date_of_birth", "expiry_date",
                                                          "surname", "sex", "nationality")]),
    "cross.name_passport_form_a": (PASSPORT_NAME, [("form_a", "beneficial_owner_name")]),
    "cross.name_passport_bill": (PASSPORT_NAME, [("proof_of_address", "name")]),
    "cross.dob": ([("passport", "date_of_birth")], [("form_a", "beneficial_owner_date_of_birth")]),
    "cross.nationality": ([("passport", "nationality")], [("form_a", "beneficial_owner_nationality")]),
    "cross.address": ([("form_a", "beneficial_owner_address")], [("proof_of_address", "address")]),
}


def corroborate(evidence: dict, checks: list[Check]) -> tuple[list[dict], list[Check]]:
    """An unverified value that a passing cross-check ties to a verified value counts as corroborated.

    Safe because each document is extracted on its own: the model cannot copy a value from the passport
    into the Form A. Runs until nothing changes, so MRZ -> passport date of birth -> Form A date of birth chains.
    """
    passed = {c.name for c in checks if c.passed}
    trusted = lambda d, f: evidence.get(d, {}).get(f, {}).get("status") in {"verified", "corroborated"}
    log, changed = [], True
    while changed:
        changed = False
        for check, (support, supported) in CORROBORATION.items():
            if check not in passed:
                continue
            for a, b in ((support, supported), (supported, support)):
                if not all(trusted(d, f) for d, f in a):
                    continue
                for d, f in b:
                    ev = evidence.get(d, {}).get(f)
                    if ev and ev["status"] == "unverified":
                        ev["status"], ev["corroborated_by"] = "corroborated", check
                        log.append({"field": f"{d}.{f}", "by": check, "value": ev["value"]})
                        changed = True
    out = []
    for doc_type, fields in evidence.items():
        unverified = [f for f, e in fields.items() if e["status"] == "unverified"]
        dropped = [f for f, e in fields.items() if e["status"] == "dropped"]
        bad = [f"{f} (not found on the page)" for f in unverified] + [f"{f} ({fields[f]['why']})" for f in dropped]
        out.append(Check(f"{doc_type}.evidence", "Every value is found on the page or corroborated", not bad,
                         "all values verified or corroborated" if not bad else "check by eye: " + "; ".join(bad),
                         "EVIDENCE_NOT_FOUND", "medium",
                         {s: sum(e["status"] == s for e in fields.values())
                          for s in ("verified", "corroborated", "unverified", "dropped")}))
    return log, out


def check_required(doc_type: str, data: BaseModel | None) -> list[Check]:
    if data is None:
        return [Check(f"{doc_type}.present", f"{doc_type} was provided", False, "document missing",
                      "MISSING_DOCUMENT")]
    missing = [f for f in REQUIRED[doc_type] if _v(data, f) is None]
    return [Check(f"{doc_type}.required", "All required fields were extracted", not missing,
                  "missing: " + ", ".join(missing) if missing else "all present", "MISSING_FIELD", "medium",
                  {"required": REQUIRED[doc_type]})]


def check_injection(doc_type: str, doc: Document, model_report: FieldValue | None) -> list[Check]:
    """Two independent detectors: a multilingual regex over the OCR text, and the model itself."""
    hit = None
    for page in doc.texts:
        m = INJECTION_PATTERNS.search(" ".join(page.split()))
        if m:
            hit = m.group(0)
            break
    # The model as a detector must be validated per model: Qwen 2.5-VL 7B reports every legal warning.
    use_model = os.getenv("KYC_MODEL_INJECTION_DETECTOR", "on") != "off"
    model_quote = (model_report.quote or model_report.value) if model_report and use_model else None
    model_hit, grounded = None, False
    if model_quote:
        grounded = locate(model_quote, doc.pages).method != "not_found"
        # Faint print can be readable to a vision model and lost to OCR. An ungrounded report still counts when
        # the quote itself reads as an instruction: a false alarm costs a manual review, a miss lets it through.
        if grounded or INJECTION_PATTERNS.search(model_quote):
            model_hit = model_quote
    passed = not hit and not model_hit
    detail = "no instruction-like text" if passed else "; ".join(
        x for x in [f"regex matched {hit!r}" if hit else "",
                    f"model reported {model_hit!r}" + ("" if grounded else " (not in the OCR text)") if model_hit
                    else ""] if x)
    return [Check(f"{doc_type}.injection", "No text addressed to an AI system", passed, detail,
                  "SUSPICIOUS_INSTRUCTIONS", "high",
                  {"regex_match": hit, "model_report": model_quote, "model_report_grounded": grounded})]


# --- passport ----------------------------------------------------------------------------------

def surname_matches_mrz(visual: str, mrz_surname: str) -> bool:
    """ICAO allows Ü -> UE or U, and OCR often drops the umlaut, so accept either transliteration."""
    mrz = text_key(mrz_surname).replace(" ", "")
    options = {text_key(transliterate(visual).replace("<", " ")).replace(" ", ""),
               text_key(strip_accents(visual)).replace(" ", "")}
    return mrz in options or mrz.replace("ue", "u").replace("oe", "o").replace("ae", "a") in options


def check_passport(p: BaseModel | None, as_of: date) -> list[Check]:
    if p is None:
        return []
    checks = []
    l1, l2 = _v(p, "mrz_line1"), _v(p, "mrz_line2")
    mrz = None
    if l1 and l2:
        try:
            mrz = parse_td3(l1, l2, today=as_of)
        except ValueError as e:
            checks.append(Check("passport.mrz_format", "MRZ has two 44-character lines", False, str(e),
                                "MRZ_CHECK_FAILED", inputs={"line1": l1, "line2": l2}))
    if mrz:
        failed = [k for k, ok in mrz["checks"].items() if not ok]
        checks.append(Check("passport.mrz_check_digits", "MRZ check digits (ICAO 9303, weights 7-3-1)",
                            not failed, "all 5 check digits valid" if not failed else f"failed: {', '.join(failed)}",
                            "MRZ_CHECK_FAILED", inputs={"line1": l1, "line2": l2, "checks": mrz["checks"]}))
        visual = {"document_number": _v(p, "document_number"), "date_of_birth": _v(p, "date_of_birth"),
                  "expiry_date": _v(p, "expiry_date"), "sex": _v(p, "sex"), "nationality": _v(p, "nationality")}
        diffs = [k for k, v in visual.items() if v and text_key(v) != text_key(mrz[k])]
        if _v(p, "surname") and not surname_matches_mrz(_v(p, "surname"), mrz["surname"]):
            diffs.append("surname")
        checks.append(Check("passport.mrz_vs_visual", "MRZ agrees with the printed data page", not diffs,
                            "MRZ and printed page agree" if not diffs else f"disagree on: {', '.join(diffs)}",
                            "MRZ_VISUAL_MISMATCH",
                            inputs={"printed": {**visual, "surname": _v(p, "surname")},
                                    "mrz": {k: mrz[k] for k in (*visual, "surname")}}))
    elif not (l1 and l2):
        checks.append(Check("passport.mrz_check_digits", "MRZ check digits (ICAO 9303, weights 7-3-1)", None,
                            "skipped: MRZ not extracted"))
    expiry = parse_date(_v(p, "expiry_date")) or (parse_date(mrz["expiry_date"]) if mrz else None)
    if expiry:
        days = (expiry - as_of).days
        checks.append(Check("passport.not_expired", "Passport valid on the review date", days >= 0,
                            f"expires {expiry.isoformat()} ({days} days from {as_of.isoformat()})"
                            if days >= 0 else f"expired {-days} days ago, on {expiry.isoformat()}",
                            "PASSPORT_EXPIRED", inputs={"expiry_date": expiry.isoformat(), "as_of": as_of.isoformat()}))
    else:
        checks.append(Check("passport.not_expired", "Passport valid on the review date", None,
                            "skipped: no expiry date"))
    return checks


# --- across documents ------------------------------------------------------------------------------

def check_cross_document(p, fa, poa, as_of: date) -> list[Check]:
    checks = []
    passport_name = f"{_v(p, 'given_names') or ''} {_v(p, 'surname') or ''}".strip() or None

    def compare(name, label, flag, a, b, same, how):
        if not (a and b):
            checks.append(Check(name, label, None, "skipped: a value is missing", flag, inputs={"a": a, "b": b}))
            return
        ok = same(a, b)
        checks.append(Check(name, label, ok, f"match ({how})" if ok else f"{a!r} vs {b!r}", flag,
                            inputs={"a": a, "b": b, "rule": how}))

    compare("cross.name_passport_form_a", "Passport name = Form A beneficial owner", "NAME_MISMATCH",
            passport_name, _v(fa, "beneficial_owner_name"), names_match,
            "same name tokens in any order; a missing middle name is allowed")
    compare("cross.name_passport_bill", "Passport name = name on proof of address", "NAME_MISMATCH",
            passport_name, _v(poa, "name"), names_match,
            "same name tokens in any order; a missing middle name is allowed")
    compare("cross.dob", "Passport date of birth = Form A date of birth", "DOB_MISMATCH",
            _v(p, "date_of_birth"), _v(fa, "beneficial_owner_date_of_birth"), lambda a, b: a == b, "same ISO date")
    compare("cross.nationality", "Passport nationality = Form A nationality", "NATIONALITY_MISMATCH",
            _v(p, "nationality"), _v(fa, "beneficial_owner_nationality"), lambda a, b: a == b, "same ISO code")
    compare("cross.address", "Form A address = proof of address", "ADDRESS_MISMATCH",
            _v(fa, "beneficial_owner_address"), _v(poa, "address"),
            lambda a, b: address_key(a) == address_key(b),
            "same tokens after expanding abbreviations, city aliases, dropping country and CH-")
    issued = parse_date(_v(poa, "issue_date"))
    if issued:
        age = (as_of - issued).days
        checks.append(Check("poa.age", f"Proof of address at most {MAX_PROOF_AGE_DAYS} days old",
                            age <= MAX_PROOF_AGE_DAYS, f"issued {issued.isoformat()}, {age} days before review",
                            "PROOF_OF_ADDRESS_TOO_OLD", "medium",
                            {"issue_date": issued.isoformat(), "as_of": as_of.isoformat(), "max_days": MAX_PROOF_AGE_DAYS}))
    else:
        checks.append(Check("poa.age", f"Proof of address at most {MAX_PROOF_AGE_DAYS} days old", None,
                            "skipped: no issue date", "PROOF_OF_ADDRESS_TOO_OLD", "medium"))
    return checks


def flags_from(checks: list[Check]) -> list[dict]:
    return [{"code": c.flag, "severity": c.severity, "message": f"{c.label}: {c.detail}", "check": c.name}
            for c in checks if c.passed is False and c.flag]
