#!/bin/sh -l

# LinkCanary GitHub Action Entrypoint
# This script handles the integration between GitHub Actions and LinkCanary

set -e  # Exit immediately if any command fails

# Debug: Print all environment variables starting with INPUT_
# echo "=== DEBUG: Input Environment Variables ==="
# env | grep ^INPUT_ | sort

# Read inputs from environment variables
# GitHub Actions converts input names to uppercase with underscores
SITEMAP_URL="${INPUT_SITEMAP_URL}"
FAIL_ON_PRIORITY="${INPUT_FAIL_ON_PRIORITY:-high}"
MAX_PAGES="${INPUT_MAX_PAGES:-0}"
SKIP_OK="${INPUT_SKIP_OK:-true}"
DELAY="${INPUT_DELAY:-0.5}"
TIMEOUT="${INPUT_TIMEOUT:-10}"
AUTH_USER="${INPUT_AUTH_USER}"
AUTH_PASS="${INPUT_AUTH_PASS}"
WEBHOOK_URL="${INPUT_WEBHOOK_URL}"
INTERNAL_ONLY="${INPUT_INTERNAL_ONLY:-false}"
INCLUDE_SUBDOMAINS="${INPUT_INCLUDE_SUBDOMAINS:-false}"

# Initialize variables
LOCAL_SERVER_PID=""
REPORT_PATH="link_report.csv"
EXIT_CODE=0

# Cleanup function to kill local server if started
cleanup() {
    if [ -n "$LOCAL_SERVER_PID" ]; then
        echo "Cleaning up local HTTP server (PID: $LOCAL_SERVER_PID)"
        kill "$LOCAL_SERVER_PID" 2>/dev/null || true
    fi
}

# Set trap to ensure cleanup runs on exit
trap cleanup EXIT

# Function to start local HTTP server for file-based sitemaps
start_local_server() {
    echo "Starting local HTTP server for file-based sitemap..."
    python3 -m http.server 8080 &
    LOCAL_SERVER_PID=$!
    sleep 2  # Give server time to start
    echo "Local server started on PID: $LOCAL_SERVER_PID"
}

# Handle local file vs remote URL
if echo "$SITEMAP_URL" | grep -q '^http'; then
    echo "Using remote sitemap URL: $SITEMAP_URL"
    PROCESSED_SITEMAP_URL="$SITEMAP_URL"
else
    echo "Using local sitemap file: $SITEMAP_URL"
    start_local_server
    PROCESSED_SITEMAP_URL="http://localhost:8080/$SITEMAP_URL"
    echo "Serving local file at: $PROCESSED_SITEMAP_URL"
fi

# Build the linkcheck command
LINKCHECK_CMD="linkcheck $PROCESSED_SITEMAP_URL \
    --max-pages $MAX_PAGES \
    --delay $DELAY \
    --timeout $TIMEOUT \
    --csv-report $REPORT_PATH"

# Add optional flags
if [ "$SKIP_OK" = "true" ]; then
    LINKCHECK_CMD="$LINKCHECK_CMD --skip-ok"
fi

if [ "$INTERNAL_ONLY" = "true" ]; then
    LINKCHECK_CMD="$LINKCHECK_CMD --internal-only"
fi

if [ "$INCLUDE_SUBDOMAINS" = "true" ]; then
    LINKCHECK_CMD="$LINKCHECK_CMD --include-subdomains"
fi

if [ -n "$AUTH_USER" ] && [ -n "$AUTH_PASS" ]; then
    LINKCHECK_CMD="$LINKCHECK_CMD --auth $AUTH_USER:$AUTH_PASS"
fi

echo "Running LinkCanary with command:"
echo "$LINKCHECK_CMD"

# Execute the crawl and capture exit code
set +e  # Temporarily disable exit on error to capture exit code
eval "$LINKCHECK_CMD"
LINKCHECK_EXIT_CODE=$?
set -e  # Re-enable exit on error

echo "LinkCanary completed with exit code: $LINKCHECK_EXIT_CODE"

# Parse the CSV report to extract issue counts
if [ -f "$REPORT_PATH" ]; then
    echo "Parsing report: $REPORT_PATH"
    
    # Skip header and count issues by priority
    TOTAL_ISSUES=$(tail -n +2 "$REPORT_PATH" | wc -l)
    CRITICAL_COUNT=$(grep -c ',critical$' "$REPORT_PATH" || echo 0)
    HIGH_COUNT=$(grep -c ',high$' "$REPORT_PATH" || echo 0)
    MEDIUM_COUNT=$(grep -c ',medium$' "$REPORT_PATH" || echo 0)
    LOW_COUNT=$(grep -c ',low$' "$REPORT_PATH" || echo 0)
    
    # Remove any trailing carriage returns
    TOTAL_ISSUES=$(echo "$TOTAL_ISSUES" | tr -d '\r')
    CRITICAL_COUNT=$(echo "$CRITICAL_COUNT" | tr -d '\r')
    HIGH_COUNT=$(echo "$HIGH_COUNT" | tr -d '\r')
    MEDIUM_COUNT=$(echo "$MEDIUM_COUNT" | tr -d '\r')
    LOW_COUNT=$(echo "$LOW_COUNT" | tr -d '\r')
    
    echo "Issue counts:"
    echo "  Total: $TOTAL_ISSUES"
    echo "  Critical: $CRITICAL_COUNT"
    echo "  High: $HIGH_COUNT"
    echo "  Medium: $MEDIUM_COUNT"
    echo "  Low: $LOW_COUNT"
else
    echo "Error: Report file not found at $REPORT_PATH"
    TOTAL_ISSUES=0
    CRITICAL_COUNT=0
    HIGH_COUNT=0
    MEDIUM_COUNT=0
    LOW_COUNT=0
fi

# Set GitHub Action outputs
if [ -n "$GITHUB_OUTPUT" ]; then
    echo "Setting GitHub Action outputs..."
    echo "total-issues=$TOTAL_ISSUES" >> "$GITHUB_OUTPUT"
    echo "critical-count=$CRITICAL_COUNT" >> "$GITHUB_OUTPUT"
    echo "high-count=$HIGH_COUNT" >> "$GITHUB_OUTPUT"
    echo "medium-count=$MEDIUM_COUNT" >> "$GITHUB_OUTPUT"
    echo "report-path=$REPORT_PATH" >> "$GITHUB_OUTPUT"
    echo "exit-code=$LINKCHECK_EXIT_CODE" >> "$GITHUB_OUTPUT"
fi

# Generate GitHub Step Summary
if [ -n "$GITHUB_STEP_SUMMARY" ]; then
    echo "Generating GitHub Step Summary..."
    cat > "$GITHUB_STEP_SUMMARY" << EOF
# LinkCanary Report Summary

## 🔍 Crawl Results

| Metric | Count |
|--------|-------|
| **Total Issues** | $TOTAL_ISSUES |
| **Critical** | $CRITICAL_COUNT |
| **High** | $HIGH_COUNT |
| **Medium** | $MEDIUM_COUNT |
| **Low** | $LOW_COUNT |

## 📊 Priority Breakdown

<details>
<summary>Show Details</summary>

- **Critical Issues**: $CRITICAL_COUNT (require immediate attention)
- **High Priority**: $HIGH_COUNT (should be fixed soon)
- **Medium Priority**: $MEDIUM_COUNT (consider fixing)
- **Low Priority**: $LOW_COUNT (optional fixes)

</details>

## 📄 Report

- [Download CSV Report]($REPORT_PATH)
- Generated by [LinkCanary](https://github.com/chesterbeard/linkcanary)
EOF
fi

# Send webhook notification if configured
if [ -n "$WEBHOOK_URL" ]; then
    echo "Sending webhook notification to: $WEBHOOK_URL"
    
    # Create JSON payload
    WEBHOOK_PAYLOAD=$(cat <<EOF
{
  "event": "linkcanary.crawl_complete",
  "repository": "$GITHUB_REPOSITORY",
  "commit": "$GITHUB_SHA",
  "ref": "$GITHUB_REF",
  "summary": {
    "total_issues": $TOTAL_ISSUES,
    "critical": $CRITICAL_COUNT,
    "high": $HIGH_COUNT,
    "medium": $MEDIUM_COUNT,
    "low": $LOW_COUNT
  },
  "report_url": "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
}
EOF
    )
    
    # Send POST request
    curl -X POST -H "Content-Type: application/json" -d "$WEBHOOK_PAYLOAD" "$WEBHOOK_URL" || echo "Webhook delivery failed"
fi

# Priority-based exit logic
PRIORITY_VALUE=0
case "$FAIL_ON_PRIORITY" in
  critical) PRIORITY_VALUE=4 ;;
  high) PRIORITY_VALUE=3 ;;
  medium) PRIORITY_VALUE=2 ;;
  low) PRIORITY_VALUE=1 ;;
  none) PRIORITY_VALUE=0 ;;
  *) PRIORITY_VALUE=3 ;;  # Default to high
esac

echo "Priority threshold: $FAIL_ON_PRIORITY (value: $PRIORITY_VALUE)"

# Determine if we should fail the build
SHOULD_FAIL=0

if [ "$PRIORITY_VALUE" -ge 4 ] && [ "$CRITICAL_COUNT" -gt 0 ]; then
    echo "❌ Build failed: Critical issues found"
    SHOULD_FAIL=1
elif [ "$PRIORITY_VALUE" -ge 3 ] && [ $((CRITICAL_COUNT + HIGH_COUNT)) -gt 0 ]; then
    echo "❌ Build failed: High or critical issues found"
    SHOULD_FAIL=1
elif [ "$PRIORITY_VALUE" -ge 2 ] && [ $((CRITICAL_COUNT + HIGH_COUNT + MEDIUM_COUNT)) -gt 0 ]; then
    echo "❌ Build failed: Medium or higher priority issues found"
    SHOULD_FAIL=1
elif [ "$PRIORITY_VALUE" -ge 1 ] && [ "$TOTAL_ISSUES" -gt 0 ]; then
    echo "❌ Build failed: Any issues found"
    SHOULD_FAIL=1
else
    echo "✅ Build passed: No issues at specified priority level"
    SHOULD_FAIL=0
fi

# Exit with appropriate code
exit $SHOULD_FAIL