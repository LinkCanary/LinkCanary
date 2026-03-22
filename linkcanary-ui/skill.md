---
name: linkcanary
description: A tool for crawling websites to find broken links and check the status of crawls.
---

# LinkCanary Skill

## Overview

This skill allows an AI agent to interact with the LinkCanary API to perform two main actions:

1.  **Start a new crawl:** Initiate a new link-checking crawl for a given URL.
2.  **Check crawl status:** Get the status and results of a previously started crawl.

## When to Use

Use this skill when you need to:

*   Verify the integrity of links on a website.
*   Check for broken links on a specific URL.
*   Monitor the progress of a link-checking scan.

## Instructions

### 1. Start a New Crawl

To start a new crawl, use the `start_crawl` tool.

**Tool:** `start_crawl`

**Parameters:**

*   `url` (string, required): The URL to start the crawl from.

**Example:**

```json
{
  "tool": "start_crawl",
  "url": "https://example.com"
}
```

**Output:**

A JSON object containing the `crawl_id` of the newly started crawl.

```json
{
  "crawl_id": "some-unique-crawl-id"
}
```

### 2. Check Crawl Status

To check the status of a crawl, use the `check_crawl_status` tool.

**Tool:** `check_crawl_status`

**Parameters:**

*   `crawl_id` (string, required): The ID of the crawl to check.

**Example:**

```json
{
  "tool": "check_crawl_status",
  "crawl_id": "some-unique-crawl-id"
}
```

**Output:**

A JSON object containing the status of the crawl and any results.

```json
{
  "status": "completed",
  "results": {
    "broken_links": [
      {
        "url": "https://example.com/broken",
        "status_code": 404
      }
    ]
  }
}
```
