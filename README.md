# codex-base-review

Claude Code / Grok plugin: Codex `/review` → "Review against a base branch (PR Style)".

The orchestrator does not review. It resolves the merge-base, then spawns a child with Codex's
review rubric and user prompt — both taken verbatim from the Codex CLI sources, see
[Provenance](#provenance). The child inspects `git diff <merge-base>` and returns JSON findings.

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
Same-name tracking refs (`origin/<current-branch>`) are skipped. If `git diff <merge-base>`
is empty, the skill stops and does not spawn a reviewer.

Effort is not an argument. The child inherits the session `/effort`; Grok then clamps it to the chosen model's `reasoning_efforts`.

## What it is not

- Uncommitted-only review, single-commit review, or posting a GitHub review.
- Grok's bundled `/review` — different rubric and output.

## Provenance

The prompt is not original work. It is lifted from the OpenAI Codex CLI
([openai/codex](https://github.com/openai/codex), Apache-2.0), so that a review here returns
what Codex's own `/review` would return:

| This repo | Codex CLI source |
|---|---|
| `skills/codex-base-review/references/rubric.md` | `codex-rs/prompts/templates/review/rubric.md` — byte-identical copy |
| `USER_PROMPT` / `USER_PROMPT_BACKUP` in `scripts/merge_base.py` | `BASE_BRANCH_PROMPT` / `BASE_BRANCH_PROMPT_BACKUP` in `codex-rs/prompts/src/review_request.rs` |
| `merge_base_with_head()` in `scripts/merge_base.py` | `merge_base_with_head()` in `codex-rs/git-utils/src/branch.rs` — prefer the upstream ref when it is ahead of the local branch |

Checked against Codex CLI at commit `fcf05456bb`. Do not paraphrase or "improve" the rubric:
the whole point is to keep Codex's wording, its priority tags (`[P0]`…`[P3]`) and its JSON
output schema.

Not from Codex: base-branch auto-detection. The Codex TUI asks which branch to compare
against; this plugin guesses, and stops instead of guessing when the resulting diff is empty.

The plugin's own code is MIT (`LICENSE`); the vendored rubric remains under Codex's
Apache-2.0 license. `NOTICE` lists exactly what was taken and what was changed;
`third_party/codex/LICENSE` carries the Apache-2.0 text.

This is an unofficial plugin: not affiliated with, endorsed by, or sponsored by OpenAI.
"Codex" is used only to describe the review it reproduces.

## Dependencies

- `git`
- `python3` (stdlib only; `scripts/merge_base.py`)
- `gh` optional, used only to read an open PR's base (3s timeout)
