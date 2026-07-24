You are receiving Subproject 4 (Evidence Explorer) as a completed artifact.

  

WHAT WAS BUILT:

A single static HTML file (index.html) implementing the Evidence Explorer.

- Safe evidence rendering with line numbering

- Four views: Map, Teach, Debug, Govern

- Side-by-side comparison for two records

- Markdown and JSON export

- All six acceptance test cases pass (report attached)

  

WHAT WAS DEFERRED (for Subproject 5 or later):

- Vector search / semantic evidence routing (this is Subproject 5's domain)

- PDF export pipeline

- Multi-tenant hosting

- Accounts, auth, billing

- Background workers

  

FILES DELIVERED:

- index.html — the Explorer

- README.md — usage instructions

- CHANGELOG.md — build history and deferred items

- acceptance-test-report.md — Gate 3 results

- sample-records/ — test fixtures (pass, fail, host-internal-visible, host-internal-invoked, forbidden-extra, incomplete-evidence)

  

HOW TO OPEN:

Open index.html in any modern browser (file:/// works, no server needed).

Drag one or two attempt record JSON files onto the page.

  

ARCHITECTURE NOTES FOR SUBPROJECT 5:

- The internal data model is ExperimentRecord (see inline comments in index.html).

- Every verdict carries evidence_refs (line numbers). Subproject 5's router can query these.

- The Explorer has no write path — it cannot mutate evidence. Subproject 5 should preserve this.

- The Explorer has no search index. Subproject 5 should build semantic search over these records.