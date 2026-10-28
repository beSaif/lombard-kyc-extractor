# Extractor comparison

Synthetic files. The standard suite shows the system working; the hard suite is built to break it (defects inside traps, thresholds at their edge, one-digit changes, new injection wordings, Form A cases the standard suite lacks, and held-out names and places the normaliser was never tuned on). The blind suite was written by someone who never saw the rules, tables or prompt, and is scored once, on code frozen before it existed. `oracle` is not a model: it reads the true values from truth.json, so its column is the ceiling OCR, grounding and the rules put on every model. Intervals are 95% Wilson intervals: with this few cases, 100% is not a proof.

## standard suite, clean

| Metric | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `oracle` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Files | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 |
| Field accuracy | 100% | 100% | 100% | 86% | 100% | 99% | 100% | 54% |
| Critical-field accuracy | 100% | 100% | 100% | 88% | 100% | 99% | 100% | 48% |
| Defect recall (95% interval) | 100% (83%-100%) | 100% (83%-100%) | 100% (83%-100%) | 84% (62%-94%) | 100% (83%-100%) | 100% (83%-100%) | 100% (83%-100%) | 42% (23%-64%) |
| Defects not flagged | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 11 |
| Defects caught by the right check | 100% | 100% | 100% | 84% | 100% | 100% | 100% | 37% |
| Defect precision | 90% | 100% | 100% | 38% | 90% | 90% | 100% | 32% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 100% (78%-100%) | 100% (78%-100%) | 100% (78%-100%) | 21% (8%-48%) | 86% (60%-96%) | 93% (68%-99%) | 100% (78%-100%) | 0% (0%-22%) |
| Trap false-alarm rate | 0% | 0% | 0% | 17% | 4% | 6% | 0% | 4% |
| Process flags per file | 0.07 | 0.1 | 0.07 | 1.13 | 0.1 | 0.1 | 0.07 | 2.23 |
| Errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Model seconds per file | 8.19 | 16.3 | 8.11 | 8.78 | 9.77 | 9.23 | 0.0 | 0.0 |
| $ per file | $0.0047 | $0.0149 | $0.0102 | $0.0071 | $0.0100 | $0.0565 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## standard suite, scan

| Metric | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `oracle` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Files | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 |
| Field accuracy | 99% | 100% | 100% | 83% | 100% | 100% | 100% | 20% |
| Critical-field accuracy | 100% | 100% | 100% | 82% | 100% | 99% | 100% | 8% |
| Defect recall (95% interval) | 95% (75%-99%) | 100% (83%-100%) | 100% (83%-100%) | 68% (46%-85%) | 100% (83%-100%) | 100% (83%-100%) | 100% (83%-100%) | 32% (15%-54%) |
| Defects not flagged | 1 | 0 | 0 | 6 | 0 | 0 | 0 | 13 |
| Defects caught by the right check | 95% | 100% | 100% | 68% | 100% | 100% | 100% | 26% |
| Defect precision | 86% | 95% | 95% | 31% | 95% | 90% | 100% | 40% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 86% (60%-96%) | 86% (60%-96%) | 86% (60%-96%) | 0% (0%-22%) | 93% (68%-99%) | 79% (52%-92%) | 93% (68%-99%) | 0% (0%-22%) |
| Trap false-alarm rate | 0% | 0% | 0% | 22% | 0% | 0% | 0% | 0% |
| Process flags per file | 0.37 | 0.3 | 0.2 | 1.7 | 0.2 | 0.23 | 0.2 | 2.27 |
| Errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Model seconds per file | 8.64 | 18.0 | 9.36 | 10.11 | 10.96 | 9.53 | 0.0 | 0.0 |
| $ per file | $0.0048 | $0.0159 | $0.0111 | $0.0081 | $0.0108 | $0.0574 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## standard suite, photo

| Metric | `ollama:qwen2.5:7b@text` | `ollama:qwen2.5vl:7b@both` | `ollama:qwen2.5vl:7b@both#regex-only-injection` | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `oracle` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Files | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 | 30 |
| Field accuracy | 66% | 99% | 99% | 99% | 100% | 100% | 79% | 99% | 100% | 100% | 35% |
| Critical-field accuracy | 59% | 99% | 99% | 99% | 99% | 99% | 76% | 99% | 99% | 100% | 23% |
| Defect recall (95% interval) | 47% (27%-68%) | 100% (83%-100%) | 95% (75%-99%) | 100% (83%-100%) | 100% (83%-100%) | 100% (83%-100%) | 79% (57%-92%) | 100% (83%-100%) | 100% (83%-100%) | 100% (83%-100%) | 32% (15%-54%) |
| Defects not flagged | 10 | 0 | 1 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 13 |
| Defects caught by the right check | 42% | 100% | 95% | 100% | 100% | 100% | 79% | 100% | 100% | 100% | 32% |
| Defect precision | 29% | 48% | 78% | 86% | 90% | 90% | 44% | 90% | 90% | 100% | 50% |
| Defect files sent to the quick queue | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-22%) | 36% (16%-61%) | 71% (45%-88%) | 64% (39%-84%) | 79% (52%-92%) | 86% (60%-96%) | 0% (0%-22%) | 93% (68%-99%) | 86% (60%-96%) | 100% (78%-100%) | 0% (0%-22%) |
| Trap false-alarm rate | 13% | 6% | 6% | 2% | 0% | 0% | 11% | 0% | 2% | 0% | 2% |
| Process flags per file | 2.8 | 0.2 | 0.2 | 0.3 | 0.23 | 0.13 | 2.07 | 0.13 | 0.17 | 0.1 | 2.17 |
| Errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Model seconds per file | 38.79 | 76.14 | 76.14 | 8.38 | 16.74 | 8.36 | 9.28 | 9.32 | 9.21 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 | $0.0050 | $0.0157 | $0.0106 | $0.0074 | $0.0105 | $0.0595 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## hard suite, clean

| Metric | `openai:gpt-5.4-mini@both` | `oracle` | `oracle:decoy` | `rules` |
| --- | --- | --- | --- | --- |
| Files | 18 | 18 | 18 | 18 |
| Field accuracy | 99% | 100% | 99% | 54% |
| Critical-field accuracy | 99% | 100% | 99% | 48% |
| Defect recall (95% interval) | 100% (78%-100%) | 100% (78%-100%) | 86% (60%-96%) | 29% (12%-55%) |
| Defects not flagged | 0 | 0 | 2 | 10 |
| Defects caught by the right check | 100% | 100% | 86% | 29% |
| Defect precision | 78% | 93% | 92% | 24% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 50% (15%-85%) | 75% (30%-95%) | 75% (30%-95%) | 0% (0%-49%) |
| Trap false-alarm rate | 50% | 25% | 25% | 25% |
| Process flags per file | 0.17 | 0.11 | 0.17 | 2.17 |
| Errors | 0 | 0 | 0 | 0 |
| Model seconds per file | 8.8 | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0101 | $0.0000 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## hard suite, scan

| Metric | `openai:gpt-5.4-mini@both` | `oracle` | `oracle:decoy` | `rules` |
| --- | --- | --- | --- | --- |
| Files | 18 | 18 | 18 | 18 |
| Field accuracy | 99% | 100% | 99% | 18% |
| Critical-field accuracy | 100% | 100% | 99% | 4% |
| Defect recall (95% interval) | 93% (68%-99%) | 93% (68%-99%) | 79% (52%-92%) | 21% (8%-48%) |
| Defects not flagged | 1 | 1 | 3 | 11 |
| Defects caught by the right check | 93% | 93% | 79% | 21% |
| Defect precision | 76% | 93% | 92% | 30% |
| Defect files sent to the quick queue | 1 | 1 | 1 | 0 |
| Straight-through (clean files, 95% interval) | 50% (15%-85%) | 75% (30%-95%) | 75% (30%-95%) | 0% (0%-49%) |
| Trap false-alarm rate | 50% | 25% | 25% | 0% |
| Process flags per file | 0.17 | 0.11 | 0.17 | 2.28 |
| Errors | 0 | 0 | 0 | 0 |
| Model seconds per file | 9.35 | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0107 | $0.0000 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## hard suite, photo

| Metric | `ollama:qwen2.5vl:7b@both` | `openai:gpt-5.4-mini@both` | `oracle` | `oracle:decoy` | `rules` |
| --- | --- | --- | --- | --- | --- |
| Files | 16 | 18 | 18 | 18 | 18 |
| Field accuracy | 98% | 99% | 100% | 99% | 33% |
| Critical-field accuracy | 98% | 99% | 100% | 99% | 22% |
| Defect recall (95% interval) | 92% (65%-98%) | 93% (68%-99%) | 93% (68%-99%) | 79% (52%-92%) | 14% (4%-40%) |
| Defects not flagged | 1 | 1 | 1 | 3 | 12 |
| Defects caught by the right check | 92% | 93% | 93% | 79% | 14% |
| Defect precision | 39% | 76% | 93% | 92% | 20% |
| Defect files sent to the quick queue | 1 | 1 | 1 | 1 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-49%) | 50% (15%-85%) | 75% (30%-95%) | 75% (30%-95%) | 0% (0%-49%) |
| Trap false-alarm rate | 50% | 50% | 25% | 25% | 0% |
| Process flags per file | 0.25 | 0.33 | 0.33 | 0.33 | 2.11 |
| Errors | 0 | 0 | 0 | 0 | 0 |
| Model seconds per file | 80.52 | 8.81 | 0.0 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0108 | $0.0000 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## blind suite, clean

| Metric | `openai:gpt-5.4-mini@both` | `oracle` | `rules` |
| --- | --- | --- | --- |
| Files | 24 | 24 | 24 |
| Field accuracy | 92% | 100% | 16% |
| Critical-field accuracy | 91% | 100% | 0% |
| Defect recall (95% interval) | 96% (81%-99%) | 92% (76%-98%) | 27% (14%-46%) |
| Defects not flagged | 1 | 2 | 19 |
| Defects caught by the right check | 96% | 92% | 27% |
| Defect precision | 35% | 52% | 41% |
| Defect files sent to the quick queue | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-30%) | 22% (6%-55%) | 0% (0%-30%) |
| Trap false-alarm rate | 40% | 34% | 0% |
| Process flags per file | 1.04 | 0.62 | 2.08 |
| Errors | 0 | 0 | 0 |
| Model seconds per file | 8.98 | 0.0 | 0.0 |
| $ per file | $0.0110 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## blind suite, scan

| Metric | `openai:gpt-5.4-mini@both` | `oracle` | `rules` |
| --- | --- | --- | --- |
| Files | 24 | 24 | 24 |
| Field accuracy | 91% | 100% | 16% |
| Critical-field accuracy | 90% | 100% | 1% |
| Defect recall (95% interval) | 92% (76%-98%) | 92% (76%-98%) | 27% (14%-46%) |
| Defects not flagged | 2 | 2 | 19 |
| Defects caught by the right check | 92% | 92% | 27% |
| Defect precision | 34% | 57% | 47% |
| Defect files sent to the quick queue | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-30%) | 22% (6%-55%) | 0% (0%-30%) |
| Trap false-alarm rate | 40% | 34% | 0% |
| Process flags per file | 1.17 | 0.71 | 2.12 |
| Errors | 0 | 0 | 0 |
| Model seconds per file | 8.51 | 0.0 | 0.0 |
| $ per file | $0.0109 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## blind suite, photo

| Metric | `ollama:qwen2.5vl:7b@both` | `openai:gpt-5.4-mini@both` | `oracle` | `rules` |
| --- | --- | --- | --- | --- |
| Files | 24 | 24 | 24 | 24 |
| Field accuracy | 88% | 90% | 100% | 16% |
| Critical-field accuracy | 86% | 88% | 100% | 0% |
| Defect recall (95% interval) | 88% (71%-96%) | 92% (76%-98%) | 92% (76%-98%) | 27% (14%-46%) |
| Defects not flagged | 3 | 2 | 2 | 19 |
| Defects caught by the right check | 88% | 92% | 92% | 27% |
| Defect precision | 23% | 31% | 46% | 32% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-30%) | 0% (0%-30%) | 22% (6%-55%) | 0% (0%-30%) |
| Trap false-alarm rate | 36% | 42% | 34% | 0% |
| Process flags per file | 1.38 | 0.88 | 0.42 | 2.08 |
| Errors | 0 | 0 | 0 | 0 |
| Model seconds per file | 116.77 | 8.63 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0114 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |

## real suite, real

| Metric | `ollama:qwen2.5vl:7b@both` | `openai:gpt-5.4-mini@both` | `oracle` | `rules` |
| --- | --- | --- | --- | --- |
| Files | 14 | 16 | 16 | 16 |
| Field accuracy | 67% | 82% | 99% | 11% |
| Critical-field accuracy | 66% | 88% | 99% | 0% |
| Defect recall (95% interval) | 100% (68%-100%) | 100% (68%-100%) | 100% (68%-100%) | 88% (53%-98%) |
| Defects not flagged | 0 | 0 | 0 | 1 |
| Defects caught by the right check | 100% | 100% | 100% | 88% |
| Defect precision | 31% | 35% | 67% | 50% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 |
| Straight-through (clean files, 95% interval) | 0% (0%-39%) | 0% (0%-32%) | 0% (0%-32%) | 0% (0%-32%) |
| Trap false-alarm rate | - | - | - | - |
| Process flags per file | 3.0 | 2.69 | 2.5 | 3.06 |
| Errors | 2 | 0 | 0 | 0 |
| Model seconds per file | 70.4 | 4.4 | 0.0 | 0.0 |
| $ per file | $0.0000 | $0.0051 | $0.0000 | $0.0000 |
| Run on | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 | macOS, tesseract 5.5.1 |
