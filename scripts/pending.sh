#!/bin/sh
# The runs that need a key this repository does not have: Azure AI Document Intelligence instead of a model
# (needs AZURE_DOCINTEL_ENDPOINT and AZURE_DOCINTEL_KEY; billed per page). Run them on macOS (see README) so
# the standard and hard suites render like the published numbers. The blind and real suites render the same
# everywhere.
set -e
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/bin/python}

$PY -m kyc_demo eval -e azure:prebuilt --suite standard
$PY -m kyc_demo eval -e azure:prebuilt --suite hard
$PY -m kyc_demo generate --suite blind
$PY -m kyc_demo eval -e azure:prebuilt --suite blind
$PY -m kyc_demo fetch-real
$PY -m kyc_demo eval -e azure:prebuilt --suite real --tiers real

$PY -m kyc_demo compare > /dev/null
echo "results/comparison.md updated"
