"""The real suite: public specimen passports, photographed or scanned by someone else, labelled by hand.

Everything else here is drawn by our own code, so it can only show that the parts agree with each other.
These pages were not: they are real states' specimen data pages (sample persons, 'SPECIMEN'/'MUSTER'/
'ОБРАЗЕЦ' printed across them), with real security printing, real fonts and layouts, photographed or
scanned under conditions we did not choose. They test the passport path only (OCR, the MRZ pass and its
check digits, the visual zone, grounding), because no public source has real Form As or utility bills.

The images are not in the repository. Each entry has its Wikimedia Commons file, licence and author;
`python -m kyc_demo fetch-real` downloads them into cases/real/real_NNN/passport.jpg and writes truth.json.
The values were read off the images by hand, and every MRZ was checked against its check digits. The review
date is the common as_of, so a specimen that expired years ago is expected to raise PASSPORT_EXPIRED.

ICAO 9303 does not require an issuing state to print the nationality as a code, and these use words in the
national language ('BULGARIA', 'CYPRIOT', 'Fürstentum Liechtenstein'): the truth is the ISO code from the MRZ.
"""

import hashlib
import json
import time
from datetime import date
from pathlib import Path

import requests

COMMONS = "https://upload.wikimedia.org/wikipedia/commons"
USER_AGENT = "kyc-demo-research/0.1 (student project; https://github.com/besaif/lombard-kyc-extractor)"

# file on Commons, licence, author, true values, and what is printed for each value (for the oracle).
SPECIMENS = [
    {"file": "Bulgaria_passport_data_page_sample.jpg", "licence": "public domain", "author": "Government of Bulgaria",
     "fields": {"surname": "IVANOVA", "given_names": "MARITSA RADNEVA", "nationality": "BGR",
                "date_of_birth": "1985-08-01", "sex": "F", "document_number": "300000000",
                "expiry_date": "2015-03-20", "mrz_line1": "P<BGRIVANOVA<<MARITSA<RADNEVA<<<<<<<<<<<<<<<",
                "mrz_line2": "3000000001BGR8508018F15032098508010133<<<<54"},
     "printed": {"surname": "IVANOVA", "given_names": "MARITSA RADNEVA", "nationality": "BULGARIA",
                 "date_of_birth": "01.08.1985", "sex": "F", "document_number": "300000000",
                 "expiry_date": "20.03.2015"}},
    {"file": "Cypriot_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "POLITIS", "given_names": "ZINONAS", "nationality": "CYP", "date_of_birth": "1980-12-14",
                "sex": "M", "document_number": "L00000000", "expiry_date": "2030-06-15",
                "mrz_line1": "P<CYPPOLITIS<<ZINONAS<<<<<<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "L000000007CYP8012148M3006151<<<<<<<<<<<<<<08"},
     "printed": {"surname": "POLITIS", "given_names": "ZINONAS", "nationality": "CYPRIOT",
                 "date_of_birth": "14/12/1980", "sex": "M", "document_number": "L00000000",
                 "expiry_date": "15/06/2030"}},
    {"file": "Liechtenstein_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "WALCH", "given_names": "HANS PETER", "nationality": "LIE", "date_of_birth": "1953-09-05",
                "sex": "M", "document_number": "R00000", "expiry_date": "2016-12-26",
                "mrz_line1": "P<LIEWALCH<<HANS<PETER<<<<<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "R00000<<<9LIE5309052M1612262<<<<<<<<<<<<<<<0"},
     "printed": {"surname": "Walch", "given_names": "Hans Peter", "nationality": "Fürstentum Liechtenstein",
                 "date_of_birth": "05.09.1953", "sex": "M", "document_number": "R 00000",
                 "expiry_date": "26.12.2016"}},
    {"file": "Danish_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "ØSTERGÅRD", "given_names": "HANNE KRISTINE", "nationality": "DNK",
                "date_of_birth": "1985-06-09", "sex": "F", "document_number": "000000000",
                "expiry_date": "2031-10-01", "mrz_line1": "P<DNKOESTERGAARD<<HANNE<KRISTINE<<<<<<<<<<<<",
                "mrz_line2": "0000000000DNK8506092F3110016090685<9996<<<58"},
     "printed": {"surname": "ØSTERGÅRD", "given_names": "HANNE KRISTINE", "nationality": "DANSK/DANISH/DANOISE",
                 "date_of_birth": "09 06 85", "sex": "F", "document_number": "000000000",
                 "expiry_date": "01 10 31"}},
    {"file": "French_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "SPECIMEN ABB", "given_names": "NATACHA", "nationality": "FRA",
                "date_of_birth": "1973-07-12", "sex": "F", "document_number": "90RF02331",
                "expiry_date": "2029-03-03", "mrz_line1": "P<FRASPECIMEN<ABB<<NATACHA<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "90RF023318FRA7307122F2903035<<<<<<<<<<<<<<02"},
     "printed": {"surname": "SPECIMEN ABB", "given_names": "NATACHA", "nationality": "Française",
                 "date_of_birth": "12 07 1973", "sex": "F", "document_number": "90RF02331",
                 "expiry_date": "03 03 2029"}},
    {"file": "Greek_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "ELLINAS", "given_names": "GEORGIOS", "nationality": "GRC",
                "date_of_birth": "1975-05-15", "sex": "M", "document_number": "AA1234567",
                "expiry_date": "2033-12-10", "mrz_line1": "P<GRCELLINAS<<GEORGIOS<<<<<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "AA12345678GRC7505157M3312108<<<<<<<<<<<<<<06"},
     "printed": {"surname": "ELLINAS", "given_names": "GEORGIOS", "nationality": "ΕΛΛΗΝΙΚΗ / HELLENIC",
                 "date_of_birth": "15 MAY 1975", "sex": "M", "document_number": "AA1234567",
                 "expiry_date": "10 DEC 2033"}},
    # Born 1912, not 2012: the passport was issued in 2007, and the kennitala's last digit (9) is the 1900s.
    # The MRZ cannot say which century, and mrz._yymmdd reads '121212' as 2012.
    {"file": "Icelandic_passport_data_page_sample.jpg", "licence": "public domain", "author": "MonicasHouse",
     "fields": {"surname": "ÆVARSDÓTTIR", "given_names": "ÞURÍÐUR ÖSP", "nationality": "ISL",
                "date_of_birth": "1912-12-12", "sex": "F", "document_number": "A2040611",
                "expiry_date": "2011-06-29", "mrz_line1": "PAISLAEVARSDOTTIR<<THURIDUR<OESP<<<<<<<<<<<<",
                "mrz_line2": "A2040611<0ISL1212123F1106297121212<1239<<<66"},
     "printed": {"surname": "ÆVARSDÓTTIR", "given_names": "ÞURÍÐUR ÖSP",
                 "nationality": "ÍSLENSKT/ ICELANDIC/ ISLANDAISE", "date_of_birth": "12 DES /DEC 12",
                 "sex": "KVK /F", "document_number": "A2040611", "expiry_date": "29 JÚN /JUN 11"}},
    {"file": "Latvian_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "OZOLKALNA", "given_names": "LIENE MĀRA", "nationality": "LVA",
                "date_of_birth": "1964-11-18", "sex": "F", "document_number": "LV9903176",
                "expiry_date": "2033-11-23", "mrz_line1": "P<LVAOZOLKALNA<<LIENE<MARA<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "LV99031769LVA6411183F3311237327707<98976<<58"},
     "printed": {"surname": "OZOLKALNA", "given_names": "LIENE MĀRA", "nationality": "LATVIJAS",
                 "date_of_birth": "18.11.1964.", "sex": "S/F", "document_number": "LV9903176",
                 "expiry_date": "23.11.2033."}},
    {"file": "Maltese_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "MICALLEF", "given_names": "GIOVANNI", "nationality": "MLT",
                "date_of_birth": "1968-11-11", "sex": "M", "document_number": "0981489",
                "expiry_date": "2020-06-26", "mrz_line1": "P<MLTMICALLEF<<GIOVANNI<<<<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "0981489<<5MLT6811118M2006268<<<<<<<<<<<<<<06"},
     "printed": {"surname": "MICALLEF", "given_names": "GIOVANNI", "nationality": "MALTESE",
                 "date_of_birth": "11 NOV /NOV 1968", "sex": "M", "document_number": "0981489",
                 "expiry_date": "26 JUN /JUIN 2020"}},
    {"file": "Portuguese_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "GARÇÃO DE MAGALHÃES", "given_names": "INÊS", "nationality": "PRT",
                "date_of_birth": "1974-04-07", "sex": "F", "document_number": "I700044",
                "expiry_date": "2022-06-16", "mrz_line1": "P<PRTGARCAO<DE<MAGALHAES<<INES<<<<<<<<<<<<<<",
                "mrz_line2": "I700044<<9PRT7404076F220616199999999<<<<<<80"},
     "printed": {"surname": "GARÇÃO DE MAGALHÃES", "given_names": "INÊS", "nationality": "PORTUGUESA",
                 "date_of_birth": "07.04.1974", "sex": "F", "document_number": "I700044",
                 "expiry_date": "16.06.2022"}},
    # Born 1911: the MRZ's '111111' reads as 2011.
    {"file": "Slovak_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "SPECIMEN", "given_names": "VZORKA", "nationality": "SVK",
                "date_of_birth": "1911-11-11", "sex": "F", "document_number": "XR1231883",
                "expiry_date": "2034-09-18", "mrz_line1": "PPSVKSPECIMEN<<VZORKA<<<<<<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "XR12318830SVK1111112F34091871111111111<<<<06"},
     "printed": {"surname": "Specimen", "given_names": "Vzorka", "nationality": "Slovenská republika",
                 "date_of_birth": "11.11.1911", "sex": "F", "document_number": "XR1231883",
                 "expiry_date": "18.09.2034"}},
    # The passport number box is empty on this specimen: the number is only in the MRZ, so nothing is quoted for it.
    {"file": "Slovenian_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "VZOREC", "given_names": "ANA", "nationality": "SVN",
                "date_of_birth": "1978-11-18", "sex": "F", "document_number": "PB9006212",
                "expiry_date": "2026-12-12", "mrz_line1": "P<SVNVZOREC<<ANA<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "PB90062122SVN7811182F26121221811978505602<14"},
     "printed": {"surname": "Vzorec", "given_names": "Ana", "nationality": "Slovenije",
                 "date_of_birth": "18.11.1978", "sex": "Ž", "expiry_date": "12.12.2026"}},
    {"file": "Spanish_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "ESPAÑOLA ESPAÑOLA", "given_names": "CARMEN", "nationality": "ESP",
                "date_of_birth": "1980-01-01", "sex": "F", "document_number": "ZAB000254",
                "expiry_date": "2025-01-01", "mrz_line1": "P<ESPESPANOLA<ESPANOLA<<CARMEN<<<<<<<<<<<<<<",
                "mrz_line2": "ZAB0002549ESP8001014F2501017A9999999900<<<44"},
     "printed": {"surname": "ESPAÑOLA ESPAÑOLA", "given_names": "CARMEN", "nationality": "ESPAÑOLA",
                 "date_of_birth": "01 01 1980", "sex": "F", "document_number": "ZAB000254",
                 "expiry_date": "01 01 2025"}},
    {"file": "Swiss_passport_data_page_sample.jpg", "licence": "CC BY-SA 4.0", "author": "MonicasHouse",
     "fields": {"surname": "DE MAIENFELD", "given_names": "PIERRE", "nationality": "CHE",
                "date_of_birth": "1971-08-01", "sex": "M", "document_number": "S2100023",
                "expiry_date": "2020-02-29", "mrz_line1": "PMCHEDE<MAIENFELD<<PIERRE<<<<<<<<<<<<<<<<<<<",
                "mrz_line2": "S2100023<6CHE7108019M2002293<<<<<<<<<<<<<<<6"},
     "printed": {"surname": "de Maienfeld", "given_names": "Pierre",
                 "nationality": "Schweiz Suisse Svizzera Svizra Switzerland", "date_of_birth": "01.08.1971",
                 "sex": "M", "document_number": "S2100023", "expiry_date": "29.02.2020"}},
    {"file": "Dutch_passport_specimen_issued_9_March_2014.jpg", "licence": "CC0",
     "author": "Rijksdienst voor Identiteitsgegevens (RvIG)",
     "fields": {"surname": "DE BRUIJN", "given_names": "WILLEKE LISELOTTE", "nationality": "NLD",
                "date_of_birth": "1965-03-10", "sex": "F", "document_number": "SPECI2014",
                "expiry_date": "2024-03-09", "mrz_line1": "P<NLDDE<BRUIJN<<WILLEKE<LISELOTTE<<<<<<<<<<<",
                "mrz_line2": "SPECI20142NLD6503101F2403096999999990<<<<<84"},
     "printed": {"surname": "De Bruijn", "given_names": "Willeke Liselotte", "nationality": "Nederlandse",
                 "date_of_birth": "10 MAA/MAR 1965", "sex": "V/F", "document_number": "SPECI2014",
                 "expiry_date": "09 MAA/MAR 2024"}},
    {"file": "Norwegian_Passport_Specimen.jpg", "licence": "public domain", "author": "Government of Norway",
     "fields": {"surname": "ØSTENBYEN", "given_names": "ÅSAMUND SPECIMEN", "nationality": "NOR",
                "date_of_birth": "1956-04-23", "sex": "M", "document_number": "CCC002251",
                "expiry_date": "2030-04-15", "mrz_line1": "P<NOROESTENBYEN<<AASAMUND<SPECIMEN<<<<<<<<<<",
                "mrz_line2": "CCC0022514NOR5604230M3004157<<<<<<<<<<<<<<04"},
     "printed": {"surname": "ØSTENBYEN", "given_names": "ÅSAMUND SPECIMEN", "nationality": "NORSK/ NORWEGIAN",
                 "date_of_birth": "23 APR /APR 56", "sex": "M", "document_number": "CCC002251",
                 "expiry_date": "15 APR /APR 30"}},
]


def commons_url(name: str) -> str:
    h = hashlib.md5(name.encode()).hexdigest()
    return f"{COMMONS}/{h[0]}/{h[:2]}/{name}"


def fetch(out: Path, as_of: date) -> list[Path]:
    """Download every specimen (politely: Wikimedia rate-limits shared addresses) and write its truth.json."""
    dirs = []
    for i, s in enumerate(SPECIMENS, start=1):
        d = out / "real" / f"real_{i:03d}"
        d.mkdir(parents=True, exist_ok=True)
        img = d / "passport.jpg"
        for attempt in range(6):
            if img.exists() and img.stat().st_size > 20_000:
                break
            r = requests.get(commons_url(s["file"]), headers={"User-Agent": USER_AGENT}, timeout=60)
            if r.ok:
                img.write_bytes(r.content)
                break
            time.sleep(int(r.headers.get("retry-after", 10)) * (attempt + 1))
        else:
            print(f"  could not download {s['file']} (HTTP {r.status_code}); try again later")
            continue
        expired = date.fromisoformat(s["fields"]["expiry_date"]) < as_of
        defects = ["PASSPORT_EXPIRED"] if expired else []
        mrz = {k: s["fields"][k] for k in ("mrz_line1", "mrz_line2")}
        truth = {"case": d.name, "suite": "real", "tier": "real", "as_of": as_of.isoformat(), "defects": defects,
                 "expected_flags": defects, "expected_checks": ["passport.not_expired"] if expired else [],
                 "traps": [], "layouts": {"passport": s["file"].split("_")[0]},
                 "source": {"file": f"https://commons.wikimedia.org/wiki/File:{s['file']}", "licence": s["licence"],
                            "author": s["author"]},
                 "fields": {"passport": s["fields"]}, "printed": {"passport": {**s["printed"], **mrz}}}
        (d / "truth.json").write_text(json.dumps(truth, indent=2, ensure_ascii=False))
        dirs.append(d)
        time.sleep(3)
    return dirs
