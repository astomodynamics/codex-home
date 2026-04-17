---
name: git-branch-commit-pr
description: Use for creating a branch, committing staged or unstaged changes safely, pushing the branch, and opening a pull request by extending the git-commit and git-pr workflows.
---

# Purpose

Compose the existing `git-commit` and `git-pr` workflows into one publish flow: create or confirm the feature branch, commit the intended changes, push the branch, and open the PR.

# When to use

- You want one end-to-end flow from local changes to an open PR
- You need a safe branch name derived from the actual work
- You want commit and PR text grounded in the real diff

# Do not use

- Cases that require history rewriting, rebasing, or `--amend`
- Cases where the worktree contains unrelated changes that should not be grouped together
- Cases where the user only wants a commit or only wants a PR

# Workflow

1. Inspect branch state and worktree before changing anything
2. If already on the intended feature branch, keep it; otherwise draft a branch name from the work and create it with `git switch -c <branch>`
3. Follow the `git-commit` workflow:
   - check staged changes first
   - if staged is empty, inspect unstaged changes and decide stage all / stage specific files / stop
   - read the actual staged diff and recent commit style
   - create the commit with a message based on the diff
4. Push the branch with upstream tracking: `git push -u origin <branch>`
5. Follow the `git-pr` workflow, but use a branch-vs-base diff after the commit:
   - determine the PR base branch before drafting, using the repo default branch or the user-provided target branch
   - inspect branch, status, and `git diff <base>...HEAD` instead of a clean-worktree diff
   - draft a concise reviewer-facing title from the actual changes
   - write `.pr_description.md` at the repo root with no placeholders
   - run `gh pr create --title ... --body-file .pr_description.md`
6. Report the branch, commit, push result, and PR URL or blocking error

# Required checks

- `git rev-parse --abbrev-ref HEAD`
- `git status --short`
- `git diff --staged --stat`
- `git diff --stat` when needed
- `git diff --staged --name-only`
- `git log -5 --oneline`
- `git diff <base>...HEAD`

# Branch rules

- If the user provides a branch name, use it exactly
- Otherwise derive a short kebab-case branch name from the change intent
- Prefer prefixes already used in the repo such as `feat/`, `fix/`, `chore/`, or `docs/`
- Do not rename or replace an existing non-empty branch on your own
- If you are already on a feature branch that matches the requested scope, reuse it instead of creating another branch

# Commit rules

- Preserve the `git-commit` guardrails
- Read the staged diff before writing the message
- Do not use `--amend` unless the user asks
- Do not stage unrelated files on your own
- Prefer `<type>(scope?): <summary>` when the repo uses Conventional Commits
- Add a short body when the change is non-trivial

# PR rules

- Preserve the `git-pr` guardrails
- Base the title and body on the branch diff against the chosen PR base
- Leave no placeholders in `.pr_description.md`
- Make every test claim a real command or an explicit not-run note
- Be explicit about `gh` auth or remote push failures

# Output template

## Publish plan
- Branch:
- Staging mode:
- Commit:
- PR title:

## Result
- Branch command:
- Commit:
- Push:
- PR:
- Remaining status:
