---
name: commit-msg
description: Use when the user wants to generate a one-line git commit message based on staged or unstaged changes since the last commit on the current branch.
---

# Commit Message Generator

Generate a one-line commit message from the changes on the current branch.

**Announce at start:** "Generating commit message..."

## Process

### Step 1: Gather Changes

Run:

```bash
git diff HEAD~1..HEAD --stat
git diff HEAD~1..HEAD
```

If there are uncommitted changes (staged or unstaged), use this instead:

```bash
git diff HEAD --stat
git diff HEAD
```

To decide which, first check:

```bash
git status --porcelain
```

If there is output (uncommitted changes exist), diff against `HEAD`. Otherwise diff against `HEAD~1`.

### Step 2: Incorporate Conversation Context

Before generating the message, check for context from the current conversation that can inform the *why* behind the changes:

- **Implementation plan**: If there is an active plan (from `superpowers:writing-plans`, `superpowers:executing-plans`, or similar), note the goal, motivation, and relevant plan step being completed.
- **Conversation history**: If the current session includes discussion about what problem is being solved, what feature is being added, or what bug is being fixed, use that intent to write a more accurate message.
- **Task context**: If tasks were created during the session, reference the task descriptions for additional context on purpose.

Use this context to capture the *why* — the diff alone often only shows the *what*.

### Step 3: Generate the Message

Write a single-line commit message:
- Imperative mood ("Add", "Fix", "Update", not "Added", "Fixes", "Updates")
- Under 72 characters
- No period at the end
- Focus on *what* and *why*, not *how*
- Conventional style (e.g., "Add user authentication endpoint", "Fix null check in payment handler")
- If conversation/plan context provides a clearer *why* than the diff alone, prefer that framing

### Step 4: Output

Print the message as a code block so it's easy to copy:

```
<the commit message>
```

Do not run any git commands that modify the repository. This skill is read-only.
