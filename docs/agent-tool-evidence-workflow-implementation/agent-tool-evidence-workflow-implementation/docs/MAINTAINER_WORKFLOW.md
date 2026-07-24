# Agent-Tool-Evidence — Maintainer Workflow

## Purpose

This workflow reduces restart cost without increasing experiment context pressure. It separates permanent project rules, current state, raw evidence, and the next action so that a fresh maintainer session can resume from sources instead of pasted transcripts.

## The four-layer context model

### 1. Durable instructions

Location:

```text
.github/copilot-instructions.md
```

Contains only rules expected to remain stable across many tasks: evidence authority, change discipline, verification expectations, capability preflight, and links/identity for the current methodology.

Do **not** place session history, current hashes, temporary failures, or large handoff payloads here.

### 2. Authoritative methodology

Keep methodological detail in the versioned handoff/specification, currently the v3.1 native MCP reliability handoff.

This is where detailed experimental rules belong, including tool-surface classification, validity rules, gates, and scoring semantics.

Do not duplicate the entire methodology into Copilot instructions or recovery prompts. Point to it.

### 3. Project resume record

Location recommended:

```text
docs/PROJECT_RESUME.md
```

This is a deliberately small, frequently updated state record. It answers: **where are we now?**

It should contain only:

- current branch and Git state summary;
- current acceptance gate or bounded task;
- authoritative document path/version;
- raw evidence paths and SHA-256 values relevant to the current task;
- frozen invariants and accepted baselines;
- allowed file scope;
- required verification commands;
- current pass/fail/incomplete state;
- exact unfinished action or next bounded action.

Do not use it as a diary. Replace stale state rather than appending generations of narrative.

### 4. Task prompt

A fresh task prompt should normally contain only the delta:

1. read `.github/copilot-instructions.md`;
2. read `docs/PROJECT_RESUME.md`;
3. read the named authoritative methodology section if needed;
4. perform one exact unfinished action;
5. remain inside the allowed file scope;
6. run the listed verification.

Raw evidence contents should not be pasted into the prompt when the agent can read the files directly.

---

## Session-start preflight

For evidence-sensitive work, begin with a capability check before touching baselines.

Confirm the session can:

- read the workspace and named evidence files;
- edit the allowed files if mutation is requested;
- execute the verification commands;
- hash or otherwise inspect raw evidence where the task depends on byte identity.

If one is missing, stop the evidence-changing portion of the task. Do not compensate by reconstructing raw evidence from chat history.

### Why this matters

An agent that can reason about a task but cannot read files or run commands cannot safely verify an immutable evidence contract. Discovering that limitation early is cheaper than reconstructing several turns of state and only then discovering the task is impossible in that session.

---

## Raw evidence rule

Treat evidence files as **addressable inputs**, not prose to shuttle between chats.

A good task instruction names:

```text
Source: <path>
Expected SHA-256: <hash, when frozen>
Extraction rule: <deterministic rule>
Invariant: <what must remain true>
```

The agent should reopen the source and derive the needed value itself.

This prevents character-level drift, whitespace drift, escaping mistakes, truncation, and accidental "helpful" normalization caused by repeated copy/paste.

When a derived fixture intentionally contains normalized data, record the exact transformation and keep the source hash beside it.

---

## Recovery after interruption or freeze

Do not paste the previous assistant transcript into the next session by default.

Instead:

1. update `docs/PROJECT_RESUME.md` from observed state;
2. include exact evidence paths/hashes relevant to the unfinished change;
3. record the last verification result actually observed;
4. name the unfinished action precisely;
5. start a fresh session with the recovery prompt below.

Example:

```text
Read .github/copilot-instructions.md and docs/PROJECT_RESUME.md first.
The previous maintainer session was interrupted during the bounded action recorded there.
Inspect the actual repository before assuming the recorded state is still current.
Continue only the "Next action" from the resume record, stay within its allowed file scope, and run its verification commands.
Do not commit or push.
```

If the actual workspace differs from the resume record, the workspace wins and the discrepancy must be reported.

---

## When to start a fresh chat

Starting focused chats is appropriate when the unit of work changes, a task reaches a verification boundary, or a previous session becomes unreliable/interrupted.

Do not restart merely to "save context" when the current session remains coherent. The goal is not maximal chat longevity; it is cheap, deterministic resumption.

Useful boundaries include:

- after a verified implementation chunk;
- before changing an experimental variable;
- after freezing a new evidence checksum;
- after a commit/release boundary;
- after an interrupted or capability-limited session.

---

## Prompt design rule

Prefer a **source-linked contract** over a self-contained mega-prompt.

A strong maintenance prompt usually needs:

- one goal;
- one bounded file scope;
- one or more source paths;
- relevant invariant(s);
- verification commands;
- explicit prohibitions only when they matter to the task.

Everything stable should already live in durable instructions or methodology. Everything current should already live in the resume record.

---

## Completion record

At the end of a successful bounded chunk, update the resume record with observed facts before beginning another large task.

Record:

- what changed;
- verification outcomes;
- current Git state;
- new/changed evidence hashes if applicable;
- whether the acceptance gate changed;
- exactly one next action.

This makes the repository itself the handoff mechanism instead of the chat transcript.
