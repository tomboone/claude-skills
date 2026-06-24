# Implementation Loop — Design Spec

- **Date:** 2026-06-24
- **Status:** Approved design (brainstorming output)
- **Repo:** `claude-skills` (the `personal` plugin)
- **Linear ticket:** none (exploratory personal work)

## Summary

A headless Python orchestrator (`plugins/personal/scripts/loop.py`) that drives the existing
`personal` plugin commands non-interactively via `claude -p`. Per run it processes one wave of
ready work tickets — those a prior `/projectit` run marked `loop-ready` whose dependencies are
satisfied — running `/implementit → /shipit → /reviewit` for each, opening a reviewed PR per
ticket. It **stops before merge**; merging stays a manual, human-gated step. Re-run as PRs merge to
pick up the next wave.

## Context & relationship

This is the **consumer** half of the pipeline whose producer is `/projectit` (see
`2026-06-24-projectit-planning-flow-design.md`). `/projectit` populates Linear + writes on-disk
specs/plans and labels tickets `loop-ready`; this loop consumes that contract:

- **Ready marker:** the `loop-ready` label.
- **Plan discovery:** `/implementit` finds each ticket's plan on disk by ticket ID and follows the
  `**Milestone spec:**` reference — so the loop needs no plan content itself.
- **Execution order:** `blockedBy` relations; a ticket is eligible only once its blockers are `Done`.

It reuses the existing commands unchanged except for one small addition to `/reviewit` (a
machine-readable STATUS line). `/planit-auto` from the original handoff doc is **not needed** —
plans are pre-baked by `/projectit`.

## Scope

**In scope:** `plugins/personal/scripts/loop.py`; a `STATUS:` line added to `/reviewit`.

**Out of scope:** `/mergeit` changes (the loop stops before merge); `/planit-auto` (dropped); the
merge step itself (manual); auto-merge of any kind.

## Key decisions (from brainstorming)

1. **Stop before merge** — the loop runs `/implementit → /shipit → /reviewit` per ticket and stops
   with reviewed PRs open. Merging is manual, honoring the global guardrail that merging PRs
   requires explicit confirmation.
2. **One unblocked wave per run** — each run processes only `loop-ready` tickets whose blockers are
   `Done`, each branched off `main`; you review + merge, then re-run for the next wave.
3. **Skip-and-report on hard failure** — a ticket that hard-fails a step is flagged and skipped; the
   run continues and prints a summary.
4. **Independent `claude -p` per step** — no `--resume`; the commands re-resolve all state from
   ticket ID + disk + GitHub/Linear, so fresh context per step matches their design.
5. **Claude/MCP triage** — a `claude -p` call computes the wave via the Linear MCP (no direct Linear
   API integration).
6. **`bypassPermissions`** for the agentic steps, with safety from deny-rules + the no-merge
   boundary (see Per-ticket pipeline).

## The script: `loop.py`

Python 3, standard library only (`subprocess`, `json`, `argparse` — no dependencies). Run from
inside the target app's repo so `claude -p`'s file reads and git operations resolve there.

### Invocation

```bash
plugins/personal/scripts/loop.py [--project <name>] [--label loop-ready] \
                                 [--tickets ID ...] [--dry-run] [--check] \
                                 [--limit N] [--notify]
```

- `--project` overrides repo-inferred project; `--tickets` bypasses triage with an explicit list.
- `--dry-run` runs triage (read-only) and prints the wave + the exact `claude -p` commands without
  executing the pipeline.
- `--check` runs only the feasibility guard.
- `--limit N` caps wave size. `--notify` enables the end-of-run Pushover ping.

### Run flow (one wave)

1. **Feasibility guard** — abort early if the loop can't work (see *Feasibility guard*).
2. **Triage** — one `claude -p` call returns the wave as JSON (see *Triage*).
3. **Per-ticket pipeline** — for each ticket: `/implementit → /shipit → /reviewit`, skipping the
   ticket on hard failure (see *Per-ticket pipeline*).
4. **Summary** — print per-ticket outcomes + the `held` list; optional notification.

### Models

`implementit` → Sonnet; `shipit` → Sonnet; `reviewit` → Opus; triage → Sonnet; feasibility guard →
Haiku. (Planning quality was front-loaded into `/projectit`; execution runs on the cheaper tier.)

## Triage

One read-only `claude -p` (Sonnet) call asks Claude, via the Linear MCP, to:

- list issues with the `loop-ready` label in the target project (`list_issues` by label + project);
- for each, fetch `blockedBy` relations and those blockers' statuses;
- include a ticket only if **every blocker is `Done`** (the GitHub↔Linear connector sets `Done` on
  PR merge) **and the ticket itself is still un-started** (status `Todo`/`Backlog`, not already
  `In Progress`/`In Review`/`Done`);
- return ONLY a strict JSON object as its final message.

**Return shape** (parsed from `--output-format json`'s `result`; extract the last JSON object to be
robust against stray text):

```json
{
  "project": "digest-emails",
  "wave":  [{"id": "PROJ-12", "title": "..."}],
  "held":  [{"id": "PROJ-20", "title": "...", "waiting_on": ["PROJ-12"]}]
}
```

**Wave members are mutually independent by construction:** if B `blockedBy` A and A isn't merged
yet, B is held (its blocker isn't `Done`), so it cannot share a wave with A. Every wave ticket
branches cleanly off `main`; intra-wave order is irrelevant.

**Re-run safety (idempotency):** the un-started filter means a ticket the loop already processed
(now `In Progress`/`In Review` via the connector) is automatically excluded from later waves, so a
re-run never re-implements a ticket that already has a PR.

**Project resolution is non-interactive** (headless can't prompt): `--project`, else the repo's
`linear_initiative`/`linear_team` CLAUDE.md hints (the convention `/projectit` added). If
unresolvable without asking, abort with a clear message.

## Per-ticket pipeline

For each ticket `T` in the wave, three independent `claude -p` invocations run in sequence:

| Step | Command | Model |
|---|---|---|
| 1 | `/personal:implementit T` | Sonnet |
| 2 | `/personal:shipit T` | Sonnet |
| 3 | `/personal:reviewit T` | Opus |

Each invocation uses `--output-format json --permission-mode bypassPermissions --model <model>`,
run **without** `--bare` so the configured Linear + GitHub MCP servers load.

**Failure handling:** a **hard failure** = nonzero exit, wall-clock timeout, or a `result` signalling
the command couldn't proceed (e.g. `/shipit` produced no PR URL). On hard failure, record it and
skip `T`'s remaining steps; continue to the next ticket. If `/shipit` yields no PR, skip
`/reviewit` for `T` (it needs the PR). A review verdict of `CHANGES_REQUESTED` is **not** a failure
— the PR is open; it is recorded and the loop continues.

**Permissions & safety model:** `bypassPermissions` is required because `/implementit` and `/shipit`
must write files, branch/commit, push, and `gh pr create` unattended (`dontAsk` would auto-deny
those). Safety comes from: (a) `settings.json` **deny-rules still apply** under `bypassPermissions`
(deny precedes bypass) — the guardrail-blocked ops (merging/closing PRs, releases, etc.) stay
blocked; (b) the loop never invokes `/mergeit`; (c) all work lands on feature branches behind PRs
reviewed before merge. **(a) must be verified once** during the implementation spike (attempt a
known-denied op under `bypassPermissions` and confirm it is blocked).

**Safety cap without `--max-turns`** (which is not a real CLI flag): a per-invocation wall-clock
timeout via `subprocess` (generous default, e.g. ~30 min implement, shorter ship/review); on timeout
kill the process, count as hard failure, skip.

## `/reviewit` STATUS change

Add a final line to `/reviewit`'s response (so it lands in the `result`): `STATUS: APPROVED` or
`STATUS: CHANGES_REQUESTED`, mapped from the existing assessment ("Ready to merge" → `APPROVED`;
Critical/Important issues → `CHANGES_REQUESTED`). The loop greps `result` for this token to record
the per-ticket verdict. Backwards-compatible: it is one extra line, invisible to interactive use.
The existing human-facing assessment + PR comment are unchanged.

## Summary & reporting

After the wave, print a table: ticket → implemented? / PR URL / review STATUS / failure reason,
plus the `held` list (next run's candidates). **Exit code:** 0 if the run completed (even with
skipped tickets); nonzero only if the loop could not run at all (guard or triage failed).

## Feasibility guard

Per-run and lightweight: a `claude -p` (Haiku) call that confirms a `/personal:` command resolves
headless and the Linear + GitHub MCP servers are reachable; abort with a diagnostic if not. This
de-risks the loop's load-bearing-but-undocumented assumptions (plugin commands under `claude -p`;
MCP availability) once, up front, rather than failing mid-ticket. The heavier deny-rule-under-bypass
check is a one-time implementation-spike step, not a per-run cost.

## Notifications (optional)

Off by default; `--notify` (or an env var) sends a single end-of-run Pushover ping via the existing
Sentry-Pushover relay. Lowest priority; acceptable to defer to a follow-up.

## Error handling

- Triage JSON unparseable → abort (cannot determine the wave).
- Per-ticket hard failure / timeout → record + skip, continue.
- All failures surface in the summary with reasons.

## Testing

- **`--dry-run`** — read-only triage + print the exact `claude -p` commands; no execution.
- **`--check`** — run only the feasibility guard.
- **End-to-end (user-run)** — on the `/projectit` sandbox project, run one wave; confirm a PR is
  opened + reviewed per unblocked ticket and the summary is correct. Requires the plugin reloaded +
  live Linear/GitHub, so it is owed by the user (as with `/projectit`'s runtime validation).

## Open items / deferred

- Verify (implementation spike) that `settings.json` deny-rules survive `--permission-mode
  bypassPermissions`, and that plugin slash commands run under `claude -p` with MCP available.
- Pushover notifications are optional and may ship in a follow-up.
- This whole effort (this loop + `/projectit`) lands as one combined PR when complete.

## Appendix: `claude -p` flags & Linear MCP used

- Flags: `-p`, `--output-format json` (yields `session_id`, `result`), `--permission-mode
  bypassPermissions`, `--model <opus|sonnet|haiku>`. NOT `--max-turns` (not a real flag) and NOT
  `--resume` (unnecessary here). Run without `--bare` so MCP config loads.
- Linear MCP (triage): `list_issues` (by label + project), issue `blockedBy` relations + statuses.
