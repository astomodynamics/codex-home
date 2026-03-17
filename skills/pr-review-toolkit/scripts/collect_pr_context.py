#!/usr/bin/env python3
"""Collect git context for PR-style code review."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

COMMON_DEFAULT_BRANCH_NAMES = (
    "main",
    "master",
    "trunk",
    "develop",
    "development",
)


def run_git(repo_root: Path, args: list[str], check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(f"git {' '.join(args)}: {message}")
    return result.stdout.strip()


def try_git(repo_root: Path, args: list[str]) -> str | None:
    try:
        return run_git(repo_root, args)
    except RuntimeError:
        return None


def resolve_repo_root(cwd: Path) -> Path:
    return Path(run_git(cwd, ["rev-parse", "--show-toplevel"]))


def ref_exists(repo_root: Path, ref: str) -> bool:
    return try_git(repo_root, ["rev-parse", "--verify", ref]) is not None


def list_refs(repo_root: Path, *prefixes: str) -> list[str]:
    output = run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", *prefixes], check=False)
    return [line for line in output.splitlines() if line.strip()]


def dedupe_refs(refs: list[str]) -> list[str]:
    return list(dict.fromkeys(refs))


def resolve_remote_default_branch(repo_root: Path) -> str | None:
    output = run_git(
        repo_root,
        ["for-each-ref", "--format=%(symref:short)", "refs/remotes/*/HEAD"],
        check=False,
    )
    for line in output.splitlines():
        ref = line.strip()
        if ref:
            return ref
    return None


def resolve_single_branch_fallback(repo_root: Path, current_branch: str | None) -> str | None:
    excluded = {"HEAD"}
    if current_branch:
        excluded.add(current_branch)
        excluded.add(f"origin/{current_branch}")

    candidates = [
        ref
        for ref in list_refs(repo_root, "refs/heads", "refs/remotes")
        if ref not in excluded and not ref.endswith("/HEAD")
    ]
    candidates = dedupe_refs(candidates)
    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_auto_base(repo_root: Path) -> str:
    remote_default = resolve_remote_default_branch(repo_root)
    if remote_default:
        return remote_default

    configured_default = try_git(repo_root, ["config", "--get", "init.defaultBranch"])
    configured_candidates: list[str] = []
    if configured_default:
        configured_candidates.extend([f"origin/{configured_default}", configured_default])

    named_candidates = configured_candidates + [
        f"origin/{name}" for name in COMMON_DEFAULT_BRANCH_NAMES
    ] + list(COMMON_DEFAULT_BRANCH_NAMES)
    for candidate in dedupe_refs(named_candidates):
        if ref_exists(repo_root, candidate):
            return candidate

    current_branch = try_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    single_branch_fallback = resolve_single_branch_fallback(repo_root, current_branch)
    if single_branch_fallback:
        return single_branch_fallback

    if not ref_exists(repo_root, "HEAD~1"):
        return "HEAD"

    raise RuntimeError("could not auto-detect a default base branch; pass --base explicitly")


def parse_name_status(output: str) -> list[dict[str, object]]:
    changed_files: list[dict[str, object]] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        fields = raw_line.split("\t")
        status_code = fields[0]
        status = status_code[0]

        entry: dict[str, object] = {
            "status": status,
            "status_code": status_code,
            "path": "",
        }

        if status in {"R", "C"} and len(fields) >= 3:
            entry["rename_from"] = fields[1]
            entry["path"] = fields[2]
        elif len(fields) >= 2:
            entry["path"] = fields[1]
        else:
            entry["path"] = raw_line

        changed_files.append(entry)

    return changed_files


def parse_numstat(output: str) -> list[tuple[int | None, int | None]]:
    stats: list[tuple[int | None, int | None]] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        fields = raw_line.split("\t")
        if len(fields) < 2:
            continue
        additions = None if fields[0] == "-" else int(fields[0])
        deletions = None if fields[1] == "-" else int(fields[1])
        stats.append((additions, deletions))
    return stats


def categorize_path(path: str) -> str:
    pure_path = Path(path)
    lower_path = path.lower()
    name = pure_path.name.lower()
    suffix = pure_path.suffix.lower()
    parts = {part.lower() for part in pure_path.parts}

    if {"vendor", "third_party", "node_modules"} & parts:
        return "vendor"
    if {"migrations", "alembic"} & parts:
        return "migration"
    if "__pycache__" in parts or "generated" in parts or name.endswith(".lock"):
        return "generated"
    if name in {"dockerfile", "makefile"} or ".github" in parts or "workflows" in parts:
        return "build"
    if suffix in {".md", ".rst"} or "docs" in parts or name in {"readme.md", "changelog.md"}:
        return "docs"
    if (
        "tests" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".spec.ts")
        or name.endswith(".test.ts")
        or name.endswith(".spec.tsx")
        or name.endswith(".test.tsx")
    ):
        return "test"
    if suffix in {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"}:
        return "config"
    return "source"


def is_lockfile(path: str) -> bool:
    name = Path(path).name.lower()
    return name in {
        "poetry.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "cargo.lock",
        "uv.lock",
    }


def is_public_api_path(path: str) -> bool:
    parts = [part.lower() for part in Path(path).parts]
    name = Path(path).name.lower()

    if name == "__init__.py" and "src" in parts:
        return True
    return any(part in {"api", "public", "cli", "interfaces"} for part in parts)


def normalize_test_stem(path: str) -> str:
    stem = Path(path).stem.lower()
    for prefix in ("test_", "spec_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
            break
    for suffix in ("_test", "_spec", ".test", ".spec", "-test", "-spec"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem


def matches_test(source_path: str, test_path: str) -> bool:
    source = Path(source_path)
    source_stem = source.stem.lower()
    test_stem = normalize_test_stem(test_path)
    if source_stem and source_stem == test_stem:
        return True

    parent_name = source.parent.name.lower()
    test_parts = {part.lower() for part in Path(test_path).parts}
    return bool(parent_name and parent_name in test_parts)


def build_test_signals(changed_files: list[dict[str, object]]) -> tuple[list[str], list[str]]:
    test_paths = [entry["path"] for entry in changed_files if entry["category"] == "test"]
    source_paths = [entry["path"] for entry in changed_files if entry["category"] == "source"]
    likely_untested: list[str] = []

    for source_path in source_paths:
        if not any(matches_test(str(source_path), str(test_path)) for test_path in test_paths):
            likely_untested.append(str(source_path))

    return [str(path) for path in test_paths], likely_untested


def build_hotspots(changed_files: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    ranked = sorted(
        changed_files,
        key=lambda entry: (
            -((entry.get("additions") or 0) + (entry.get("deletions") or 0)),
            str(entry["path"]),
        ),
    )
    return ranked[:limit]


def build_directory_summary(changed_files: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: Counter[str] = Counter()
    for entry in changed_files:
        parent = str(Path(str(entry["path"])).parent)
        counts[parent if parent != "." else "<root>"] += 1
    return [
        {"directory": directory, "files_changed": count}
        for directory, count in counts.most_common()
    ]


def collect_status(repo_root: Path) -> list[str]:
    status = run_git(repo_root, ["status", "--short"], check=False)
    return status.splitlines() if status else []


def collect_commits(repo_root: Path, commit_range: str, limit: int) -> list[dict[str, str]]:
    if not commit_range:
        return []

    output = run_git(
        repo_root,
        [
            "log",
            "--format=%H%x09%an%x09%aI%x09%s",
            f"--max-count={limit}",
            commit_range,
        ],
    )
    commits: list[dict[str, str]] = []
    for line in output.splitlines():
        sha, author, timestamp, subject = line.split("\t", 3)
        commits.append(
            {
                "sha": sha,
                "short_sha": sha[:12],
                "author": author,
                "timestamp": timestamp,
                "subject": subject,
            }
        )
    return commits


def resolve_range_commit_spec(repo_root: Path, base_ref: str, head_ref: str) -> tuple[str, str]:
    if base_ref == head_ref == "HEAD" and not ref_exists(repo_root, "HEAD~1"):
        return head_ref, head_ref

    merge_base = run_git(repo_root, ["merge-base", base_ref, head_ref])
    return merge_base, f"{merge_base}..{head_ref}"


def diff_arguments(mode: str, diff_spec: str | None) -> list[str]:
    if mode == "range":
        assert diff_spec is not None
        if ".." not in diff_spec:
            return ["diff-tree", "--root", "--no-commit-id", "-r", diff_spec]
        return ["diff", diff_spec]
    if mode == "staged":
        return ["diff", "--cached"]
    return ["diff"]


def collect_untracked_files(repo_root: Path) -> list[str]:
    output = run_git(repo_root, ["ls-files", "--others", "--exclude-standard"], check=False)
    return [line for line in output.splitlines() if line.strip()]


def count_text_lines(contents: bytes) -> int:
    if not contents:
        return 0
    return contents.count(b"\n") + (0 if contents.endswith(b"\n") else 1)


def collect_untracked_numstat(repo_root: Path, path: str) -> tuple[int | None, int | None]:
    file_path = repo_root / path
    try:
        contents = file_path.read_bytes()
    except OSError:
        return None, None

    if b"\0" in contents:
        return None, None
    return count_text_lines(contents), 0


def collect_changed_files(
    repo_root: Path,
    mode: str,
    diff_spec: str | None,
) -> list[dict[str, object]]:
    base_args = diff_arguments(mode, diff_spec)
    name_status_output = run_git(repo_root, [*base_args, "--find-renames=90%", "--name-status"])
    numstat_output = run_git(repo_root, [*base_args, "--find-renames=90%", "--numstat"])

    changed_files = parse_name_status(name_status_output)
    numstats = parse_numstat(numstat_output)
    for entry, (additions, deletions) in zip(changed_files, numstats):
        entry["additions"] = additions
        entry["deletions"] = deletions
        entry["category"] = categorize_path(str(entry["path"]))

    for entry in changed_files[len(numstats) :]:
        entry["additions"] = None
        entry["deletions"] = None
        entry["category"] = categorize_path(str(entry["path"]))

    if mode == "working-tree":
        tracked_paths = {str(entry["path"]) for entry in changed_files}
        for path in collect_untracked_files(repo_root):
            if path in tracked_paths:
                continue
            additions, deletions = collect_untracked_numstat(repo_root, path)
            changed_files.append(
                {
                    "status": "?",
                    "status_code": "??",
                    "path": path,
                    "additions": additions,
                    "deletions": deletions,
                    "category": categorize_path(path),
                }
            )

    return changed_files


def build_flags(changed_files: list[dict[str, object]]) -> dict[str, bool]:
    categories = {str(entry["category"]) for entry in changed_files}
    paths = [str(entry["path"]) for entry in changed_files]
    return {
        "docs_only": bool(changed_files) and categories <= {"docs"},
        "has_generated_changes": any(entry["category"] == "generated" for entry in changed_files),
        "has_migrations": any(entry["category"] == "migration" for entry in changed_files),
        "has_lockfile_changes": any(is_lockfile(path) for path in paths),
        "has_public_api_changes": any(is_public_api_path(path) for path in paths),
        "has_test_changes": any(entry["category"] == "test" for entry in changed_files),
        "has_build_changes": any(entry["category"] == "build" for entry in changed_files),
        "has_config_changes": any(entry["category"] == "config" for entry in changed_files),
    }


def build_payload(
    repo_root: Path,
    mode: str,
    base_ref: str | None,
    head_ref: str | None,
    merge_base: str | None,
    commit_range: str | None,
    max_commits: int,
    max_hotspots: int,
) -> dict[str, object]:
    changed_files = collect_changed_files(repo_root, mode, commit_range)
    total_additions = sum(entry["additions"] or 0 for entry in changed_files)
    total_deletions = sum(entry["deletions"] or 0 for entry in changed_files)
    test_files_changed, likely_untested_paths = build_test_signals(changed_files)

    return {
        "repo_root": str(repo_root),
        "review_mode": mode,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "merge_base": merge_base,
        "commit_range": commit_range,
        "commits": collect_commits(repo_root, commit_range, max_commits),
        "diff_stats": {
            "files_changed": len(changed_files),
            "additions": total_additions,
            "deletions": total_deletions,
        },
        "changed_files": changed_files,
        "hotspots": build_hotspots(changed_files, max_hotspots),
        "directory_summary": build_directory_summary(changed_files),
        "test_files_changed": test_files_changed,
        "likely_untested_paths": likely_untested_paths,
        "flags": build_flags(changed_files),
        "worktree_status": collect_status(repo_root),
    }


def format_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# PR Review Context",
        "",
        f"- repo_root: `{payload['repo_root']}`",
        f"- review_mode: `{payload['review_mode']}`",
    ]

    for key in ("base_ref", "head_ref", "merge_base", "commit_range"):
        value = payload.get(key)
        if value:
            lines.append(f"- {key}: `{value}`")

    diff_stats = payload["diff_stats"]
    lines.extend(
        [
            f"- files_changed: `{diff_stats['files_changed']}`",
            f"- additions: `{diff_stats['additions']}`",
            f"- deletions: `{diff_stats['deletions']}`",
        ]
    )

    enabled_flags = [name for name, enabled in payload["flags"].items() if enabled]
    lines.append(f"- flags: `{', '.join(enabled_flags) if enabled_flags else 'none'}`")

    commits = payload["commits"]
    if commits:
        lines.extend(["", "## Commits"])
        for commit in commits:
            lines.append(
                f"- `{commit['short_sha']}` {commit['subject']} ({commit['author']}, {commit['timestamp']})"
            )

    hotspots = payload["hotspots"]
    if hotspots:
        lines.extend(["", "## Hotspots"])
        for entry in hotspots:
            additions = entry["additions"] if entry["additions"] is not None else "binary"
            deletions = entry["deletions"] if entry["deletions"] is not None else "binary"
            lines.append(f"- `{entry['path']}` [{entry['category']}] (+{additions} / -{deletions})")

    changed_files = payload["changed_files"]
    if changed_files:
        lines.extend(["", "## Changed Files"])
        for entry in changed_files:
            additions = entry["additions"] if entry["additions"] is not None else "binary"
            deletions = entry["deletions"] if entry["deletions"] is not None else "binary"
            rename_note = ""
            if entry.get("rename_from"):
                rename_note = f" (from `{entry['rename_from']}`)"
            lines.append(
                f"- `{entry['status_code']}` `{entry['path']}`{rename_note} "
                f"[{entry['category']}] (+{additions} / -{deletions})"
            )

    lines.extend(["", "## Test Signals"])
    test_files = payload["test_files_changed"]
    if test_files:
        lines.append("- changed tests:")
        lines.extend(f"  - `{path}`" for path in test_files)
    else:
        lines.append("- changed tests: none")

    untested = payload["likely_untested_paths"]
    if untested:
        lines.append("- likely untested paths:")
        lines.extend(f"  - `{path}`" for path in untested)
    else:
        lines.append("- likely untested paths: none")

    directory_summary = payload["directory_summary"]
    if directory_summary:
        lines.extend(["", "## Directory Summary"])
        for entry in directory_summary:
            lines.append(f"- `{entry['directory']}`: {entry['files_changed']} file(s)")

    worktree_status = payload["worktree_status"]
    if worktree_status:
        lines.extend(["", "## Worktree Status"])
        lines.extend(f"- `{line}`" for line in worktree_status)

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("range", "staged", "working-tree"),
        default="range",
        help="Diff source to inspect. 'range' compares a base and head ref.",
    )
    parser.add_argument(
        "--base",
        default="auto",
        help="Base ref for range review. Default: auto-detect default branch.",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="Head ref for range review. Default: HEAD.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=25,
        help="Maximum commits to include in the summary.",
    )
    parser.add_argument(
        "--max-hotspots",
        type=int,
        default=10,
        help="Maximum hotspot files to include in the summary.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path. Print to stdout when omitted.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cwd = Path.cwd()
    repo_root = resolve_repo_root(cwd)

    base_ref: str | None = None
    head_ref: str | None = None
    merge_base: str | None = None
    commit_range: str | None = None

    if args.mode == "range":
        base_ref = resolve_auto_base(repo_root) if args.base == "auto" else args.base
        head_ref = args.head
        merge_base, commit_range = resolve_range_commit_spec(repo_root, base_ref, head_ref)
    elif args.mode == "staged":
        base_ref = "INDEX"
        head_ref = "STAGED"
    else:
        base_ref = "INDEX"
        head_ref = "WORKTREE"

    payload = build_payload(
        repo_root=repo_root,
        mode=args.mode,
        base_ref=base_ref,
        head_ref=head_ref,
        merge_base=merge_base,
        commit_range=commit_range,
        max_commits=args.max_commits,
        max_hotspots=args.max_hotspots,
    )

    if args.format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    else:
        rendered = format_markdown(payload)

    if args.output:
        Path(args.output).write_text(rendered)
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
