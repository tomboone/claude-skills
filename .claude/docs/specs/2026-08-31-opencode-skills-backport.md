# Backport the `opencode-skills` improvements into the `personal` plugin

**Status:** Approved — implemented on `feat/backport-opencode-improvements`
**Date:** 2026-08-31
**Affects:** all eight files in `plugins/personal/commands/`, four new wrapper commands,
`plugins/personal/.claude-plugin/plugin.json`, `README.md`, `CONTEXT.md`
**Source:** `~/opencode-skills` — a fork of this repo taken 2026-08-16 (`3f7a155`) and adapted for
OpenCode, with four substantive commits since

## Motivation

`~/opencode-skills` began as a mirror of this repo and has diverged by exactly four commits. Three
of them are portable improvements to how a command file steers an agent; one is opencode-specific
model routing that translates cleanly. Nothing else in that repo should come back — the rest is
opencode plumbing (`OPENCODE_CONFIG_DIR`, `AGENTS.md` in place of `CLAUDE.md`, DeepSeek pinning).

| Commit | Change | Verdict |
|---|---|---|
| `63aff71` | `name`/`description` frontmatter + a `**CRITICAL: …**` step-order header on the six pipeline commands | Port (frontmatter reshaped, see below) |
| `c0db06e` | Strip the leading `/` from `name:` | Moot — `name:` is dropped entirely here |
| `d7b2ab9` | Wrapper commands for four Pocock skills | Port, reshaped |
| `ae52d80` | `/code-review`'s Standards sub-agent delegated to a cheap model | Port |

The frontmatter change is the load-bearing one, and it turns out to correct two factual errors in
this repo's own command prose. Those errors are why `/doit` carries a hand-rolled
read-the-file-from-disk mechanism that it does not need.

## Verified mechanics

The frontmatter decision hinges on how a command file behaves when reached through the `Skill`
tool. This was measured on Claude Code 2.1.251, not assumed. Four probes, run headlessly with
`claude -p --output-format stream-json`:

1. **Command-skills load inline, not in a sub-agent.** A probe command invoked via
   `Skill({skill: "probeit"})` returned `"Launching skill: probeit"` with
   `tool_use_result: {success: true, commandName: "probeit"}`; the command body was then injected
   into the same conversation as a synthetic user message (`parent_tool_use_id: null`,
   `isSynthetic: true`); the run ended with `subagent_stats: {spawned: 0}`. The probe body asked
   for a marker value stated earlier in the conversation and got it back (`MARKER=zebra42`) —
   the command sees the full prior context.
2. **A command is `Skill`-invocable by exact name with or without a `description`.** A
   frontmatter-less probe (`# comment` first line, exactly the shape of every command in this repo
   today) invoked cleanly, inline, with prior context intact (`NODESC-MARKER=quokka99`,
   `spawned: 0`).
3. **A *plugin* command needs a frontmatter `description` to appear in the model's available-skills
   listing.** Asked to quote the listed description verbatim for each of four commands, a session
   loaded with a throwaway plugin via `--plugin-dir` returned:
   `probeplug:pdesc :: Described plugin command probe`, `probeplug:pnodesc :: ABSENT`,
   `personal:doit :: ABSENT`. Project-level `.claude/commands/` files fall back to their first line
   as a description; **plugin** commands get no such fallback. This is why no `personal:*` command
   appears in any session's skill listing today.
4. **`/implement`'s `disable-model-invocation: true` is real and enforced.**
   `Skill({skill: "implement"})` returns an error: *"Skill implement cannot be used with Skill tool
   due to disable-model-invocation."*

Consequences for existing prose:

- `doit.md:14-18` — *"these command files carry no frontmatter `description`, so they are not
  model-invocable at all. Reading the file *is* the mechanism, not a fallback."* — **false.** Probe
  2 invokes a descriptionless command directly. The `description` governs discoverability, not
  invocability.
- `implementit.md:71-74` — *"custom commands have been merged into skills, so there is no longer a
  `SlashCommand` tool that could call one programmatically"* — **false in its conclusion.** The
  `SlashCommand` tool is indeed gone; the `Skill` tool replaced it and does call commands
  programmatically. The *surrounding* argument still holds for the reason given in probe 4:
  `/implement` is unreachable because of its flag, not because commands are unreachable.

Probe 1 is what makes "embrace it" safe: `/doit`'s entire premise is that its three phases share
one warm context, and an inline-loading `Skill` call preserves that.

## Change 1 — Frontmatter on all eight commands

Every command gains:

```markdown
---
description: <the current `# ` first line, trimmed to one line>
argument-hint: "{TICKET_ID} [--base <branch>] [--no-merge]"
---
```

and loses its `# <description>` / `# Usage: …` comment pair, which `argument-hint` and `description`
now carry structurally. Drop opencode's `name:` field — Claude Code derives the command name from
the filename and ignores it.

`projectit`'s current first line is a five-line paragraph; it is cut to one sentence for the
`description`, and the detail it carries moves into the body under the existing **Conventions used
by this command** heading rather than being lost.

**`/doit` switches to `Skill` invocation.** Steps that currently read
`${CLAUDE_PLUGIN_ROOT}/commands/<name>.md` and follow it verbatim become
`Skill({skill: "personal:implementit"})` and so on, with the phase **Overrides** stated in `doit.md`
still applying to the loaded body. The paragraph at `doit.md:14-18` justifying the file-read is
deleted; the paragraph above it — *"Execute the phases in this session. Do not spawn sub-agents…"* —
stays, and is now enforced by the mechanism rather than merely asserted, since probe 1 shows the
loaded command runs in the same context.

`implementit.md:69-75` is rewritten to keep its conclusion and fix its reasoning: `/implement` is
not delegated to because it carries `disable-model-invocation: true` (probe 4), full stop. The
claim about `SlashCommand` no longer existing is removed.

**Rejected alternative:** adding `disable-model-invocation: true` alongside each description, which
would buy `/help` text while preserving today's semantics exactly. Rejected because it would keep
`/doit`'s file-read workaround alive for no benefit now that probe 1 has settled the context
question, and because a command the model cannot invoke cannot be a phase of an attended pipeline.

**Risk accepted:** with descriptions in place, `personal:mergeit` becomes model-invocable, and it
merges PRs. It cannot be flagged off — `/doit`'s merge phase needs it. Mitigation is in the
description text, which states that it is invoked by `/personal:doit`'s merge phase and is not to be
invoked spontaneously. The substantive gates are unchanged and unaffected: CI still gates the merge,
and `MERGE_BLOCKED` still beats a forced merge.

**Not in scope:** changing how `loop.py` invokes commands. It passes `/personal:<cmd> {TICKET}` as
the `claude -p` prompt, which is the human-typed path and works regardless of frontmatter.

## Change 2 — Step-order compliance header

opencode uses one string on all six pipeline commands:

> `**CRITICAL: Follow every step in order. Do not skip, reorder, or jump to implementation.**`

Ported with per-command wording, because "jump to implementation" is meaningless in `shipit` and
`mergeit`. The base form is:

> `**CRITICAL: Follow every step in order. Do not skip or reorder steps.**`

with the `Do not jump ahead to implementation.` clause appended only on `doit`, `implementit`, and
`addressit` — the three that have code-writing steps a model can race toward. Placed immediately
after the frontmatter, before the first prose line.

This is cheap insurance against the failure the loop is most exposed to: a headless
`--permission-mode bypassPermissions` step skipping its guard-rail step. It does not replace any
existing guard.

## Change 3 — Wrapper commands for the Pocock skills

Four new files in `plugins/personal/commands/`, exposed as `/personal:code-review`,
`/personal:tdd`, `/personal:grilling`, `/personal:domain-modeling`.

In opencode these are pure indirection ("load and run the X skill"), which is all they can be there.
Here `/code-review`, `/tdd`, `/grilling` and `/domain-modeling` already exist as installed skills, so
a pass-through wrapper would be a hop nobody takes. Each wrapper therefore has to hold content the
bare skill does not, and the pipeline commands have to reference the wrapper rather than the skill,
or the indirection is dead on arrival:

- **`personal:code-review`** — the substantive one. Absorbs the sub-agent model routing from Change 4
  and the severity-scoping rule currently inlined at `implementit.md:87-99` (apply hard violations
  and genuine defects; list the twelve named Fowler smells rather than refactoring them). That rule
  is this repo's policy about a third-party skill, it is referenced by ADR 0006, and it currently
  lives in one command while `reviewit.md` restates the axes separately. One home for it.
- **`personal:tdd`** — carries the "at pre-agreed seams where applicable, failing test first wherever
  the repo's conventions call for it" framing that `implementit.md:81-82` states, so the constraint
  travels with the invocation.
- **`personal:grilling`** and **`personal:domain-modeling`** — thin. They exist to declare the
  dependency and to give `planit`/`projectit` a stable name to reference.

Call sites updated: `implementit.md` (steps 1 and 3), `reviewit.md` (step 4), `planit.md` (step 4),
`projectit.md` (phase 1).

This also fixes something the plugin leaves implicit today: nothing declares that it depends on
`mattpocock/skills` being installed. `implementit.md:70` mentions `~/.agents/.skill-lock.json` in
passing, inside a parenthetical about a different skill. Four wrapper files make the dependency a
visible part of the plugin.

**Rejected alternative:** collapsing `grilling` + `domain-modeling` into one
`personal:design-session` wrapper, since `planit` and `projectit` always invoke the pair together
with the same framing. Rejected because it invents a name for a thing the repo's own vocabulary does
not have — `CONTEXT.md` has no such term — and because the two skills are usable separately by hand.

**Not in scope:** wrapping any other installed skill (`research`, `prototype`, `diagnosing-bugs`,
`codebase-design`). The pipeline does not reference them.

## Change 4 — Route `/code-review`'s Standards sub-agent to a cheap model

`/code-review` fans out into two parallel sub-agents. opencode pins Standards to a cheap worker and
leaves Spec on the primary model, on the argument that Standards is rubric-matching against
documented rules and a fixed smell list, while judging whether an implementation honours spec intent
is not. That argument holds here and matches what `loop.py` already does per step in
`default_models()`.

Translated: **Standards on Haiku, Spec on the session model.** Stated in the `personal:code-review`
wrapper from Change 3, which is the only place that can state it — the skill itself is vendored from
`mattpocock/skills` and is not ours to edit.

The saving lands where the loop's cost is concentrated: `implementit` runs on Opus at high effort and
its `/code-review` pass is the loop's only code review (ADR 0005), so the Standards axis is currently
Opus-priced for checklist work.

**Not in scope:** retuning `default_models()` in `loop.py`. Unrelated lever, separate change.

## Change 5 — Two stale `/review` references

`README.md:72` and `CONTEXT.md:20` both describe `/reviewit` as reviewing the PR "via `/review`".
There is no `/review` skill; `reviewit.md:37-43` invokes `/code-review`. Both become
`/personal:code-review` under Change 3. Small, but it is exactly the reference-drift the wrappers
exist to prevent, so it lands in the same change.

## Explicitly not ported

- **The `planit` edits inside `d7b2ab9`** — they swap `CLAUDE.md` for `AGENTS.md` and delete the
  retired `DOCS_DIR/superpowers/{specs,plans}/` fallbacks. Both are wrong here: this repo reads
  `CLAUDE.md`, and the retired layout still holds real docs, including this repo's own.
- **`skills-lock.json`** — opencode has to vendor its own manifest of the Pocock skills. This machine
  already has `~/.agents/.skill-lock.json` maintained by the marketplace installer. A second,
  hand-maintained copy would drift.
- **All opencode plumbing** — `install.sh`, `OPENCODE_CONFIG_DIR`, the `conventions/` top-level
  directory (this repo keeps those files beside the plugin), DeepSeek model IDs, and the
  `agent: build` / `model:` frontmatter.

## Definition of done

- [ ] All eight `plugins/personal/commands/*.md` files carry `description` and, where they take
      arguments, `argument-hint`; no `# ` comment header remains in any of them.
- [ ] `personal:doit` and the other seven appear in a session's available-skills listing — verify by
      running the probe-3 query (`--plugin-dir` against a working copy) and getting a real
      description back instead of `ABSENT`.
- [ ] `/doit` invokes its three phases via `Skill` and no longer reads `${CLAUDE_PLUGIN_ROOT}`; the
      false paragraph at `doit.md:14-18` is gone.
- [ ] `implementit.md` still refuses to delegate to `/implement`, and now gives
      `disable-model-invocation: true` as the reason without the `SlashCommand` claim.
- [ ] Each of the six pipeline commands plus `addressit` opens with the step-order header, with the
      implementation clause only on `doit`, `implementit`, `addressit`.
- [ ] Four wrapper commands exist, and `grep -rn '/code-review\|/tdd\|/grilling\|/domain-modeling'`
      over `plugins/personal/commands/` shows every call site pointing at the `personal:` wrapper.
- [ ] The severity-scoping rule appears once, in `personal:code-review`, referenced (not restated) by
      `implementit`.
- [ ] `personal:code-review` states Standards→Haiku, Spec→session model.
- [ ] No reference to a `/review` skill remains in `README.md` or `CONTEXT.md`.
- [ ] `plugins/personal/.claude-plugin/plugin.json` bumped to 0.19.0, and the README's version note
      and command table match.
- [ ] A real `/personal:doit` run on one ticket reaches `STATUS:` without the phase-loading change
      stalling it.

## References

Source repo `~/opencode-skills` @ `ae52d80`. Related: `docs/adr/0005-the-loop-drops-post-ship-review.md`,
`docs/adr/0006-implementit-applies-review-findings-by-severity.md`,
`docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md`. Supersedes the reasoning in commit
`c5d8956` ("stop delegating to the un-invocable /implement skill") only where that reasoning
generalised from `/implement` to all commands.
