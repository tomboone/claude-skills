# Bootstrap the docs convention: pin `specs_dir` on first use — Design Spec

**Status:** Approved design
**Date:** 2026-06-28
**Repo:** `~/claude-skills` (personal plugin)
**Affects:** `plugins/personal/spec-and-plan-convention.md` (canonical), `plugins/personal/commands/planit.md`, `plugins/personal/commands/projectit.md`

---

## 1. Problem

`DOCS_DIR` resolution falls back to **implicit auto-resolution** (`<umbrella>/docs` for umbrella
layouts, `<repo>/.claude/docs` for single repos) whenever no `specs_dir` is set. That implicit step
silently misfired on boone-gifts: the umbrella isn't a git repo → resolution chose `<umbrella>/docs`
(which didn't exist and wasn't where docs actually lived, `<repo>/docs`), so the loop failed
NEU-349/350/351 with `NO_PLAN` and even auto-created a stray empty `<umbrella>/docs`. The fix we
applied by hand — adding `specs_dir: docs` — is exactly what the tooling should establish **the first
time** an authoring command resolves docs for a repo, so resolution is never implicit again.

## 2. Decision

**The authoring commands (`/planit`, `/projectit`) offer to PIN `specs_dir` when none is set**, before
ever falling back to implicit auto-resolution. Read-only consumers (`/implementit`, `/reviewit`, and
the loop) never prompt — they resolve via override-or-auto and, if nothing is found, report
(`NO_PLAN`). Pinning is an authoring-time setup step.

The behavior is defined once in the canonical `spec-and-plan-convention.md` and referenced by the
commands.

## 3. The offer (when an authoring command resolves docs for a repo and `specs_dir` is unset)

1. **Detect an existing superpowers docs tree** under the repo, in priority order:
   `<repo>/docs/superpowers`, `<repo>/.claude/docs/superpowers`, and (umbrella layout)
   `<umbrella>/docs/superpowers`. If one exists, **propose `specs_dir` = its base** (`docs`,
   `.claude/docs`, or the umbrella path) — "lock to where your docs already are." *(This alone would
   have caught boone-gifts: it would have found `<repo>/docs` and pinned it.)*
2. **Else propose the default `specs_dir: docs`** (a `docs/` folder at the repo root).
3. **Show the proposal; the user confirms, edits the value, or declines.**
4. **On confirm:** write `specs_dir: <value>` into the repo's `CLAUDE.md` (prefer an existing
   `.claude/CLAUDE.md`, else `CLAUDE.md`; create `.claude/CLAUDE.md` if neither exists), and ensure
   `<DOCS_DIR>/superpowers/{specs,plans}` exist. `DOCS_DIR = <repo>/<value>`.
5. **On decline:** fall back to the existing auto-resolution for this run (unchanged behavior), and
   note that resolution is implicit and can be pinned later.

**Greenfield default = `docs`** (i.e. `specs_dir: docs` → `<repo>/docs`). This is what we've
standardized on; it's visible, per-repo, and plays well with the per-ticket/per-repo model. The user
can choose `.claude/docs` or any other value at the prompt.

## 4. Where it applies

- **`/planit` Step 1:** when resolving `DOCS_DIR`, if `specs_dir` is unset, run the §3 offer before
  auto-resolving.
- **`/projectit`:** `docs_dir_for(repo)` runs the §3 offer **per assigned repo** (each sibling repo
  gets its own `specs_dir` pinned on first use). projectit Phase 0 is interactive, so this fits its
  gates. A repo not checked out locally can't be pinned — skip it (as already specified for doc
  generation).
- **`/implementit`, `/reviewit`, the loop:** **no change, never prompt.** They resolve via
  override-or-auto only. (`/implementit`'s `NO_PLAN` path already tells the user to run `/planit`,
  which is where pinning happens.)

## 5. Canonical convention doc change

In `spec-and-plan-convention.md` → "Resolving the docs directory (`DOCS_DIR`)", insert a step after
the `specs_dir` override and before auto-resolution:

> **2. No `specs_dir`? Authoring commands offer to pin one.** When run by `/planit` or `/projectit`
> with no `specs_dir` set, do not silently auto-resolve — offer to make the convention explicit
> [the §3 procedure]. Read-only commands (`/implementit`, `/reviewit`) and the loop never prompt;
> they fall through to auto-resolution and report if nothing is found.

Renumber the existing auto-resolve/create steps accordingly. Note that this offer is what keeps
auto-resolution a rarely-hit fallback rather than the silent default.

## 6. Backward compatibility
- `specs_dir` already set → unchanged (override wins; no offer).
- User declines the offer → exact current auto-resolution behavior.
- `/implementit`, `/reviewit`, loop → unchanged; never prompt (preserves headless safety).
- Existing pinned repos (boone-gifts FE/BE, now `specs_dir: docs`) → no offer, resolve straight to
  `<repo>/docs`.

## 7. Out of scope
- Changing the auto-resolution fallback itself (still `<umbrella>/docs` / `<repo>/.claude/docs`).
- Making `/implementit` or `/reviewit` interactive.
- Migrating/moving any existing docs.

## 8. Testing
Prose commands — verify by read-through + `grep`, plus reasoning over scenarios:
- `specs_dir` set → no offer (override path).
- unset + existing `<repo>/docs/superpowers` → offer proposes `specs_dir: docs`; on confirm, the line
  is written and folders ensured.
- unset + greenfield → offer proposes `docs`; decline → auto-resolution unchanged.
- `/implementit`/`/reviewit` text still contains **no** prompt/offer (read-only).
- projectit: the offer is described as per-repo within `docs_dir_for(repo)`.
