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
