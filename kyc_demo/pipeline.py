"""One client file in, pre-filled fields plus review flags out, with a step-by-step trace.

    for each document:  load -> (pre-process -> OCR | text layer) -> prompt -> model -> normalise -> ground
    then, per file:     validation checks -> (optional second-model cross-check) -> route
"""

import time
from datetime import date
from pathlib import Path

from .mrz import reconcile
from .normalise import same
from .read import find_file, read_document
from .trace import Trace
from .validate import (Check, check_cross_document, check_injection, check_passport, check_required, check_signature,
                       corroborate, flags_from, ground_fields)

DOC_TYPES = ("passport", "form_a", "proof_of_address")


def reconcile_passport_mrz(data, doc, trace: Trace) -> None:
    ocr = next((p.mrz for p in doc.pages if p.mrz), None)
    with trace.step("mrz", "Reconcile the MRZ", doc="passport",
                    code=("kyc_demo.mrz.reconcile", "kyc_demo.mrz.repair_filler", "kyc_demo.mrz.check_digit"),
                    explain="The MRZ is machine-checkable, so we do not have to trust the model's copy of it. "
                            "Candidates: the model's reading, the same with '<' filler repaired, and the "
                            "dedicated OCR pass. The first whose check digits all pass wins.") as d:
        r = reconcile((data.mrz_line1.value, data.mrz_line2.value), ocr)
        for i, line in enumerate(r["lines"], start=1):
            fv = getattr(data, f"mrz_line{i}")
            if line and line != fv.value:
                fv.value = fv.quote = line
                fv.page = fv.page or 1
        d.update(r)


def cross_check(doc_type: str, a, b) -> Check:
    """Field-by-field agreement between two models. Disagreement is a cheap, model-free confidence signal."""
    rows, disagree = {}, []
    for name in type(a).model_fields:
        va, vb = getattr(a, name).value, getattr(b, name).value
        agree = (va is None and vb is None) or same(name, va, vb)
        rows[name] = {"primary": va, "second": vb, "agree": agree}
        if not agree:
            disagree.append(name)
    return Check(f"{doc_type}.cross_model", "Two independent models agree on every field", not disagree,
                 "all fields agree" if not disagree else f"disagree on: {', '.join(disagree)}",
                 "MODEL_DISAGREEMENT", "medium", {"fields": rows})


def run_case(case_dir: Path, extractor, as_of: date, reader: str = "auto", second=None,
             trace: Trace | None = None) -> dict:
    trace = trace or Trace()
    extracted, evidence, usage, checks = {}, {}, {}, []
    start = time.perf_counter()
    for doc_type in DOC_TYPES:
        path = find_file(case_dir, doc_type)
        if path is None:
            extracted[doc_type] = None
            continue
        doc = read_document(path, reader, doc_type, trace)
        ex = extractor.extract(doc_type, doc, trace)
        if doc_type == "passport":
            reconcile_passport_mrz(ex.data, doc, trace)
        with trace.step("ground", "Ground every value in the page", doc=doc_type,
                        code=("kyc_demo.validate.ground_fields", "kyc_demo.ground.locate"),
                        explain="Two tests per value. Does its own quote say it (same name tokens, same date, same "
                                "digits)? If not, it is dropped. Is the quote on the page (fuzzy for OCR noise, "
                                "exact for digits)? If not, it is unverified and a human checks it unless another "
                                "document corroborates it. The MRZ is verified by its check digits instead.") as d:
            ev = ground_fields(doc_type, ex.data, doc)
            d.update(evidence=ev, fields=ex.data.model_dump())
        reports = [ex.embedded_instructions]
        if second is not None:
            ex2 = second.extract(doc_type, doc, trace)
            reports.append(ex2.embedded_instructions)
            if doc_type == "passport":  # compare like with like: both MRZs go through the same reconciliation
                reconcile_passport_mrz(ex2.data, doc, trace)
            ground_fields(doc_type, ex2.data, doc)
            with trace.step("cross_model", f"Cross-check with {second.name}", doc=doc_type,
                            code=("kyc_demo.pipeline.cross_check",),
                            explain="A second model read the same document. Fields where the two disagree go "
                                    "to a human, even if every rule passes.") as d:
                c = cross_check(doc_type, ex.data, ex2.data)
                d.update(check=c.to_dict())
            checks.append(c)
            usage[f"{doc_type}:second"] = ex2.usage
        checks += check_injection(doc_type, doc, reports)
        if doc_type == "form_a":
            with trace.step("signature", "Look for a signature", doc=doc_type,
                            code=("kyc_demo.validate.check_signature", "kyc_demo.signature.signature_band",
                                  "kyc_demo.signature.ink_ratio"),
                            explain="Pixels, not the model: find the signature label, measure the ink in the band "
                                    "above it after removing the printed line. An empty band is an unsigned form.") as d:
                sig = check_signature(doc)
                d.update(check=sig[0].to_dict())
            checks += sig
        extracted[doc_type], evidence[doc_type], usage[doc_type] = ex.data, ev, ex.usage

    with trace.step("validate", "Run the validation rules", code=(
            "kyc_demo.validate.check_required", "kyc_demo.validate.check_passport", "kyc_demo.mrz.parse_td3",
            "kyc_demo.mrz.check_digit", "kyc_demo.validate.check_cross_document", "kyc_demo.normalise.person_matches",
            "kyc_demo.normalise.address_key", "kyc_demo.validate.check_injection"),
            explain="Deterministic rules: required fields, MRZ checksums, MRZ vs printed page, expiry, and "
                    "consistency across the three documents. Every check is listed, passed or not.") as d:
        for doc_type in DOC_TYPES:
            checks += check_required(doc_type, extracted[doc_type])
        checks += check_passport(extracted["passport"], as_of)
        checks += check_cross_document(extracted["passport"], extracted["form_a"], extracted["proof_of_address"], as_of)
        d["checks"] = [c.to_dict() for c in checks]

    with trace.step("corroborate", "Corroborate unverified values", code=("kyc_demo.validate.corroborate",),
                    explain="A value OCR could not find (often handwriting) is trusted if a passing check ties it "
                            "to a verified value on another document. Whatever is left must be checked by eye.") as d:
        log, ev_checks = corroborate(evidence, checks)
        checks += ev_checks
        d.update(corroborated=log, checks=[c.to_dict() for c in ev_checks],
                 status={doc: {f: e["status"] for f, e in fields.items()} for doc, fields in evidence.items()})

    flags = flags_from(checks)
    with trace.step("route", "Route the file", code=("kyc_demo.pipeline.run_case",),
                    explain="No failed check: a pre-filled file for a quick review. Any failed check: the manual "
                            "queue, with the reasons. A compliance officer signs off either way.") as d:
        decision = "manual_review" if flags else "pre_filled_review"
        d.update(decision=decision, flags=flags)

    totals = {
        "seconds": round(time.perf_counter() - start, 2),
        "model_seconds": round(sum((u.get("seconds") or 0) for u in usage.values()), 2),
        "input_tokens": sum((u.get("input_tokens") or 0) for u in usage.values()),
        "output_tokens": sum((u.get("output_tokens") or 0) for u in usage.values()),
        "cost_usd": None if any(u and u.get("cost_usd") is None for u in usage.values())
        else round(sum((u.get("cost_usd") or 0) for u in usage.values()), 5),
    }
    return {
        "case": case_dir.name,
        "tier": case_dir.parent.name,
        "extractor": extractor.name,
        "second": second.name if second else None,
        "reader": reader,
        "as_of": as_of.isoformat(),
        "decision": decision,
        "flags": flags,
        "checks": [c.to_dict() for c in checks],
        "fields": {k: (v.model_dump() if v is not None else None) for k, v in extracted.items()},
        "evidence": evidence,
        "usage": usage,
        "totals": totals,
        "steps": trace.steps,
    }
