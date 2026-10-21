"""Turn a file (PDF or photo) into pages: an image, the words on it with boxes, and plain text.

Three reading strategies, picked with `mode`:
- text: the PDF's own text layer. Free and exact, but only born-digital PDFs have one.
- ocr:  Tesseract on the page image, after flattening a photographed page.
- auto: the text layer when there is one, OCR otherwise (what you would run in production).

Every word keeps its bounding box (fractions of the page, 0-1) so evidence can be shown on the page.
"""

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from .trace import Trace

RENDER_DPI = 200
OCR_LANGS_WANTED = ["eng", "fra", "deu", "ita"]
MRZ_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
CACHE = Path("runs/cache/ocr")


@dataclass
class Word:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of the page
    conf: float | None = None                 # Tesseract confidence 0-100; None for a text layer


@dataclass
class Page:
    number: int                     # 1-based
    image: np.ndarray = field(repr=False)  # BGR, what the words' boxes refer to
    words: list[Word]
    text: str
    source: str                     # "text_layer" | "ocr"
    original: np.ndarray | None = field(default=None, repr=False)  # before flattening, if it changed
    ocr_input: np.ndarray | None = field(default=None, repr=False)  # the exact image Tesseract saw
    preprocess: dict = field(default_factory=dict)
    mrz: list[str] | None = None    # dedicated MRZ pass (passports only)


@dataclass
class Document:
    path: Path
    sha256: str
    kind: str                       # "pdf" | "image"
    has_text_layer: bool
    pages: list[Page]

    @property
    def texts(self) -> list[str]:
        """Page texts as the extractor sees them, including the dedicated MRZ lines."""
        out = []
        for p in self.pages:
            t = p.text
            if p.mrz:
                t += "\n\n[machine-readable zone, dedicated OCR pass]\n" + "\n".join(p.mrz)
            out.append(t)
        return out


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- loading ------------------------------------------------------------------------------

def load_pages(path: Path) -> tuple[str, list[np.ndarray], list[list[Word]]]:
    """Render every page to an image and collect the text-layer words (empty for scans and photos)."""
    if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"cannot read image {path}")
        return "image", [img], [[]]
    images, layers = [], []
    for page in pymupdf.open(path):
        pix = page.get_pixmap(dpi=RENDER_DPI)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        images.append(cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR))
        W, H = page.rect.width, page.rect.height
        layers.append([Word(w[4], (w[0] / W, w[1] / H, w[2] / W, w[3] / H))
                       for w in page.get_text("words")])
    return "pdf", images, layers


def words_to_text(words: list[Word]) -> str:
    """Rebuild reading-order text: group words into lines by vertical position."""
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: ((w.bbox[1] + w.bbox[3]) / 2, w.bbox[0])):
        mid = (w.bbox[1] + w.bbox[3]) / 2
        if lines:
            last = lines[-1][-1]
            h = last.bbox[3] - last.bbox[1]
            if abs(mid - (last.bbox[1] + last.bbox[3]) / 2) < 0.5 * h:
                lines[-1].append(w)
                continue
        lines.append([w])
    return "\n".join(" ".join(w.text for w in sorted(l, key=lambda w: w.bbox[0])) for l in lines)


# --- pre-processing: find a photographed page and flatten it -----------------------------------

def _order(pts: np.ndarray) -> np.ndarray:
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.float32([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]])


def flatten_document(img: np.ndarray) -> tuple[np.ndarray, dict]:
    """Find the largest four-cornered outline and warp it to a flat rectangle.

    Scans and digital pages fill the frame already, so nothing happens to them. Photos of a page on a
    desk get the desk cropped away and the perspective undone, which OCR needs badly.
    """
    h, w = img.shape[:2]
    scale = 1000 / max(h, w)
    small = cv2.resize(img, None, fx=scale, fy=scale)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 40, 120), np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = small.shape[0] * small.shape[1]
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
        frac = cv2.contourArea(approx) / area
        if len(approx) != 4 or frac < 0.25:
            continue
        if frac > 0.93:
            return img, {"applied": False, "reason": f"page already fills {frac:.0%} of the frame"}
        quad = _order(approx.reshape(4, 2).astype(np.float32) / scale)
        tw = int(max(np.linalg.norm(quad[0] - quad[1]), np.linalg.norm(quad[3] - quad[2])))
        th = int(max(np.linalg.norm(quad[0] - quad[3]), np.linalg.norm(quad[1] - quad[2])))
        M = cv2.getPerspectiveTransform(quad, np.float32([[0, 0], [tw, 0], [tw, th], [0, th]]))
        flat = cv2.warpPerspective(img, M, (tw, th))
        return flat, {"applied": True, "corners": quad.round(1).tolist(), "page_fraction": round(frac, 3),
                      "size_before": [w, h], "size_after": [tw, th]}
    return img, {"applied": False, "reason": "no four-cornered page outline found"}


def even_out_light(img: np.ndarray) -> np.ndarray:
    """Greyscale, then divide by an estimate of the paper's own brightness.

    Tesseract binarises with one global threshold, so in a photo with a shadow the text inside the
    shadow falls below it and vanishes. Dilating removes the (dark, thin) text, a large median blur then
    gives the lighting alone; dividing by it leaves evenly lit paper with the text intact.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if max(h, w) < 1800:  # Tesseract likes ~30 px tall capitals; upscale small photos
        f = 1800 / max(h, w)
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    background = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), 51)
    return cv2.divide(gray, background, scale=255)


# --- OCR ------------------------------------------------------------------------------------

def ocr_languages() -> list[str]:
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout.split()
    return [l for l in OCR_LANGS_WANTED if l in out] or ["eng"]


def _tesseract(img: np.ndarray, args: list[str]) -> str:
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract is not installed (brew install tesseract tesseract-lang)")
    ok, png = cv2.imencode(".png", img)
    return subprocess.run(["tesseract", "stdin", "stdout", *args], input=png.tobytes(),
                          capture_output=True, check=True).stdout.decode()


def _tsv_words(gray: np.ndarray, langs: str, psm: str) -> list[Word]:
    gh, gw = gray.shape
    words = []
    for row in _tesseract(gray, ["-l", langs, "--psm", psm, "tsv"]).splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5" or not cols[11].strip():
            continue
        left, top, width, height, conf = int(cols[6]), int(cols[7]), int(cols[8]), int(cols[9]), float(cols[10])
        words.append(Word(cols[11].strip(), (left / gw, top / gh, (left + width) / gw, (top + height) / gh),
                          round(conf, 1)))
    return words


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def ocr_page(gray: np.ndarray) -> list[Word]:
    """Two Tesseract passes, merged, cached by image hash.

    --psm 3 (automatic layout) reads printed paragraphs in order but skips most handwriting.
    --psm 11 (sparse text) finds scattered words, including handwritten answers on forms.
    Words found by both (boxes overlapping by IoU > 0.5) are kept once, with the higher confidence.
    """
    langs = "+".join(ocr_languages())
    key = hashlib.sha256(gray.tobytes() + langs.encode() + b"psm3+11").hexdigest()
    cached = CACHE / f"{key}.json"
    if cached.exists():
        return [Word(w["text"], tuple(w["bbox"]), w["conf"]) for w in json.loads(cached.read_text())]
    words = _tsv_words(gray, langs, "3")
    for w in _tsv_words(gray, langs, "11"):
        dup = next((i for i, v in enumerate(words) if _iou(v.bbox, w.bbox) > 0.5), None)
        if dup is None:
            words.append(w)
        elif (w.conf or 0) > (words[dup].conf or 0):
            words[dup] = w
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps([asdict(w) for w in words]))
    return words


# Line 2 positions that can only hold a digit (or '<' as filler): check digits and dates.
MRZ_DIGIT_POSITIONS = [9, *range(13, 20), *range(21, 28), 42, 43]
LOOKS_LIKE_DIGIT = str.maketrans({"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5",
                                  "G": "6", "B": "8"})


def fix_mrz_digits(line2: str) -> str:
    """Position-aware correction: where ICAO allows only a digit, a B is an 8 and an O is a 0."""
    chars = list(line2)
    for i in MRZ_DIGIT_POSITIONS:
        if i < len(chars):
            chars[i] = chars[i].translate(LOOKS_LIKE_DIGIT)
    return "".join(chars)


def _mrz_lines(text: str) -> list[str] | None:
    lines = [re.sub(r"\s+", "", l) for l in text.splitlines()]
    line2 = next((i for i in range(len(lines) - 1, -1, -1)
                  if len(lines[i]) >= 30 and sum(c.isdigit() for c in lines[i]) >= 10), None)
    if line2 is None or line2 == 0:
        return None
    line1 = lines[line2 - 1]
    if not (line1.startswith("P") and "<<" in line1 and len(line1) >= 12):
        return None
    # Tesseract drops trailing chevrons, so pad; line 2 keeps its last two characters (check digits) in place
    l2 = lines[line2]
    if len(l2) < 44 and re.fullmatch(r".{28}<*..", l2):
        l2 = l2[:-2].ljust(42, "<") + l2[-2:]
    return [line1[:44].ljust(44, "<"), fix_mrz_digits(l2[:44].ljust(44, "<"))]


def read_mrz(gray: np.ndarray) -> list[str] | None:
    """Separate OCR pass on the bottom of a passport, restricted to the 37 MRZ characters.

    General OCR reads '<' as '«', 'K' or 'C' and 0 as O. Real ID readers always OCR the MRZ separately with
    its own alphabet (it is printed in OCR-B for exactly this reason), then fix characters by position.
    Tries the light-normalised image first, then a binarised one if a line is missing.
    """
    h = gray.shape[0]
    crop = gray[int(h * 0.72):, :]
    binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    args = ["-l", "eng", "-c", f"tessedit_char_whitelist={MRZ_CHARS}"]
    for img, psm in ((crop, "6"), (binary, "6"), (crop, "4"), (binary, "11")):
        lines = _mrz_lines(_tesseract(img, [*args, "--psm", psm]))
        if lines:
            return lines
    return None


# --- the reader -----------------------------------------------------------------------------

def read_document(path: Path, mode: str = "auto", doc_type: str | None = None, trace: Trace | None = None) -> Document:
    trace = trace or Trace()
    with trace.step("load", "Load the file", doc=doc_type, code=("kyc_demo.read.load_pages",),
                    explain="PDFs are rendered to images at 200 dpi and their text layer (if any) is read with "
                            "word positions. Photos are loaded as they are.") as d:
        kind, images, layers = load_pages(path)
        has_layer = any(len(ws) > 3 for ws in layers)
        d.update(file=path.name, bytes=path.stat().st_size, sha256=file_sha256(path), kind=kind,
                 pages=len(images), text_layer_words=[len(ws) for ws in layers], has_text_layer=has_layer,
                 reader_mode=mode, images=[trace.image(f"{doc_type}_p{i}_original", img)
                                           for i, img in enumerate(images, start=1)])
    pages = []
    for i, (img, layer) in enumerate(zip(images, layers), start=1):
        if mode == "text" or (mode == "auto" and len(layer) > 3):
            with trace.step("read", "Use the PDF text layer", doc=doc_type,
                            code=("kyc_demo.read.words_to_text",),
                            explain="Born-digital PDF: the text is already there, exact and free. No OCR.") as d:
                page = Page(i, img, layer, words_to_text(layer), "text_layer")
                d.update(page=i, source="text_layer", text=page.text, words=_words_out(layer),
                         image=trace.image(f"{doc_type}_p{i}_page", img))
            pages.append(page)
            continue
        with trace.step("preprocess", "Flatten the page and even out the light", doc=doc_type,
                        code=("kyc_demo.read.flatten_document", "kyc_demo.read.even_out_light"),
                        explain="Find the page outline and undo the perspective (photos only), then divide out "
                                "uneven lighting so shadows do not swallow text.") as d:
            flat, info = flatten_document(img)
            gray = even_out_light(flat)
            d.update(page=i, flatten=info, before=trace.image(f"{doc_type}_p{i}_before", img),
                     flattened=trace.image(f"{doc_type}_p{i}_flat", flat),
                     ocr_input=trace.image(f"{doc_type}_p{i}_ocr_input", gray))
        with trace.step("read", "OCR with Tesseract", doc=doc_type,
                        code=("kyc_demo.read.ocr_page", "kyc_demo.read.read_mrz", "kyc_demo.read.words_to_text"),
                        explain=f"Tesseract ({'+'.join(ocr_languages())}) runs twice (layout mode and sparse-text mode, which catches handwriting), merged. Every word has a box and a "
                                "confidence. Passports get a second pass over the MRZ with only its 37 characters "
                                "allowed.") as d:
            words = ocr_page(gray)
            page = Page(i, flat, words, words_to_text(words), "ocr",
                        original=img if info["applied"] else None, ocr_input=gray, preprocess=info)
            if doc_type == "passport":
                page.mrz = read_mrz(gray)
            confs = [w.conf for w in words if w.conf is not None]
            d.update(page=i, source="ocr", languages=ocr_languages(), text=page.text, words=_words_out(words),
                     mean_confidence=round(sum(confs) / len(confs), 1) if confs else None,
                     low_confidence=[w.text for w in words if w.conf is not None and w.conf < 60][:40],
                     mrz=page.mrz, image=trace.image(f"{doc_type}_p{i}_page", flat))
        pages.append(page)
    return Document(path, file_sha256(path), kind, has_layer, pages)


def _words_out(words: list[Word]) -> list[dict]:
    return [{"t": w.text, "b": [round(v, 4) for v in w.bbox], "c": w.conf} for w in words]


def find_file(case_dir: Path, doc_type: str) -> Path | None:
    for ext in (".pdf", ".jpg", ".jpeg", ".png"):
        if (case_dir / f"{doc_type}{ext}").exists():
            return case_dir / f"{doc_type}{ext}"
    return None
