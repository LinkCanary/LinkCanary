---
name: jira
description: A tool for creating issues in Jira.
---

# Jira Skill

## Overview

This skill allows an AI agent to create a new issue in Jira.

## When to Use

Use this skill when you need to:

*   Create a new issue in a specific Jira project.

## Instructions

### 1. Create a New Issue

To create a new issue, use the `create_jira_issue` tool.

**Tool:** `create_jira_issue`

**Parameters:**

*   `summary` (string, required): The summary or title of the issue.
*   `description` (string, optional): The description for the issue.

**Example:**

```json
{
  "tool": "create_jira_issue",
  "summary": "Fix broken links on the website",
  "description": "There are several broken links that need to be fixed. See the latest LinkCanary report for details."
}
```

**Output:**

A JSON object containing the ID and key of the newly created issue.

```json
{
  "issue_id": "some-unique-issue-id",
  "issue_key": "PROJ-123"
}
```
