# Loop Repo Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the autonomous loop work only the tickets belonging to the repo it runs in, by filtering triage on a per-repo `repo:<name>` label that `/projectit` stamps at creation.

**Architecture:** One shared canonical-repo-name derivation (git remote → basename) gives the loop its own identity and gives `/projectit` the label value, so the two sides always agree. The loop's triage prompt gains a `repo:<name>` filter plus a parent/user-story exclusion guard. `/projectit` resolves each ticket's repo (explicit list → local sibling scan → GitHub → ask) and applies the matching label alongside `loop-ready`.

**Tech Stack:** Python 3 standard library (`argparse`, `subprocess`, `unittest`); the `/projectit` command is a Markdown instruction file driving the Linear MCP.

## Global Constraints

- **Spec:** `.claude/docs/superpowers/specs/2026-06-26-loop-repo-scoping-design.md` — every task realizes part of it.
- **Match existing `loop.py` style:** plain functions, **no type annotations** (the file uses none). Do not introduce type hints here even though the global Python style prefers them — consistency with the file wins.
- **Label format:** namespaced `repo:<name>`; `<name>` is the repo **basename** (e.g. `claude-skills`), `.git` stripped. Never a hardcoded `backend`/`frontend` shortcut.
- **Loop repo-identity precedence:** `--repo` flag → `linear_repo:` in `CLAUDE.md` → `git remote get-url origin` basename. If none resolve → `SystemExit` (never run unscoped).
- **Testability via injection:** follow the existing `resolve_project(args, read_claude_md=...)` pattern — inject `read_claude_md` and a `remote_url_fn` so unit tests never shell out to git.
- **Run tests from** `plugins/personal/scripts/` with `python -m unittest test_loop -v` (the test file does `sys.path.insert(0, <its dir>)` then `import loop`).
- **Commits:** Conventional Commits, no Linear ticket → no parenthetical; code → `feat(personal): …`, command/docs → `docs: …`. No `Co-Authored-By` trailer, no footer on commit messages.

## File Structure

- **Modify** `plugins/personal/scripts/loop.py`
  - New: `_repo_name_from_url(url)` — pure URL→basename normalization.
  - New: `_git_remote_url()` — thin `git remote get-url origin` wrapper.
  - New: `resolve_repo_label(args, read_claude_md=_read_repo_claude_md, remote_url_fn=_git_remote_url)`.
  - Modify: `parse_args` (+`--repo`), `TRIAGE_PROMPT` (repo filter + parent guard), `run_triage` (+`repo_label` param), `main` (resolve + thread `repo_label`, dry-run print).
- **Modify** `plugins/personal/scripts/test_loop.py`
  - New test classes for the four pure/seam functions; fix `TestMainDryRun`'s injected `triage_fn` signature and add a repo-filter assertion.
- **Modify** `plugins/personal/commands/projectit.md`
  - Phase 0 candidate-repo resolution; Phase 3 per-ticket assignment; Phase 5 label bootstrap + application.
- **Modify** `README.md` (conventions section)
  - Document the `linear_repo:` / `linear_repos:` `CLAUDE.md` keys.

---

## Task 1: `_repo_name_from_url` — pure URL normalization

**Files:**
- Modify: `plugins/personal/scripts/loop.py`
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Produces: `_repo_name_from_url(url)` → repo basename `str`, or `None` for empty/unparseable input. Strips a trailing `.git` and any trailing slash; handles both scp-style (`git@host:org/repo.git`) and URL-style (`https://host/org/repo.git`).

- [ ] **Step 1: Write the failing test**

Add to `test_loop.py` (after `TestResolveProject`, near line 309):

```python
class TestRepoNameFromUrl(unittest.TestCase):
    def test_ssh_remote(self):
        self.assertEqual(loop._repo_name_from_url("git@github.com:tomboone/claude-skills.git"), "claude-skills")

    def test_https_remote(self):
        self.assertEqual(loop._repo_name_from_url("https://github.com/org/report-exporters.git"), "report-exporters")

    def test_without_git_suffix(self):
        self.assertEqual(loop._repo_name_from_url("https://github.com/org/report-exporters"), "report-exporters")

    def test_trailing_slash(self):
        self.assertEqual(loop._repo_name_from_url("https://github.com/org/report-exporters/"), "report-exporters")

    def test_empty_or_none(self):
        self.assertIsNone(loop._repo_name_from_url(""))
        self.assertIsNone(loop._repo_name_from_url(None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_loop.TestRepoNameFromUrl -v`
Expected: FAIL with `AttributeError: module 'loop' has no attribute '_repo_name_from_url'`

- [ ] **Step 3: Write minimal implementation**

Add to `loop.py` immediately after `_read_repo_claude_md` (currently ends at line 366):

```python
def _repo_name_from_url(url):
    """Canonical repo name (basename, no .git) from an origin remote URL; None if unparseable."""
    s = (url or "").strip().rstrip("/")
    if not s:
        return None
    if s.endswith(".git"):
        s = s[:-4]
    # scp-style uses ':' before the path; normalize it to '/' then take the last segment
    last = s.replace(":", "/").rstrip("/").split("/")[-1]
    return last or None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest test_loop.TestRepoNameFromUrl -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(personal): add canonical repo-name derivation for the loop"
```

---

## Task 2: `resolve_repo_label` + `--repo` flag

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`parse_args`, new `_git_remote_url`, new `resolve_repo_label`)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `_repo_name_from_url` (Task 1); `_read_repo_claude_md`.
- Produces:
  - `parse_args(...)` result now has a `.repo` attribute (`str | None`, default `None`).
  - `_git_remote_url()` → remote URL `str` or `None` (subprocess seam; injected in tests).
  - `resolve_repo_label(args, read_claude_md=_read_repo_claude_md, remote_url_fn=_git_remote_url)` → `"repo:<name>"`; raises `SystemExit` when nothing resolves. Precedence: `args.repo` → `linear_repo:` in CLAUDE.md → `_repo_name_from_url(remote_url_fn())`.

- [ ] **Step 1: Write the failing test**

Add the `--repo` arg test to the existing `TestMaxRoundsArg` neighbors — create a small class, and add the resolver tests (place after `TestRepoNameFromUrl`):

```python
class TestRepoArg(unittest.TestCase):
    def test_flag_parsed(self):
        self.assertEqual(loop.parse_args(["--repo", "myrepo"]).repo, "myrepo")

    def test_default_none(self):
        self.assertIsNone(loop.parse_args([]).repo)


class TestResolveRepoLabel(unittest.TestCase):
    def test_explicit_flag_wins(self):
        args = loop.parse_args(["--repo", "backend"])
        label = loop.resolve_repo_label(args, read_claude_md=lambda: "linear_repo: other\n",
                                        remote_url_fn=lambda: "git@github.com:o/remote-repo.git")
        self.assertEqual(label, "repo:backend")

    def test_claude_md_hint_second(self):
        args = loop.parse_args([])
        label = loop.resolve_repo_label(args, read_claude_md=lambda: "linear_initiative: X\nlinear_repo: bi-api\n",
                                        remote_url_fn=lambda: "git@github.com:o/remote-repo.git")
        self.assertEqual(label, "repo:bi-api")

    def test_git_remote_fallback(self):
        args = loop.parse_args([])
        label = loop.resolve_repo_label(args, read_claude_md=lambda: "",
                                        remote_url_fn=lambda: "https://github.com/o/report-exporters.git")
        self.assertEqual(label, "repo:report-exporters")

    def test_aborts_when_unresolvable(self):
        args = loop.parse_args([])
        with self.assertRaises(SystemExit):
            loop.resolve_repo_label(args, read_claude_md=lambda: "", remote_url_fn=lambda: None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_loop.TestRepoArg test_loop.TestResolveRepoLabel -v`
Expected: FAIL — `--repo` is an unrecognized argument / `loop` has no attribute `resolve_repo_label`.

- [ ] **Step 3: Write minimal implementation**

In `parse_args` (line 308-319), add the flag next to `--project`:

```python
    p.add_argument("--repo")
```

Add after `_repo_name_from_url` (from Task 1) in `loop.py`:

```python
def _git_remote_url():
    """origin remote URL via git, or None if unavailable (no repo / no remote / git missing)."""
    try:
        proc = subprocess.run(["git", "remote", "get-url", "origin"],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def resolve_repo_label(args, read_claude_md=_read_repo_claude_md, remote_url_fn=_git_remote_url):
    """Resolve this repo's loop label as 'repo:<name>'. --repo > linear_repo: hint > git remote."""
    name = args.repo
    if name is None:
        for line in read_claude_md().splitlines():
            if line.strip().lower().startswith("linear_repo:"):
                name = line.split(":", 1)[1].strip()
                break
    if name is None:
        name = _repo_name_from_url(remote_url_fn())
    if not name:
        raise SystemExit(
            "Cannot resolve repo: pass --repo, set 'linear_repo:' in the repo CLAUDE.md, "
            "or run from a repo with an 'origin' git remote."
        )
    return f"repo:{name}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest test_loop.TestRepoArg test_loop.TestResolveRepoLabel -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(personal): resolve the loop's repo label with flag/CLAUDE.md/git precedence"
```

---

## Task 3: Triage prompt — repo filter + parent/user-story guard

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`TRIAGE_PROMPT`, `run_triage`)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: nothing new (string + format).
- Produces:
  - `TRIAGE_PROMPT` now has a `{repo_label}` placeholder and an explicit parent/user-story exclusion clause.
  - `run_triage(project, label, repo_label, runner)` — **signature gains `repo_label`** before `runner`.

- [ ] **Step 1: Write the failing test**

Add after `TestResolveRepoLabel`:

```python
class TestTriagePrompt(unittest.TestCase):
    def test_prompt_includes_repo_and_parent_guard(self):
        rendered = loop.TRIAGE_PROMPT.format(project="P", label="loop-ready", repo_label="repo:backend")
        self.assertIn("repo:backend", rendered)
        self.assertIn("loop-ready", rendered)
        # parent / user-story exclusion must be present
        self.assertIn("sub-issues", rendered)
        self.assertIn("user-story", rendered)
        # JSON contract is unchanged
        self.assertIn('"wave"', rendered)
        self.assertIn('"held"', rendered)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_loop.TestTriagePrompt -v`
Expected: FAIL — `KeyError: 'repo_label'` (the placeholder doesn't exist yet) or missing-substring assertion.

- [ ] **Step 3: Write minimal implementation**

Replace `TRIAGE_PROMPT` (lines 276-283) with:

```python
TRIAGE_PROMPT = (
    "Using the Linear MCP, find work tickets in project {project!r} that are ready for the "
    "implementation loop. A ticket qualifies only if ALL hold: it carries BOTH the {label!r} "
    "label AND the {repo_label!r} label; every one of its blockedBy blockers has status Done; "
    "and the ticket itself is still un-started (status Todo or Backlog, not In Progress/In "
    "Review/Done). EXCLUDE any issue that has sub-issues (children) or carries the 'user-story' "
    "label — those are containers, not implementable work. Return ONLY a JSON object as your "
    "final message, no prose:\n"
    '{{"project": "{project}", "wave": [{{"id": "...", "title": "..."}}], '
    '"held": [{{"id": "...", "title": "...", "waiting_on": ["..."]}}]}}'
)
```

Update `run_triage` (lines 387-391) to thread `repo_label`:

```python
def run_triage(project, label, repo_label, runner):
    res = runner(build_claude_cmd(
        TRIAGE_PROMPT.format(project=project, label=label, repo_label=repo_label), "sonnet"), 300)
    if res.timed_out or res.returncode != 0:
        raise SystemExit("Triage call failed.")
    return parse_triage_result(res.result_text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest test_loop.TestTriagePrompt -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(personal): scope loop triage by repo label and exclude parent issues"
```

---

## Task 4: Wire `repo_label` through `main` + dry-run + fix dry-run test

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`main`)
- Test: `plugins/personal/scripts/test_loop.py` (`TestMainDryRun`)

**Interfaces:**
- Consumes: `resolve_repo_label` (Task 2); `run_triage(project, label, repo_label, runner)` (Task 3).
- Produces: `main` resolves `repo_label` and passes it to `triage_fn(project, label, repo_label, runner)`. The injected `triage_fn` contract is now 4-arg. Dry-run output includes a `Repo filter: repo:<name>` segment. The `--tickets` explicit path stays **unfiltered**.

- [ ] **Step 1: Update the existing dry-run test (it will fail against current `main`)**

Replace `TestMainDryRun` (lines 321-335) with a version that passes `--repo`, uses the 4-arg `triage_fn`, and asserts the repo filter is printed:

```python
class TestMainDryRun(unittest.TestCase):
    def test_dry_run_prints_commands_without_running_pipeline(self):
        import io, contextlib
        wave = {"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": []}
        calls = []
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--repo", "testrepo", "--dry-run"],
                runner=lambda cmd, timeout: calls.append(cmd) or loop.InvocationResult(0, "", False),
                triage_fn=lambda project, label, repo_label, runner: wave,
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        # pipeline must not run in dry-run:
        self.assertEqual(calls, [])
        # the resolved repo filter is surfaced:
        self.assertIn("Repo filter: repo:testrepo", buf.getvalue())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_loop.TestMainDryRun -v`
Expected: FAIL — `main` still calls `triage_fn(project, label, runner)` (3-arg) / output lacks `Repo filter:`.

- [ ] **Step 3: Implement in `main`**

In `main`, after `project = resolve_project(args)` (line 415) add the resolve and thread it into triage:

```python
    project = resolve_project(args)
    repo_label = resolve_repo_label(args)
    if args.tickets:
        triage = {"project": project, "wave": [{"id": t, "title": ""} for t in args.tickets], "held": []}
    else:
        triage = triage_fn(project, args.label, repo_label, runner)
```

Update the dry-run header line (line 424) to include the repo filter:

```python
        print(f"Project: {project}. Repo filter: {repo_label}. Wave ({len(wave)}): {[t['id'] for t in wave]}")
```

- [ ] **Step 4: Run the FULL suite to verify everything passes**

Run: `python -m unittest test_loop -v`
Expected: PASS (all tests — the four new classes plus the existing suite; no failures).

- [ ] **Step 5: Smoke-test the real CLI dry-run from this repo**

Run (from `plugins/personal/scripts/`):
`python loop.py --project "Anything" --dry-run`
Expected: prints `Repo filter: repo:claude-skills` (derived from this repo's `origin` remote), then `No tickets processed.` — confirming end-to-end resolution shells out correctly. (Triage runs a real `claude -p`; if MCP/auth is unavailable this may error after the filter line is printed — the repo-filter line is what this step verifies.)

- [ ] **Step 6: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(personal): thread the repo filter through the loop and surface it in dry-run"
```

---

## Task 5: `/projectit` stamps the `repo:<name>` label

**Files:**
- Modify: `plugins/personal/commands/projectit.md`

**Interfaces:**
- Consumes: the `repo:<name>` convention from the loop tasks (basename, `.git` stripped) — `/projectit` MUST produce labels the loop will match.
- Produces: every leaf work ticket carries `repo:<assigned-repo>` alongside `loop-ready`.

This task edits a Markdown instruction file (no unit tests); its test cycle is a `--dry-run` walkthrough. Apply each edit, then verify.

- [ ] **Step 1: Add candidate-repo resolution to Phase 0**

In `projectit.md`, append a step 7 to **Phase 0** (after the current step 6, line 23):

```markdown
7. **Candidate repos (`REPOS`):** resolve the set of repos this project's tickets may target,
   most authoritative first: (a) a `linear_repos:` list in `CLAUDE.md`; else (b) local sibling
   git repos discovered by scanning the umbrella folder **and** the surrounding workspace root
   (a bounded walk-up — stop at the workspace root, do not scan the whole filesystem), taking
   each repo's canonical name from `git remote get-url origin` (basename, strip `.git`); else
   (c) query GitHub for likely repos (org repos, prioritizing names matching the
   initiative/project) and propose them. Record the resolved set as `REPOS`. If it resolves to a
   single repo, default all tickets to that repo's canonical name.
```

- [ ] **Step 2: Add per-ticket repo assignment to Phase 3**

In **Phase 3**, after the granularity-rule paragraph (ends line 40, "Note inter-ticket dependencies (B builds on A)."), insert:

```markdown
**Repo assignment:** assign each work ticket exactly one repo from `REPOS` (its `repo:<name>`).
**Never silently guess** — whenever a ticket's repo is ambiguous (multiple plausible candidates,
or `REPOS` is thin/empty), ask the user which repo to label. Show each ticket's assigned repo in
the breakdown so the user can edit it at the gate. Stories (parent issues) get no repo assignment.
```

- [ ] **Step 3: Bootstrap `repo:<name>` labels in Phase 5 Step 1**

In **Phase 5 → Step 1** (lines 90-94), after the `user-story` / `loop-ready` bootstrap sentence, add:

```markdown
Also, for each repo in `REPOS`, ensure a `repo:<name>` label exists; create any missing one with
`create_issue_label` using a distinct color (e.g. `color="#0091FF"`). (Dry-run: print each call.)
```

- [ ] **Step 4: Apply the label in Phase 5 Step 2**

In **Phase 5 → Step 2**, change the `save_issue` label list (line 108) from:

```markdown
Call `save_issue(id=<ticket-id>, description=<updated>, labels=["loop-ready"])` where the updated
```

to:

```markdown
Call `save_issue(id=<ticket-id>, description=<updated>, labels=["loop-ready", "repo:<assigned-repo>"])` where the updated
```

- [ ] **Step 5: Update the closing note about loop selection**

In **Phase 5 → Step 4**, replace the final paragraph (lines 149-151, beginning "The `loop-ready` label is the signal…") with:

```markdown
The loop selects work tickets by the `loop-ready` label **scoped to the repo it runs in** (the
`repo:<name>` label), so running it in a given repo root only picks up that repo's tickets. The
loop reads plans from disk by ticket ID; the Linear `links` attachment added in Step 2 is a
human-convenience reference, not load-bearing for the loop.
```

- [ ] **Step 6: Verify with a dry-run walkthrough**

Run `/projectit --dry-run "<a small two-repo idea>"` against a project whose `REPOS` resolves to two repos. Confirm in the printed (not executed) output that: each leaf ticket shows an assigned repo at the Phase-3 gate; Phase 5 prints `create_issue_label` for each `repo:<name>`; each `save_issue` prints `labels=["loop-ready", "repo:<name>"]`; and no Linear writes occur. Fix wording if any step's output is wrong.

- [ ] **Step 7: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat(personal): tag work tickets with a repo label in projectit"
```

---

## Task 6: Document the `linear_repo:` / `linear_repos:` CLAUDE.md keys

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the conventions established in Tasks 2 and 5.
- Produces: user-facing documentation so the keys are discoverable next to the existing hints.

- [ ] **Step 1: Locate the conventions section**

Run: `grep -n "linear_initiative\|linear_team\|specs_dir" README.md`
Expected: the line(s) where the existing `CLAUDE.md` hint keys are documented. (If none exist in `README.md`, place the new lines in the section that documents the loop / `/projectit` setup.)

- [ ] **Step 2: Add the two keys**

Next to the existing `linear_initiative:` / `linear_team:` documentation, add:

```markdown
- `linear_repo: <name>` — overrides the loop's auto-derived repo label (`repo:<name>`). The loop
  otherwise derives `<name>` from `git remote get-url origin` (basename). Used to filter triage to
  this repo's tickets within a multi-repo project.
- `linear_repos: [<name>, <name>, …]` — for `/projectit`: the canonical repo names a project's
  tickets may target, so each ticket can be tagged with the right `repo:<name>` at creation.
```

- [ ] **Step 3: Verify the docs read correctly**

Run: `grep -n "linear_repo" README.md`
Expected: both new entries present and adjacent to the existing hint keys.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document linear_repo/linear_repos CLAUDE.md keys"
```

---

## Self-Review

**Spec coverage:**
- Part 1 (shared canonical-name derivation, precedence, normalization, `repo:` format, basename) → Tasks 1–2. ✓
- Part 2 (triage filters both labels; parent/user-story guard; `run_triage` signature; `main` threading; dry-run surfaces filter; `held` semantics preserved — wrong-repo tickets are simply absent because the prompt never returns them) → Tasks 3–4. ✓
- Part 3a/3b/3c/3d (layered discovery → ask; Phase-3 assignment; label bootstrap; label application) → Task 5. ✓
- "What does NOT change" (plan-doc location) → honored: no task touches doc-gen. ✓
- Open item: document the `CLAUDE.md` keys → Task 6. ✓

**Placeholder scan:** No `TBD`/`TODO`/"handle edge cases"; every code step shows complete code; every command shows expected output. The `<a small two-repo idea>` and `<assigned-repo>` tokens in Task 5 are author-supplied values at runtime, not unfilled plan content. ✓

**Type consistency:** `resolve_repo_label(args, read_claude_md, remote_url_fn)` is defined in Task 2 and called as `resolve_repo_label(args)` in Task 4 (defaults supply the seams) — consistent. `run_triage(project, label, repo_label, runner)` is defined in Task 3 and called with exactly those args in Task 4; the injected `triage_fn` lambda in `TestMainDryRun` matches the 4-arg shape. `_repo_name_from_url` (Task 1) is consumed by `resolve_repo_label` (Task 2). No annotations introduced, matching `loop.py`. ✓
