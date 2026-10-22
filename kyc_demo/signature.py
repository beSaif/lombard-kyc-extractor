"""Is the Form A signed? A pixel test, not a model's opinion.

The bank's own form has a signature line with a printed label under it ("Signature(s)", "Unterschrift(en)",
"Firma/e"). OCR finds the label; the band just above it is where a signature goes. Printed rules are
removed (a long horizontal run of ink is a line, not handwriting), and what ink is left decides.

It cannot tell whose signature it is, or whether it is a signature at all rather than a scribble: it
answers "is something written where the signature goes", which is what a missing-signature check needs.
CDB 20 art. 63(b) treats an incomplete Form A as a minor breach only if it is signed, so this is the
Form A field that matters most.
"""

import cv2
import numpy as np
from rapidfuzz import fuzz

from .normalise import text_key
from .read import Document

LABELS = ("signature", "signatures", "unterschrift", "unterschriften", "firma", "firme")
# The "Place and date" label of the same form sits 90 mm to the left on the same line. When a signature runs
# into its label, OCR reads the two as one blur and loses the label, but this one is still there.
PLACE_LABELS, PLACE_OFFSET = ("place", "lieu", "ort", "luogo"), 90 / 210
# The band above the label, in fractions of an A4 page: from 2 mm to 14 mm above (the legal notice starts
# just higher), 75 mm wide.
BAND_ABOVE, BAND_HEIGHT, BAND_WIDTH = 2 / 297, 12 / 297, 75 / 210
# Share of the band covered by ink. On the synthetic forms unsigned bands measure 0.0 in every tier and the
# faintest signature (a blurred phone photo) 0.004; set on that data, so check it on real scans before use.
MIN_INK = 0.0015


def _lowest(doc: Document, labels: tuple[str, ...]):
    best = None
    for page in doc.pages:
        for w in page.words:
            key = text_key(w.text).split()
            if key and max(fuzz.ratio(key[0], label) for label in labels) >= 80:
                if best is None or (page.number, w.bbox[1]) > (best[0].number, best[1].bbox[1]):
                    best = (page, w)
    return best


def find_label(doc: Document):
    """Where the signature label starts: (page, x0, y0, text), from the label itself or from 'Place and date'."""
    found = _lowest(doc, LABELS)
    if found:
        return found[0], found[1].bbox[0], found[1].bbox[1], found[1].text
    found = _lowest(doc, PLACE_LABELS)
    if found:
        return found[0], found[1].bbox[0] + PLACE_OFFSET, found[1].bbox[1], f"{found[1].text} (+90 mm)"
    return None


def ink_ratio(gray: np.ndarray, box: tuple[float, float, float, float]) -> float:
    h, w = gray.shape
    x0, y0, x1, y1 = (int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))
    band = gray[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
    if band.size == 0:
        return 0.0
    ink = (band < 140).astype(np.uint8)
    # A printed rule is a horizontal run far longer than any stroke of handwriting is flat.
    lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, band.shape[1] // 6), 1)))
    ink = cv2.subtract(ink, cv2.dilate(lines, np.ones((3, 3), np.uint8)))
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))  # specks of scan noise
    return float(ink.mean())


def signature_band(doc: Document) -> dict | None:
    """Where the signature should be, and how much ink is there. None if the label was not found."""
    found = find_label(doc)
    if found is None:
        return None
    page, x0, y0, label = found
    box = (max(0.0, x0 - 0.01), max(0.0, y0 - BAND_ABOVE - BAND_HEIGHT), min(1.0, x0 + BAND_WIDTH), y0 - BAND_ABOVE)
    gray = page.ocr_input if page.ocr_input is not None else cv2.cvtColor(page.image, cv2.COLOR_BGR2GRAY)
    return {"page": page.number, "label": label, "bbox": box, "ink": round(ink_ratio(gray, box), 4)}
