# Evaluation: rules

13 synthetic client files, as of 2026-10-21.

| Metric | Value |
| --- | --- |
| Field accuracy | 66.7% |
| Flag precision | 26.7% |
| Flag recall | 57.1% |
| Routing accuracy | 61.5% |

| Case | Planted defect | Layouts (Form A / bill) | Routed to | Flags raised |
| --- | --- | --- | --- | --- |
| case_001 | none | fr / en | manual_review | MISSING_FIELD |
| case_002 | none | fr / en | manual_review | MISSING_FIELD |
| case_003 | none | en / en | pre_filled_review | - |
| case_004 | none | en / fr | manual_review | MISSING_FIELD |
| case_005 | none | fr / fr | manual_review | MISSING_FIELD |
| case_006 | none | fr / fr | manual_review | MISSING_FIELD |
| case_007 | PASSPORT_EXPIRED | fr / fr | manual_review | MISSING_FIELD, PASSPORT_EXPIRED |
| case_008 | MRZ_CHECK_FAILED | fr / en | manual_review | MISSING_FIELD, MRZ_CHECK_FAILED |
| case_009 | NAME_MISMATCH | fr / fr | manual_review | MISSING_FIELD |
| case_010 | ADDRESS_MISMATCH | fr / en | manual_review | MISSING_FIELD |
| case_011 | PROOF_OF_ADDRESS_TOO_OLD | fr / fr | manual_review | MISSING_FIELD |
| case_012 | DOB_MISMATCH | en / en | manual_review | DOB_MISMATCH |
| case_013 | SUSPICIOUS_INSTRUCTIONS | fr / fr | manual_review | MISSING_FIELD, SUSPICIOUS_INSTRUCTIONS |

| Field | Accuracy |
| --- | --- |
| form_a.beneficial_owner_address | 23% |
| form_a.beneficial_owner_date_of_birth | 23% |
| form_a.beneficial_owner_name | 23% |
| form_a.beneficial_owner_nationality | 23% |
| form_a.contracting_partner | 23% |
| passport.date_of_birth | 100% |
| passport.document_number | 100% |
| passport.expiry_date | 100% |
| passport.given_names | 100% |
| passport.mrz_line1 | 100% |
| passport.mrz_line2 | 100% |
| passport.nationality | 100% |
| passport.sex | 100% |
| passport.surname | 100% |
| proof_of_address.address | 46% |
| proof_of_address.issue_date | 46% |
| proof_of_address.issuer | 46% |
| proof_of_address.name | 46% |
