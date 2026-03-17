---
name: pr-review-toolkit
description: "Extensive pull-request-style code review for local branches, working tree diffs, commit ranges, and PR-sized changesets. Use when Codex needs to review code like a human reviewer: inspect a diff against a base branch, surface concrete bugs or regressions, assess security and test risk, or split a broad review across multiple agents. Helpful for prompts like 'review this branch', 'do a PR review', 'find issues in this diff', 'act like a reviewer', or 'run a multi-agent code review'."
---

# PR Review Toolkit

## Overview

Perform findings-first code review against a real diff, not a vague codebase skim.
Scope the exact change, inspect the highest-risk files first, validate suspicious
behavior against surrounding code and tests, and report only actionable findings.

## Quick Start

1. Resolve the review target. Prefer an explicit `base..head` range over ad hoc
   file browsing.
2. Run the bundled context collector before deep reading:

```bash
python3 skills/pr-review-toolkit/scripts/collect_pr_context.py --base origin/main --head HEAD
```

3. Read `references/review_rubric.md` for severity and evidence standards.
4. If the diff is broad or high-risk, read `references/multi_agent_review.md`
   and split the review.
5. Return findings first. Use `references/review_output.md` for the response
   shape.

## Review Workflow

### 1. Choose the review target

- Review a real range and state it explicitly in the final answer.
- For branch review, compare the branch against the default branch or an
  explicit user-supplied base.
- For staged or working-tree review, use the script's alternate modes instead of
  silently reviewing only committed changes.

### 2. Build context before judging the patch

- Run `scripts/collect_pr_context.py` to gather commits, changed files, hotspots,
  file categories, and test signals.
- Use the output to pick the first files to inspect in full.
- Read full files around suspicious hunks. Do not make final claims from diff
  snippets alone.

### 3. Decide whether to parallelize

- Stay single-agent for small, focused diffs in one subsystem.
- Split the review when the change is large, spans unrelated directories, mixes
  code and infra, or touches security, migrations, or public APIs.
- Keep synthesis local. Agents should return findings; the lead reviewer should
  merge, de-duplicate, and verify them.

### 4. Review in risk order

Inspect these categories in order unless the user asks for something narrower:

1. Correctness and behavioral regressions
2. Security, authorization, and data safety
3. State, caching, ordering, and concurrency issues
4. API, CLI, config, and migration compatibility
5. Tests: missing coverage, weakened assertions, misleading fixtures
6. Performance only when the concern is concrete and user-visible
7. Maintainability only when it plausibly causes breakage or review blind spots

### 5. Validate each finding

- Trace the code path through callers, callees, and related tests as needed.
- Check whether the changed tests actually cover the risky behavior.
- Run focused local tests when quick and relevant. If not run, say so.
- Do not report speculation. Every finding needs evidence from code, types,
  tests, docs, or an executable path through the program.

### 6. Write the review

- Put findings first and sort them by severity.
- Give each finding a file reference, the issue, the impact, and the reason the
  current code causes it.
- After findings, include open questions or assumptions, then a brief overall
  assessment.
- If there are no verified findings, say so explicitly and mention residual risk
  or testing gaps.

## Bundled Resources

- `scripts/collect_pr_context.py`
  Gather the review range, commits, changed files, hotspots, and test signals.
- `references/review_rubric.md`
  Severity definitions, evidence rules, and common failure modes.
- `references/review_output.md`
  Findings-first response contract and compact examples.
- `references/multi_agent_review.md`
  Split points, agent ownership patterns, and prompt templates for parallel
  review.
