## Summary
- Add a new `create-commit` skill that codifies content-aware git commit behavior and removes reliance on separate PR template file for commit metadata.
- Add a new `create-pr` skill flow using an embedded in-skill PR template and updated agent metadata for consistent PR-body generation.
- Introduce supporting reference artifacts (`commit-command.md` and `pull_request_template.md`) to make both skills immediately usable without external dependencies.

## Changes
- **Skills definitions**: Added `skills/create-commit/SKILL.md` and updated `skills/create-pr/SKILL.md` with explicit workflows for commit message generation and PR drafting from branch diffs.
- **Agent metadata**: Updated `skills/create-commit/agents/openai.yaml` and `skills/create-pr/agents/openai.yaml` with behavior-aligned prompts for commit/PR command invocation.
- **Reference content**: Added `skills/create-commit/references/commit-command.md` and `skills/create-pr/references/pull_request_template.md` with concrete command and format guidance.

## Test Plan
- [x] `git diff --stat origin/main...HEAD` confirms exactly 6 file changes (361 insertions total).
- [x] `git diff --name-only origin/main...HEAD` confirms all changed paths are within the two new/updated skill directories.
- [x] `git log --oneline origin/main..HEAD` shows the expected feature commit on top of `origin/main`.
- [ ] `colcon build --packages-select <package_name>` (not applicable for this repo change; no ROS package to build).
- [ ] `colcon test --packages-select <package_name>` (not applicable for this docs-only workflow change).
- [ ] `ros2 launch <package_name> <launch_file>.launch.py` (not applicable for this repository).

## Related Issues
- Closes #
- Related to #
- Docs: `skills/create-commit/SKILL.md`, `skills/create-pr/SKILL.md`

## How to Test
```bash
# Verify branch and diff context
git rev-parse --abbrev-ref HEAD
git status --short

# Validate PR input context
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
git log --oneline origin/main..HEAD

# Inspect generated artifacts
sed -n '1,220p' skills/create-commit/SKILL.md
sed -n '1,220p' skills/create-pr/SKILL.md
cat skills/create-commit/agents/openai.yaml
cat skills/create-pr/agents/openai.yaml
```

## Screenshots/Videos
Not applicable (documentation and workflow skill additions only).

## Additional Notes
- No runtime package behavior changed; only agent skill metadata and reference instructions were added.
- These updates are scoped to command-driven workflows and should be reviewed with existing skill invocation tooling to ensure they are discoverable by name.
