import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from kyc_demo.evaluate import evaluate
from kyc_demo.mrz import build_td3, check_digit, parse_td3
from kyc_demo.read import read_pages
from kyc_demo.schemas import DOC_SCHEMAS, FieldValue
from kyc_demo.synth import generate
from kyc_demo.validate import enforce_evidence

AS_OF = date(2026, 10, 21)

# ICAO Doc 9303 part 4 specimen passport (Anna Maria Eriksson, Utopia).
ICAO_L1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
ICAO_L2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


class TruthExtractor:
    """Returns the ground truth as if extraction were perfect, quoting the value itself."""
    name = "truth"

    def __init__(self, case_dir: Path):
        self.truth = json.loads((case_dir / "truth.json").read_text())["fields"]

    def extract(self, doc_type, pages):
        return DOC_SCHEMAS[doc_type](**{k: FieldValue(value=v, quote=v, page=1)
                                        for k, v in self.truth[doc_type].items()})


class MrzTests(unittest.TestCase):
    def test_icao_specimen_check_digits(self):
        parsed = parse_td3(ICAO_L1, ICAO_L2, today=AS_OF)
        self.assertTrue(all(parsed["checks"].values()), parsed["checks"])
        self.assertEqual(parsed["surname"], "ERIKSSON")
        self.assertEqual(parsed["date_of_birth"], "1974-08-12")
        self.assertEqual(parsed["expiry_date"], "2012-04-15")

    def test_known_check_digits(self):
        self.assertEqual(check_digit("L898902C<"), "3")
        self.assertEqual(check_digit("740812"), "2")

    def test_build_round_trips_and_transliterates(self):
        l1, l2 = build_td3(issuing_state="UTO", surname="Müller", given_names="Anna Maria",
                           document_number="X1234567", nationality="CHE", birth=date(1994, 8, 12),
                           sex="F", expiry=date(2031, 4, 15))
        parsed = parse_td3(l1, l2, today=AS_OF)
        self.assertTrue(all(parsed["checks"].values()))
        self.assertEqual(parsed["surname"], "MUELLER")

    def test_corrupted_digit_is_caught(self):
        bad = ICAO_L2[:9] + "4" + ICAO_L2[10:]
        self.assertFalse(parse_td3(ICAO_L1, bad, today=AS_OF)["checks"]["document_number"])


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.cases = Path(cls.tmp.name)
        generate(cls.cases, AS_OF)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_rules_flag_exactly_the_planted_defect_given_perfect_extraction(self):
        for case in sorted(self.cases.iterdir()):
            truth = json.loads((case / "truth.json").read_text())
            r = evaluate_one(case)
            self.assertEqual(sorted({f["code"] for f in r["flags"]}), truth["expected_flags"], case.name)

    def test_hallucinated_value_is_dropped(self):
        case = sorted(self.cases.iterdir())[0]
        pages = read_pages(case / "passport.pdf")
        data = DOC_SCHEMAS["passport"](document_number=FieldValue(value="Z9999999", quote="Z9999999", page=1))
        flags = enforce_evidence("passport", data, pages)
        self.assertIsNone(data.document_number.value)
        self.assertEqual([f.code for f in flags], ["EVIDENCE_NOT_FOUND"])

    def test_rules_baseline_reads_every_passport(self):
        from kyc_demo.extract import RulesExtractor
        r = evaluate(self.cases, RulesExtractor(), AS_OF)
        passport = {k: v for k, v in r["fields"].items() if k.startswith("passport.")}
        self.assertTrue(all(v == 1.0 for v in passport.values()), passport)


def evaluate_one(case: Path) -> dict:
    """Validation only: skip the evidence check, since truth values are normalised, not verbatim."""
    from kyc_demo.validate import (check_cross_document, check_passport, check_required,
                                   check_suspicious_text)
    ex = TruthExtractor(case)
    docs = {d: ex.extract(d, []) for d in ("passport", "form_a", "proof_of_address")}
    flags = []
    for d, data in docs.items():
        flags += check_suspicious_text(d, read_pages(case / f"{d}.pdf"))
        flags += check_required(d, data)
    flags += check_passport(docs["passport"], AS_OF)
    flags += check_cross_document(docs["passport"], docs["form_a"], docs["proof_of_address"], AS_OF)
    return {"flags": [f.to_dict() for f in flags]}


if __name__ == "__main__":
    unittest.main()
