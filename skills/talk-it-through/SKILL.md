---
name: talk-it-through
description: Talk through questions, explain concepts or code, brainstorm options, summarize tradeoffs, and help users think through problems entirely in chat. Use when the user wants discussion, Q&A, explanation, planning, or idea review without modifying files, writing code, running fixes, or changing the repository.
---

# Talk It Through

## Overview

Stay in conversation mode. Help the user understand, decide, or explore without making code changes.

Prefer a direct answer over a long workflow. Read repository files only when that context is needed to answer accurately, and keep all work read-only.

## Workflow

1. Confirm that the request is advisory, explanatory, or exploratory rather than implementation work.
2. Gather only the minimum context needed to answer well.
3. Inspect files or run read-only commands if repository context matters.
4. Answer in chat with clear reasoning, concrete examples, and explicit assumptions.
5. Stop before editing files, running fix-oriented commands, or proposing patches unless the user explicitly changes the request.

## Allowed Work

- Explain code, architecture, algorithms, tests, or errors.
- Summarize files, documents, diffs, or design tradeoffs.
- Brainstorm approaches, compare options, and pressure-test ideas.
- Help the user phrase questions, prompts, or follow-up requests.
- Suggest next steps in prose without implementing them.

## Avoid

- Do not create, edit, delete, or rename files.
- Do not run formatting, linting, tests, migrations, or build commands unless the user explicitly asks for them as part of the discussion.
- Do not slip into implementation mode because a solution seems obvious.
- Do not end with a patch plan unless the user asks for code changes.

## Response Style

- Lead with the answer or recommendation.
- Keep the tone collaborative and low-friction.
- Use short lists only when they make the tradeoffs clearer.
- Call out uncertainty and missing context plainly.
- Ask a concise clarifying question only when the answer would otherwise be unreliable.

## Escalation

If the user asks for implementation after a talk-it-through exchange, acknowledge the shift and move into the normal coding workflow. Treat that as a separate mode from this skill.

## Example Triggers

- "Use $talk-it-through to explain this solver step."
- "Use $talk-it-through to compare these two designs without changing code."
- "Use $talk-it-through to help me think through the API shape."
- "Use $talk-it-through to answer this repo question in chat only."
