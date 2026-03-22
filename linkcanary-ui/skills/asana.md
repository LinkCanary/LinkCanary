---
name: asana
description: A tool for creating tasks in Asana.
---

# Asana Skill

## Overview

This skill allows an AI agent to create a new task in Asana.

## When to Use

Use this skill when you need to:

*   Create a new task in a specific Asana project.

## Instructions

### 1. Create a New Task

To create a new task, use the `create_asana_task` tool.

**Tool:** `create_asana_task`

**Parameters:**

*   `title` (string, required): The title of the task.
*   `notes` (string, optional): The notes or description for the task.

**Example:**

```json
{
  "tool": "create_asana_task",
  "title": "Fix broken links on the website",
  "notes": "There are several broken links that need to be fixed. See the latest LinkCanary report for details."
}
```

**Output:**

A JSON object containing the ID of the newly created task.

```json
{
  "task_id": "some-unique-task-id"
}
```
