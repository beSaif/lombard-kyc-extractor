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

Every value comes back with a quote. A value only counts as verified when three things hold:

- **The quote says the value.** The quote "Anna Müller" doesn't back up the value "Hans Muster", and
  "25.08.2026" doesn't back up 2025-08-25. If the quote says something else, the value is dropped. If it's
  only close (the model copied an OCR misreading like "Cuca" into the quote but read "Luca" off the image),
  the value is kept but stays unverified.
- **The quote is on the page.** It's fuzzy-matched against the OCR words, because OCR misreads letters. But
  digits have to match exactly. "Musterweg 51" scores 92 against "Musterweg 57", and one digit off is a
  different house, date or passport.
- **The quote is where that field is printed** (`kyc_demo/anchor.py`). Being on the page isn't enough: a
  bill can print a second address in its footer, or a Form A can say "New address from next month: ..." in
  its remarks. A model that's been steered, or just confused, can quote that one. And if the decoy matches
  the other documents, every cross-check passes too. So I look at where the quote sits. If it's in fine
  print, or under the label of something I don't extract (a due date, a billing period, a remarks box), the
  value is **out of place**. A person has to look at it, and no other document can vouch for it, because a
  decoy is made to agree with them. If it only turns up under another extracted field's label (the country
  ends the address and is also the nationality), it's just unverified. No label nearby proves nothing: an
  address window has none, and OCR loses small labels on photos.

I tuned this with a perfect reader (the `oracle`, below) on all 144 synthetic files. It now raises **zero**
false alarms on clean, scan and photo. Two hard cases plant decoys for it. The remarks decoy (`hard_018`) is
caught at every quality. The footer decoy (`hard_017`) is only caught on the born-digital bill. On scans
and photos, OCR loses the 6 pt footer, so the decoy isn't found at all. It stays unverified, and the Form A
it was made to match then corroborates it. Print size can only be judged from a PDF text layer, because
Tesseract's boxes for the same 9 pt type vary by a factor of two on a photo. That's a real hole: the check
can only judge text that OCR can see.

Zero false alarms held for the oracle, not for the models. When I replayed the cached model answers through
it, it raised 11 false EVIDENCE_OUT_OF_PLACE: 6 on gpt-4.1-mini, which cost it 6 straight-through files, and
5 on qwen2.5:7b. Every one of those values was right and printed in the right place. The models had quoted
the label with the value ("Rechnungsdatum 16.09.2026", "Verbrauchsadresse: Musterweg 49, 4051 Basel").
`place()` skips any label that sits inside the quote, so the field's own label was ignored, and the label
on the row above ("Rechnungsnummer", "Abrechnungsperiode") decided the verdict. The oracle never quotes
a label, so tuning on it couldn't show this. gpt-5.4-mini quotes only the value and wasn't affected.

Each verified value also says what it rests on. `text_layer` means the PDF's own text. `ocr` means Tesseract
read the same thing, but in `text` and `both` mode the model was shown that OCR text, so this is agreement
with OCR, not two independent readings. `checksum` means the MRZ check digits pass, and that's the one check
neither OCR nor the model can fake. Unverified values go to a person unless a passing check on another
document backs them up. When I measured it, that's where most of the real catching happens: the
cross-document checks, more than the quotes.

## Four test suites

The first two are mine, which is their weakness. I wrote the generator, the truth, the rules, the tables
and the prompt, so 100% on them mostly shows that my code agrees with itself. The other two exist because
of that.

The 30 standard cases show the pipeline working. The 18 cases in the hard suite (`hard_001` to `hard_018`)
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
- two decoys (`hard_017`, `hard_018`), described above. I added them last so the first 16 render exactly as
  before (I checked: every page renders to the same pixels), and the cached model answers still apply.

To be honest about the hard suite: most of its checks were written in the same commit as the cases that
test them, so apart from the two held-out cases it isn't really held out.

The **blind suite** (`blind_001` to `blind_024`, `kyc_demo/blind.py`) is the held-out test. I had another
agent write its generator, and it wasn't allowed to open the rules, the normaliser's tables, the prompt or
the grounding code. It got only the truth.json format, what each defect means and the bank's policy, and it
was asked for realistic Swiss onboarding files. So it made its own:

- three passport layouts
- three Form A layouts in four languages, filled in with two handwriting fonts the system has never seen
- electricity, telecom and health-insurance bills with distracting dates
- 31 kinds of trap of its own, each with the flag it must not raise
- people from 23 countries, living in about 20 Swiss towns

I froze the code in a commit before the suite existed, generated it, and scored it once. Whatever it says
stays in the results; I don't fix the code against it. One disclosure: I read the agent's summary of its
cases (the defect mix and trap names, not its code or pages) before I froze the location check. One line I
added to the label list after that, "new address", was for my own `hard_018` decoy, but the summary had
mentioned moving notices on bills, so it may not be fully blind.

The **real suite** (`real_NNN`, `kyc_demo/real.py`) is public specimen passports from Wikimedia Commons:
real states' sample data pages, with real security printing, fonts and layouts, photographed by someone
else. I read their values off by hand and checked every MRZ against its check digits. The images aren't in
the repository; `python -m kyc_demo fetch-real` downloads them. It only tests the passport path, because
nobody publishes real Form As or bills. It's 16 passports: Bulgaria, Cyprus, Denmark, France, Greece,
Iceland, Latvia, Liechtenstein, Malta, the Netherlands, Norway, Portugal, Slovakia, Slovenia, Spain and
Switzerland. Each one's licence (public domain, CC0 or CC BY-SA 4.0) and author is in `real.py`. Every MRZ
passes all five check digits. The first three alone found a real bug: Liechtenstein prints its passport number in groups ("R 00000"), and the quote
check dropped the correct value because "R 00000" didn't "say" R00000. That's fixed now, with a test.

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
That's why the quick-queue number always needs to be read next to straight-through. Straight-through now
carries an interval too: with 14 clean files, 86% (12 of 14) means anything from about 60% to 96%, so the
differences between the models' straight-through rates in `results/comparison.md` are mostly noise.

Hard suite, phone photos, with the local Qwen model: 11 of 12 defects flagged (95% interval 65-98%). The
miss is a real one. `hard_009` hides a new English injection in the bill's 6pt grey footer. On the photo,
Tesseract lost the footer entirely and Qwen didn't report it, so the file went to the quick queue. I first
put that down to Qwen, but the oracle (next section) shows it's the pipeline's fault. Even a reader that
reports the injection perfectly is overruled on scans and photos. Its report can't be found in the OCR text,
the new wording doesn't match the regex, and an ungrounded report that doesn't read like an instruction is
thrown away. No model can get that file right with the rules as they stand. The two held-out cases failed as
expected, and the edge cases (a bill exactly 90 days old, a passport expiring today) passed. Qwen also
reports the forms' legal notices as injections, which costs review time but not safety.

Hard suite, all 18 cases, with gpt-5.4-mini (the first 16 from the response cache, the two decoys new):

| | gpt-5.4-mini, both | oracle (perfect reader) | rules |
| --- | --- | --- | --- |
| Defects flagged | 14/14 clean, 13/14 scan and photo | the same | 4/14 clean, 3/14 scan, 2/14 photo |
| Defect files sent to the quick queue | 0 clean, 1 scan and photo (`hard_009`) | the same | 0 |
| Clean files straight through | 2 of 4 at every quality | 3 of 4 | 0 of 4 |

It misses exactly what the perfect reader misses: `hard_009`, for the reason above. It wasn't fooled by
either decoy. It quoted the real address both times, so the planted ADDRESS_MISMATCH was flagged by name.
Of the 4 clean files, two are the held-out cases, which fail as expected (the Canadian nationality and
Lucerne). Its other false flags are its own misreads, all safe: "Belspielstrasse" for a handwritten
"Beispielstrasse", a dropped last MRZ character, a handwritten 21 read as 24. Each was caught by a
cross-check and sent the file to a person.

### What I've now run

The hard, blind and real runs that were waiting for keys are done, on the Mac that made the published
numbers. They cost about $0.95 in OpenAI calls, and the local Qwen runs cost nothing but time (about two
minutes a file). The model columns below come from those runs. Only the Azure comparison is still pending:
I don't have an Azure key. `scripts/pending.sh` now holds just those lines.

### The ceiling: a perfect reader

`-e oracle` is not a model. It reads the true values from truth.json and quotes exactly what's printed for
each one. So everything after the model (OCR, grounding, the location check, the rules, routing) is
measured as if the model made no mistakes. It's free, runs anywhere, and it's the most any model can
score here, except on injections: the oracle only reports an injection when truth.json records its text.

I first measured it on Linux (`results/linux/`), where handwriting renders in Kalam instead of Bradley Hand
and Tesseract is 5.3.4. On the Mac (Tesseract 5.5.1) it differs in two places, so here are both:

| | oracle, standard | oracle, hard | `oracle:decoy`, hard |
| --- | --- | --- | --- |
| Defects flagged | 19/19 at every quality | 14/14 clean, 13/14 scan and photo (`hard_009`) | see below |
| Defect files sent to the quick queue | 0 | 0 clean, 1 scan and photo | Mac: 0 clean, 1 scan, 1 photo. Linux: 0, 2, 1 |
| Clean files straight through | Mac: 100% clean, 93% scan, 100% photo. Linux: 100%, 93%, 93% | 75% (the held-out cases) | 75% |

So on the Mac's pages, gpt-5.4-mini's 86% straight-through on photos is 14 points under the ceiling, not 7
as I first wrote from the Linux numbers, and on scans it's 7 under. The photo gap is the model, not OCR: on
two Form As it misread handwritten digits (postcode 8001 as 2001, a 14 as 17). The cross-checks caught
both, so they cost review time, not safety.

`oracle:decoy` is a perfectly *fooled* reader: on the two decoy cases it quotes the decoy, as a steered
model would. On clean files both get stopped by the location check (flagged EVIDENCE_OUT_OF_PLACE, not
ADDRESS_MISMATCH: the file is stopped and the reviewer is told why, but the defect itself isn't named). On
scans and photos the remarks decoy is still stopped. The footer decoy gets through to the quick queue on the
Linux scan, for the reason given above. On the Mac it doesn't, but only by luck: Tesseract didn't read the
handwritten address on the Form A, so nothing was there to corroborate the decoy, and the file went to a
person as EVIDENCE_NOT_FOUND. The hole is the same. Before and after the location check, the rules baseline routes every file the
same way and flags the same defects (`results/linux/comparison.md` has both columns). Two of the 90
standard files pick up an extra EVIDENCE_NOT_FOUND, because a value found only under another field's label
is now unverified.

### The blind suite

This is the number I'd trust most, and it's bad. I scored it once, on the code as frozen in commit
`12579ff`: first with only the rules baseline and the perfect reader, then with the two models (24 files):

| | rules | oracle (perfect reader) | gpt-5.4-mini, both | qwen2.5vl:7b, both (photos only) |
| --- | --- | --- | --- | --- |
| Defects flagged | 7 of 26 (27%) | 23 of 26 (88%, 95% interval 71-96%) | 25 of 26 clean, 24 of 26 scan and photo | 23 of 26 |
| Defect files sent to the quick queue | 0 of 15 | 0 of 15 | 0 of 15 | 0 of 15 |
| Clean files straight through | 0 of 9 | 1 of 9 | 0 of 9 | 0 of 9 |
| Trap false alarms | 0% | 34% | 40-42% | 36% |

Rules and oracle are the same at every quality. Their first run was on Linux with Tesseract 5.3.4
(`results/linux/`). I re-scored them on the Mac (5.5.1) so they sit on the same pages as the models: some
individual flags moved, but every total and every routing decision came out the same.

Even with every value read perfectly, the system catches 88% of the defects and sends 8 of 9 clean files to
manual review. That's the rules and tables failing on someone else's paperwork. The numbers are identical
on clean, scan and photo, so OCR isn't the cause. The models make it no better for clean files: gpt-5.4-mini
flags more defects than the perfect reader (it reports injections, below), but sends every clean file to a
person. What broke:

- **The tables.** Towns written in another national language (Biel/Bienne, Sion/Sitten, Delémont/Delsberg,
  Neuchâtel/Neuenburg) aren't in the alias table: 5 false ADDRESS_MISMATCH. Names with a middle initial,
  "ue" for "ü", only the second given name, only the first of two surnames, or two holders on one bill
  break the name rule: 8 false NAME_MISMATCH. Abbreviated streets, street names in the other language, a
  "CH-" prefix and the house number first made 5 more false ADDRESS_MISMATCH.
- **The signature check.** It fires FORM_A_UNSIGNED on 9 signed forms. It looks for ink above a label in the
  places my own layouts put it, and the new layouts put it elsewhere.
- **Two-digit years.** Two passport layouts print "17 MAY/MAI 29". The date parser reads that as 17 May of
  the year 29 AD (literally), the quote then doesn't "say" the value, and the expiry is dropped. That's how
  a printed expiry one year off the MRZ (`blind_022`) got through.
  Both models hit the same bug: gpt-5.4-mini read `blind_022`'s expiry right, and the quote was still dropped.
- **Injections.** The blind truth doesn't record the injections' text, so the oracle didn't report them,
  and this is the regex alone: it caught the Italian one and missed a handwritten English one and a French
  footer. The models do better. gpt-5.4-mini reported all three on the clean pages, but missed the French
  one (`blind_013`) on the scan and the photo. qwen reported all three on the photos, but it also calls
  something on 19 of the 24 files an injection (mostly the forms' legal notices), so its reports cost a
  lot of review time.
- **Nationality, which only a model shows.** The models report nationality as written: 'brésilien',
  'japanisch', 'SOUTH KOREAN', 'Schweizer', 'italiana'. The country table knows a few names and codes, not
  adjectives in four languages, so every model run gets 16 false NATIONALITY_MISMATCH per quality and 7-8
  false MRZ_VISUAL_MISMATCH (the passport's printed nationality "disagrees" with its MRZ). The perfect
  reader hides this completely, because it hands over the ISO code. That's the limit of the ceiling: it
  measures everything after the model, but not the step that turns what a model reads into what the
  rules compare.
- **Model mistakes.** Fewer than the table problems. qwen missed two address mismatches that gpt-5.4-mini
  caught: its quote didn't back up the address it reported, so the address was dropped and the comparison
  couldn't run (the file still went to a person, flagged CHECK_SKIPPED). One qwen run on `blind_008` failed
  when Ollama's runner crashed (I had two evals sharing it), and the re-run is what's counted.

Nothing went to the quick queue with a defect in it. But that's mostly because almost nothing went to the
quick queue at all. Read the way the README tells you to read the rules baseline, this is a system that
saves very little time on paperwork it wasn't written for. I haven't fixed any of it, on purpose. The
two-digit year is a plain bug I'll fix in its own commit, and from then on the suite isn't blind for it.
The rest is what the critique of this project said would happen: tables written for my generator don't
reach other people's documents.

### Real passports

Sixteen specimens, still more anecdotes than rates. Each is a passport on its own, so every file goes to
manual review (MISSING_DOCUMENT) and routing says nothing here. What counts is what's read and what's
falsely flagged. 8 of the 16 have expired, which is the one planted defect.

| | rules | oracle (perfect reader) | gpt-5.4-mini, both | qwen2.5vl:7b, both |
| --- | --- | --- | --- | --- |
| Field accuracy | 11% | 97% | 81% | 66% (14 files; 2 failed) |
| Expired passports flagged | 7 of 8 | 8 of 8 | 8 of 8 | 8 of 8 |
| Specimens with no false flag | 0 of 16 | 8 of 16 | 1 of 16 (Switzerland) | 1 of 14 (Switzerland) |

Even the perfect reader raises false alarms on half of them. Three are OCR on small photos: most of these
images are 600 pixels wide, and on Cyprus, France and Greece Tesseract doesn't find one printed value (a
given name, or the sex and MRZ line 1), so it stays unverified (EVIDENCE_NOT_FOUND). Every other cause is
something my synthetic passports never had:

- **Nordic letters.** Denmark, Iceland and Norway print ØSTERGÅRD, ÆVARSDÓTTIR and ØSTENBYEN. ICAO writes those
  OESTERGAARD, AEVARSDOTTIR and OESTENBYEN in the MRZ. The name comparison doesn't know that, so all three get
  MRZ_VISUAL_MISMATCH even from the perfect reader. "What it doesn't do" listed this; now it's measured.
- **Two-digit years, again.** Iceland prints "12 DES /DEC 12" (with the Icelandic month), Norway
  "15 APR /APR 30", Denmark "09 06 85". The parser drops the first two, so the perfect reader loses those
  dates (MISSING_FIELD). qwen's Icelandic dates came out as the years 12 and 29 AD.
- **Born before 1926.** Slovakia's holder was born 11.11.1911, and Iceland's in 1912. The passport was issued in
  2007, and the last digit of her national number (9) means the 1900s. The MRZ has no century, and the
  parser reads 111111 and 121212 as 2011 and 2012. So both get MRZ_VISUAL_MISMATCH.
- **Sex as "Ž".** Slovenia prints Ž (ženski) for F, which the quote check doesn't accept. Slovenia also prints
  no passport number in the visual zone at all, so there's nothing to quote for it.
- **Nationality in words.** Same as the blind suite: gpt-5.4-mini reports 'HELLENIC', 'LATVIJAS',
  'Nederlandse', 'Slovenská republika', and the country table doesn't know them. That's most of its false
  MRZ_VISUAL_MISMATCH. (The oracle hands over the ISO code, so it never sees this.)
- **A half-fixed bug.** The quote check now accepts "R 00000" for R00000 (below), but the value itself isn't
  normalised. A model that reports "R 00000", as both did, still gets a false MRZ_VISUAL_MISMATCH on
  Liechtenstein.

The models' own mistakes were all stopped before they could do harm:

- gpt-5.4-mini read Portugal's "I700044" as 1700044 and added the check digit to Slovenia's number. It
  wrote Cyprus's MRZ with one '<' too many (45 characters, which the filler repair doesn't cover). It quoted
  Bulgaria's given names in Cyrillic, which the quote check rightly doesn't accept as "MARITSA RADNEVA".
- qwen made up a surname. It reported "LÓPEZ" for Spain's ESPAÑOLA ESPAÑOLA, and "LÓPEZ" isn't on the page,
  so the quote check stopped it. It shifted Norway's fields by one (surname "NOR"), returned the whole MRZ
  as the Dutch passport number, and read Cyprus's expiry as 2020, a false PASSPORT_EXPIRED.
- qwen failed outright on Latvia and Slovenia. It started repeating '<' in MRZ line 1 and never closed the
  JSON. At temperature 0 it fails the same way every time. These two count as errors and are left out of
  its numbers.
- The rules baseline missed Switzerland's expiry: OCR lost the first MRZ character, so the check digits
  failed and the expiry check couldn't run. The file still went to a person.

From the first three specimens:

- The MRZ OCR pass reads line 2 with valid check digits on Bulgaria and Liechtenstein. On Cyprus it reads
  the zeros in "L00000000" as O, Q and D. So the rules baseline, which has only the OCR, flags a valid
  passport as MRZ_CHECK_FAILED. That's a false alarm, but a safe one.
- The rules baseline reads almost none of the visual zone. Its patterns only know my own layout.
- They found two bugs, both fixed with tests. The grouped passport number above was one. The other:
  OCR read Liechtenstein's MRZ number "R00000" as "ROOOOO", and that passes the check digit too (five O's
  add 24 x 15 = 360, which is 0 mod 10). Because the OCR reading won ties, the system reported a false
  MRZ_VISUAL_MISMATCH. Now, when the model's reading also passes and the two differ only in look-alike
  characters, the model's wins.

## Reviewing a file

After a run, open **Review** in the UI. Each value sits next to its box on the page, and you accept it,
correct it or reject it. The rules for signing off are in `kyc_demo/review.py`:

- every value the system couldn't verify has to be checked by eye first
- a file with flags needs a note saying why the flags don't stand in the way
- approval needs two different reviewers
- every action is appended to `runs/audit.jsonl` with the hash of the line before it, so editing or
  deleting an old line shows up when you verify the chain. What the chain can't show on its own is lines
  cut off the end, or the whole chain rewritten with fresh hashes (anyone who can write the file can do
  that). Both need a copy of the head kept somewhere the writer can't change, like a ticket or a WORM store.
  `/api/audit/verify?seq=…&head=…` checks the log against such a copy.

Corrections are saved next to what the model said (`/api/corrections`), which turns real use into labelled
data for the next eval. You can also upload your own documents ("Upload your own…"). They have no
`truth.json`, so they can't be scored, but they can be reviewed. Reviewer names are just typed in; a real
bank would take them from its single sign-on.

## Compared with something a bank could buy

The rules baseline is a straw man: English regexes on forms in four languages. To see what a model adds,
you'd compare it with a product a bank could buy instead. `kyc_demo/azure.py` plugs Azure AI Document
Intelligence in as `-e azure:prebuilt`. I picked it because its ID model reads passports from anywhere,
while AWS Textract's AnalyzeID and Google's identity processors only do US documents. Its "query fields"
add-on also lets you ask for `BeneficialOwnerFullName` or `InvoiceDate` on any page without training
anything. Each field comes back with the text it was read from, which becomes the quote, so grounding, the
location check and the rules run on it unchanged. Azure gives no injection report, so only the regex guards
against injections there.

I haven't run it. The adapter follows the 2024-11-30 REST API, and tests check it against a response of the
documented shape, not against the service. It needs `AZURE_DOCINTEL_ENDPOINT` and `AZURE_DOCINTEL_KEY`, and
the runs are in `scripts/pending.sh`. Responses are cached like the model calls.

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
- **Decoys OCR can't see.** The location check can only judge text OCR found. A decoy in a footer that OCR
  loses on a photo is "not found", and if it matches the other documents, they corroborate it. Print size
  is only judged on PDFs with a text layer.

## Running it

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # pinned; requirements.txt alone to run without the tests
brew install tesseract tesseract-lang      # OCR, with French/German/Italian
echo "OPENAI_API_KEY=sk-..." > .env        # optional, for the OpenAI models
ollama pull qwen2.5vl:7b                   # optional, to run everything locally

python -m kyc_demo generate                # standard + hard suites into cases/{clean,scan,photo}/
python -m kyc_demo generate --suite blind  # the blind suite
python -m kyc_demo fetch-real              # the specimen passports, into cases/real/
python -m kyc_demo run cases/photo/case_016 -e openai:gpt-5.4-mini@both
python -m kyc_demo eval -e rules -e oracle -e openai:gpt-5.4-mini@both --tiers photo
python -m kyc_demo eval -e ollama:qwen2.5vl:7b@both --suite hard
python -m kyc_demo eval -e oracle --suite real --tiers real
python -m pytest
scripts/pending.sh                         # the Azure runs, which need a key I don't have

python -m kyc_demo serve                   # API on :8000
cd web && pnpm install && pnpm dev         # web UI on :5173
```

`-e` picks the model as `provider:model@input`, where input is `text` (OCR text only), `vision` (page
images only) or `both`. `rules` is the no-LLM baseline, `oracle` the perfect reader, `azure:prebuilt` the
commercial parser, and `ollama:qwen2.5vl:7b@both` keeps all the data on your machine.

Model responses are cached on disk by a hash of the exact request. `scripts/replay.sh` re-scores every saved
eval from that cache with `KYC_OFFLINE=1`, so a change to the grounding, rules or routing can be measured on
every model for free. A changed prompt misses the cache and fails loudly instead of quietly spending money.
The reports live in `results/eval/`, and `results/comparison.md` is built from them. The published numbers
come from macOS, which has the Bradley Hand font. On other systems the handwriting is Kalam (bundled, OFL
licence), so the pages look different and the cache won't apply. Every report now records the platform and
Tesseract version it was made on, and `results/linux/` holds the Linux runs, apart from the macOS ones. The
blind suite only uses fonts it bundles, so it renders the same everywhere. The specimens are fixed images.
Tesseract runs one thread per process, since parallel evals plus its own threads made pages take minutes.

And here's a short demo video (Voiced over by ElevenLabs) of it running:

[![Demo video](https://img.youtube.com/vi/LZuj11_8ink/hqdefault.jpg)](https://youtu.be/LZuj11_8ink)
