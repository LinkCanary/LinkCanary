#!/bin/sh -l
set -e

# LinkCanary GitHub Action Entrypoint
# Parses inputs, runs linkcheck, sets outputs, triggers webhooks

# Ensure output directory exists
mkdir -p /output

# Parse inputs from environment variables (GitHub Actions sets these)
SITEMAP_URL="${INPUT_SITEMAP_URL:-$1}"
FAIL_ON="${INPUT_FAIL_ON_PRIORITY:-high}"
MAX_PAGES="${INPUT_MAX_PAGES:-0}"
SKIP_OK="${INPUT_SKIP_OK:-true}"
DELAY="${INPUT_DELAY:-0.5}"
TIMEOUT="${INPUT_TIMEOUT:-10}"
FORMAT="${INPUT_FORMAT:-csv}"
EXCLUDE_PATTERNS="${INPUT_EXCLUDE_PATTERN:-}"
INCLUDE_PATTERNS="${INPUT_INCLUDE_PATTERN:-}"
PATTERN_TYPE="${INPUT_PATTERN_TYPE:-glob}"
WEBHOOK_URL="${INPUT_WEBHOOK_URL:-}"

# Determine output file extension based on format
case "$FORMAT" in
  json)   REPORT_EXT="json" ;;
  mdx)    REPORT_EXT="mdx" ;;
  xlsx)   REPORT_EXT="xlsx" ;;
  pdf)    REPORT_EXT="pdf" ;;
  *)      REPORT_EXT="csv" ;;
esac

# Validate required input
if [ -z "$SITEMAP_URL" ]; then
    echo "::error::sitemap-url is required"
    exit 2
fi

# Build command arguments
ARGS="--fail-on-priority ${FAIL_ON}"
ARGS="$ARGS --output /output/link_report.${REPORT_EXT}"
ARGS="$ARGS --format ${FORMAT}"
ARGS="$ARGS --html-report /output/report.html"
ARGS="$ARGS --delay ${DELAY}"
ARGS="$ARGS --timeout ${TIMEOUT}"
ARGS="$ARGS --ci"

if [ "$MAX_PAGES" != "0" ] && [ -n "$MAX_PAGES" ]; then
    ARGS="$ARGS --max-pages ${MAX_PAGES}"
fi

if [ "$SKIP_OK" = "true" ]; then
    ARGS="$ARGS --skip-ok"
fi

# Add pattern filtering
if [ -n "$EXCLUDE_PATTERNS" ]; then
    # Handle multiline input
  echo "$EXCLUDE_PATTERNS" | while read -r pattern; do
    if [ -n "$pattern" ]; then
      ARGS="$ARGS --exclude-pattern \"${pattern}\""
    fi
  done
  # Simpler approach for single patterns
  PATTERN_COUNT=$(echo "$EXCLUDE_PATTERNS" | grep -c . || echo 0)
  if [ "$PATTERN_COUNT" -gt 0 ]; then
    for pattern in $EXCLUDE_PATTERNS; do
      ARGS="$ARGS --exclude-pattern '${pattern}'"
    done
  fi
fi

if [ -n "$INCLUDE_PATTERNS" ]; then
  for pattern in $INCLUDE_PATTERNS; do
    if [ -n "$pattern" ]; then
      ARGS="$ARGS --include-pattern '${pattern}'"
    fi
  done
fi

if [ "$PATTERN_TYPE" = "regex" ]; then
    ARGS="$ARGS --pattern-type regex"
fi

# Run LinkCanary
echo "Running LinkCanary..."
echo "Sitemap: ${SITEMAP_URL}"
echo "Fail on priority: ${FAIL_ON}"
echo "Format: ${FORMAT}"
if [ -n "$EXCLUDE_PATTERNS" ]; then
    echo "Exclude patterns: ${EXCLUDE_PATTERNS}"
fi
if [ -n "$INCLUDE_PATTERNS" ]; then
    echo "Include patterns: ${INCLUDE_PATTERNS}"
fi

cd /linkcanary
linkcheck "${SITEMAP_URL}" $ARGS
EXIT_CODE=$?

# Copy reports to GitHub workspace if available
REPORT_PATH="/output/link_report.${REPORT_EXT}"
if [ -n "$GITHUB_WORKSPACE" ] && [ -f "$REPORT_PATH" ]; then
    cp "$REPORT_PATH" "$GITHUB_WORKSPACE/link_report.${REPORT_EXT}" 2>/dev/null || true
    cp /output/report.html "$GITHUB_WORKSPACE/report.html" 2>/dev/null || true
    REPORT_PATH="$GITHUB_WORKSPACE/link_report.${REPORT_EXT}"
fi

# Parse issue counts from report for outputs
CRITICAL_COUNT=0
HIGH_COUNT=0
MEDIUM_COUNT=0
LOW_COUNT=0
TOTAL_ISSUES=0

# Parse from CSV (still generate CSV for stats even if different format requested)
if [ -f "/output/link_report.csv" ]; then
    TOTAL_ISSUES=$(tail -n +2 /output/link_report.csv | wc -l | tr -d ' ')
    CRITICAL_COUNT=$(tail -n +2 /output/link_report.csv | grep -c ',critical,' 2>/dev/null || echo 0)
    HIGH_COUNT=$(tail -n +2 /output/link_report.csv | grep -c ',high,' 2>/dev/null || echo 0)
    MEDIUM_COUNT=$(tail -n +2 /output/link_report.csv | grep -c ',medium,' 2>/dev/null || echo 0)
    LOW_COUNT=$(tail -n +2 /output/link_report.csv | grep -c ',low,' 2>/dev/null || echo 0)
elif [ -f "/output/link_report.json" ]; then
    # Parse from JSON if CSV not available
    TOTAL_ISSUES=$(grep -o '"total_issues": [0-9]*' /output/link_report.json | grep -o '[0-9]*' || echo 0)
fi

# Set GitHub Actions outputs
echo "total-issues=${TOTAL_ISSUES}" >> $GITHUB_OUTPUT
echo "critical-count=${CRITICAL_COUNT}" >> $GITHUB_OUTPUT
echo "high-count=${HIGH_COUNT}" >> $GITHUB_OUTPUT
echo "medium-count=${MEDIUM_COUNT}" >> $GITHUB_OUTPUT
echo "low-count=${LOW_COUNT}" >> $GITHUB_OUTPUT
echo "report-path=${REPORT_PATH}" >> $GITHUB_OUTPUT

# Output summary for GitHub Actions
echo ""
echo "## LinkCanary Results" >> $GITHUB_STEP_SUMMARY
echo "" >> $GITHUB_STEP_SUMMARY
echo "| Priority | Count |" >> $GITHUB_STEP_SUMMARY
echo "|----------|-------|" >> $GITHUB_STEP_SUMMARY
echo "| Critical | ${CRITICAL_COUNT} |" >> $GITHUB_STEP_SUMMARY
echo "| High | ${HIGH_COUNT} |" >> $GITHUB_STEP_SUMMARY
echo "| Medium | ${MEDIUM_COUNT} |" >> $GITHUB_STEP_SUMMARY
echo "| Low | ${LOW_COUNT} |" >> $GITHUB_STEP_SUMMARY
echo "| **Total** | **${TOTAL_ISSUES}** |" >> $GITHUB_STEP_SUMMARY
echo "" >> $GITHUB_STEP_SUMMARY

# Show top 10 issues if any
if [ "$TOTAL_ISSUES" -gt 0 ]; then
    echo "### Top Issues Found" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "| Link URL | Status | Priority | Issue Type |" >> $GITHUB_STEP_SUMMARY
    echo "|----------|--------|----------|------------|" >> $GITHUB_STEP_SUMMARY
    tail -n +2 /output/link_report.csv | head -n 10 | while IFS=, read -r source count example url text type status issue priority rest; do
        url_short=$(echo "$url" | cut -c1-50)
        echo "| \`${url_short}...\` | ${status} | ${priority} | ${issue} |" >> $GITHUB_STEP_SUMMARY
    done
    echo "" >> $GITHUB_STEP_SUMMARY
fi

echo "📁 **Reports:** \`link_report.csv\`, \`report.html\`" >> $GITHUB_STEP_SUMMARY

# Trigger webhook if configured (future extensibility)
if [ -n "$WEBHOOK_URL" ] && [ "$TOTAL_ISSUES" -gt 0 ]; then
    echo ""
    echo "Triggering webhook notification..."
    WEBHOOK_PAYLOAD=$(cat <<EOF
{
  "event": "link_check_completed",
  "repository": "${GITHUB_REPOSITORY}",
  "commit": "${GITHUB_SHA}",
  "ref": "${GITHUB_REF}",
  "summary": {
    "total_issues": ${TOTAL_ISSUES},
    "critical": ${CRITICAL_COUNT},
    "high": ${HIGH_COUNT},
    "medium": ${MEDIUM_COUNT},
    "low": ${LOW_COUNT}
  },
  "report_url": "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
}
EOF
)
    curl -s -X POST -H "Content-Type: application/json" -d "$WEBHOOK_PAYLOAD" "$WEBHOOK_URL" > /dev/null 2>&1 || true
    echo "Webhook triggered"
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ No issues found at ${FAIL_ON}+ priority level"
else
    echo "❌ Issues found at ${FAIL_ON}+ priority level - failing build"
fi

exit $EXIT_CODE
