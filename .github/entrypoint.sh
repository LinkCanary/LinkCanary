#!/bin/bash
set -e

# LinkCanary GitHub Action Entrypoint
# Parses inputs, runs linkcheck, sets outputs

# Ensure output directory exists
mkdir -p /output

# Parse inputs from environment variables (GitHub Actions sets these)
SITEMAP_URL="${INPUT_SITEMAP_URL:-$1}"
FAIL_ON="${INPUT_FAIL_ON_PRIORITY:-high}"
MAX_PAGES="${INPUT_MAX_PAGES:-0}"
SKIP_OK="${INPUT_SKIP_OK:-true}"
DELAY="${INPUT_DELAY:-0.5}"
TIMEOUT="${INPUT_TIMEOUT:-10}"
USER_AGENT="${INPUT_USER_AGENT:-LinkCanary/1.0}"
INTERNAL_ONLY="${INPUT_INTERNAL_ONLY:-false}"
EXTERNAL_ONLY="${INPUT_EXTERNAL_ONLY:-false}"
INCLUDE_SUBDOMAINS="${INPUT_INCLUDE_SUBDOMAINS:-false}"

# Validate required input
if [ -z "$SITEMAP_URL" ]; then
    echo "::error::sitemap-url is required"
    exit 2
fi

# Build command arguments
ARGS="--fail-on-priority ${FAIL_ON}"
ARGS="$ARGS --output /output/link_report.csv"
ARGS="$ARGS --html-report /output/report.html"
ARGS="$ARGS --delay ${DELAY}"
ARGS="$ARGS --timeout ${TIMEOUT}"
ARGS="$ARGS --user-agent \"${USER_AGENT}\""
ARGS="$ARGS --ci"

if [ "$MAX_PAGES" != "0" ] && [ -n "$MAX_PAGES" ]; then
    ARGS="$ARGS --max-pages ${MAX_PAGES}"
fi

if [ "$SKIP_OK" = "true" ]; then
    ARGS="$ARGS --skip-ok"
fi

if [ "$INTERNAL_ONLY" = "true" ]; then
    ARGS="$ARGS --internal-only"
fi

if [ "$EXTERNAL_ONLY" = "true" ]; then
    ARGS="$ARGS --external-only"
fi

if [ "$INCLUDE_SUBDOMAINS" = "true" ]; then
    ARGS="$ARGS --include-subdomains"
fi

# Run LinkCanary
echo "Running LinkCanary..."
echo "Sitemap: ${SITEMAP_URL}"
echo "Fail on priority: ${FAIL_ON}"

cd /linkcanary
linkcheck "${SITEMAP_URL}" $ARGS
EXIT_CODE=$?

# Copy reports to GitHub workspace if available
if [ -n "$GITHUB_WORKSPACE" ]; then
    cp /output/link_report.csv "$GITHUB_WORKSPACE/" 2>/dev/null || true
    cp /output/report.html "$GITHUB_WORKSPACE/" 2>/dev/null || true
fi

# Output summary for GitHub Actions
echo ""
echo "## LinkCanary Results" >> $GITHUB_STEP_SUMMARY
echo "" >> $GITHUB_STEP_SUMMARY

if [ -f /output/link_report.csv ]; then
    ISSUES=$(wc -l < /output/link_report.csv)
    echo "📊 **Total Issues:** $((ISSUES))" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    
    # Show top 10 issues if any
    if [ "$ISSUES" -gt 1 ]; then
        echo "### Top Issues Found" >> $GITHUB_STEP_SUMMARY
        echo "" >> $GITHUB_STEP_SUMMARY
        echo "| Link URL | Status | Priority | Issue Type |" >> $GITHUB_STEP_SUMMARY
        echo "|----------|--------|----------|------------|" >> $GITHUB_STEP_SUMMARY
        head -n 11 /output/link_report.csv | tail -n 10 | while IFS=, read -r source count example url text type status issue priority rest; do
            echo "| \`${url:0:50}...\` | ${status} | ${priority} | ${issue} |" >> $GITHUB_STEP_SUMMARY
        done
        echo "" >> $GITHUB_STEP_SUMMARY
    fi
    
    echo "📁 **Reports:**" >> $GITHUB_STEP_SUMMARY
    echo "- CSV: \`link_report.csv\`" >> $GITHUB_STEP_SUMMARY
    echo "- HTML: \`report.html\`" >> $GITHUB_STEP_SUMMARY
fi

# Set exit code output
echo "exit-code=${EXIT_CODE}" >> $GITHUB_OUTPUT

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ No issues found at ${FAIL_ON}+ priority level"
else
    echo "❌ Issues found at ${FAIL_ON}+ priority level - failing build"
fi

exit $EXIT_CODE
