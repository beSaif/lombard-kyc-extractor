#!/bin/sh
# Re-score every saved eval from the response cache: no model call is made (KYC_OFFLINE=1), so a change to
# grounding, rules or routing can be measured on every extractor for free. A prompt change misses the cache
# and fails loudly instead of spending money.
set -e
cd "$(dirname "$0")/.."
export KYC_OFFLINE=1
PY=${PYTHON:-.venv/bin/python}
run() { $PY -m kyc_demo eval "$@" > /dev/null; }

run -e rules -e openai:gpt-4.1-mini@both -e openai:gpt-5.4-mini@both -e openai:gpt-5.4-mini@text \
    -e openai:gpt-5.4-mini@vision -e openai:gpt-5.5@both
run -e openai:gpt-5.4-mini@both --second openai:gpt-4.1-mini@both
run -e ollama:qwen2.5:7b@text -e ollama:qwen2.5vl:7b@both --tiers photo --workers 6
KYC_MODEL_INJECTION_DETECTOR=off run -e ollama:qwen2.5vl:7b@both --tiers photo --workers 6
# hard_017 and hard_018 (the decoys) were added later and have no cached responses: replay the first 16.
run -e ollama:qwen2.5vl:7b@both --suite hard --tiers photo --limit 16 --workers 6
# No model at all: the oracle (the true values) on both suites; oracle:decoy quotes the hard decoys.
run -e oracle --workers 4
run -e rules -e oracle -e oracle:decoy --suite hard --workers 4
$PY -m kyc_demo compare > /dev/null
echo "results/comparison.md updated"
