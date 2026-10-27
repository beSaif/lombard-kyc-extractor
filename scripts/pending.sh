#!/bin/sh
# The runs that need a key this repository does not have. Each line prints what it costs before it runs; run
# them on the machine that produced the published numbers (macOS, see README) so the standard and hard
# suites hit the response cache where they can. The blind and real suites render the same everywhere.
set -e
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/bin/python}

# 1. The best model on the cases built to break it (README estimate: under $1 for all three qualities).
$PY -m kyc_demo eval -e openai:gpt-5.4-mini@both --suite hard

# 2. The blind suite, scored once: the model, the local model, and the oracle ceiling.
$PY -m kyc_demo generate --suite blind
$PY -m kyc_demo eval -e openai:gpt-5.4-mini@both --suite blind
$PY -m kyc_demo eval -e ollama:qwen2.5vl:7b@both --suite blind --tiers photo

# 3. Real specimen passports.
$PY -m kyc_demo fetch-real
$PY -m kyc_demo eval -e openai:gpt-5.4-mini@both -e ollama:qwen2.5vl:7b@both --suite real --tiers real

# 4. A commercial parser instead of a model (needs AZURE_DOCINTEL_ENDPOINT and AZURE_DOCINTEL_KEY; billed per page).
$PY -m kyc_demo eval -e azure:prebuilt --suite standard
$PY -m kyc_demo eval -e azure:prebuilt --suite hard
$PY -m kyc_demo eval -e azure:prebuilt --suite blind
$PY -m kyc_demo eval -e azure:prebuilt --suite real --tiers real

$PY -m kyc_demo compare > /dev/null
echo "results/comparison.md updated"
