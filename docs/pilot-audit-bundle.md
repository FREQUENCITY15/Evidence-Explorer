# Evidence Explorer pilot walkthrough

This walkthrough is the repeatable 10–15 minute Evidence Explorer pilot. Its
purpose is to test whether a reviewer can reach a defensible decision from an
agent-tool attempt without trusting a generated summary.

## What the pilot demonstrates

The bundled `QWEN-VSCODE-MCP-ECHO-001` record deliberately contains imperfect
evidence:

- the preflight reports tool-surface drift, so Govern remains **unscored**;
- a host-internal tool was visible but not invoked, retained as an amber finding;
- the six reliability verdicts are legacy bare strings, so they are visibly
  unmoored from exact evidence citations;
- the record declares a raw-artifact checksum, but the raw artifact is not
  bundled and must not be described as verified.

Those are useful pilot conditions. The product should expose uncertainty rather
than manufacture a clean result.

## Before the conversation

1. Install dependencies and run the complete test suite using the commands in
   the repository `README.md`.
2. Start the loopback server:

   ```bash
   .venv/bin/python -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000
   ```

3. Confirm <http://127.0.0.1:8000/api/health> reports version `0.8.0`.
4. Open
   <http://127.0.0.1:8000/evidence/QWEN-VSCODE-MCP-ECHO-001>.

For a disposable import demonstration, set `EVIDENCE_RECORDS_DIR` to an
existing temporary pilot folder before starting. Import is append-only; the
browser intentionally provides no deletion or overwrite action.

## Pilot sequence

### 1. Establish evidence completeness

Start in **Evidence quality**. Explain that malformed content is rejected, while
missing observations remain visible as completeness gaps. Confirm the sample is
loadable and that warnings do not disappear behind a generic pass/fail badge.

Question for the reviewer:

> Could you tell what is missing before making a decision?

### 2. Read Govern independently from reliability

Open **Govern** and confirm:

- primary status is **unscored**;
- `surface_drift` is retained;
- `host_internal_tool_visible` remains visible as a separate amber finding;
- no model prose is used to calculate either result.

Explain that reliability and policy compliance are separate. An attempt can fail
without violating tool policy, and a drifted experiment cannot honestly receive
a clean scored result.

Question for the reviewer:

> Is the reason this attempt cannot be scored obvious?

### 3. Follow evidence citations

Choose the `#/failureCategory` citation. It should focus and highlight the
exact node in **Raw evidence**. Review another finding or verdict citation when
available.

Question for the reviewer:

> Can you move from the conclusion to the underlying evidence without searching
> through the whole record?

### 4. Inspect the six reliability layers

Review selection, arguments, protocol, execution, interpretation, and
completion. For the bundled legacy sample, confirm all six show that no exact
evidence citation was supplied. Do not reinterpret `invalid_test` as a pass.

### 5. Demonstrate validation-first import

When using a disposable record directory:

1. Choose **Import canonical JSON**.
2. Select a schema `1.0.0` record with a safe `attemptId`.
3. Choose **Validate and import**.
4. Confirm the index refreshes and the imported record opens.
5. Try importing the same file again and confirm the application refuses to
   overwrite the existing record.

The import limit is 1,000,000 serialized bytes. Invalid schema versions,
fabricated JSON Pointer citations, unsafe identifiers, and oversized records
must fail before persistence.

### 6. Verify a raw artifact when one is available

1. Select the corresponding file under **Raw artifact for checksum**.
2. Choose **Verify SHA-256**.
3. Confirm the result is either **Verified** or **Mismatch**.
4. Confirm the message says the artifact was not retained.

The server hashes at most 10,000,000 bytes and compares them with
`checksums.main_jsonl`. It does not store the raw artifact or verification
result. If no corresponding artifact is available, skip this step and retain
`not_performed`; do not use an unrelated file to imply assurance.

### 7. Export the audit bundle

Use both explicit export buttons:

1. **Export audit JSON** — lossless source of truth.
2. **Export audit Markdown** — readable review or ticket attachment.

The same artifacts are available through:

```text
GET /api/evidence/QWEN-VSCODE-MCP-ECHO-001/audit?export_format=json
GET /api/evidence/QWEN-VSCODE-MCP-ECHO-001/audit?export_format=markdown
```

Confirm the exports:

- contain the unchanged canonical record;
- contain deterministic validation and Govern results;
- contain no runtime generation timestamp;
- state `checksumVerification: "not_performed"`.

Transient browser checksum results are not injected into later downloads. A
durable verification claim will require a future versioned attestation artifact.

## Pilot acceptance questions

Record the reviewer's answers:

1. What decision were you trying to make?
2. Which finding mattered most?
3. Could you verify that finding from the raw evidence?
4. Was any status or warning confusing?
5. Would the JSON or Markdown artifact fit an existing review, incident, or
   compliance workflow?
6. What evidence source would you want to import first?
7. Who else would need to trust or approve this output?
8. Would this save enough review time or reduce enough risk to justify a paid
   pilot?

## Successful pilot outcome

The pilot is successful when the reviewer can:

- distinguish verified evidence from missing or unscored evidence;
- explain the Govern result without relying on model-generated prose;
- follow at least one conclusion to its exact source node;
- export an artifact they could attach to a real workflow;
- identify a concrete next evidence source or use case.

Do not treat a polished demo alone as validation. The commercial signal is a
reviewer willing to bring a real record, repeat the workflow, or sponsor the next
pilot.
