# Changelog

All notable changes to codex-base-review will be documented here.

## [Unreleased]

## [0.1.0] - 2026-09-17

### Added
- Initial release: Codex-style base-branch (PR Style) review as a marketplace plugin.
- `codex-base-review` skill — orchestrator resolves merge-base, spawns a child with
  Codex's review rubric, and presents JSON findings. Does not modify files or post
  GitHub reviews.
- `scripts/merge_base.py` — Codex `merge_base_with_head` (prefer upstream when it is
  ahead) plus auto-detect of the branch this one was cut from.
- `references/rubric.md` — verbatim copy of Codex `review/rubric.md`.
