# Extractor comparison

Synthetic files. The standard suite shows the system working; the hard suite is built to break it (defects inside traps, thresholds at their edge, one-digit changes, new injection wordings, Form A cases the standard suite lacks, and held-out names and places the normaliser was never tuned on). The blind suite was written by someone who never saw the rules, tables or prompt, and is scored once, on code frozen before it existed. `oracle` is not a model: it reads the true values from truth.json, so its column is the ceiling OCR, grounding and the rules put on every model. Intervals are 95% Wilson intervals: with this few cases, 100% is not a proof.

## standard suite, clean

| Metric | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Files | 30 | 30 | 30 | 30 | 30 | 30 | 30 |
| Field accuracy | 100% | 100% | 100% | 86% | 100% | 99% | 54% |
| Critical-field accuracy | 100% | 100% | 100% | 88% | 100% | 99% | 48% |
| Defect recall (95% interval) | 100% (83%-100%) | 100% (83%-100%) | 100% (83%-100%) | 84% (62%-94%) | 100% (83%-100%) | 100% (83%-100%) | 42% (23%-64%) |
| Defects not flagged | 0 | 0 | 0 | 3 | 0 | 0 | 11 |
| Defects caught by the right check | 100% | 100% | 100% | 84% | 100% | 100% | 37% |
| Defect precision | 90% | 100% | 100% | 38% | 90% | 90% | 32% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 100% (78%-100%) | 100% (78%-100%) | 100% (78%-100%) | 21% (8%-48%) | 86% (60%-96%) | 93% (68%-99%) | 0% (0%-22%) |
| Trap false-alarm rate | 0% | 0% | 0% | 17% | 4% | 6% | 4% |
| Process flags per file | 0.07 | 0.1 | 0.07 | 1.1 | 0.1 | 0.1 | 2.23 |
| Errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Model seconds per file | 8.19 | 16.3 | 8.11 | 8.78 | 9.77 | 9.23 | 0.0 |
| $ per file | $0.0047 | $0.0149 | $0.0102 | $0.0071 | $0.0100 | $0.0565 | $0.0000 |
| Run on | macOS | macOS | macOS | macOS | macOS | macOS | macOS |

## standard suite, scan

| Metric | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Files | 30 | 30 | 30 | 30 | 30 | 30 | 30 |
| Field accuracy | 99% | 100% | 100% | 83% | 100% | 100% | 20% |
| Critical-field accuracy | 100% | 100% | 100% | 82% | 100% | 99% | 8% |
| Defect recall (95% interval) | 95% (75%-99%) | 100% (83%-100%) | 100% (83%-100%) | 68% (46%-85%) | 100% (83%-100%) | 100% (83%-100%) | 32% (15%-54%) |
| Defects not flagged | 1 | 0 | 0 | 6 | 0 | 0 | 13 |
| Defects caught by the right check | 95% | 100% | 100% | 68% | 100% | 100% | 26% |
| Defect precision | 86% | 95% | 95% | 31% | 95% | 90% | 40% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 86% (60%-96%) | 86% (60%-96%) | 86% (60%-96%) | 0% (0%-22%) | 93% (68%-99%) | 79% (52%-92%) | 0% (0%-22%) |
| Trap false-alarm rate | 0% | 0% | 0% | 22% | 0% | 0% | 0% |
| Process flags per file | 0.37 | 0.3 | 0.2 | 1.7 | 0.2 | 0.23 | 2.27 |
| Errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Model seconds per file | 8.64 | 18.0 | 9.36 | 10.11 | 10.96 | 9.53 | 0.0 |
| $ per file | $0.0048 | $0.0159 | $0.0111 | $0.0081 | $0.0108 | $0.0574 | $0.0000 |
| Run on | macOS | macOS | macOS | macOS | macOS | macOS | macOS |

## standard suite, photo

| Metric | `ollama:qwen2.5:7b@text` | `ollama:qwen2.5vl:7b@both` | `ollama:qwen2.5vl:7b@both#regex-only-injection` | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Files | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 |
| Field accuracy | 66% | 99% | 99% | 99% | 100% | 100% | 79% | 99% | 100% | 35% |
| Critical-field accuracy | 59% | 99% | 99% | 99% | 99% | 99% | 76% | 99% | 99% | 23% |
| Defect recall (95% interval) | 47% (27%-68%) | 100% (83%-100%) | 95% (75%-99%) | 100% (83%-100%) | 100% (83%-100%) | 100% (83%-100%) | 79% (57%-92%) | 100% (83%-100%) | 100% (83%-100%) | 32% (15%-54%) |
| Defects not flagged | 10 | 0 | 1 | 0 | 0 | 0 | 4 | 0 | 0 | 13 |
| Defects caught by the right check | 42% | 100% | 95% | 100% | 100% | 100% | 79% | 100% | 100% | 32% |
| Defect precision | 29% | 48% | 78% | 86% | 90% | 90% | 44% | 90% | 90% | 50% |
| Defect files sent to the quick queue | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-22%) | 36% (16%-61%) | 71% (45%-88%) | 64% (39%-84%) | 79% (52%-92%) | 86% (60%-96%) | 0% (0%-22%) | 93% (68%-99%) | 86% (60%-96%) | 0% (0%-22%) |
| Trap false-alarm rate | 13% | 6% | 6% | 2% | 0% | 0% | 11% | 0% | 2% | 2% |
| Process flags per file | 2.8 | 0.17 | 0.17 | 0.3 | 0.23 | 0.13 | 2.07 | 0.13 | 0.17 | 2.17 |
| Errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Model seconds per file | 38.79 | 76.14 | 76.14 | 8.38 | 16.74 | 8.36 | 9.28 | 9.32 | 9.21 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 | $0.0050 | $0.0157 | $0.0106 | $0.0074 | $0.0105 | $0.0595 | $0.0000 |
| Run on | macOS | macOS | macOS | macOS | macOS | macOS | macOS | macOS | macOS | macOS |

## hard suite, clean

| Metric | `rules` |
| --- | --- |
| Files | 16 |
| Field accuracy | 54% |
| Critical-field accuracy | 48% |
| Defect recall (95% interval) | 33% (14%-61%) |
| Defects not flagged | 8 |
| Defects caught by the right check | 33% |
| Defect precision | 25% |
| Defect files sent to the quick queue | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-49%) |
| Trap false-alarm rate | 25% |
| Process flags per file | 2.19 |
| Errors | 0 |
| Model seconds per file | 0.0 |
| $ per file | $0.0000 |
| Run on | macOS |

## hard suite, scan

| Metric | `rules` |
| --- | --- |
| Files | 16 |
| Field accuracy | 18% |
| Critical-field accuracy | 4% |
| Defect recall (95% interval) | 25% (9%-53%) |
| Defects not flagged | 9 |
| Defects caught by the right check | 25% |
| Defect precision | 33% |
| Defect files sent to the quick queue | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-49%) |
| Trap false-alarm rate | 0% |
| Process flags per file | 2.25 |
| Errors | 0 |
| Model seconds per file | 0.0 |
| $ per file | $0.0000 |
| Run on | macOS |

## hard suite, photo

| Metric | `ollama:qwen2.5vl:7b@both` | `rules` |
| --- | --- | --- |
| Files | 16 | 16 |
| Field accuracy | 98% | 33% |
| Critical-field accuracy | 98% | 23% |
| Defect recall (95% interval) | 92% (65%-98%) | 17% (5%-45%) |
| Defects not flagged | 1 | 10 |
| Defects caught by the right check | 92% | 17% |
| Defect precision | 39% | 22% |
| Defect files sent to the quick queue | 1 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-49%) | 0% (0%-49%) |
| Trap false-alarm rate | 50% | 0% |
| Process flags per file | 0.25 | 2.12 |
| Errors | 0 | 0 |
| Model seconds per file | 80.52 | 0.0 |
| $ per file | $0.0000 | $0.0000 |
| Run on | macOS | macOS |

## blind suite, clean

| Metric | `oracle` | `rules` |
| --- | --- | --- |
| Files | 24 | 24 |
| Field accuracy | 99% | 16% |
| Critical-field accuracy | 98% | 0% |
| Defect recall (95% interval) | 88% (71%-96%) | 27% (14%-46%) |
| Defects not flagged | 3 | 19 |
| Defects caught by the right check | 88% | 27% |
| Defect precision | 51% | 44% |
| Defect files sent to the quick queue | 0 | 0 |
| Straight-through (clean files, 95% interval) | 11% (2%-44%) | 0% (0%-30%) |
| Trap false-alarm rate | 34% | 0% |
| Process flags per file | 0.96 | 2.12 |
| Errors | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## blind suite, scan

| Metric | `oracle` | `rules` |
| --- | --- | --- |
| Files | 24 | 24 |
| Field accuracy | 99% | 16% |
| Critical-field accuracy | 98% | 0% |
| Defect recall (95% interval) | 88% (71%-96%) | 27% (14%-46%) |
| Defects not flagged | 3 | 19 |
| Defects caught by the right check | 88% | 27% |
| Defect precision | 55% | 50% |
| Defect files sent to the quick queue | 0 | 0 |
| Straight-through (clean files, 95% interval) | 11% (2%-44%) | 0% (0%-30%) |
| Trap false-alarm rate | 34% | 0% |
| Process flags per file | 1.04 | 2.12 |
| Errors | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## blind suite, photo

| Metric | `oracle` | `rules` |
| --- | --- | --- |
| Files | 24 | 24 |
| Field accuracy | 99% | 16% |
| Critical-field accuracy | 98% | 0% |
| Defect recall (95% interval) | 88% (71%-96%) | 27% (14%-46%) |
| Defects not flagged | 3 | 19 |
| Defects caught by the right check | 88% | 27% |
| Defect precision | 45% | 32% |
| Defect files sent to the quick queue | 0 | 0 |
| Straight-through (clean files, 95% interval) | 11% (2%-44%) | 0% (0%-30%) |
| Trap false-alarm rate | 34% | 0% |
| Process flags per file | 0.75 | 2.08 |
| Errors | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |

## real suite, real

| Metric | `oracle` | `rules` |
| --- | --- | --- |
| Files | 3 | 3 |
| Field accuracy | 100% | 11% |
| Critical-field accuracy | 100% | 0% |
| Defect recall (95% interval) | 100% (34%-100%) | 100% (34%-100%) |
| Defects not flagged | 0 | 0 |
| Defects caught by the right check | 100% | 100% |
| Defect precision | 100% | 67% |
| Defect files sent to the quick queue | 0 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-79%) | 0% (0%-79%) |
| Trap false-alarm rate | - | - |
| Process flags per file | 2.33 | 3.0 |
| Errors | 0 | 0 |
| Model seconds per file | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 |
| Run on | linux, tesseract 5.3.4 | linux, tesseract 5.3.4 |
