# KYC extractor (learning prototype)

I built this to learn how you'd actually use an LLM for KYC onboarding without trusting it blindly. You
give it a client's file (passport, Form A and proof of address, as clean PDFs, scans or phone photos) and
it pulls out the fields a compliance officer needs, checks them, and sends the file to the right review
queue. All the client data is synthetic, and every case comes with a `truth.json` (the correct values, the
problems I planted, and the flags a good run should raise), which is what I score each run against.

There's also a small web UI that replays a run step by step, so you can see what went into each stage,
what came out, and the code that ran.

How I went about it:

- First I needed data. I didn't want to use real client documents, so I wrote a generator
  (`kyc_demo/synth.py`) that makes up 30 fictional people and draws their paperwork with reportlab. The
  passports are issued by ICAO's specimen country "Utopia" and say SPECIMEN across the page, so nothing
  here could pass for a real document.
- Each person gets three files: a passport, a Form A and a utility bill as proof of address.
  - The passport is a proper TD3 data page with an MRZ.
  - The Form A is filled in by "hand" (a handwriting font), in English, French, German or Italian.
  - The bill looks like a normal Swiss bill, with an address window and a QR receipt.

  Here's `case_001` (clean tier). The bill says "Anna Müller" and "Berne" where the passport has "Anna
  Maria" and the form has "Bern", and the passport expires in three weeks. None of that should be flagged.

  <p>
    <img src="docs/examples/passport.png" alt="Passport data page" width="32%">
    <img src="docs/examples/form_a.png" alt="Form A, handwritten in Italian" width="32%">
    <img src="docs/examples/proof_of_address.png" alt="Utility bill as proof of address" width="32%">
  </p>

- Next to them sits a `truth.json` that says what the right values are, which problems I planted on
  purpose (an expired passport, a wrong MRZ check digit, a bill in someone else's name, a prompt injection
  hidden in the fine print, and so on) and which harmless differences should _not_ be flagged, like `Av.`
  for `Avenue` or a missing middle name.
- The same three documents are rendered again as a noisy grey scan and as a phone photo with shadows and
  blur, so the only thing that changes between them is image quality.
- Then I built a web UI to load these cases and watch them go through the pipeline. You pick a case, a
  quality level and a model, press Run, and each step shows up as it happens:
  - the pages are loaded, and photos get flattened and their lighting evened out
  - Tesseract OCR reads the text, with a separate pass just for the MRZ
  - the page image and the OCR text go to the model, which returns the fields as JSON with a quote for each
  - each value has to match its own quote, and each quote is looked up on the page, so every value has a box
    you can point at (more on what "verified" means below)
  - a pixel check looks for ink on the Form A signature line
  - plain rules check everything against everything else (MRZ check digits, expiry, names and dates across
    the three documents, who the account holder and the beneficial owner are, how old the bill is) and
    decide which review queue the file goes to. A check that could not run counts as a flag, never a pass
- Last, a compliance officer reviews the file in the same UI: accept or correct each value next to its box,
  then sign off. Approval takes two different people, and every action goes into an audit log.

Here's the whole pipeline in one picture (the source is `docs/pipeline.excalidraw` if you want to open it
in Excalidraw and change it):

![How one case goes through the pipeline](docs/pipeline.png)

## What "verified" means

Every value comes back with a quote. A value only counts as verified when two things hold:

- **The quote says the value.** The quote "Anna Müller" doesn't back up the value "Hans Muster", and
  "25.08.2026" doesn't back up 2025-08-25. If the quote says something else, the value is dropped. If it's
  only close (the model copied an OCR misreading like "Cuca" into the quote but read "Luca" off the image),
  the value is kept but stays unverified.
- **The quote is on the page.** It's fuzzy-matched against the OCR words, because OCR misreads letters. But
  digits have to match exactly. "Musterweg 51" scores 92 against "Musterweg 57", and one digit off is a
  different house, date or passport.

Each verified value also says what it rests on. `text_layer` means the PDF's own text. `ocr` means Tesseract
read the same thing, but in `text` and `both` mode the model was shown that OCR text, so this is agreement
with OCR, not two independent readings. `checksum` means the MRZ check digits pass, and that's the one check
neither OCR nor the model can fake. Unverified values go to a person unless a passing check on another
document backs them up. When I measured it, that's where most of the real catching happens: the
cross-document checks, more than the quotes.

## Two test suites

The 30 standard cases show the pipeline working. The 16 cases in the hard suite (`hard_001` to `hard_016`)
are built to break it:

- a defect hidden inside a trap ("Av." and a wrong house number)
- every limit right at its edge (a bill 90 and 91 days old, a passport expiring today)
- one-digit changes (a date of birth, a printed passport number that's one digit off the MRZ)
- prompt injections in wordings and languages the regex never saw
- Form A cases the standard suite doesn't have: someone else as beneficial owner, no signature, an account
  in another person's name
- two held-out cases (a Canadian, Luzern written as Lucerne) that the country and city tables were never
  given. They're expected to fail, and I'm leaving them that way on purpose: they show how far the tables
  go, and fixing them would just be tuning to the test.

The hard suite has its own random seed, so adding it didn't change a single page of the standard 30.
Recall comes with a 95% interval, because with 19 planted defects, 19 out of 19 only tells you recall is
probably above 83%.

## Results

All the numbers are in `results/comparison.md`. Here are the main ones.

Standard suite (14 clean files and 16 with defects, holding 19 defects, per quality level):

| | gpt-5.4-mini, both | qwen2.5vl:7b, both (local, photos only) | rules |
| --- | --- | --- | --- |
| Defects flagged | 19/19 at every quality (95% interval 83-100%) | 19/19 | 6-8 of 19 |
| Defect files sent to the quick queue | 0 of 16 | 0 of 16 | 0 of 16 |
| Clean files straight through | 100% clean, 86% scan, 86% photo | 36% | 0% |

The rules baseline also scores 0 in the quick queue, but only because it sends everything to manual review.
That's why the quick-queue number always needs to be read next to straight-through.

Hard suite, phone photos, with the local Qwen model: 11 of 12 defects flagged (95% interval 65-98%). The
miss is a real one. `hard_009` hides a new English injection in the bill's 6pt grey footer. On the photo,
Tesseract lost the footer entirely and Qwen didn't report it, so the file went to the quick queue. The two
held-out cases failed as expected, and the edge cases (a bill exactly 90 days old, a passport expiring
today) passed. Qwen also reports the forms' legal notices as injections, which costs review time but not
safety. I haven't run the OpenAI models on the hard suite yet, because that costs money (under $1 for
gpt-5.4-mini on all three qualities).

## Reviewing a file

After a run, open **Review** in the UI. Each value sits next to its box on the page, and you accept it,
correct it or reject it. The rules for signing off are in `kyc_demo/review.py`:

- every value the system couldn't verify has to be checked by eye first
- a file with flags needs a note saying why the flags don't stand in the way
- approval needs two different reviewers
- every action is appended to `runs/audit.jsonl` with the hash of the line before it, so editing or
  deleting an old line shows up when you verify the chain

Corrections are saved next to what the model said (`/api/corrections`), which turns real use into labelled
data for the next eval. You can also upload your own documents ("Upload your own…"). They have no
`truth.json`, so they can't be scored, but they can be reviewed. Reviewer names are just typed in; a real
bank would take them from its single sign-on.

## Where the data goes

By default nothing leaves your machine: the UI picks a local Ollama model when you have one, and otherwise
the `rules` baseline. With an `openai:` model, the page images and OCR text go to OpenAI in the US. For real
client data at a Swiss bank, that raises banking secrecy (Banking Act art. 47), Swiss data protection (the
US only counts as adequate for companies certified under the Swiss-US Data Privacy Framework), and FINMA's
expectations for AI and outsourcing (Guidance 08/2024). That's why the local path exists and why it's the
default. I haven't done a legal review; treat this as the list of questions to ask, not the answers.

## What it doesn't do

- **ID cards and residence permits.** Only the passport MRZ format (TD3) is parsed.
- **More than one beneficial owner, or a company as owner.** The Form A schema has one person. Forms K, T
  and S for companies, trusts and foundations aren't there either.
- **Certified copies and onboarding channel.** CDB 20 has different rules for face-to-face and remote
  onboarding, and the system doesn't check for a certification stamp.
- **Screening and risk.** No sanctions, PEP or adverse-media screening, and no risk scoring. Routing has
  just two queues.
- **Real forgery.** A consistent forgery with a valid MRZ passes by design: the rules only catch documents
  that disagree with each other. Photo swaps, font edits and an edited PDF's hidden text layer aren't
  checked.
- **Names and places outside the tables.** Non-Latin names (Ø and Æ are dropped instead of written as OE
  and AE), nationalities outside the 16 in the generator, cities outside the alias table, and US-style
  month-first dates.
- **Who signed.** The signature check only answers "is something written on the line".

## Running it

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # pinned; requirements.txt alone to run without the tests
brew install tesseract tesseract-lang      # OCR, with French/German/Italian
echo "OPENAI_API_KEY=sk-..." > .env        # optional, for the OpenAI models
ollama pull qwen2.5vl:7b                   # optional, to run everything locally

python -m kyc_demo generate                # both suites into cases/{clean,scan,photo}/
python -m kyc_demo run cases/photo/case_016 -e openai:gpt-5.4-mini@both
python -m kyc_demo eval -e rules -e openai:gpt-5.4-mini@both --tiers photo
python -m kyc_demo eval -e ollama:qwen2.5vl:7b@both --suite hard
python -m pytest

python -m kyc_demo serve                   # API on :8000
cd web && pnpm install && pnpm dev         # web UI on :5173
```

`-e` picks the model as `provider:model@input`, where input is `text` (OCR text only), `vision` (page
images only) or `both`. `rules` is the no-LLM baseline, and `ollama:qwen2.5vl:7b@both` keeps all the data
on your machine.

Model responses are cached on disk by a hash of the exact request. `scripts/replay.sh` re-scores every saved
eval from that cache with `KYC_OFFLINE=1`, so a change to the grounding, rules or routing can be measured on
every model for free. A changed prompt misses the cache and fails loudly instead of quietly spending money.
The reports live in `results/eval/`, and `results/comparison.md` is built from them. The published numbers
come from macOS, which has the Bradley Hand font. On other systems the handwriting is Kalam (bundled, OFL
licence), so the pages look different and the cache won't apply.

And here's a short demo video (Voiced over by ElevenLabs) of it running:

[![Demo video](https://img.youtube.com/vi/LZuj11_8ink/hqdefault.jpg)](https://youtu.be/LZuj11_8ink)
