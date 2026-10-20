"""What we extract from each document type. Every field carries its evidence: the verbatim quote and page."""

from pydantic import BaseModel, Field


class FieldValue(BaseModel):
    value: str | None = None  # normalised (dates YYYY-MM-DD, countries ISO alpha-3)
    quote: str | None = None  # text copied verbatim from the document
    page: int | None = None   # 1-based


class PassportData(BaseModel):
    surname: FieldValue = Field(default_factory=FieldValue)
    given_names: FieldValue = Field(default_factory=FieldValue)
    nationality: FieldValue = Field(default_factory=FieldValue)
    date_of_birth: FieldValue = Field(default_factory=FieldValue)
    sex: FieldValue = Field(default_factory=FieldValue)
    document_number: FieldValue = Field(default_factory=FieldValue)
    expiry_date: FieldValue = Field(default_factory=FieldValue)
    mrz_line1: FieldValue = Field(default_factory=FieldValue)
    mrz_line2: FieldValue = Field(default_factory=FieldValue)


class FormAData(BaseModel):
    contracting_partner: FieldValue = Field(default_factory=FieldValue)
    beneficial_owner_name: FieldValue = Field(default_factory=FieldValue)
    beneficial_owner_date_of_birth: FieldValue = Field(default_factory=FieldValue)
    beneficial_owner_nationality: FieldValue = Field(default_factory=FieldValue)
    beneficial_owner_address: FieldValue = Field(default_factory=FieldValue)


class ProofOfAddressData(BaseModel):
    name: FieldValue = Field(default_factory=FieldValue)
    address: FieldValue = Field(default_factory=FieldValue)
    issue_date: FieldValue = Field(default_factory=FieldValue)
    issuer: FieldValue = Field(default_factory=FieldValue)


DOC_SCHEMAS: dict[str, type[BaseModel]] = {
    "passport": PassportData,
    "form_a": FormAData,
    "proof_of_address": ProofOfAddressData,
}

FIELD_HINTS = {
    "passport": {
        "surname": "surname from the visual zone, as printed",
        "given_names": "given names from the visual zone, as printed",
        "nationality": "ISO 3166-1 alpha-3 code",
        "date_of_birth": "YYYY-MM-DD",
        "sex": "M, F or X",
        "document_number": "passport number",
        "expiry_date": "YYYY-MM-DD",
        "mrz_line1": "first 44-character machine-readable line",
        "mrz_line2": "second 44-character machine-readable line",
    },
    "form_a": {
        "contracting_partner": "account holder name",
        "beneficial_owner_name": "beneficial owner's full name",
        "beneficial_owner_date_of_birth": "YYYY-MM-DD",
        "beneficial_owner_nationality": "ISO 3166-1 alpha-3 code",
        "beneficial_owner_address": "full domicile address",
    },
    "proof_of_address": {
        "name": "customer name",
        "address": "service or supply address",
        "issue_date": "document or invoice date, YYYY-MM-DD",
        "issuer": "company that issued the document",
    },
}


def llm_json_schema(doc_type: str) -> dict:
    """Flat JSON schema (no $ref) so local models with grammar-constrained decoding accept it."""
    field = {
        "type": "object",
        "properties": {
            "value": {"type": ["string", "null"]},
            "quote": {"type": ["string", "null"]},
            "page": {"type": ["integer", "null"]},
        },
        "required": ["value", "quote", "page"],
    }
    names = list(DOC_SCHEMAS[doc_type].model_fields)
    return {"type": "object", "properties": {n: field for n in names}, "required": names}
