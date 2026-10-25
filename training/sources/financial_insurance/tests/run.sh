#!/usr/bin/env bash
# Self-test on local fixtures (no network): render the fixture template, build from
# fixture Gretel-like rows (one per drop reason), and check the outputs.
set -euo pipefail
cd "$(dirname "$0")/.."
out="$(mktemp -d)"
python3 build_real.py --templates tests/fixture_templates --out "$out/insurance_real.jsonl"
python3 build_gretel.py --rows tests/gretel_rows.jsonl --out-dir "$out" --n 10
python3 check.py "$out/insurance_real.jsonl" "$out/financial.jsonl" "$out/insurance.jsonl"
echo "self-test passed ($out)"
