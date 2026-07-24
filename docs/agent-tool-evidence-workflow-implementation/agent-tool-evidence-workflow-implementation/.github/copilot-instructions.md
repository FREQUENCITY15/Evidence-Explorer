# Agent-Tool-Evidence — Copilot Project Instructions

These instructions are durable repository rules. Task-specific state belongs in the project resume record or the authoritative methodology documents, not here.

## Evidence contract

- Inspect actual files, Git state, tests, logs, and raw evidence before making claims or edits.
- Treat observed raw evidence as authoritative. Never synthesize, reconstruct, normalize, or "repair" raw evidence to make it match an expected baseline.
- Distinguish **Observed**, **Inferred**, and **Recommended** statements.
- Preserve historical evidence, classifications, failures, fixtures, and prior accepted results unless an explicit migration says otherwise.
- Missing evidence is not success. Fail closed where the authoritative methodology requires conclusive proof.
- Keep tool-use reliability layers separate. Do not collapse exposure, selection, arguments, protocol, execution, interpretation, and completion into one unexplained result.

## Tool-surface rules

For the current v3.1 native VS Code/Copilot MCP experiment, follow the authoritative handoff rather than duplicating its full contents here.

Current frozen taxonomy:

- `experimental`: `mcp_everything_re_echo`
- `host_internal`: `session_store_sql`
- `forbidden_extra`: every other model-visible function

A host-internal function may be visible only when it matches the accepted frozen baseline. Its invocation invalidates the experimental attempt. Any new, removed, or schema-changed host-internal function is surface drift and requires an unscored preflight.

## Change discipline

- Keep edits within the user-approved file scope.
- Prefer the smallest change that satisfies the current acceptance gate.
- Do not delete, rewrite, or broadly reorganize historical material merely because it is untidy.
- Do not perform destructive Git operations.
- Do not commit, push, rename branches, rename the repository, or publish evidence unless explicitly authorized.
- Do not add a custom MCP client, generic agent framework, dashboard, cloud API, database, routing layer, or unrelated infrastructure while the v0.1 evidence core is being frozen.
- Separate formatting-only changes from behavioral changes where practical.

## Evidence handling

- Treat raw evidence files as inputs. Read them from their recorded paths and verify hashes when required; do not ask for their contents to be pasted into prompts when filesystem access is available.
- Preserve exact source bytes for checksummed evidence. Apply extraction or normalization only in deterministic derived processing, never by altering the source.
- Do not expose or commit secrets, credentials, unrelated private content, or unreviewed raw debug logs.

## Verification discipline

Before claiming a change is complete, inspect `package.json` and the active task documentation, then run the applicable repository-defined checks. For the current extractor work these normally include:

```powershell
npm run typecheck
npm test
npm run extract -- --help
git --no-pager diff --check
git status --short --branch
```

Report the actual observed outcomes. Do not assume a command passed because it passed in a previous session.

## Capability preflight

Before an evidence-sensitive task that requires repository mutation or command execution, confirm that the current session can:

1. read the workspace files required by the task;
2. write the explicitly allowed files when edits are requested;
3. execute the required verification commands;
4. access the named raw evidence paths.

If a required capability is unavailable, stop before modifying baselines or reconstructing history. Report the missing capability and continue only in a tool-enabled session.

## Authority order

When instructions disagree, use this order:

1. actual observed repository and raw evidence;
2. the current authoritative methodology/handoff (v3.1 for the native MCP experiment);
3. current project resume record;
4. task prompt;
5. older handoffs and historical notes.

Report material discrepancies instead of silently choosing the more convenient interpretation.
