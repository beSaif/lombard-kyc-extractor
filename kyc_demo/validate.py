"""Deterministic checks on extracted data. The model proposes; these rules decide what a human must look at.

Every check is recorded, passed or failed, with the inputs it compared, so a reviewer (or the UI) can see
why a file was routed the way it was. A failed check raises its flag code, and so does a skipped one
(CHECK_SKIPPED): a check that could not run has not passed, so it must never let a file through.
"""

import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from pydantic import BaseModel
from rapidfuzz import fuzz

from .anchor import place
from .ground import FUZZY_MIN, MRZ_ZONE, Match, locate, locate_all, locate_in_mrz
from .mrz import parse_td3, transliterate
from .normalise import (ADDRESS_FIELDS, address_key, country_code, find_date, names_match, parse_date,
                        person_matches, strip_accents, text_key)
from .read import Document
from .signature import MIN_INK, signature_band
from .schemas import FieldValue

REQUIRED = {
    "passport": ["surname", "given_names", "nationality", "date_of_birth", "document_number",
                 "expiry_date", "mrz_line1", "mrz_line2"],
    "form_a": ["contracting_partner", "beneficial_owner_name", "beneficial_owner_date_of_birth",
               "beneficial_owner_nationality", "beneficial_owner_address"],
    "proof_of_address": ["name", "address", "issue_date"],
}
DATE_FIELDS = {"date_of_birth", "expiry_date", "beneficial_owner_date_of_birth", "issue_date"}
COUNTRY_FIELDS = {"nationality", "beneficial_owner_nationality"}
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

def quote_says(name: str, value: str, quote: str | None) -> str | None:
    """Does the quote say the value? 'yes', 'close', 'no', or None when the text alone cannot tell.

    Finding the quote on the page proves only that the quote is there. Without this, a value of
    'Hans Muster' next to a real quote 'Anna Müller' would count as verified.

    'close' is OCR noise: shown the OCR text, models often copy its errors into the quote ('Cuca
    Bernasconi') while reading the right value off the image ('Luca'). Every letter-word of the value
    is then within one or two characters of a word in the quote, and the numbers are identical.
    """
    if not quote or name.startswith("mrz_line"):  # MRZ lines are chosen by check digits, see reconcile
        return None
    if name in DATE_FIELDS:
        d = find_date(quote, birth="birth" in name)
        return None if d is None else "yes" if d.isoformat() == value else "no"
    if name in COUNTRY_FIELDS:
        code = country_code(quote)
        return None if code is None else "yes" if code == value else "no"
    key = address_key if name in ADDRESS_FIELDS else text_key
    if text_key(value).replace(" ", "") == text_key(quote).replace(" ", ""):
        return "yes"  # 'R 00000' says 'R00000': passport numbers are printed in groups
    want, got = key(value).split(), set(key(quote).split())
    missing = [t for t in want if t not in got]
    if not missing:
        return "yes"
    if any(t.isdigit() for t in missing):  # '51' is not '57', whatever the letters around it say
        return "no"
    near = lambda t: any(fuzz.ratio(t, g) >= 75 for g in got if not g.isdigit())
    return "close" if all(near(t) for t in missing) else "no"


def mrz_line2_valid(data: BaseModel) -> bool:
    try:
        return all(parse_td3(_v(data, "mrz_line1") or "", _v(data, "mrz_line2") or "")["checks"].values())
    except ValueError:
        return False


def ground_fields(doc_type: str, data: BaseModel, doc: Document) -> dict:
    """Give each value an evidence status, and say what the evidence rests on (its basis):

    verified      the quote says the value, and the quote was found on the page
    unverified    the quote was not found (e.g. handwriting OCR could not read), or it is only close to the
                  value (see quote_says). Kept, but a human must check it unless another document
                  corroborates it (see corroborate)
    dropped       the quote does not say the value (another date, another name): the value is removed
    out_of_place  the quote is on the page but not where this field is printed: in fine print, or under the
                  label of something we do not extract, such as a remarks box or a due date (see anchor.py).
                  Kept, a human must check it, and no other document can vouch for it: a planted decoy is
                  made to agree with them. Found only under another extracted field's label, it is unverified

    basis         text_layer: the PDF's own text, exact
                  ocr: Tesseract read the same thing. In 'text' and 'both' mode the model was shown that
                       OCR text, so this is agreement with OCR, not an independent second reading
                  checksum: the MRZ's ICAO check digits pass, which neither OCR nor the model can fake
    """
    evidence = {}
    sources = {p.number: p.source for p in doc.pages}
    pages = {p.number: p for p in doc.pages}
    for name in type(data).model_fields:
        fv: FieldValue = getattr(data, name)
        if fv.value is None:
            continue
        if name == "mrz_line2" and mrz_line2_valid(data):
            evidence[name] = {**Match("checksum", 100.0, fv.page, MRZ_ZONE, fv.value).to_dict(),
                              "status": "verified", "basis": "checksum", "value": fv.value}
            continue
        m = locate(fv.quote, doc.pages)
        if m.method == "not_found" and doc_type == "passport":
            m = locate_in_mrz(name, fv.value, doc.pages) or m
        basis = None if m.method == "not_found" else "checksum" if m.matched_text and m.matched_text.startswith(
            "MRZ line") else sources.get(m.page, "ocr")
        ev = {**m.to_dict(), "status": "verified" if basis else "unverified", "basis": basis, "value": fv.value}
        says = quote_says(name, fv.value, fv.quote)
        where = (place(doc_type, name, m.bbox, pages[m.page]) if m.method in {"exact", "fuzzy"} and m.page in pages
                 else None)
        if where is not None and where.misplaced:  # out of place only if every place that prints it is wrong
            for alt in locate_all(fv.quote, doc.pages):
                alt_where = place(doc_type, name, alt.bbox, pages[alt.page])
                if not alt_where.misplaced:
                    m, where = alt, alt_where
                    ev.update(m.to_dict())
                    break
        if where is not None:
            ev["place"] = where.to_dict()
        if says == "no":
            ev["status"], ev["why"] = "dropped", f"the quote {fv.quote!r} does not say {fv.value!r}"
            fv.value = None
        elif where is not None and where.misplaced:
            ev["status"], ev["basis"] = "out_of_place", None
            ev["why"] = (f"the quote is in fine print ({where.height_ratio:.0%} of the page's body text height)"
                         if where.verdict == "fine_print" else
                         f"the quote sits under or beside {where.label!r}, which is not this field")
        elif where is not None and where.verdict == "other_field":
            ev["status"], ev["basis"] = "unverified", None
            ev["why"] = f"the quote was only found under {where.label!r}, the label of {where.label_field}"
        elif says == "close":
            ev["status"], ev["basis"] = "unverified", None
            ev["why"] = f"the quote {fv.quote!r} is close to {fv.value!r} but does not say it (OCR noise or a misreading)"
        elif m.method == "not_found":
            ev["why"] = f"best match on the page scored {m.score} (< {FUZZY_MIN}, or other digits)"
        evidence[name] = ev
    return evidence


# Which passing check lets a verified value vouch for an unverified one: (supporting side, supported side).
PASSPORT_NAME = [("passport", "surname"), ("passport", "given_names")]
CORROBORATION = {
    "passport.mrz_vs_visual": ([("passport", "mrz_line1"), ("passport", "mrz_line2")],
                               [("passport", f) for f in ("document_number", "date_of_birth", "expiry_date",
                                                          "surname", "sex", "nationality")]),
    "cross.name_passport_partner": (PASSPORT_NAME, [("form_a", "contracting_partner")]),
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
    An out-of-place value is never corroborated: a decoy in a footnote is planted to agree with the other
    documents, so their agreement is no evidence for it.
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
                          for s in ("verified", "corroborated", "unverified", "dropped", "out_of_place")}))
        misplaced = [f"{f} ({e['why']})" for f, e in fields.items() if e["status"] == "out_of_place"]
        out.append(Check(f"{doc_type}.evidence_place", "Every value is printed where its field is", not misplaced,
                         "no value comes from fine print or another field's label" if not misplaced
                         else "check by eye: " + "; ".join(misplaced), "EVIDENCE_OUT_OF_PLACE", "high",
                         {"place": {f: e["place"]["verdict"] for f, e in fields.items() if e.get("place")}}))
    return log, out


def check_required(doc_type: str, data: BaseModel | None) -> list[Check]:
    if data is None:
        return [Check(f"{doc_type}.present", f"{doc_type} was provided", False, "document missing",
                      "MISSING_DOCUMENT")]
    missing = [f for f in REQUIRED[doc_type] if _v(data, f) is None]
    return [Check(f"{doc_type}.required", "All required fields were extracted", not missing,
                  "missing: " + ", ".join(missing) if missing else "all present", "MISSING_FIELD", "medium",
                  {"required": REQUIRED[doc_type]})]


def check_injection(doc_type: str, doc: Document, model_reports: list[FieldValue | None]) -> list[Check]:
    """Independent detectors: a multilingual regex over the OCR text, and each model that read the document."""
    hit = None
    for page in doc.texts:
        m = INJECTION_PATTERNS.search(" ".join(page.split()))
        if m:
            hit = m.group(0)
            break
    # The model as a detector must be validated per model: Qwen 2.5-VL 7B reports every legal warning.
    use_model = os.getenv("KYC_MODEL_INJECTION_DETECTOR", "on") != "off"
    quotes = [r.quote or r.value for r in model_reports if r and use_model and (r.quote or r.value)]
    model_quote, model_hit, grounded = (quotes[0] if quotes else None), None, False
    for quote in quotes:
        grounded = locate(quote, doc.pages).method != "not_found"
        # Faint print can be readable to a vision model and lost to OCR. An ungrounded report still counts when
        # the quote itself reads as an instruction: a false alarm costs a manual review, a miss lets it through.
        if grounded or INJECTION_PATTERNS.search(quote):
            model_quote = model_hit = quote
            break
    passed = not hit and not model_hit
    found = None if passed else locate(hit or model_hit, doc.pages)  # where it is, for the reviewer to see
    where = {"page": found.page, "bbox": found.bbox} if found and found.method != "not_found" else None
    detail = "no instruction-like text" if passed else "; ".join(
        x for x in [f"regex matched {hit!r}" if hit else "",
                    f"model reported {model_hit!r}" + ("" if grounded else " (not in the OCR text)") if model_hit
                    else ""] if x)
    return [Check(f"{doc_type}.injection", "No text addressed to an AI system", passed, detail,
                  "SUSPICIOUS_INSTRUCTIONS", "high",
                  {"regex_match": hit, "model_report": model_quote, "model_report_grounded": grounded,
                   "where": where})]


def check_signature(doc: Document) -> list[Check]:
    band = signature_band(doc)
    if band is None:
        return [Check("form_a.signed", "Form A is signed", None, "skipped: the signature line was not found",
                      "FORM_A_UNSIGNED")]
    signed = band["ink"] >= MIN_INK
    return [Check("form_a.signed", "Form A is signed", signed,
                  f"ink covers {band['ink']:.2%} of the signature band (signed from {MIN_INK:.2%})"
                  if signed else f"nothing written above '{band['label']}' ({band['ink']:.2%} ink)",
                  "FORM_A_UNSIGNED", inputs=band)]


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
    """The passport identifies the contracting partner (the account holder). Form A names the beneficial
    owner. Only when they are the same person can the Form A person be checked against the passport."""
    checks = []
    surname, given = _v(p, "surname"), _v(p, "given_names")
    passport_name = f"{given or ''} {surname or ''}".strip() or None
    is_holder = lambda _, other: person_matches(surname, given, other)
    name_rule = "surname and first given name present, nothing that is not on the passport; any order"

    def compare(name, label, flag, a, b, same, how):
        if not (a and b):
            checks.append(Check(name, label, None, "skipped: a value is missing", flag, inputs={"a": a, "b": b}))
            return
        ok = same(a, b)
        checks.append(Check(name, label, ok, f"match ({how})" if ok else f"{a!r} vs {b!r}", flag,
                            inputs={"a": a, "b": b, "rule": how}))

    partner, owner = _v(fa, "contracting_partner"), _v(fa, "beneficial_owner_name")
    compare("cross.name_passport_partner", "Passport name = Form A contracting partner", "NAME_MISMATCH",
            passport_name, partner, is_holder, name_rule)
    compare("cross.name_passport_bill", "Passport name = name on proof of address", "NAME_MISMATCH",
            passport_name, _v(poa, "name"), is_holder, name_rule)
    # Neither the passport holder nor the contracting partner, nor a misspelling of either ('Maximillian'):
    # those are checked in full, and the name checks flag the difference.
    same_person = lambda a, b: names_match(a, b) or fuzz.token_sort_ratio(text_key(a), text_key(b)) >= 85
    third_party = bool(partner and owner and not person_matches(surname, given, owner)
                       and not same_person(partner, owner) and not same_person(passport_name, owner))
    if fa is not None and partner and owner:
        checks.append(Check("form_a.owner_is_client", "The beneficial owner is the client", not third_party,
                            "the beneficial owner is the passport holder or the contracting partner"
                            if not third_party else
                            f"Form A names {owner!r} as beneficial owner of {partner!r}'s assets: that person "
                            "must be identified on their own, and the Form A details cannot be checked against "
                            "this passport", "THIRD_PARTY_OWNER", "medium", {"partner": partner, "owner": owner}))
    if not third_party:
        compare("cross.name_passport_form_a", "Passport name = Form A beneficial owner", "NAME_MISMATCH",
                passport_name, owner, is_holder, name_rule)
        compare("cross.dob", "Passport date of birth = Form A date of birth", "DOB_MISMATCH",
                _v(p, "date_of_birth"), _v(fa, "beneficial_owner_date_of_birth"), lambda a, b: a == b,
                "same ISO date")
        compare("cross.nationality", "Passport nationality = Form A nationality", "NATIONALITY_MISMATCH",
                _v(p, "nationality"), _v(fa, "beneficial_owner_nationality"), lambda a, b: a == b, "same ISO code")
        compare("cross.address", "Form A address = proof of address", "ADDRESS_MISMATCH",
                _v(fa, "beneficial_owner_address"), _v(poa, "address"),
                lambda a, b: address_key(a) == address_key(b),
                "same tokens after expanding abbreviations, city aliases, dropping a trailing country and CH-")
    raw = _v(poa, "issue_date")
    issued = parse_date(raw)
    label = f"Proof of address at most {MAX_PROOF_AGE_DAYS} days old"
    if issued:
        age = (as_of - issued).days
        inputs = {"issue_date": issued.isoformat(), "as_of": as_of.isoformat(), "max_days": MAX_PROOF_AGE_DAYS}
        if age < 0:
            checks.append(Check("poa.age", label, False, f"dated {issued.isoformat()}, {-age} days after the review",
                                "IMPLAUSIBLE_DATE", "high", inputs))
        else:
            checks.append(Check("poa.age", label, age <= MAX_PROOF_AGE_DAYS,
                                f"issued {issued.isoformat()}, {age} days before review",
                                "PROOF_OF_ADDRESS_TOO_OLD", "medium", inputs))
    else:
        checks.append(Check("poa.age", label, None,
                            f"skipped: issue date {raw!r} could not be read" if raw else "skipped: no issue date",
                            "PROOF_OF_ADDRESS_TOO_OLD", "medium"))
    return checks


def flags_from(checks: list[Check]) -> list[dict]:
    """Failed checks raise their own flag; skipped ones raise CHECK_SKIPPED. Either way a human looks."""
    flags = []
    for c in checks:
        if c.passed is False and c.flag:
            flags.append({"code": c.flag, "severity": c.severity, "message": f"{c.label}: {c.detail}", "check": c.name})
        elif c.passed is None:
            flags.append({"code": "CHECK_SKIPPED", "severity": "medium", "message": f"{c.label}: {c.detail}",
                          "check": c.name})
    return flags
