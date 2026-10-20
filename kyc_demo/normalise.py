"""Normalisation shared by extraction, validation and evaluation."""

import re
import unicodedata
from datetime import date, datetime

FRENCH_MONTHS = {
    "janvier": "January", "février": "February", "fevrier": "February", "mars": "March",
    "avril": "April", "mai": "May", "juin": "June", "juillet": "July", "août": "August",
    "aout": "August", "septembre": "September", "octobre": "October", "novembre": "November",
    "décembre": "December", "decembre": "December",
}
COUNTRIES = {
    "CHE": ("switzerland", "suisse"), "FRA": ("france",), "ITA": ("italy", "italie"),
    "DEU": ("germany", "allemagne"), "IND": ("india", "inde"), "PRT": ("portugal",),
    "ESP": ("spain", "espagne"), "NGA": ("nigeria", "nigéria"),
}
COUNTRY_WORDS = {w for names in COUNTRIES.values() for w in names}
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y")


def strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def text_key(s: str | None) -> str:
    """Casefolded, accent-free, punctuation-free, single-spaced."""
    if not s:
        return ""
    s = strip_accents(s).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def name_key(s: str | None) -> str:
    """Order-independent name key: 'Müller, Anna Maria' == 'ANNA MARIA MULLER'."""
    return " ".join(sorted(text_key(s).split()))


def address_key(s: str | None) -> str:
    return " ".join(t for t in text_key(s).split() if t not in COUNTRY_WORDS)


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = " ".join(s.strip().split())
    for fr, en in FRENCH_MONTHS.items():
        s = re.sub(rf"\b{fr}\b", en, s, flags=re.IGNORECASE)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def iso_date(s: str | None) -> str | None:
    d = parse_date(s)
    return d.isoformat() if d else None


def country_code(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if re.fullmatch(r"[A-Z]{3}", s):
        return s
    key = text_key(s)
    for code, names in COUNTRIES.items():
        if key in {text_key(n) for n in names}:
            return code
    return None
