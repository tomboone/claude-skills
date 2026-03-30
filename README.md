# claude-skills

Personal Claude Code plugin with productivity skills.

## Installation

Add the marketplace to Claude Code:

```bash
claude plugin marketplace add --source github --repo <your-username>/claude-skills
```

Then enable the plugin:

```bash
claude plugin install personal@personal-skills
```

## Skills

| Skill | Description |
|-------|-------------|
| <nobr><code>/pr-desc</code></nobr> | Generate a PR title and markdown description from the current branch's changes. Detects stacked PRs, diffs against the appropriate base, and writes the result to `/tmp/pr-description.md`. |
