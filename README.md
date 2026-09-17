# codex-base-review

Claude Code / Grok plugin: Codex `/review` → "Review against a base branch (PR Style)".

The orchestrator does not review. It resolves the merge-base, then spawns a child with Codex's review rubric and user prompt. The child inspects `git diff <merge-base>` and returns JSON findings.

## Install

```
/plugin marketplace add zinin/claude-plugins
/plugin install codex-base-review@zinin
```

In Grok, add the same marketplace, then:

```
grok plugin install codex-base-review --trust
```

If you previously copied the skill into `~/.agents/skills/codex-base-review` (or the `~/.claude/skills` / `~/.grok/skills` symlinks), remove that copy after installing the plugin so only one `codex-base-review` is loaded.

## Usage

```
/codex-base-review
/codex-base-review glm-5-3
/codex-base-review grok-4.6 main
```

Plugin-qualified name, if the bare command is taken: `/codex-base-review:codex-base-review`.

| Tokens | Meaning |
|---|---|
| none | inherit session model; auto-detect base |
| one git ref | base branch; inherit model |
| one non-ref token | model; auto-detect base |
| two tokens | `model` then `base-branch` |

Auto-detect order: GitHub PR base → reflog "cut from" → `origin/HEAD` → nearest local fork.

Effort is not an argument. The child inherits the session `/effort`; Grok then clamps it to the chosen model's `reasoning_efforts`.

## What it is not

- Uncommitted-only review, single-commit review, or posting a GitHub review (use [claude-mesh](https://github.com/zinin/claude-mesh) / [herdr-review](https://github.com/zinin/herdr-review) for those).
- Grok's bundled `/review` — different rubric and output.

## Dependencies

- `git`
- `python3` (stdlib only; `scripts/merge_base.py`)
- `gh` optional, used only to read an open PR's base (3s timeout)

## See also

- [claude-mesh](https://github.com/zinin/claude-mesh) — multi-model code review, alt-Claude execution, session helpers
- [herdr-review](https://github.com/zinin/herdr-review) — multi-agent review inside herdr
- [claude-forge](https://github.com/zinin/claude-forge) — build/test/lint delegation and dependency updates
- [claude-atlassian](https://github.com/zinin/claude-atlassian) — Jira/Confluence analysis and bug investigation
- [claude-prd](https://github.com/zinin/claude-prd) — idea to PRD to tasks
