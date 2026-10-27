"""Azure AI Document Intelligence as an extractor: a commercial document parser to compare the LLMs with.

The rules baseline (English regexes on four-language forms) is easy to beat, so it says little about what
an LLM adds. A fairer comparison is a product a bank could buy instead. Azure's fits this problem best:

- its prebuilt ID model reads worldwide passports, MRZ included (AWS Textract's AnalyzeID and Google's
  identity processors only cover US documents)
- the 'query fields' add-on asks for named fields on any document, so the Form A and the bill need no
  custom model: we ask for 'BeneficialOwnerName', 'InvoiceDate' and so on
- every field comes back with the text it was read from ('content') and where it is. That is the same
  evidence our models return, so 'content' becomes the quote and grounding, the location check and the
  rules run unchanged

Spec: azure:prebuilt. Needs AZURE_DOCINTEL_ENDPOINT (https://<resource>.cognitiveservices.azure.com) and
AZURE_DOCINTEL_KEY, in the environment or .env. Responses are cached on disk like the LLM calls, and
KYC_OFFLINE=1 replays them. There is no injection report: Azure has no notion of one, so only the regex
detector runs (the eval shows what that costs).

The published results do not include it yet: no Azure account was available. The mapping follows the
2024-11-30 (v4.0 GA) REST API, and tests check it against a response of that shape, not against the service.
"""

import base64
import hashlib
import json
import os
import re
import time

import requests
from dotenv import dotenv_values

from .extract import LLM_CACHE, ROOT, Extraction, postprocess
from .read import Document
from .schemas import DOC_SCHEMAS, FieldValue
from .trace import Trace

API_VERSION = "2024-11-30"
PASSPORT_MODEL, QUERY_MODEL = "prebuilt-idDocument", "prebuilt-layout"
# Our field -> the prebuilt ID model's field.
PASSPORT_FIELDS = {"surname": "LastName", "given_names": "FirstName", "nationality": "Nationality",
                   "date_of_birth": "DateOfBirth", "sex": "Sex", "document_number": "DocumentNumber",
                   "expiry_date": "DateOfExpiration"}
# Our field -> the query field we ask for. The names are the whole prompt, so they say what is meant.
QUERY_FIELDS = {
    "form_a": {"contracting_partner": "ContractingPartnerName", "beneficial_owner_name": "BeneficialOwnerFullName",
               "beneficial_owner_date_of_birth": "BeneficialOwnerDateOfBirth",
               "beneficial_owner_nationality": "BeneficialOwnerNationality",
               "beneficial_owner_address": "BeneficialOwnerDomicileAddress"},
    "proof_of_address": {"name": "CustomerName", "address": "CustomerAddress", "issue_date": "InvoiceDate",
                         "issuer": "IssuingCompany"},
}
VALUE_KEYS = ("valueString", "valueDate", "valueCountryRegion", "valueNumber", "valueInteger")


def _setting(name: str) -> str:
    return os.getenv(name) or dotenv_values(ROOT / ".env").get(name) or ""


def field_value(f: dict | None) -> FieldValue:
    """One Azure field -> value, quote (the text it was read from) and page."""
    if not f:
        return FieldValue()
    value = next((str(f[k]) for k in VALUE_KEYS if f.get(k) not in (None, "")), None)
    quote = f.get("content") or value
    regions = f.get("boundingRegions") or []
    return FieldValue(value=value or quote, quote=quote, page=regions[0]["pageNumber"] if regions else None)


def mrz_lines(f: dict | None) -> tuple[str | None, str | None]:
    """The MRZ comes back as one object whose content is both lines; split it into two 44-character lines."""
    text = re.sub(r"\s+", "", (f or {}).get("content") or "")
    if len(text) == 88:
        return text[:44], text[44:]
    lines = [re.sub(r"\s+", "", l) for l in ((f or {}).get("content") or "").splitlines() if l.strip()]
    return (lines[0], lines[1]) if len(lines) == 2 else (None, None)


def to_fields(doc_type: str, result: dict) -> dict[str, FieldValue]:
    docs = (result.get("analyzeResult") or {}).get("documents") or []
    fields = docs[0].get("fields", {}) if docs else {}
    if doc_type == "passport":
        out = {ours: field_value(fields.get(theirs)) for ours, theirs in PASSPORT_FIELDS.items()}
        l1, l2 = mrz_lines(fields.get("MachineReadableZone"))
        page = field_value(fields.get("MachineReadableZone")).page or 1
        out["mrz_line1"] = FieldValue(value=l1, quote=l1, page=page if l1 else None)
        out["mrz_line2"] = FieldValue(value=l2, quote=l2, page=page if l2 else None)
        return out
    return {ours: field_value(fields.get(theirs)) for ours, theirs in QUERY_FIELDS[doc_type].items()}


class AzureExtractor:
    def __init__(self, variant: str = "prebuilt"):
        if variant != "prebuilt":
            raise ValueError(f"unknown Azure variant {variant!r} (only 'prebuilt')")
        self.name = f"azure:{variant}"
        self.endpoint = _setting("AZURE_DOCINTEL_ENDPOINT").rstrip("/")

    def request(self, doc_type: str) -> str:
        if doc_type == "passport":
            return f"{self.endpoint}/documentintelligence/documentModels/{PASSPORT_MODEL}:analyze?api-version={API_VERSION}"
        names = ",".join(QUERY_FIELDS[doc_type].values())
        return (f"{self.endpoint}/documentintelligence/documentModels/{QUERY_MODEL}:analyze"
                f"?api-version={API_VERSION}&features=queryFields&queryFields={names}")

    def call(self, url: str, data: bytes) -> dict:
        """Submit, poll until done, cache by a hash of the request (not of the key)."""
        key = hashlib.sha256((url.split("/documentintelligence/")[1]).encode() + data).hexdigest()
        cached = LLM_CACHE / f"azure_{key}.json"
        if cached.exists():
            return {**json.loads(cached.read_text()), "cached": True}
        if os.getenv("KYC_OFFLINE") == "1":
            raise RuntimeError("KYC_OFFLINE=1 and no cached response for this Azure request")
        if not self.endpoint or not _setting("AZURE_DOCINTEL_KEY"):
            raise RuntimeError("set AZURE_DOCINTEL_ENDPOINT and AZURE_DOCINTEL_KEY to use azure:prebuilt")
        headers = {"Ocp-Apim-Subscription-Key": _setting("AZURE_DOCINTEL_KEY")}
        start = time.perf_counter()
        r = requests.post(url, json={"base64Source": base64.b64encode(data).decode()}, headers=headers, timeout=120)
        if r.status_code != 202:
            raise RuntimeError(f"azure HTTP {r.status_code}: {r.text[:500]}")
        poll = r.headers["Operation-Location"]
        while True:
            time.sleep(1)
            j = requests.get(poll, headers=headers, timeout=60).json()
            if j.get("status") in {"succeeded", "failed"}:
                break
            if time.perf_counter() - start > 300:
                raise RuntimeError("azure analysis did not finish in 5 minutes")
        if j["status"] == "failed":
            raise RuntimeError(f"azure analysis failed: {json.dumps(j.get('error'))[:500]}")
        out = {"result": j, "seconds": round(time.perf_counter() - start, 2),
               "pages": len((j.get("analyzeResult") or {}).get("pages") or [])}
        LLM_CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(out))
        return {**out, "cached": False}

    def extract(self, doc_type: str, doc: Document, trace: Trace) -> Extraction:
        url = self.request(doc_type)
        with trace.step("llm", "Call Azure Document Intelligence", doc=doc_type,
                        code=("kyc_demo.azure.AzureExtractor.call", "kyc_demo.azure.to_fields"),
                        explain="The original file goes to the prebuilt ID model (passport) or to the layout model "
                                "with query fields (Form A, bill). Each field's 'content' becomes its quote.") as d:
            res = self.call(url, doc.path.read_bytes())
            data = DOC_SCHEMAS[doc_type](**to_fields(doc_type, res["result"]))
            d.update(endpoint=url, cached=res["cached"], seconds=res["seconds"], pages=res["pages"],
                     fields=data.model_dump())
        with trace.step("normalise", "Normalise values", doc=doc_type, code=("kyc_demo.extract.postprocess",),
                        explain="Dates to YYYY-MM-DD, countries to ISO alpha-3, whatever the source format.") as d:
            d["changes"] = postprocess(doc_type, data)
        # Billed per page; the price depends on the region and tier, so it is not guessed here.
        usage = {"seconds": res["seconds"], "pages": res["pages"], "cost_usd": None}
        return Extraction(data, FieldValue(), usage)
