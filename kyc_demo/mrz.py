"""ICAO Doc 9303 TD3 (passport) machine-readable zone: check digits, building and parsing."""

import re
import unicodedata
from datetime import date

WEIGHTS = (7, 3, 1)
ISSUING_STATES = {"UTO", "CHE", "FRA", "ITA", "DEU", "AUT", "GBR", "ESP", "PRT", "NLD", "BEL", "SWE", "HRV",
                  "IND", "NGA", "BRA", "LBN", "USA", "D<<"}  # a demo subset of ICAO codes
GERMAN = {"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS"}
LOOKALIKES = [{"O", "0"}, {"Q", "0"}, {"D", "0"}, {"I", "1"}, {"B", "8"}, {"S", "5"}, {"Z", "2"}, {"G", "6"}]


def char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if "A" <= c <= "Z":
        return ord(c) - 55
    if c == "<":
        return 0
    raise ValueError(f"invalid MRZ character: {c!r}")


def check_digit(s: str) -> str:
    return str(sum(char_value(c) * WEIGHTS[i % 3] for i, c in enumerate(s)) % 10)


def transliterate(text: str) -> str:
    """Latin name -> MRZ characters (ICAO 9303 part 3: Ü -> UE, accents dropped, separators -> <)."""
    text = "".join(GERMAN.get(c, c) for c in text.upper())
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "<" for c in text)


def _pad(text: str, length: int) -> str:
    return (text + "<" * length)[:length]


def build_td3(*, issuing_state: str, surname: str, given_names: str, document_number: str,
              nationality: str, birth: date, sex: str, expiry: date) -> tuple[str, str]:
    name = _pad(f"{transliterate(surname)}<<{transliterate(given_names)}", 39)
    line1 = f"P<{issuing_state}{name}"
    doc = _pad(document_number, 9)
    dob, exp = birth.strftime("%y%m%d"), expiry.strftime("%y%m%d")
    personal = "<" * 14
    line2 = (doc + check_digit(doc) + nationality + dob + check_digit(dob) + sex
             + exp + check_digit(exp) + personal + "<")
    line2 += check_digit(line2[0:10] + line2[13:20] + line2[21:43])
    return line1, line2


def _safe_check(field: str, digit: str) -> bool:
    try:
        return check_digit(field) == digit
    except ValueError:
        return False


def _yymmdd(s: str, *, birth: bool, today: date) -> str | None:
    try:
        yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
        century = 1900 if birth and yy > today.year % 100 else 2000
        return date(century + yy, mm, dd).isoformat()
    except ValueError:
        return None


def parse_td3(line1: str, line2: str, today: date | None = None) -> dict:
    """Parse a TD3 MRZ and verify its check digits. Raises ValueError if the lines are not 44 chars."""
    l1, l2 = line1.strip(), line2.strip()
    if len(l1) != 44 or len(l2) != 44:
        raise ValueError("TD3 lines must be 44 characters")
    today = today or date.today()
    surname, _, given = l1[5:44].partition("<<")
    personal = l2[28:42]
    return {
        "issuing_state": l1[2:5],
        "surname": surname.replace("<", " ").strip(),
        "given_names": given.replace("<", " ").strip(),
        "document_number": l2[0:9].rstrip("<"),
        "nationality": l2[10:13],
        "date_of_birth": _yymmdd(l2[13:19], birth=True, today=today),
        "sex": l2[20],
        "expiry_date": _yymmdd(l2[21:27], birth=False, today=today),
        "checks": {
            "document_number": _safe_check(l2[0:9], l2[9]),
            "date_of_birth": _safe_check(l2[13:19], l2[19]),
            "expiry_date": _safe_check(l2[21:27], l2[27]),
            "personal_number": (set(personal + l2[42]) <= {"<", "0"}) or _safe_check(personal, l2[42]),
            "composite": _safe_check(l2[0:10] + l2[13:20] + l2[21:43], l2[43]),
        },
    }


def repair_filler(line: str | None, which: int) -> str | None:
    """Fix filler ('<') errors, the commonest MRZ misreads, without touching a real letter or digit.

    - Models read text as tokens, and a run like '<<<<<<<<<<<<' is a few tokens of unknown length, so
      they miscount it: the line comes back 43 or 46 characters long.
    - OCR reads chevrons as K, E, S, L or 6, so the filler tail fills up with letters.
    Line 1 has no check digit, so it is repaired structurally: no name contains '<<<', so everything after
    the first '<<<' in the name field is filler. Line 2's only filler is the 14-character personal-number
    field; a real error elsewhere still fails its check digit.
    """
    if not line:
        return line
    line = re.sub(r"\s+", "", line).upper()
    if which == 1:
        head, name = line[:5], line[5:]
        cut = name.find("<<<")
        if cut >= 0:
            name = name[:cut]
        return (head + name)[:44].ljust(44, "<")
    if len(line) != 44 and re.fullmatch(r".{28}<+..", line):
        return line[:28] + "<" * 14 + line[-2:]
    return line


def _valid(l1: str | None, l2: str | None) -> bool:
    try:
        return bool(l1 and l2) and all(parse_td3(l1, l2, today=date(2000, 1, 1))["checks"].values())
    except ValueError:
        return False


def reconcile(model_lines: tuple[str | None, str | None], ocr_lines: list[str] | None) -> dict:
    """Choose the MRZ to trust: deterministic where possible.

    Candidates in order of trust: the dedicated OCR pass, the same filler-repaired, the model's reading
    filler-repaired. The first whose check digits all pass wins. If none passes, the model's reading is kept
    and will fail validation, as it should.
    """
    ocr = tuple(ocr_lines) if ocr_lines else (None, None)
    candidates = {
        "ocr_pass": ocr,
        "ocr_repaired": (repair_filler(ocr[0], 1), repair_filler(ocr[1], 2)),
        "model": tuple(model_lines),
        "model_repaired": (repair_filler(model_lines[0], 1), repair_filler(model_lines[1], 2)),
    }
    valid = {k: _valid(*v) for k, v in candidates.items()}
    for key in ("ocr_pass", "ocr_repaired", "model_repaired"):
        if valid[key]:
            chosen, source = candidates[key], f"{key.replace('_', ' ')}: all check digits valid"
            break
    else:
        chosen, source = candidates["model_repaired"], "model reading: check digits fail on every candidate"
    # Check digits do not always tell O from 0: 'ROOOOO' and 'R00000' share one (five O's add 24 x 15 = 360,
    # 0 mod 10). When the model's line 2 passes too and differs only in such look-alikes, OCR's confusion is
    # the likelier error (found on a real Liechtenstein specimen).
    model2 = candidates["model_repaired"][1]
    if (source.startswith("ocr") and valid["model_repaired"] and model2 != chosen[1]
            and all(a == b or {a, b} in LOOKALIKES for a, b in zip(model2, chosen[1]))):
        chosen, source = (chosen[0], model2), "model reading: OCR differs only in look-alike characters (O/0...)"
    # Line 1 has no check digit, so no candidate can prove itself. Take the first well-formed one: a known
    # document type and issuing state ('PKLUTO...' is OCR noise for 'P<UTO...') and a name of letters and
    # filler only ('JOA0' is not). The model comes first: Tesseract's MRZ pass reads chevrons as letters.
    line1s = [repair_filler(l, 1) for l in (model_lines[0], ocr[0], chosen[0]) if l]
    well_formed = lambda l: (re.match(r"P[<A-Z][A-Z<]{3}[A-Z<]{39}$", l) is not None and l[2:5] in ISSUING_STATES)
    chosen = (next((l for l in line1s if well_formed(l)), line1s[0] if line1s else None), chosen[1])
    return {"lines": chosen, "source": source, "candidates": {k: list(v) for k, v in candidates.items()},
            "valid": valid}
