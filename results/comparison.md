# Extractor comparison

Synthetic files, review date 2026-10-21.

## clean (30 files)

| Metric | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Field accuracy | 100% | 100% | 100% | 86% | 100% | 99% | 54% |
| Critical-field accuracy | 100% | 100% | 100% | 88% | 100% | 99% | 48% |
| Defect recall | 100% | 100% | 100% | 84% | 100% | 100% | 37% |
| Defect precision | 90% | 100% | 100% | 43% | 95% | 90% | 32% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files) | 93% | 93% | 93% | 21% | 86% | 86% | 0% |
| Trap false-alarm rate | 0% | 0% | 0% | 15% | 4% | 6% | 2% |
| Process flags per file | 0.13 | 0.13 | 0.1 | 0.73 | 0.13 | 0.13 | 1.27 |
| Model seconds per file | 8.19 | 16.3 | 8.11 | 8.78 | 9.77 | 9.23 | 0.0 |
| $ per file | $0.0047 | $0.0149 | $0.0102 | $0.0071 | $0.0100 | $0.0565 | $0.0000 |

## scan (30 files)

| Metric | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Field accuracy | 99% | 99% | 99% | 83% | 99% | 99% | 20% |
| Critical-field accuracy | 100% | 100% | 100% | 82% | 100% | 99% | 8% |
| Defect recall | 95% | 100% | 100% | 68% | 100% | 100% | 26% |
| Defect precision | 86% | 95% | 95% | 38% | 95% | 90% | 46% |
| Defect files sent to the quick queue | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files) | 71% | 79% | 79% | 14% | 79% | 71% | 0% |
| Trap false-alarm rate | 0% | 0% | 0% | 13% | 0% | 0% | 0% |
| Process flags per file | 0.33 | 0.33 | 0.23 | 0.97 | 0.23 | 0.27 | 1.3 |
| Model seconds per file | 8.64 | 18.0 | 9.36 | 10.11 | 10.96 | 9.53 | 0.0 |
| $ per file | $0.0048 | $0.0159 | $0.0111 | $0.0081 | $0.0108 | $0.0574 | $0.0000 |

## photo (30 files)

| Metric | `ollama:qwen2.5:7b@text` | `ollama:qwen2.5vl:7b@both` | `ollama:qwen2.5vl:7b@both#regex-only-injection` | `openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both+openai:gpt-4.1-mini@both` | `openai:gpt-5.4-mini@both` | `openai:gpt-5.4-mini@text` | `openai:gpt-5.4-mini@vision` | `openai:gpt-5.5@both` | `rules` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Field accuracy | 69% | 99% | 99% | 99% | 99% | 99% | 79% | 99% | 99% | 35% |
| Critical-field accuracy | 59% | 99% | 99% | 99% | 99% | 99% | 76% | 99% | 99% | 23% |
| Defect recall | 47% | 100% | 95% | 100% | 100% | 100% | 79% | 100% | 100% | 37% |
| Defect precision | 27% | 48% | 78% | 86% | 90% | 90% | 47% | 90% | 90% | 64% |
| Defect files sent to the quick queue | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Straight-through (clean files) | 0% | 29% | 64% | 57% | 71% | 79% | 0% | 86% | 79% | 0% |
| Trap false-alarm rate | 15% | 6% | 6% | 2% | 0% | 0% | 11% | 0% | 2% | 0% |
| Process flags per file | 1.47 | 0.17 | 0.17 | 0.27 | 0.27 | 0.17 | 1.17 | 0.17 | 0.2 | 1.17 |
| Model seconds per file | 38.79 | 76.14 | 76.14 | 8.38 | 16.74 | 8.36 | 9.28 | 9.32 | 9.21 | 0.0 |
| $ per file | $0.0000 | $0.0000 | $0.0000 | $0.0050 | $0.0157 | $0.0106 | $0.0074 | $0.0105 | $0.0595 | $0.0000 |
