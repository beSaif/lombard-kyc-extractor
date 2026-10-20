"""ICAO Doc 9303 TD3 (passport) machine-readable zone: check digits, building and parsing."""

import unicodedata
from datetime import date

WEIGHTS = (7, 3, 1)
GERMAN = {"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS"}


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
