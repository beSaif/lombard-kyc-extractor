# KYC extractor (demo)

A small prototype of AI-assisted KYC document processing: read a client's onboarding documents,
extract the fields a compliance officer needs, check them, and route the file to the right review queue.
Everything runs on synthetic data.

**The idea in one line:** the model proposes, deterministic rules verify, and a human decides.
Every extracted value carries the exact quote and page it came from.

## Quick start

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m kyc_demo generate                 # 13 synthetic client files in cases/
python -m kyc_demo eval --backend rules     # regex baseline, no model needed
python -m kyc_demo run cases/case_013       # one file: fields, evidence, flags, routing

# Local open-weight model (client data never leaves the machine)
ollama pull qwen2.5:7b
python -m kyc_demo eval --backend ollama --report results/ollama.md

python -m pytest -q tests
```

Any OpenAI-compatible endpoint also works: `--backend openai`, with `OPENAI_BASE_URL`,
`OPENAI_API_KEY` and `KYC_MODEL`.

## How it works

```
PDF -> read pages -> extract (rules | local LLM) -> enforce evidence -> validate -> route
```

| Step | File | What it does |
| --- | --- | --- |
| Synthetic data | `kyc_demo/synth.py` | Passport, Form A and utility bill per client, in English or French layouts. Each defective case breaks exactly one rule; `truth.json` holds the answers. |
| Read | `kyc_demo/read.py` | PDF text layer per page. An OCR engine would plug in here for scans. |
| Extract | `kyc_demo/extract.py` | Pydantic schema per document type. The LLM gets a JSON schema it must fill (value, verbatim quote, page) and is told document text is data, not instructions. |
| Evidence | `kyc_demo/validate.py` | Any value whose quote is not literally in the document is dropped and flagged. This is the hallucination guard. |
| Validate | `kyc_demo/validate.py`, `kyc_demo/mrz.py` | Passport MRZ check digits (ICAO 9303), MRZ against the printed page, expiry date, name/DOB/nationality/address across documents, proof-of-address age, instruction-like text. |
| Route | `kyc_demo/pipeline.py` | No flags: pre-filled review. Any flag: manual review. A compliance officer signs off either way. |
| Evaluate | `kyc_demo/evaluate.py` | Field accuracy, flag precision and recall, routing accuracy against ground truth. |

## Results so far

Rules baseline (`results/rules.md`), 13 files, as of 2026-10-21:

| Metric | Rules baseline | Local LLM |
| --- | --- | --- |
| Field accuracy | 66.7% | run it |
| Flag precision | 26.7% | run it |
| Flag recall | 57.1% | run it |
| Routing accuracy | 61.5% | run it |

The baseline reads every passport perfectly, because passports are standardised and the MRZ can be
parsed deterministically. It fails on the French Form A and bill layouts it has never seen. Those gaps
then show up as false "missing field" flags and missed defects. That gap is exactly what the LLM
extractor is for.

The test suite checks the MRZ code against the ICAO specimen passport, and checks that with perfect
extraction the validators flag exactly the planted defect in all 13 cases and nothing else.

## Design choices worth discussing

- **Deterministic where possible, LLM where needed.** MRZ parsing and checksums beat any model on
  passports. The LLM earns its place on free-form, multilingual documents.
- **Evidence or nothing.** A value without a verbatim quote is rejected, so the model cannot invent a
  date of birth.
- **Local model by default.** Banking secrecy and the Swiss data protection act favour keeping client
  documents on bank infrastructure.
- **Prompt injection is a KYC risk.** Uploaded documents are attacker-controlled. Case 13 hides an
  instruction in a utility bill; it is flagged, and the prompt treats document text as data.
- **Errors are not equal.** Missing a beneficial owner costs far more than a false alarm, so the
  routing leans toward human review.

## Limitations

- Synthetic, text-layer PDFs only: no scans, handwriting, stamps or photos yet.
- One person per file; no companies, trusts or multiple beneficial owners.
- 13 cases is a smoke test, not a benchmark.
- The 90-day proof-of-address rule is an assumed policy, not a regulatory requirement.

## Next steps

1. OCR or a vision-language model for scanned documents, with noisy scans in the synthetic set.
2. Corporate clients: register extracts, multiple beneficial owners, control chains.
3. A review screen showing each value next to its highlighted quote.
4. A larger labelled set, with per-field confidence and thresholds tuned on it.
