---
name: codex-base-review
description: Use when the user runs /codex-base-review, asks for a Codex-style PR review against a base branch, or wants a merge-base review on a chosen model. Not for uncommitted-only review, single-commit review, or posting a GitHub review.
argument-hint: "[model] [base-branch]"
user-invocable: true
---

# Codex Base-Branch Review

You are the orchestrator. You never review the diff. A child reviewer does, with Codex's rubric and user prompt.

**Core principle:** Same result as Codex `/review` → "Review against a base branch (PR Style)".

## Arguments

Parse `$ARGUMENTS` into at most two tokens.

| Tokens | Meaning |
|---|---|
| none | inherit session model; auto-detect base |
| one token that `git rev-parse --verify` (or `origin/<token>`) resolves | base branch; inherit model |
| one token that does not resolve as a ref | model; auto-detect base |
| two tokens | `model` then `base-branch` |

Pass `model` to the child spawn tool only when the user named one. Do not pass effort: the child inherits the session `/effort`, then Grok clamps it to that model's `reasoning_efforts` (catalog default if the level is missing).

## Setup

`SKILL_DIR` = directory containing this `SKILL.md`.

1. Confirm git: `git rev-parse --is-inside-work-tree`. If this fails, stop.
2. Run the helper (inline absolute paths; do not rely on cwd for the script path):

```text
python3 <SKILL_DIR>/scripts/merge_base.py
python3 <SKILL_DIR>/scripts/merge_base.py --branch <base-branch>
```

Use `--branch` only when the user named a base. Read JSON stdout: `base_branch`, `merge_base_sha`, `user_prompt`, `detection`. If the helper exits non-zero, print stderr and stop.

3. Read `<SKILL_DIR>/references/rubric.md` in full. That file is the child's system prompt. Do not summarize it, rewrite it, or paste a different rubric.

## Spawn the reviewer

Spawn a **new** child (Grok: `spawn_subagent`; Claude Code: `Task`; Codex: `spawn_agent`) with a clean context.

- `subagent_type` / agent type: `general-purpose`
- `description`: `[reviewer] base-branch vs <base_branch>`
- `model`: user token, or omit
- Do **not** pass effort, persona, or capability mode
- Do **not** review inline, even if the diff looks small
- Do **not** invoke `/review` or any other skill

Child prompt, in this order:

```
<verbatim contents of references/rubric.md>

---

<user_prompt from the helper, verbatim>
```

Add one line after the user prompt: `Do not invoke skills or slash commands. Do not modify files.`

## After the child returns

Parse the last assistant message as Codex `ReviewOutputEvent` JSON (`findings`, `overall_correctness`, `overall_explanation`, `overall_confidence_score`). If the whole text is not JSON, take the substring from the first `{` to the last `}`. If that still fails, show the raw text and stop.

Present to the user:

1. Base: `<base_branch>` (`detection`), merge-base SHA
2. Model (child) and that effort was inherited from the session
3. Each finding: title, priority, file:lines, body
4. Overall correctness + explanation

Do not fix the code. Do not post a GitHub review.

## Common mistakes

| Excuse | Reality |
|---|---|
| "The diff is tiny, I'll review it here" | Orchestrator never reviews. Always spawn. |
| "`git diff main` is the PR" | That is vs the tip, including later base commits. The helper computes merge-base; the child runs `git diff <sha>`. |
| "Markdown is clearer than JSON" | The child emits the rubric schema. You format after parse. |
| "Missing tests / commit message are findings" | The rubric drops non-blocking nits. Flag only defects the author would fix. |
| "I'll call /review" | Different rubric, different output. This skill replaces that path. |
