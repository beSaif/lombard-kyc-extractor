# KYC extractor (learning prototype)

AI-assisted KYC document processing on realistic synthetic files: read a client's passport, Form A and
proof of address (clean PDFs, scans or phone photos), extract the fields a compliance officer needs, verify
them, and route the file to the right review queue. A web UI replays every step of a run, with the inputs,
outputs and source code of each one.

**The idea in one line:** the model proposes, deterministic rules verify, and a human decides. Every value
carries the exact quote it came from and where that quote sits on the page.

## Quick start

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install tesseract tesseract-lang      # OCR, with French/German/Italian
echo "OPENAI_API_KEY=sk-..." > .env        # optional; `openai_key=` also works
ollama pull qwen2.5vl:7b                   # optional local vision model

python -m kyc_demo generate                # 30 cases x 3 tiers in cases/{clean,scan,photo}/
python -m kyc_demo run cases/photo/case_016 -e openai:gpt-5.4-mini@both
python -m kyc_demo eval -e rules -e openai:gpt-5.4-mini@both --tiers photo
python -m kyc_demo compare                 # results/comparison.md from every saved eval
python -m pytest -q tests

# Web UI
python -m kyc_demo serve                   # API on :8000 (serves web/dist when built)
cd web && pnpm install && pnpm dev         # UI on :5173 (proxies to :8000)
```

### Switching models

One spec string picks the extractor: `provider:model@input`.

| Spec | What the model sees |
| --- | --- |
| `rules` | Regexes on the OCR text, English labels only. The baseline |
| `openai:gpt-5.4-mini@text` | OCR / text-layer text only |
| `openai:gpt-5.4-mini@vision` | Page images only |
| `openai:gpt-5.4-mini@both` | Page images plus the OCR text as a hint |
| `ollama:qwen2.5vl:7b@both` | The same, on a local model: client data never leaves the machine |

`--second <spec>` runs a second model on every document and sends disagreements to a human.

## The web UI

`python -m kyc_demo serve` and open http://localhost:8000 (or `pnpm dev` in `web/` for development).

- **Pipeline**: pick a case, a tier and a model, press Run, and watch the steps arrive live. Each step shows
  what went in and what came out: the original and flattened images, the OCR word boxes coloured by
  confidence, the exact prompt, schema and HTTP body, the raw model reply, normalisation before/after, every
  quote's match score and box on the page, every validation check with its inputs (passed ones too), the
  corroboration chain and the routing decision. Next to each step: the source of the functions that ran,
  read live from the code. A summary compares the result with the ground truth.
- **Evals**: every saved eval side by side, per tier, with per-defect, per-trap and per-field grids; click
  a case to replay it.
- **Dataset**: every case in all three tiers, with its defects and traps explained.
- **Code**: the whole package, with a pipeline map linking each stage to its function.

## The data: why it is harder now

Each of the 30 cases is one person with three documents, rendered three times so that image quality is the
only thing that changes:

| Tier | Passport | Form A | Proof of address |
| --- | --- | --- | --- |
| clean | crisp 300 dpi scan | crisp scan, handwritten answers | born-digital PDF (text layer) |
| scan | grey, rotated, noisy 150 dpi, no text layer | same | same |
| photo | phone photo: perspective, shadow, blur, JPEG | same | same |

- **Realistic layouts.** The passport is a TD3 data page: labels above values, bilingual dates
  (`19 JUN/JUIN 1961`), a demonym (`SWISS`) instead of a code, and an MRZ. Form A has handwritten answers in
  English, French, German or Italian, in two layouts. Bills have an unlabelled address window, an invoice
  table and a QR-bill receipt that repeats the payer.
- **Defects** (must be flagged): expired passport, a wrong MRZ check digit, printed date of birth altered
  but MRZ left alone, a bill in a family member's name, a different address or house number, day and month
  swapped on Form A, a different nationality, a stale bill, and prompt injection hidden in Form A remarks or
  the bill's fine print. Some files have two.
- **Traps** (must *not* be flagged): a bill without the middle name, `MÜLLER Anna Maria`, `Muller` for
  `Müller`, `Av.` for `Avenue`, `Geneva` / `CH-1204` for `Genève`, `12, rue des Exemples`, a bill 85 days old
  when the limit is 90, a passport valid for 3 more weeks.

## The pipeline

```
per document:  load -> flatten + even out light -> OCR (2 passes + MRZ pass) -> prompt -> model
               -> normalise -> reconcile MRZ -> ground every quote on the page
per file:      validation rules -> corroboration -> route
```

| Step | Code | What happens, and the lesson in it |
| --- | --- | --- |
| Load | `read.load_pages` | PDFs rendered at 200 dpi; the text layer read with word positions if there is one |
| Flatten | `read.flatten_document` | Find the page's four corners and undo the perspective. Photos only |
| Even out light | `read.even_out_light` | Tesseract binarises with one threshold, so text in a shadow vanished. Dividing by a blurred background fixed it |
| OCR | `read.ocr_page`, `read.read_mrz` | Two Tesseract passes merged: layout mode reads print, sparse mode catches handwriting. A third pass reads only the MRZ, restricted to its 37 characters |
| Prompt | `extract.build_user_prompt` | Field hints, the document as untrusted data, and a strict JSON schema. Documents may contain text aimed at the model |
| Model | `extract.LLMExtractor` | One request, two providers. OpenAI strict `json_schema`; Ollama `format` with `num_ctx` raised, since its small default context truncates silently. Invalid JSON gets one retry with the error. Disk cache keyed on the exact request |
| Normalise | `extract.postprocess`, `normalise.py` | Dates in 8 formats and 4 languages to ISO; `SWISS`, `Svizzera`, `CH` to `CHE` |
| Reconcile MRZ | `mrz.reconcile` | Models miscount `<<<<<<` runs (tokenisation), so the MRZ comes from whichever reading passes its check digits; filler length is repaired, never letters or digits |
| Ground | `ground.locate`, `validate.ground_fields` | Each quote is fuzzy-matched against the OCR words (threshold 85), which gives evidence a box on the page. A date whose quote says something else is dropped |
| Validate | `validate.py`, `mrz.py` | MRZ check digits (ICAO 9303), MRZ vs printed page, expiry, names / dates / nationality / address across documents, bill age, injection (regex + the model as a second detector). Every check is recorded, passed or not |
| Corroborate | `validate.corroborate` | A value OCR could not find (handwriting) is trusted if a passing check ties it to a verified value elsewhere: MRZ -> passport DOB -> Form A DOB. Safe because documents are extracted separately |
| Route | `pipeline.run_case` | No failed check: pre-filled review. Otherwise the manual queue, with reasons. A human signs off either way |

## Results

Full tables per tier: [`results/comparison.md`](results/comparison.md). Photo tier, 30 files (19 defects
planted in 16 files, 46 traps), review date 2026-10-21:

| Metric | rules | gpt-5.4-mini text | gpt-5.4-mini vision | gpt-5.4-mini both | gpt-4.1-mini both | gpt-5.5 both | 5.4-mini + 4.1-mini cross-check |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Field accuracy | 35% | 79% | 99% | 99% | 99% | 99% | 99% |
| Defect recall | 37% | 79% | 100% | 100% | 100% | 100% | 100% |
| Defect precision | 64% | 47% | 90% | 90% | 86% | 90% | 90% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files) | 0% | 0% | 86% | 79% | 57% | 79% | 71% |
| Trap false-alarm rate | 0% | 11% | 0% | 0% | 2% | 2% | 0% |
| Model seconds per file | 0 | 9.3 | 9.3 | 8.4 | 8.4 | 9.2 | 16.7 |
| $ per file | 0 | $0.007 | $0.011 | $0.011 | $0.005 | $0.060 | $0.016 |

Local models on the same 30 photo files (M3 Pro, 18 GB; nothing leaves the laptop):

| Metric | qwen2.5:7b text | qwen2.5vl:7b both | qwen2.5vl:7b both, regex-only injection | gpt-5.4-mini both |
| --- | --- | --- | --- | --- |
| Field accuracy | 69% | 99% | 99% | 99% |
| Defect recall | 47% | 100% | 95% | 100% |
| Defect precision | 27% | 48% | 78% | 90% |
| Straight-through (clean files) | 0% | 29% | 64% | 79% |
| Trap false-alarm rate | 15% | 7% | 7% | 0% |
| Model seconds per file | 39 | 76 | 76 | 8.4 |
| $ per file | 0 | 0 | 0 | $0.011 |

A 7B open-weight vision model running locally extracts as well as `gpt-5.4-mini` on phone photos, at about
9x the latency on a laptop GPU. It is weaker as a judge: asked to report injected instructions, it reported
the Form A's legal penalty warning on every Form A, ignoring "legal notices are not this" in the prompt. With
the model detector switched off for it (`KYC_MODEL_INJECTION_DETECTOR=off`; the regex still runs)
straight-through more than doubles, but the fine-print injection that only the model can read gets through.
A detector has to be validated for each model.

What the numbers say:

- **The image matters more than the model.** Text-only extraction loses 20 points because OCR cannot read
  handwriting; any vision mode recovers them. `gpt-5.5` costs 6x `gpt-5.4-mini` and buys nothing here.
- **Every planted defect is caught with a vision mode.** The last one to fall was a 6-pt injection that OCR
  cannot read on a scan or a photo, but the vision model can (see below). Text-only and rules still miss it.
- **Remaining false alarms are handwriting misreads** (`3011` read as `2011`, `14` as `17`). They are
  harmless in the sense that matters: they send a clean file to a human, never a bad file to the quick queue.
- **A second model did not pay off here.** The cross-check costs 1.5x and lowers straight-through (71% vs
  79%) without catching anything the rules missed. Its only new flag came from the weaker model misreading
  an MRZ. A second opinion is only as useful as the second model, and it must be compared like with like:
  my first version compared the primary's reconciled MRZ with the second model's raw one and flagged
  disagreements that were not there.
- **Recall before precision.** No configuration sent a file with a detectable defect to the quick queue. The
  cost of the design is in straight-through: about 1 clean file in 5 still goes to manual review.

## What broke, and what it taught

Each of these showed up in a trace or an eval, and the fix is in the code. They are the real content of
this project.

| What we saw | Why | Fix |
| --- | --- | --- |
| On a photo, the left third of a bill vanished from the OCR text | A shadow pushed the text under Tesseract's single global threshold | Estimate the lighting (dilate, then a large median blur) and divide it out before OCR |
| Correct handwritten values were rejected as "not on the page" | Tesseract's layout mode skips handwriting; the vision model read it fine | Merge a sparse-text pass (`--psm 11`); keep unfound values as *unverified*, and let cross-document agreement *corroborate* them |
| A handwritten `19.06.1961` came back from OCR as `49.06.1964` | Classic 1/4 confusion on handwriting; fuzzy matching (score 80) cannot safely absorb two wrong digits in eight | Threshold left at 85; the value is corroborated by the passport instead |
| `25.08.2026` was "not found" even though OCR had it | My bug: the window size counted normalised tokens (3), while OCR had one word | Try every window size from one word up |
| Valid passports failed their MRZ checksums | Models miscount runs of `<`: `<<<<<<<<` is a few tokens of unknown length | The MRZ is machine-checkable, so don't trust the model's copy: prefer whichever reading passes its check digits, and repair filler (never letters or digits) |
| OCR read MRZ chevrons as `K`, `E`, `S`; a `B` sat where a check digit should be | Generic OCR alphabet | A dedicated MRZ pass with a 37-character whitelist, position-aware fixes (`B`->`8` only where ICAO allows only digits), and line-1 tail cleanup (no name contains `<<<`) |
| A model returned nulls for every beneficial-owner field on one Form A | It reasoned that "the contracting partner is the sole beneficial owner" was ticked, so the person section did not apply | Domain context in the field hint: fill the person section whenever it is written in |
| **`gpt-5.5` hid a forgery.** The printed date of birth was altered, the MRZ was not; the model took the date from the MRZ, so the mismatch never fired | Capable models silently reconcile conflicting evidence | Extraction must be literal ("as printed in the visual zone, never from the MRZ"). Reconciling is the rules' job. All models now catch it |
| Italian and Swedish passports came back as `CHE` on noisy scans | My hint's one example, `(SWISS -> CHE)`, primed the answer | The model copies the nationality as printed; code maps it to ISO |
| Qwen 2.5-VL flagged the Form A's legal penalty warning as prompt injection | Small models over-report when asked to detect "instructions" | Tighter definition in the hint: legal notices and form instructions are not injection |
| Injection in 6-pt grey fine print was missed on scans and photos, by every model | OCR turns it to noise, so the regex misses it. The vision model read it and reported it, but its report was dropped: grounding could not find the quote in the OCR words | A safety flag fails safe: an ungrounded model report still raises it when the quote itself matches the injection patterns. Ordinary text the model over-reports (legal warnings) is still dropped |
| The passport's `F` under "Sex / Sexe" was never found on the page, on every tier | Tesseract puts a lone character into the text line of the small label just above it, then discards it as an outlier. Erasing the label brings it back at confidence 93 | Fields the MRZ repeats (sex, nationality, dates, document number) are verified against the dedicated MRZ pass at their fixed position, only when the check digit covering them passes |
| `@text` mode was ~15 points worse than `@vision` / `@both` | The OCR text is the bottleneck on handwriting (`Natr` for `Nair`) | For handwritten forms, show the model the image |

## Limitations

- Synthetic data. Real scans have stamps, folds, glare, holograms and handwriting far worse than a font.
- One person per file; no companies, trusts, or several beneficial owners.
- 30 cases per tier is enough to see failure modes, not to give tight confidence intervals.
- The 90-day proof-of-address rule is an assumed policy.
- Corroboration trusts cross-document agreement; a forger who fakes every document consistently passes it,
  which is why identity verification in practice adds liveness checks and registry lookups.
