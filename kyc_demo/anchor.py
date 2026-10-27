"""Is a quote in the right place on the page, or only somewhere on it?

Grounding (ground.py) proves that a quote is printed on the page. That is not the same as the value being
the one the document states. A page can print a second name, address or date in a footnote or a remarks
box, and a model that was steered (by an injection, or by its own confusion) can quote that one. The quote
is on the page, so it would count as verified, and if the decoy agrees with the other documents every
cross-check passes too.

So for every quote that was found, we look at where it was found:

- fine print   printed much smaller than the page's body text (a footer, small print under a table).
               A bank does not take a client's name, address or dates from a footnote. Judged only where
               the PDF has a text layer: OCR boxes are too rough to tell 6 pt from 9 pt.
- other section  a label above it or to its left, with nothing printed in between, belongs to something
               we do not extract (a due date, a billing period, a Remarks box, a correspondence address).
- other field  ...or to another field we extract. The same text is often legitimately printed twice (the
               country ends the address and is also the nationality), and OCR may have lost the copy in
               the right place, so this only makes the value unverified: another document can vouch for it.
- anchored     one of this field's own labels is there (it wins over another field's label).
- no label     nothing that reads as a label nearby. Many real values have none (the address window of a
               letter, the issuer's letterhead) and OCR loses small labels on photos, so this proves nothing
               either way and changes nothing.

Fine print and other section make the value 'out_of_place' (see validate.ground_fields): a person has to
look, and no other document can vouch for it, because a decoy is built to agree with the other documents.

The labels are a small multilingual lexicon of what these documents call their fields (ICAO passport
labels, the CDB Form A, Swiss bills). They were written before the blind suite existed and have not been
changed after looking at it.
"""

from dataclasses import asdict, dataclass
from rapidfuzz import fuzz

from .normalise import text_key
from .read import Page, Word

OTHER = "_other"  # a label of something we do not extract, or of a free-text section
# Fine print: a quote under 70% of the page's body text height, taken as the 75th percentile of word heights
# (the median is pulled down by small labels and table headings, so a 6 pt footer looks normal against it).
# That needs exact sizes, which only a PDF text layer has: Tesseract's boxes for the same 9 pt type vary by a
# factor of two on a photo, so print size is not judged on OCR'd pages at all, nor for a quote of one or two
# characters (a lone 'F' has no telling height).
FINE_PRINT, BODY_PERCENTILE = 0.7, 0.75
# How far a label can be from its value, in units of the value's own line height (above) or of the page
# width (to the left, on the same line).
MAX_ABOVE_LINES, MAX_LEFT_WIDTH = 3.0, 0.45

NATIONALITY = ["nationality", "nationalite", "staatsangehorigkeit", "staatsangehoerigkeit", "nationalitat",
               "nazionalita", "cittadinanza", "citizenship", "nacionalidad", "nacionalidade"]
DATE_OF_BIRTH = ["date of birth", "date de naissance", "geburtsdatum", "data di nascita", "fecha de nacimiento",
                 "data de nascimento", "born", "ne le", "nee le", "geboren am", "nato il", "nata il"]
REMARKS = ["remarks", "remarques", "bemerkungen", "osservazioni", "notes", "note", "comments", "commentaires",
           "anmerkungen", "observations", "hinweis", "hinweise", "annotazioni"]
OTHER_ADDRESS = ["correspondence address", "adresse de correspondance", "korrespondenzadresse",
                 "indirizzo di corrispondenza", "postal address", "adresse postale", "postadresse",
                 "indirizzo postale", "previous address", "former address", "ancienne adresse", "fruhere adresse",
                 "precedente indirizzo", "indirizzo precedente", "new address", "future address", "nouvelle adresse",
                 "neue adresse", "nuovo indirizzo", "address on file"]

LABELS: dict[str, dict[str, list[str]]] = {
    "passport": {
        # Not 'name': OCR turns 'Given names' into '... names' and 'Name' alone would claim it for the surname.
        "surname": ["surname", "nom", "nachname", "familienname", "cognome", "apellidos", "apelidos"],
        "given_names": ["given names", "given name", "prenoms", "prenom", "vornamen", "vorname", "nomi", "nome",
                        "nombres", "nomes"],
        "nationality": NATIONALITY,
        "date_of_birth": DATE_OF_BIRTH,
        "sex": ["sex", "sexe", "geschlecht", "sesso", "sexo"],
        "document_number": ["passport no", "passport number", "no du passeport", "numero du passeport",
                            "pass nr", "passnummer", "pass no", "passaporto n", "numero del passaporto",
                            "n del passaporto", "document no", "document number", "no de document"],
        "expiry_date": ["date of expiry", "date d expiration", "gultig bis", "ablaufdatum", "data di scadenza",
                        "scadenza", "valid until", "valable jusqu au", "fecha de caducidad", "expiry"],
        OTHER: ["date of issue", "date de delivrance", "ausstellungsdatum", "datum der ausstellung",
                "data di rilascio", "place of birth", "lieu de naissance", "geburtsort", "luogo di nascita",
                "authority", "autorite", "behorde", "autorita", "personal no", "height", "taille", "grosse",
                "statura", "holder s signature", "signature du titulaire"],
    },
    "form_a": {
        "contracting_partner": ["contracting partner", "cocontractant", "vertragspartner", "vertragspartnerin",
                                "contraente", "account holder", "titulaire du compte", "kontoinhaber",
                                "titolare del conto"],
        "beneficial_owner_name": ["surname", "surnames", "first name", "first names", "last name", "full name",
                                  "nom", "noms", "prenom", "prenoms", "nom s", "name", "namen", "vorname",
                                  "vornamen", "name n", "cognome", "cognomi", "nome", "nomi", "cognome i"],
        "beneficial_owner_date_of_birth": DATE_OF_BIRTH,
        "beneficial_owner_nationality": NATIONALITY,
        "beneficial_owner_address": ["address", "domicile", "adresse", "wohnsitz", "wohnsitzadresse", "wohnadresse",
                                     "indirizzo", "domicilio", "residence", "residential address",
                                     "adresse de domicile", "indirizzo di domicilio"],
        OTHER: REMARKS + OTHER_ADDRESS + [
            "place and date", "lieu et date", "ort und datum", "luogo e data", "signature", "signatures",
            "signature s", "unterschrift", "unterschriften", "firma", "firme", "account no", "account number",
            "numero de compte", "kontonummer", "numero di conto", "telephone", "phone", "telefon", "telefono",
            "email", "e mail"],
    },
    "proof_of_address": {
        # The QR-bill receipt's "Payable by" is the debtor: the customer's name and address.
        "name": ["payable by", "zahlbar durch", "payable par", "pagabile da", "customer", "client", "kunde",
                 "kundin", "cliente", "recipient", "destinataire", "empfanger", "destinatario"],
        "address": ["payable by", "zahlbar durch", "payable par", "pagabile da", "supply address",
                    "verbrauchsadresse", "adresse de consommation", "indirizzo di fornitura", "billing address",
                    "rechnungsadresse", "adresse de facturation", "indirizzo di fatturazione", "delivery address",
                    "lieferadresse", "adresse de livraison", "service address", "anschlussadresse",
                    "objektadresse", "address", "adresse", "indirizzo"],
        "issue_date": ["invoice date", "date of invoice", "bill date", "issue date", "date of issue",
                       "rechnungsdatum", "datum der rechnung", "rechnung vom", "ausgestellt am", "date de facture",
                       "date de la facture", "facture du", "date d emission", "data fattura",
                       "data della fattura", "fattura del", "data di emissione", "date", "datum", "data"],
        "issuer": ["payable to", "account payable to", "zahlbar an", "konto zahlbar an", "payable a",
                   "compte payable a", "pagabile a", "conto pagabile a", "creditor", "creancier", "glaubiger",
                   "creditore"],
        OTHER: REMARKS + OTHER_ADDRESS + [
            "due date", "payable until", "payable by date", "zahlbar bis", "fallig am", "falligkeit",
            "falligkeitsdatum", "echeance", "date d echeance", "payable jusqu au", "a payer jusqu au", "scadenza",
            "pagabile entro", "data di scadenza", "billing period", "period", "abrechnungsperiode", "periode",
            "verbrauchsperiode", "periode de facturation", "periode de consommation", "periodo",
            "periodo di fatturazione", "meter reading", "zahlerstand", "ablesedatum", "releve", "date de releve",
            "lettura", "invoice number", "invoice no", "rechnungsnummer", "rechnungs nr", "numero de facture",
            "numero fattura", "customer number", "customer no", "kundennummer", "kunden nr", "numero client",
            "numero de client", "numero cliente", "reference", "referenz", "riferimento", "amount", "betrag",
            "montant", "importo", "total", "contract", "vertrag", "contrat", "contratto"],
    },
}


@dataclass
class Label:
    field: str
    text: str
    bbox: tuple[float, float, float, float]


@dataclass
class Place:
    verdict: str                # anchored | no_label | other_field | other_section | fine_print
    label: str | None = None    # the nearest label's text, as printed
    label_field: str | None = None
    label_bbox: tuple[float, float, float, float] | None = None
    height_ratio: float | None = None  # quote height / the page's body text height

    @property
    def misplaced(self) -> bool:
        return self.verdict in {"fine_print", "other_section"}

    def to_dict(self) -> dict:
        return asdict(self)


def _token_match(phrase: str, word: str) -> bool:
    # Short words must match exactly: 'nom' (surname) and 'nome' (given name) are different labels.
    return phrase == word if len(phrase) <= 4 else fuzz.ratio(phrase, word) >= 85


def find_labels(doc_type: str, page: Page) -> list[Label]:
    """Every label of this document type on the page. Where label phrases overlap, the longest wins:
    'due date' is not a 'date', and 'correspondence address' is not an 'address'."""
    keyed = [(text_key(w.text).split(), w) for w in page.words]
    tokens: list[tuple[str, Word]] = [(t, w) for ts, w in keyed for t in ts]
    found = []
    for field, phrases in LABELS.get(doc_type, {}).items():
        for phrase in phrases:
            want = phrase.split()
            for i in range(len(tokens) - len(want) + 1):
                if all(_token_match(p, tokens[i + k][0]) for k, p in enumerate(want)):
                    found.append((len(want), i, field, tokens[i:i + len(want)]))
    taken: set[int] = set()
    labels = []
    for n, i, field, span in sorted(found, key=lambda f: (-f[0], f[1])):
        if taken & set(range(i, i + n)):
            continue
        taken |= set(range(i, i + n))
        ws = list({id(w): w for _, w in span}.values())  # one OCR word can hold several tokens
        labels.append(Label(field, " ".join(w.text for w in ws), _union([w.bbox for w in ws])))
    return labels


def _union(boxes) -> tuple[float, float, float, float]:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _inside(inner, outer, tol: float = 1e-3) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and inner[2] <= outer[2] + tol
            and inner[3] <= outer[3] + tol)


def place(doc_type: str, field: str, bbox, page: Page) -> Place:
    """Where a found quote sits: see the module docstring."""
    # Body text: real words only, not OCR noise ('LI' read off a photo's face, at 45% confidence).
    heights = [w.bbox[3] - w.bbox[1] for w in page.words if w.bbox[3] > w.bbox[1] and len(text_key(w.text)) > 1
               and (w.conf is None or w.conf >= 60)]
    words = [w for w in page.words if _inside(w.bbox, bbox)]
    if not heights or not words:
        return Place("no_label")
    # The quote's first line: the words level with its topmost word. Its height is what the quote is printed in.
    top = min(words, key=lambda w: w.bbox[1])
    first = [w for w in words if w.bbox[1] < top.bbox[3] - 0.3 * (top.bbox[3] - top.bbox[1])]
    line = _union([w.bbox for w in first])
    h = max(w.bbox[3] - w.bbox[1] for w in first)
    body = sorted(heights)[int(BODY_PERCENTILE * (len(heights) - 1))]
    ratio = round(h / body, 2)
    if page.source == "text_layer" and len(text_key(" ".join(w.text for w in words)).replace(" ", "")) > 2 \
            and ratio < FINE_PRINT:
        return Place("fine_print", height_ratio=ratio)
    aspect = page.image.shape[0] / page.image.shape[1]  # page height / width, to measure both axes alike
    labels = find_labels(doc_type, page)
    # The lexicon matches the start of a label; the printed label runs on ('Indirizzo di domicilio' + 'effettivo
    # (incl. Stato)'). Extend each label over the rest of its run, but never over the quote.
    loose = sorted((w for w in page.words if text_key(w.text) and not _inside(w.bbox, bbox)), key=lambda w: w.bbox[0])
    for lab in labels:
        lx0, ly0, lx1, ly1 = lab.bbox
        for w in loose:
            level = min(w.bbox[3], ly1) - max(w.bbox[1], ly0) >= 0.5 * min(w.bbox[3] - w.bbox[1], ly1 - ly0)
            if level and w.bbox[0] >= lx1 - 0.002 and w.bbox[0] - lx1 <= 1.5 * (ly1 - ly0) * aspect:
                lx1 = w.bbox[2]
        lab.bbox = (lx0, ly0, lx1, ly1)
    label_boxes = [lab.bbox for lab in labels]
    # Words that can stand between a label and its value: real text, not the quote's or a label's own words.
    others = [w for w in loose if not any(_inside(w.bbox, lb) for lb in label_boxes)]
    # The printed line the quote sits in: a value can start mid-line ('New address from next month: <it>')
    # under a section label that sits above the start of the line, not above the value.
    row = list(line)
    same_line = lambda w: min(w.bbox[3], line[3]) - max(w.bbox[1], line[1]) >= 0.5 * min(w.bbox[3] - w.bbox[1], h)
    neighbours = sorted((w for w in page.words if text_key(w.text) and same_line(w)), key=lambda w: w.bbox[0])
    for w in reversed(neighbours):  # extend left while the gap is word spacing, not a column gap
        if w.bbox[2] <= row[0] + 0.002 and row[0] - w.bbox[2] <= 1.5 * h * aspect:
            row[0] = w.bbox[0]
    for w in neighbours:  # and right
        if w.bbox[0] >= row[2] - 0.002 and w.bbox[0] - row[2] <= 1.5 * h * aspect:
            row[2] = w.bbox[2]
    near = []  # (distance, label) for every label that stands before the quote with nothing in between
    for lab in labels:
        lx0, ly0, lx1, ly1 = lab.bbox
        if _inside(lab.bbox, bbox):  # a label inside the quote itself ('Payable by Anna Müller')
            continue
        d = None
        overlap = min(ly1, line[3]) - max(ly0, line[1])
        # To the left on the same line. A long label may run into the value's column ('Actual address of
        # domicile (incl. country)' in a narrow table cell), so it only has to start left of the value.
        if lx0 < line[0] and lx1 <= line[2] and overlap >= 0.3 * min(ly1 - ly0, h):
            between = [w for w in others if lx1 <= (w.bbox[0] + w.bbox[2]) / 2 <= line[0]
                       and line[1] <= (w.bbox[1] + w.bbox[3]) / 2 <= line[3]]
            if line[0] - lx1 <= MAX_LEFT_WIDTH and not between:
                d = max(0.0, line[0] - lx1)
        if d is None and ly1 <= line[1] + 0.3 * h and lx0 < row[2] and lx1 > row[0] - 0.02:  # above, overlapping in x
            between = [w for w in others if ly1 <= (w.bbox[1] + w.bbox[3]) / 2 <= line[1]
                       and w.bbox[0] < min(lx1, row[2]) and w.bbox[2] > max(lx0, row[0])]
            if line[1] - ly1 <= MAX_ABOVE_LINES * h and not between:
                d = max(0.0, line[1] - ly1) * aspect
        if d is not None:
            near.append((d, lab))
    if not near:
        return Place("no_label", height_ratio=ratio)
    # Its own label anywhere in reach is enough: rows sit close, so the label of the row above can be nearer
    # than the value's own. Other labels only count when none of its own is there.
    own = [n for n in near if n[1].field == field]
    _, best = min(own or near, key=lambda n: n[0])
    verdict = "anchored" if own else "other_section" if best.field == OTHER else "other_field"
    return Place(verdict, best.text, best.field, best.bbox, ratio)
