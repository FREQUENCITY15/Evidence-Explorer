# Agent-Tool-Evidence — Project Resume

> Keep this file compact and current. Replace stale state; do not append a transcript.

## Current checkpoint

- **Updated:** YYYY-MM-DD HH:MM Australia/Brisbane
- **Repository:** `C:\Projects\Active\Agent-Tool-Evidence`
- **Branch:** `<observed branch>`
- **Active gate / task:** `<one bounded task>`
- **Authoritative methodology:** `<path + version>`
- **Overall state:** `pass | fail | incomplete | blocked`

## Observed Git state

```text
<paste concise output from git status --short --branch>
```

## Frozen invariants

- Raw evidence is authoritative; no synthesized baselines.
- Preserve historical classifications and failures.
- Current experimental tool: `<name>`
- Accepted host-internal baseline: `<name/hash or none>`
- Forbidden-extra policy: `<rule>`
- Other task-specific invariant: `<only if currently relevant>`

## Evidence inputs

| Purpose | Path | SHA-256 | Status |
|---|---|---|---|
| `<purpose>` | `<path>` | `<hash>` | `verified | needs verification` |

Do not paste raw evidence contents here unless the source itself is tiny and the exact text is the canonical artifact.

## Allowed file scope

The current task may modify only:

```text
<path 1>
<path 2>
```

Everything else is read-only unless the task is explicitly re-scoped.

## Required verification

Inspect `package.json` first. Current expected commands:

```powershell
npm run typecheck
npm test
npm run extract -- --help
git --no-pager diff --check
git status --short --branch
```

## Last observed verification

| Check | Result | Evidence / note |
|---|---|---|
| Typecheck | `pass/fail/not run` | `<concise output>` |
| Tests | `pass/fail/not run` | `<count or failure>` |
| CLI help | `pass/fail/not run` | `<note>` |
| diff --check | `pass/fail/not run` | `<note>` |

## Current finding

**Observed:** `<facts directly established from files/logs/commands>`

**Inferred:** `<only necessary inference, with basis>`

**Unresolved:** `<specific remaining defect or uncertainty>`

## Next action

Perform exactly this bounded action:

> `<one specific action>`

Stop after its verification boundary. Do not broaden scope, commit, or push unless separately authorized.
