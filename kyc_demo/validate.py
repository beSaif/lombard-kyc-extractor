"""Deterministic checks on extracted data. The model proposes; these rules decide what a human must look at."""

import re
from dataclasses import asdict, dataclass
from datetime import date

from pydantic import BaseModel

from .mrz import parse_td3, transliterate
from .normalise import address_key, name_key, parse_date, text_key

REQUIRED = {
    "passport": ["surname", "given_names", "nationality", "date_of_birth", "document_number",
                 "expiry_date", "mrz_line1", "mrz_line2"],
    "form_a": ["beneficial_owner_name", "beneficial_owner_date_of_birth",
               "beneficial_owner_nationality", "beneficial_owner_address"],
    "proof_of_address": ["name", "address", "issue_date"],
}
MAX_PROOF_AGE_DAYS = 90  # assumed bank policy: proof of address under three months old
INJECTION_PATTERNS = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions|mark (this|the) client as|system prompt",
    re.IGNORECASE)


@dataclass
class Flag:
    code: str
    severity: str  # high | medium
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _v(data: BaseModel | None, field: str) -> str | None:
    return getattr(data, field).value if data is not None else None


def enforce_evidence(doc_type: str, data: BaseModel, pages: list[str]) -> list[Flag]:
    """Drop any value whose quote is not literally in the document. This is what stops hallucinations."""
    flags = []
    page_keys = [" ".join(p.split()).casefold() for p in pages]
    for name in type(data).model_fields:
        fv = getattr(data, name)
        if fv.value is None:
            continue
        quote = " ".join((fv.quote or "").split()).casefold()
        if not quote or not any(quote in pk for pk in page_keys):
            flags.append(Flag("EVIDENCE_NOT_FOUND", "medium",
                              f"{doc_type}.{name}: value {fv.value!r} has no supporting quote; dropped"))
            fv.value = None
    return flags


def check_required(doc_type: str, data: BaseModel | None) -> list[Flag]:
    if data is None:
        return [Flag("MISSING_DOCUMENT", "high", f"{doc_type} not provided")]
    return [Flag("MISSING_FIELD", "medium", f"{doc_type}.{f} not found")
            for f in REQUIRED[doc_type] if _v(data, f) is None]


def check_passport(p: BaseModel | None, as_of: date) -> list[Flag]:
    if p is None or not (_v(p, "mrz_line1") and _v(p, "mrz_line2")):
        return []
    flags = []
    try:
        mrz = parse_td3(_v(p, "mrz_line1"), _v(p, "mrz_line2"), today=as_of)
    except ValueError as e:
        return [Flag("MRZ_CHECK_FAILED", "high", f"MRZ unreadable: {e}")]
    failed = [k for k, ok in mrz["checks"].items() if not ok]
    if failed:
        flags.append(Flag("MRZ_CHECK_FAILED", "high", f"MRZ check digits failed: {', '.join(failed)}"))
    visual = {
        "document_number": _v(p, "document_number"),
        "date_of_birth": _v(p, "date_of_birth"),
        "expiry_date": _v(p, "expiry_date"),
        "surname": transliterate(_v(p, "surname") or "").replace("<", " ").strip(),
    }
    diffs = [k for k, v in visual.items() if v and text_key(v) != text_key(mrz[k])]
    if diffs:
        flags.append(Flag("MRZ_VISUAL_MISMATCH", "high", f"MRZ disagrees with printed page on: {', '.join(diffs)}"))
    expiry = parse_date(_v(p, "expiry_date")) or parse_date(mrz["expiry_date"])
    if expiry and expiry < as_of:
        flags.append(Flag("PASSPORT_EXPIRED", "high", f"passport expired on {expiry.isoformat()}"))
    return flags


def check_cross_document(p, fa, poa, as_of: date) -> list[Flag]:
    flags = []
    passport_name = f"{_v(p, 'given_names') or ''} {_v(p, 'surname') or ''}".strip() or None

    def mismatch(code, label, a, b, key):
        if a and b and key(a) != key(b):
            flags.append(Flag(code, "high", f"{label}: {a!r} vs {b!r}"))

    mismatch("NAME_MISMATCH", "passport vs Form A beneficial owner", passport_name,
             _v(fa, "beneficial_owner_name"), name_key)
    mismatch("NAME_MISMATCH", "passport vs proof of address", passport_name, _v(poa, "name"), name_key)
    mismatch("DOB_MISMATCH", "passport vs Form A", _v(p, "date_of_birth"),
             _v(fa, "beneficial_owner_date_of_birth"), str)
    mismatch("NATIONALITY_MISMATCH", "passport vs Form A", _v(p, "nationality"),
             _v(fa, "beneficial_owner_nationality"), str)
    mismatch("ADDRESS_MISMATCH", "Form A vs proof of address", _v(fa, "beneficial_owner_address"),
             _v(poa, "address"), address_key)
    issued = parse_date(_v(poa, "issue_date"))
    if issued and (as_of - issued).days > MAX_PROOF_AGE_DAYS:
        flags.append(Flag("PROOF_OF_ADDRESS_TOO_OLD", "medium",
                          f"issued {issued.isoformat()}, {(as_of - issued).days} days before {as_of.isoformat()}"))
    return flags


def check_suspicious_text(doc_type: str, pages: list[str]) -> list[Flag]:
    """Documents are data. Text that addresses an AI system is a red flag in its own right."""
    for page in pages:
        m = INJECTION_PATTERNS.search(" ".join(page.split()))
        if m:
            return [Flag("SUSPICIOUS_INSTRUCTIONS", "high", f"{doc_type} contains instruction-like text: {m.group(0)!r}")]
    return []
