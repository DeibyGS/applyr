#!/bin/bash
# applyr CLI examples — run from repo root or after `pip install applyr`
# Usage: bash examples/cli_usage.sh

set -e

echo "=== applyr CLI examples ==="
echo ""

# Setup
echo "--- init ---"
applyr init
echo ""

# Add offers
echo "--- add (JSON from argument) ---"
applyr add '{"title":"Frontend Engineer","company":"WebCo","tech_stack":"React,TypeScript","compatibility_pct":72}'
echo ""

echo "--- add (JSON from stdin) ---"
echo '{"title":"DevOps Engineer","company":"CloudInc","tech_stack":"Kubernetes,Terraform","compatibility_pct":68}' | applyr add -
echo ""

# List
echo "--- list ---"
applyr list
echo ""

# Show
echo "--- show 1 ---"
applyr show 1
echo ""

# Pipeline
echo "--- pipeline ---"
applyr pipeline
echo ""

# Stats
echo "--- stats ---"
applyr stats
echo ""

# Search
echo "--- search ---"
applyr search "Engineer"
echo ""

# Gaps
echo "--- gaps ---"
applyr gaps
echo ""

# Trends
echo "--- trends ---"
applyr trends --period week
echo ""

# Summary (JSON for agents)
echo "--- summary --json ---"
applyr summary --json
echo ""

# Compare
echo "--- compare ---"
applyr compare 1 2
echo ""

# Export
echo "--- export ---"
applyr export --format json
echo ""

# Doctor
echo "--- doctor ---"
applyr doctor
echo ""

# Version
echo "--- version ---"
applyr version
echo ""

echo "=== Done ==="
