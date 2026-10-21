"""Ground a model's quote in what OCR actually found on the page, and get its position.

With a clean text layer, "is the quote in the text?" is a substring test. With scans and photos it is
not: OCR reads "Surnarne" for "Surname" and the model (looking at the image) quotes the real word.
So we slide a window over the page's OCR words and take the best fuzzy match:

- score 100       exact (after case/accent/punctuation folding)
- score >= 85     fuzzy: accept, the difference is OCR noise
- below 85        not found: the value is dropped, because nothing on the page supports it

The threshold is the trade-off: lower lets hallucinations through, higher rejects true values on bad scans.
"""

from dataclasses import asdict, dataclass

from rapidfuzz import fuzz

from .mrz import parse_td3
from .normalise import text_key
from .read import Page

FUZZY_MIN = 85
MRZ_ZONE = (0.0, 0.72, 1.0, 1.0)
# Visual-zone fields the MRZ repeats: their place on TD3 line 2 and the check digit that covers them.
MRZ_FIELDS = {"document_number": (slice(0, 9), "document_number"), "nationality": (slice(10, 13), "composite"),
              "date_of_birth": (slice(13, 19), "date_of_birth"), "sex": (slice(20, 21), "composite"),
              "expiry_date": (slice(21, 27), "expiry_date")}


@dataclass
class Match:
    method: str             # exact | fuzzy | mrz_pass | not_found
    score: float
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    matched_text: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def locate(quote: str | None, pages: list[Page]) -> Match:
    q = text_key(quote)
    if not q:
        return Match("not_found", 0.0)
    q_tokens = q.split()
    best = Match("not_found", 0.0)
    for page in pages:
        if page.mrz:  # MRZ lines come from their own OCR pass and have no word boxes
            for line in page.mrz:
                s = fuzz.ratio(q.replace(" ", ""), text_key(line).replace(" ", ""))
                if s > best.score:
                    best = Match("mrz_pass", round(s, 1), page.number, MRZ_ZONE, line)
        keyed = [(text_key(w.text), w) for w in page.words]
        keyed = [(k, w) for k, w in keyed if k]
        # One OCR word can hold several tokens ("25.08.2026") and vice versa, so try every window size.
        for size in range(1, min(len(q_tokens) + 3, 14)):
            for i in range(0, max(0, len(keyed) - size) + 1):
                window = keyed[i:i + size]
                if not window:
                    continue
                s = fuzz.ratio(q, " ".join(k for k, _ in window))
                if s > best.score:
                    ws = [w for _, w in window]
                    bbox = (min(w.bbox[0] for w in ws), min(w.bbox[1] for w in ws),
                            max(w.bbox[2] for w in ws), max(w.bbox[3] for w in ws))
                    best = Match("exact" if s == 100 else "fuzzy", round(s, 1), page.number, bbox,
                                 " ".join(w.text for w in ws))
    if best.score < FUZZY_MIN:
        best.method = "not_found"
    return best


def locate_in_mrz(field: str, value: str | None, pages: list[Page]) -> Match | None:
    """Find a passport value in the MRZ pass when the page OCR lost it.

    Tesseract drops a lone 'F' under a 'Sex / Sexe' label: it merges it into the label's text line and
    discards it as an outlier. The MRZ repeats it at a fixed position, read by its own OCR pass and covered by
    a check digit, so a match there verifies the value.
    """
    if field not in MRZ_FIELDS or not value:
        return None
    span, check = MRZ_FIELDS[field]
    want = value.replace("-", "")[2:] if field in ("date_of_birth", "expiry_date") else value.upper()
    for page in pages:
        if not page.mrz or len(page.mrz) != 2:
            continue
        try:
            checks = parse_td3(*page.mrz)["checks"]
        except ValueError:
            continue
        got = page.mrz[1].strip()[span]
        if checks[check] and got.rstrip("<") == want:
            where = f"{span.start + 1}" if len(got) == 1 else f"{span.start + 1}-{span.stop}"
            return Match("mrz_pass", 100.0, page.number, MRZ_ZONE, f"MRZ line 2, position {where}: {got}")
    return None
