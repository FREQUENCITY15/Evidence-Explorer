# Evidence Explorer pilot audit bundle

Use the repository's real `QWEN-VSCODE-MCP-ECHO-001` sample for the first pilot
conversation. It already demonstrates the product's most important honesty
properties: a drifted preflight remains unscored, host-internal exposure remains
visible as an amber finding, and legacy verdicts are clearly marked unmoored.

The bundle consists of three artifacts:

1. The unchanged canonical record from `evidence/sample/`.
2. The deterministic JSON audit export, which is the lossless source of truth.
3. The readable Markdown audit export for review or ticket attachment.

With the local application running, download the two exports from the record
viewer or request them directly:

```text
GET /api/evidence/QWEN-VSCODE-MCP-ECHO-001/audit?export_format=json
GET /api/evidence/QWEN-VSCODE-MCP-ECHO-001/audit?export_format=markdown
```

Pilot reviewers should confirm that the Govern result is **unscored**, the
surface-drift and host-visible findings retain their evidence pointers, and all
six legacy reliability verdicts are marked unmoored. The export deliberately
does not claim the recorded checksum was verified: verification requires the
corresponding raw artifact and remains a separate operation.
