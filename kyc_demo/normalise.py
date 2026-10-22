"""Normalisation shared by extraction, validation and evaluation.

Most false alarms in KYC are not bad data but the same fact written two ways: "Av." and "Avenue",
Genève and Geneva, "Anna Müller" and "MÜLLER Anna Maria", 19.06.1961 and "19 JUN/JUIN 1961".
These keys make such pairs compare equal, and nothing else.
"""

import re
import unicodedata
from datetime import date, datetime

MONTH_WORDS = {
    1: ["january", "jan", "janvier", "janv", "januar", "gennaio", "genn"],
    2: ["february", "feb", "février", "fevrier", "fév", "fev", "februar", "febbraio", "febb"],
    3: ["march", "mar", "mars", "märz", "marz", "maerz", "marzo"],
    4: ["april", "apr", "avril", "avr", "aprile"],
    5: ["may", "mai", "maggio", "magg"],
    6: ["june", "jun", "juin", "juni", "giugno", "giu"],
    7: ["july", "jul", "juillet", "juil", "juli", "luglio", "lug"],
    8: ["august", "aug", "août", "aout", "agosto", "ago"],
    9: ["september", "sep", "sept", "septembre", "settembre", "sett", "set"],
    10: ["october", "oct", "octobre", "oktober", "okt", "ottobre", "ott"],
    11: ["november", "nov", "novembre"],
    12: ["december", "dec", "décembre", "decembre", "déc", "dezember", "dez", "dicembre", "dic"],
}
MONTH_LOOKUP = {w: m for m, words in MONTH_WORDS.items() for w in words}

COUNTRIES = {
    "CHE": ("switzerland", "suisse", "schweiz", "svizzera", "swiss", "suisse"),
    "FRA": ("france", "frankreich", "francia", "french", "française", "francaise"),
    "ITA": ("italy", "italie", "italien", "italia", "italian", "italienne"),
    "DEU": ("germany", "allemagne", "deutschland", "germania", "german", "deutsch"),
    "IND": ("india", "inde", "indien", "indian"),
    "PRT": ("portugal", "portogallo", "portuguese"),
    "NGA": ("nigeria", "nigéria", "nigerian"),
    "ESP": ("spain", "espagne", "spanien", "spagna", "spanish"),
    "NLD": ("netherlands", "pays-bas", "niederlande", "paesi bassi", "dutch"),
    "AUT": ("austria", "autriche", "österreich", "austrian"),
    "BRA": ("brazil", "brésil", "brasilien", "brasile", "brazilian"),
    "BEL": ("belgium", "belgique", "belgien", "belgio", "belgian"),
    "GBR": ("united kingdom", "royaume-uni", "vereinigtes königreich", "regno unito", "british", "uk"),
    "HRV": ("croatia", "croatie", "kroatien", "croazia", "croatian"),
    "SWE": ("sweden", "suède", "schweden", "svezia", "swedish"),
    "LBN": ("lebanon", "liban", "libanon", "libano", "lebanese"),
}
STREET_ABBREVIATIONS = {"av": "avenue", "ave": "avenue", "ch": "chemin", "rte": "route", "bd": "boulevard",
                        "bld": "boulevard", "r": "rue", "pl": "place", "vle": "viale", "str": "strasse"}
CITY_ALIASES = {"geneva": "geneve", "genf": "geneve", "ginevra": "geneve", "zurich": "zurich",
                "zuerich": "zurich", "berne": "bern", "berna": "bern", "bale": "basel", "basilea": "basel"}


def strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def text_key(s: str | None) -> str:
    """Casefolded, accent-free, punctuation-free, single-spaced."""
    if not s:
        return ""
    s = strip_accents(s.replace("ß", "ss")).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def name_tokens(s: str | None) -> set[str]:
    """'Müller, Anna Maria' -> {'anna', 'maria', 'muller'}. Order and case do not matter."""
    return set(text_key(s).split())


def name_key(s: str | None) -> str:
    return " ".join(sorted(name_tokens(s)))


def names_match(a: str | None, b: str | None) -> bool:
    """Two free-text names: equal tokens, or one is the other minus middle names ('Anna Müller' vs
    'Anna Maria Müller'). Neither side says which token is the surname, so when one side is a passport,
    use person_matches instead: it knows the surname and is stricter.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    small, big = (ta, tb) if len(ta) < len(tb) else (tb, ta)
    return len(small) >= 2 and small <= big


def person_matches(surname: str | None, given_names: str | None, other: str | None) -> bool:
    """Does a free-text name refer to the passport holder?

    Every surname token and the first given name must be there, and nothing that is not on the passport.
    Order does not matter ('MÜLLER Anna Maria'), a missing middle name is allowed ('Anna Müller'), but
    'Anna Maria' (no surname), 'Maria Müller' (a relative?) and 'Marco Müller' are not the holder.
    """
    sur, given, got = name_tokens(surname), text_key(given_names).split(), name_tokens(other)
    if not sur or not given or not got:
        return False
    return sur <= got and given[0] in got and got <= sur | set(given)


def address_key(s: str | None) -> str:
    """Order-free address tokens with abbreviations expanded, city aliases unified, and 'CH-' and a
    trailing country name dropped ('Avenue de France 10' keeps its 'France')."""
    if not s:
        return ""
    s = re.sub(r"\bCH-(?=\d{4}\b)", "", s)
    s = re.sub(r"(\w)str\.", r"\1strasse", s)  # Beispielstr. -> Beispielstrasse
    tokens = [CITY_ALIASES.get(t, STREET_ABBREVIATIONS.get(t, t)) for t in text_key(s).split()]
    while tokens and tokens[-1] in COUNTRY_WORDS:
        tokens.pop()
    return " ".join(sorted(tokens))


def digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def parse_date(s: str | None) -> date | None:
    """Every date style in the corpus: 21.07.1969, 21/07/1969, 1969-07-21, 21 July 1969, July 21, 1969,
    21. Juli 1969, 21 luglio 1969, and the passport's bilingual '21 JUL/JUIL 1969'."""
    if not s:
        return None
    s = " ".join(s.strip().split())
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    words = re.findall(r"[^\W\d_]+|\d+", s.casefold())
    nums = [w for w in words if w.isdigit()]
    months = [MONTH_LOOKUP[w] for w in words if w in MONTH_LOOKUP]
    if len(nums) == 2 and months:
        day, year = (int(nums[0]), int(nums[1])) if len(nums[1]) == 4 else (int(nums[1]), int(nums[0]))
        try:
            return date(year, months[0], day)
        except ValueError:
            return None
    return None


NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")


def find_date(s: str | None) -> date | None:
    """A date that is the whole string, or one written inside it ('Bern, 12.10.2026')."""
    d = parse_date(s)
    if d or not s:
        return d
    m = NUMERIC_DATE.search(s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def iso_date(s: str | None) -> str | None:
    d = parse_date(s)
    return d.isoformat() if d else None


ALPHA2 = {"CH": "CHE", "FR": "FRA", "IT": "ITA", "DE": "DEU", "IN": "IND", "PT": "PRT", "NG": "NGA",
          "ES": "ESP", "NL": "NLD", "AT": "AUT", "BR": "BRA", "BE": "BEL", "GB": "GBR", "HR": "HRV",
          "SE": "SWE", "LB": "LBN"}


def country_code(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if s.upper() in ALPHA2 and len(s) == 2:
        return ALPHA2[s.upper()]
    if re.fullmatch(r"[A-Z]{3}", s) and s in COUNTRIES:
        return s
    key = text_key(s)
    for code, names in COUNTRIES.items():
        if key in {text_key(n) for n in names}:
            return code
    return None


COUNTRY_WORDS = {w for names in COUNTRIES.values() for n in names for w in text_key(n).split()}
COUNTRY_WORDS -= {"uk"}


NAME_FIELDS = {"surname", "given_names", "contracting_partner", "beneficial_owner_name", "name"}
ADDRESS_FIELDS = {"beneficial_owner_address", "address"}


def same(field: str, got: str | None, want: str | None) -> bool:
    """Does an extracted value equal the expected one, under the field's own notion of equal?"""
    if got is None or want is None:
        return False
    if field in NAME_FIELDS:
        return name_key(got) == name_key(want)
    if field in ADDRESS_FIELDS:
        return address_key(got) == address_key(want)
    if field.startswith("mrz_line"):
        return got.replace(" ", "") == want
    return text_key(got) == text_key(want)
