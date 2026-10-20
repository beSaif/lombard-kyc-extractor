"""One client file in, pre-filled fields plus review flags out."""

import time
from datetime import date
from pathlib import Path

from .read import read_pages
from .validate import (check_cross_document, check_passport, check_required,
                       check_suspicious_text, enforce_evidence)

DOC_FILES = {"passport": "passport.pdf", "form_a": "form_a.pdf", "proof_of_address": "proof_of_address.pdf"}


def run_case(case_dir: Path, extractor, as_of: date) -> dict:
    extracted, flags, timings = {}, [], {}
    for doc_type, filename in DOC_FILES.items():
        path = case_dir / filename
        if not path.exists():
            extracted[doc_type] = None
            continue
        pages = read_pages(path)
        start = time.perf_counter()
        data = extractor.extract(doc_type, pages)
        timings[doc_type] = round(time.perf_counter() - start, 3)
        flags += enforce_evidence(doc_type, data, pages)
        flags += check_suspicious_text(doc_type, pages)
        extracted[doc_type] = data

    for doc_type in DOC_FILES:
        flags += check_required(doc_type, extracted[doc_type])
    flags += check_passport(extracted["passport"], as_of)
    flags += check_cross_document(extracted["passport"], extracted["form_a"], extracted["proof_of_address"], as_of)

    return {
        "case": case_dir.name,
        "extractor": extractor.name,
        "decision": "manual_review" if flags else "pre_filled_review",
        "flags": [f.to_dict() for f in flags],
        "fields": {k: (v.model_dump() if v is not None else None) for k, v in extracted.items()},
        "seconds": timings,
    }
