# Extractor comparison

Synthetic files. The standard suite shows the system working; the hard suite is built to break it (defects inside traps, thresholds at their edge, one-digit changes, new injection wordings, Form A cases the standard suite lacks, and held-out names and places the normaliser was never tuned on). The blind suite was written by someone who never saw the rules, tables or prompt, and is scored once, on code frozen before it existed. `oracle` is not a model: it reads the true values from truth.json, so its column is the ceiling OCR, grounding and the rules put on every model. Intervals are 95% Wilson intervals: with this few cases, 100% is not a proof.

## standard suite, clean

| Metric | `oracle` | `rules` | `rules @5c741e3 (before)` |
| --- | --- | --- | --- |
| Files | 30 | 30 | 30 |
| Field accuracy | 100% | 52% | 52% |
| Critical-field accuracy | 100% | 47% | 47% |
| Defect recall (95% interval) | 100% (83%-100%) | 37% (19%-59%) | 37% (19%-59%) |
| Defects not flagged | 0 | 12 | 12 |
| Defects caught by the right check | 100% | 32% | 32% |
| Defect precision | 100% | 28% | 28% |
| Defect files sent to the quick queue | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 100% (78%-100%) | 0% (0%-22%) | 0% (0%-22%) |
| Trap false-alarm rate | 0% | 4% | 4% |
| Process flags per file | 0.1 | 2.3 | 2.23 |
| Errors | 0 | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## standard suite, scan

| Metric | `oracle` | `rules` | `rules @5c741e3 (before)` |
| --- | --- | --- | --- |
| Files | 30 | 30 | 30 |
| Field accuracy | 100% | 23% | 23% |
| Critical-field accuracy | 100% | 9% | 9% |
| Defect recall (95% interval) | 100% (83%-100%) | 21% (8%-43%) | 21% (8%-43%) |
| Defects not flagged | 0 | 15 | 15 |
| Defects caught by the right check | 100% | 21% | 21% |
| Defect precision | 100% | 24% | 24% |
| Defect files sent to the quick queue | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 93% (68%-99%) | 0% (0%-22%) | 0% (0%-22%) |
| Trap false-alarm rate | 0% | 6% | 6% |
| Process flags per file | 0.23 | 2.2 | 2.2 |
| Errors | 0 | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## standard suite, photo

| Metric | `oracle` | `rules` | `rules @5c741e3 (before)` |
| --- | --- | --- | --- |
| Files | 30 | 30 | 30 |
| Field accuracy | 100% | 27% | 27% |
| Critical-field accuracy | 100% | 14% | 14% |
| Defect recall (95% interval) | 100% (83%-100%) | 32% (15%-54%) | 32% (15%-54%) |
| Defects not flagged | 0 | 13 | 13 |
| Defects caught by the right check | 100% | 32% | 32% |
| Defect precision | 100% | 38% | 38% |
| Defect files sent to the quick queue | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 93% (68%-99%) | 0% (0%-22%) | 0% (0%-22%) |
| Trap false-alarm rate | 0% | 2% | 2% |
| Process flags per file | 0.13 | 2.17 | 2.17 |
| Errors | 0 | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## hard suite, clean

| Metric | `oracle` | `oracle:decoy` | `rules` | `rules @5c741e3 (before)` |
| --- | --- | --- | --- | --- |
| Files | 18 | 18 | 18 | 16 |
| Field accuracy | 100% | 99% | 50% | 50% |
| Critical-field accuracy | 100% | 99% | 44% | 44% |
| Defect recall (95% interval) | 100% (78%-100%) | 86% (60%-96%) | 29% (12%-55%) | 33% (14%-61%) |
| Defects not flagged | 0 | 2 | 10 | 8 |
| Defects caught by the right check | 100% | 86% | 29% | 33% |
| Defect precision | 93% | 92% | 25% | 25% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 75% (30%-95%) | 75% (30%-95%) | 0% (0%-49%) | 0% (0%-49%) |
| Trap false-alarm rate | 25% | 25% | 0% | 0% |
| Process flags per file | 0.06 | 0.17 | 2.33 | 2.38 |
| Errors | 0 | 0 | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## hard suite, scan

| Metric | `oracle` | `oracle:decoy` | `rules` | `rules @5c741e3 (before)` |
| --- | --- | --- | --- | --- |
| Files | 18 | 18 | 18 | 16 |
| Field accuracy | 100% | 99% | 18% | 18% |
| Critical-field accuracy | 100% | 99% | 6% | 6% |
| Defect recall (95% interval) | 93% (68%-99%) | 79% (52%-92%) | 21% (8%-48%) | 25% (9%-53%) |
| Defects not flagged | 1 | 3 | 11 | 9 |
| Defects caught by the right check | 93% | 79% | 21% | 25% |
| Defect precision | 93% | 92% | 20% | 23% |
| Defect files sent to the quick queue | 1 | 2 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 75% (30%-95%) | 75% (30%-95%) | 0% (0%-49%) | 0% (0%-49%) |
| Trap false-alarm rate | 25% | 25% | 0% | 0% |
| Process flags per file | 0.17 | 0.22 | 2.28 | 2.25 |
| Errors | 0 | 0 | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## hard suite, photo

| Metric | `oracle` | `oracle:decoy` | `rules` | `rules @5c741e3 (before)` |
| --- | --- | --- | --- | --- |
| Files | 18 | 18 | 18 | 16 |
| Field accuracy | 100% | 99% | 22% | 22% |
| Critical-field accuracy | 100% | 99% | 10% | 11% |
| Defect recall (95% interval) | 93% (68%-99%) | 79% (52%-92%) | 7% (1%-32%) | 8% (2%-35%) |
| Defects not flagged | 1 | 3 | 13 | 11 |
| Defects caught by the right check | 93% | 79% | 7% | 8% |
| Defect precision | 93% | 92% | 10% | 11% |
| Defect files sent to the quick queue | 1 | 1 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 75% (30%-95%) | 75% (30%-95%) | 0% (0%-49%) | 0% (0%-49%) |
| Trap false-alarm rate | 25% | 25% | 0% | 0% |
| Process flags per file | 0.33 | 0.33 | 2.33 | 2.38 |
| Errors | 0 | 0 | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |
