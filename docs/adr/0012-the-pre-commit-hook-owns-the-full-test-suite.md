# The pre-commit hook owns the full test suite

`/implementit` used to tell the session to run *"individual test files regularly, and the full suite once at the end"*, then commit. Where a repo's pre-commit hook also runs the full suite, every ticket paid for it at least twice. The manual run came first. The commit's hook run came second. A review-fix commit added a third. Nothing said not to start a run while another was going. On fundlens NEU-2199 (2026-11-10) that cost several five-minute runs and produced spurious failures: two pytest processes shared one Postgres and one MinIO bucket and broke each other.

The rule now, in `claude-global.md` → *Running tests* so that it holds in every session and not only in the pipeline:

- The pre-commit hook is the gate. Where it runs the full suite, the session never does. It runs targeted test files while iterating, commits once, and treats a hook failure as the signal.
- `/implementit` reviews the uncommitted working tree and commits once, after the review's fixes, so the hook runs once per ticket.
- The hook should run what CI runs, so that a commit that passes it passes CI. Where it is narrower, the session runs the full suite once by hand before the commit and says so. It never leaves a check to CI: a CI failure costs far more than a local run.
- Only one test process runs at a time.
- Test cost is a hard Standards finding in `/implementit`'s review. A test that rebuilds expensive state it only reads is fixed in the ticket that adds it. The hook prints the slowest tests (`--durations`) on every commit, so a slow test shows up when it lands rather than when someone notices.

## Considered options

- **Leave the full suite to CI and keep the hook unit-only.** Rejected: a CI failure is found after the push, and the round trip costs more than the local run it saves.
- **Run the full suite by hand and keep the hook fast.** Rejected: it depends on the session remembering. The hook runs every time, and the same command on every machine.
