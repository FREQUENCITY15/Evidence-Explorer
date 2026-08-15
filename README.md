# Evidence Explorer pilot — Project Mentor 0.8.0

Evidence Explorer is the evidence-audit surface inside the local Project Mentor
application. It turns canonical agent-tool experiment records into inspectable,
citation-linked governance results and deterministic audit exports.

Project Mentor's existing Map, Teach, and Debug workflows remain available at
the application home page. Evidence Explorer adds the commercial pilot path:
import a record, inspect exactly what happened, classify tool-policy behaviour,
verify a supplied raw artifact, and export a review bundle.

## Pilot capabilities

- Loads canonical Agent-Tool-Evidence records using schema version `1.0.0`.
- Separates malformed records from incomplete but still useful evidence.
- Imports JSON records through an explicit, append-only browser action.
- Never overwrites an existing record during import.
- Shows the six reliability verdict layers with stable JSON Pointer citations.
- Renders line-numbered raw evidence using text-only DOM sinks.
- Computes deterministic Govern states: green, amber, red, flagged, or unscored.
- Verifies a user-selected raw artifact against `checksums.main_jsonl` using
  bounded SHA-256 hashing without retaining the artifact.
- Exports byte-stable JSON and readable Markdown audit artifacts.
- Requires no cloud service, API key, database, or Ollama model for the evidence
  workflow.

The pilot is local and loopback-only. Authentication, shared workspaces,
multi-user storage, remote hosting, billing, and organization administration are
not part of version `0.8.0`.

## Quick start

Python 3.12 or newer is recommended. The supplied Windows setup helper
currently requires an installed Python 3.14 interpreter (`py -3.14`).

### macOS or Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000
```

### Windows 11

```powershell
.\setup_project.bat
.\start_project_mentor.bat
```

The complete offline suite should finish with `OK` and intentionally skips one
live-Ollama smoke test unless explicitly enabled. The exact count is allowed to
grow as pilot coverage is added.

Open:

- Project Mentor home: <http://127.0.0.1:8000/>
- Evidence Explorer pilot record:
  <http://127.0.0.1:8000/evidence/QWEN-VSCODE-MCP-ECHO-001>
- API documentation: <http://127.0.0.1:8000/docs>

For the customer-facing sequence, use
[the pilot audit walkthrough](docs/pilot-audit-bundle.md).

## Evidence Explorer workflow

1. Open the bundled pilot record or select another available record.
2. Review evidence completeness before treating any verdict as conclusive.
3. Read Govern separately from reliability. A failed attempt can still be
   policy-compliant, and incomplete or drifted evidence is not scored as clean.
4. Follow verdict and finding citations into the exact raw JSON nodes.
5. To add evidence, choose **Import canonical JSON**, select one JSON object,
   then choose **Validate and import**.
6. To compare a raw capture, choose **Raw artifact for checksum**, select the
   corresponding bytes, then choose **Verify SHA-256**.
7. Export JSON as the lossless audit source of truth and Markdown as the readable
   review copy.

Imports use the record's `attemptId` as the filename and accept only flat IDs
containing letters, digits, hyphens, or underscores. Records are limited to
1,000,000 bytes. Raw checksum inputs are limited to 10,000,000 bytes.

By default, records live in `evidence/sample/`. Set
`EVIDENCE_RECORDS_DIR` before launch to use a separate writable pilot folder:

```bash
EVIDENCE_RECORDS_DIR=/absolute/path/to/pilot-records \
  .venv/bin/python -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000
```

PowerShell equivalent:

```powershell
$env:EVIDENCE_RECORDS_DIR = "C:\EvidenceExplorer\pilot-records"
.\.venv\Scripts\python.exe -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000
```

The configured directory must already exist. Direct regular `.json` files are
accepted; nested paths and symlinks are rejected.

## Evidence API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/evidence/index` | List available flat record IDs. |
| `GET` | `/api/evidence/{id}` | Return the unchanged validated record. |
| `GET` | `/api/evidence/{id}?include_validation=true` | Return record plus deterministic validation and Govern results. |
| `POST` | `/api/evidence/import` | Validate and append one canonical record. |
| `POST` | `/api/evidence/{id}/verify-checksum` | Hash a bounded octet-stream and compare its SHA-256. |
| `GET` | `/api/evidence/{id}/audit?export_format=json` | Download the lossless audit artifact. |
| `GET` | `/api/evidence/{id}/audit?export_format=markdown` | Download the readable audit artifact. |

Checksum verification is deliberately ephemeral. Standard audit exports report
`checksumVerification: "not_performed"` because a transient browser result is
not durable verification evidence.

## Trust and safety boundaries

- Record identifiers are flat and bounded; traversal and symlink records are
  rejected.
- Evidence records are read without executing or importing their content.
- Schema validation rejects unsupported versions, invalid types, unknown
  verdict vocabulary, and fabricated or unresolved evidence references.
- Missing observations and meaningful `null` or `false` values remain visible.
- Govern is a pure deterministic policy calculation and does not use an LLM.
- Unknown invoked tools default to forbidden instead of trusting self-reported
  classifications.
- Dynamic record content is inserted with `textContent`, never raw HTML.
- Imports are exclusive-create and cannot replace existing evidence.
- Raw checksum bytes are streamed, bounded, hashed, and discarded.
- Downloads occur only after an explicit user action.

## Project Mentor workflows

The original deterministic Python-codebase workflows remain at the home page:

- **Map** statically scans Python without importing or executing it.
- **Teach** builds bounded, source-grounded lessons.
- **Debug** ranks competing source-backed hypotheses without claiming a proven
  runtime root cause.
- Optional Ollama explanations remain a separate, fallible interpretation layer
  and never replace deterministic evidence.

Map uses scan schema `1.3.0`; Teach and Debug preserve their existing schemas.
Ollama is optional and is not contacted by normal evidence, scan, lesson, debug,
or test workflows.

## Known pilot limitations

- Static analysis cannot prove Python runtime behaviour.
- Evidence Explorer does not create agent-tool experiments; it audits canonical
  records produced elsewhere.
- Checksum verification results are not yet packaged as signed or durable
  attestations.
- There is no record deletion or overwrite action in the browser.
- There is no authentication, authorization, tenancy, remote synchronization,
  or billing.
- The current Starlette test client emits a dependency deprecation warning; it
  does not fail the suite.

These constraints are intentional for the first pilot: establish whether the
evidence and governance workflow is useful before expanding deployment scope.
