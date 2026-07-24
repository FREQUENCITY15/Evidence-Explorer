# Agent-Tool-Evidence — Copilot Prompting Playbook

## Objective

Use prompts to specify **the next change**, not to carry the project around inside the chat.

The repository should provide the memory:

- `.github/copilot-instructions.md` for durable rules;
- the versioned methodology/handoff for detailed experiment semantics;
- `docs/PROJECT_RESUME.md` for current state;
- raw evidence files for source truth.

The prompt then becomes a small control surface.

---

## Default maintainer prompt

```text
Read .github/copilot-instructions.md and docs/PROJECT_RESUME.md first.
Inspect the actual repository and named evidence inputs before making claims.

Task: <one bounded outcome>.

Work only within the allowed file scope recorded in PROJECT_RESUME.md.
Use the authoritative methodology referenced there for experimental semantics.
Run the recorded verification commands after the change.
Do not commit or push.

Report Observed / Inferred / Recommended separately and stop at this task's verification boundary.
```

---

## Evidence-sensitive prompt

Use this when exact bytes, hashes, fixtures, schemas, or classifications matter.

```text
First perform the capability preflight from .github/copilot-instructions.md.
If workspace read/write, command execution, or access to the named evidence inputs is missing, stop before editing and report the missing capability.

Read docs/PROJECT_RESUME.md.
Reopen each named raw evidence source from disk and verify the recorded SHA-256 where required.
Do not reconstruct source content from this prompt or prior chat output.

Task: <one deterministic extraction/validation/change>.
Invariant: <one precise invariant>.
Allowed files: use only the scope in PROJECT_RESUME.md.
Verification: run the recorded commands and report their actual outcomes.
Do not commit or push.
```

---

## Recovery prompt

```text
Read .github/copilot-instructions.md and docs/PROJECT_RESUME.md.
The prior session was interrupted. Treat the resume record as a pointer, not proof: inspect the workspace and verify that its recorded state is still current.

Continue only the exact "Next action" in PROJECT_RESUME.md.
Do not replay or reconstruct the previous chat transcript.
Do not broaden file scope, commit, or push.
Run the listed verification and update the resume record from observed state when the bounded action is complete.
```

---

## Review-only prompt

```text
Read .github/copilot-instructions.md, docs/PROJECT_RESUME.md, and the authoritative methodology it references.
Inspect the actual repository, Git state, diff, tests, and relevant raw evidence.

Do not edit anything.
Review the current bounded change for:
- evidence fidelity;
- methodological compliance;
- regression risk;
- accidental scope expansion;
- missing tests or verification.

Report Observed / Inferred / Recommended separately.
```

---

## What not to paste into routine prompts

Avoid repeatedly embedding:

- full historical handoffs;
- old assistant transcripts;
- complete baseline tool schemas;
- large raw logs;
- checksummed source text copied from disk;
- all prior test output;
- stable "do not commit/push" policy repeated across several paragraphs.

Instead, reference the file that owns that information.

There are exceptions. Paste source material when the current session genuinely cannot access it, or when the pasted text itself is the artifact under review. In those cases, state that the pasted material is the source for the task and do not pretend it was independently verified from disk.

---

## Good task granularity

Prefer prompts that produce one reviewable result, for example:

- fix one extractor invariant and its tests;
- reconcile one documentation mismatch with implemented behavior;
- add one fixture derived from one verified source;
- verify one release/freeze gate;
- update one resume checkpoint after verification.

Avoid prompts such as "finish the harness" or "make everything production ready". Those invite scope drift and make it hard to tell which evidence supports which change.

---

## Prompt quality checklist

Before sending a maintainer prompt, ask:

1. Is the requested outcome singular and testable?
2. Does the prompt point to source files instead of restating them?
3. Is the allowed mutation scope explicit somewhere durable?
4. Are the verification commands known?
5. Would a fresh session know where current state lives?
6. Does exact evidence need a hash or extraction rule?
7. Is this a maintainer task or an experimental trial? Those roles must remain separate.

If these are answered, the prompt is probably carrying only the useful delta.
