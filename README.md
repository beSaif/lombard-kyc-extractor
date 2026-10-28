# KYC extractor (learning prototype)

I built this to learn how you'd use an LLM for KYC onboarding without trusting it blindly. It reads a
client's passport, Form A and proof of address (as a clean PDF, a scan or a phone photo), pulls out the
fields, checks them against each other and sends the file to a quick or a full review. All the client data
is synthetic, and every case has a `truth.json` to score against.

<p>
  <img src="docs/examples/passport.png" alt="Passport data page" width="32%">
  <img src="docs/examples/form_a.png" alt="Form A, handwritten in Italian" width="32%">
  <img src="docs/examples/proof_of_address.png" alt="Utility bill as proof of address" width="32%">
</p>

![How one case goes through the pipeline](docs/pipeline.png)

## How it works

- Tesseract reads the pages, with a separate pass for the MRZ. The model returns each field with a quote.
- A value counts as verified only if its quote says the value, the quote is on the page (digits must match
  exactly) and it sits under that field's label, not in a footer or a remarks box.
- Plain rules check the MRZ check digits, expiry, names, dates and addresses across the three documents,
  the beneficial owner and the bill's age. A check that can't run counts as a flag.
- A reviewer accepts or corrects each value in the web UI. Approval takes two people, and every action goes
  into a hash-chained audit log.

## Test suites

- **standard** (30 cases) and **hard** (18, built to break it). I wrote both, so they mostly show that my
  code agrees with itself.
- **blind** (24). Another agent wrote it without seeing the rules, tables or prompt. I scored it once, on
  frozen code.
- **real** (16). Public specimen passports from Wikimedia Commons. `fetch-real` downloads them; they aren't
  in the repo.

The synthetic suites run as clean PDFs, scans and phone photos. `oracle` is a perfect reader (the true
values), so it shows the most any model could score.

## Results

macOS. Where there are three numbers, they're clean / scan / photo. Full tables are in `results/comparison.md`.

| | gpt-5.4-mini | qwen2.5vl:7b, local | perfect reader | rules only |
| --- | --- | --- | --- | --- |
| Standard: defects flagged | 19/19 | 19/19 (photos) | 19/19 | 6-8/19 |
| Standard: clean files straight through | 100 / 86 / 86% | 36% (photos) | 100 / 93 / 100% | 0% |
| Hard: defects flagged | 14 / 13 / 13 of 14 | 11/12 (photos) | 14 / 13 / 13 of 14 | 2-4/14 |
| Blind: defects flagged | 25 / 24 / 24 of 26 | 23/26 (photos) | 23/26 | 7/26 |
| Blind: clean files straight through | 0/9 | 0/9 | 1/9 | 0/9 |
| Real passports: fields read right | 82% | 67% | 99% | 11% |

In the runs in this table, only one file with a defect reached the quick queue: `hard_009`, an injection in
6 pt footer text that OCR loses on scans and photos.

What I learned:

- On my own documents it works. On someone else's (the blind suite) it still catches the defects but sends
  almost every clean file to manual review. Towns written in another language, name variants, a signature
  check tuned to my layouts, and nationalities written as words ('brésilien', 'Schweizer') all trip it.
- Real passports had things my generator never made: Ø, Æ and Å written OE, AE and AA in the MRZ, two-digit
  years, holders born in the 1910s, and passport numbers printed in groups.
- The cross-document checks catch most model misreads. The quote check caught qwen making up a surname.
- Fixed after the blind run: two-digit years (so the blind suite is no longer blind for that bug), and a
  location-check bug that flagged correct values when the model quoted the label along with the value.

## Limits

- Passports only (no ID cards), and one beneficial owner. No sanctions or PEP screening, and no risk scoring.
- A consistent forgery with a valid MRZ passes.
- Names, nationalities and cities outside the tables cause false alarms.
- With an `openai:` model, the page images go to OpenAI. The default is local (Ollama). I haven't done a
  legal review.
- There's an Azure Document Intelligence adapter, but I have no key to test it (`scripts/pending.sh`).

## Running it

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
brew install tesseract tesseract-lang
echo "OPENAI_API_KEY=sk-..." > .env        # optional
ollama pull qwen2.5vl:7b                   # optional, keeps everything local

python -m kyc_demo generate                # standard + hard suites
python -m kyc_demo generate --suite blind
python -m kyc_demo fetch-real
python -m kyc_demo eval -e rules -e oracle -e openai:gpt-5.4-mini@both --tiers photo
python -m pytest

python -m kyc_demo serve                   # API on :8000
cd web && pnpm install && pnpm dev         # web UI on :5173
```

Model answers are cached, and `scripts/replay.sh` re-scores every saved run for free.

[![Demo video](https://img.youtube.com/vi/LZuj11_8ink/hqdefault.jpg)](https://youtu.be/LZuj11_8ink)
