# Evidence Explorer — Design Plan (Lean & Survivable)

  

Here's how I'd approach this, guided by the principle that every piece added must justify its existence.

  

___

  

## Core shape

  

**A single static HTML page + vanilla JS.** That's it. No framework, no build step, no backend, no database. It reads evidence files (JSON/Markdown) from a local directory served by a bare static file server. The browser is the explorer.

  

Why this shape: it satisfies every non-negotiable constraint in the handoff AGENT\_TOOL\_EVID...OFF (1).md — no cloud, no auth, no persistence, no embedding, no background workers. It's trivially auditable and impossible to mutate experiment records because it has no write path.

  

___

  

## What it actually does

  

1.  **Load** — drag-and-drop or file-picker opens one or more evidence files (JSON experiment records, Markdown logs).

2.  **Display (Evidence-First)** — raw evidence occupies the primary pane, rendered as safe text (escaped, syntax-highlighted, never interpreted as HTML). Model-generated explanations go in a secondary, clearly labelled panel alongside it. If a derived verdict contradicts the raw evidence, the conflict is surfaced visually — raw evidence wins, always.

3.  **Navigate** — simple table-of-contents sidebar lets you jump between tool-call entries, argument blocks, verdicts, and final answers within a loaded experiment.

4.  **Compare** — side-by-side diff view for two experiment records, highlighting discrepancies in tool selection, argument construction, and verdict compliance.

5.  **Export** — one button dumps the current view as clean Markdown; another exports the structured evidence as JSON.

  

___

  

## Data model (the heart of it)

  

A single internal representation that everything else hangs off:

  

Collapse

  

Run

  

Save Copy

  

99

  

1

  

2

  

3

  

4

  

5

  

6

  

7

  

8

  

9

  

10

  

11

  

12

  

13

  

14

  

15

  

›

  

ExperimentRecord

  

├── metadata (id, model, timestamp, runner)

  

├── tool\_exposure\[\] ← what tools were available

  

├── calls\[\] ← each tool-use attempt

  

│ ├── selection ← which tool was chosen

  

│ ├── arguments ← constructed arguments (raw)

  

│ ├── protocol\_emission ← the actual call made

  

│ ├── host\_execution ← result from the host

  

│ ├── result\_delivery ← how the result reached the model

  

│ └── interpretation ← what the model did with the result

  

├── verdicts\[\] ← derived assessments

  

│ ├── category ← compliance / argument-validity / forbidden-use etc.

  

│ ├── determination ← pass / fail / flag

  

│ └── evidence\_refs\[\] ← pointers back to raw evidence lines

  

└── final\_answer ← what the model ultimately said

  

Every verdict must carry `evidence_refs` — pointers back to specific lines or blocks in the raw evidence. If it doesn't, the explorer flags it as unmoored. This is the traceability constraint in code AGENT\_TOOL\_EVID...OFF (1).md.

  

___

  

## Rendering rules

  

-   **All model-generated text is untrusted** — escaped by default, rendered in a monospace block with a distinct background and a visible `[MODEL OUTPUT]` label.

-   **Deterministic evidence** — rendered in a clean, undecorated panel with line numbers.

-   **Conflicts** — if a verdict says "pass" but the evidence shows a malformed argument, a red banner appears: `⚠ Verdict contradicts evidence at line 42`. No override, no hiding it.

-   **No mutation path exists.** The explorer can annotate in memory, but those annotations evaporate on refresh. There is no save button for annotations.

  

___

  

## Architecture boundaries (what we don't build)

  

|                  Thing                  |                                   Why we skip it                                    |

|-----------------------------------------|-------------------------------------------------------------------------------------|

| Frontend framework (React, Vue, Svelte) |      Adds dependency weight; vanilla JS survives longer with less maintenance       |

|           Backend/API server            | Static files are enough; a backend introduces auth, persistence, and attack surface |

|                Database                 |         Experiment records are files on disk; queries are in-memory filters         |

|              PDF pipeline               |       JSON and Markdown export covers the need; PDF is a future nice-to-have        |

|         Vector DB / embeddings          |           Semantic search over evidence is Subproject 5 (routing), not 4            |

|           Background workers            |                    Nothing needs async processing at this stage                     |

  

___

  

## Build order (what to write first)

  

1.  **Safe text renderer** — the `escape-and-display` function that treats all input as untrusted. Everything depends on this.

2.  **File loader** — drag-drop and file-picker, parsing JSON and Markdown into the internal `ExperimentRecord` shape.

3.  **Evidence pane** — the primary display, line-numbered, with verdict-to-evidence linking.

4.  **Verdict panel** — secondary panel, cross-referencing evidence lines.

5.  **Diff view** — side-by-side comparison of two records.

6.  **Export** — JSON dump and Markdown generation.

  

___

  

## The survivability test

  

If it runs in a browser opened to `file:///` with no server at all, it should still work for single-file exploration. That's the baseline. Everything above that — a static server for multi-file comparison, slightly nicer navigation — is a bonus, not a dependency.

  

___

  

That's the plan. It's deliberately minimal. The Evidence Explorer's job is to make evidence visible and verdicts auditable — nothing more. Complexity enters only when a specific piece of supplied evidence demands it.

  

Ask

  

Explain

  

1 Source

  

Yesterday at 22:00

  

your plan is approved draft a gated implementation scheme. Out line the steps and defined progress goals for this project. make hand off prompt templates that can transfer work between context sessions

  

deepseek-v4-pro

  

Yesterday at 22:00

  

Retrieved 1 source

  

Thought for 3 seconds

  

# Gated Implementation Scheme — Evidence Explorer (Subproject 4)

  

___

  

## Gate Structure Overview

  

The scheme has four implementation stages, each gated by a readiness check. No stage begins until its gate clears. This is not bureaucracy — it's the survivability constraint from the handoff: _"Subproject 4 is not authorised to bypass the gates of Subprojects 1–3."_ AGENT\_TOOL\_EVID...OFF (1).md

  

Collapse

  

Save Copy

  

9

  

1

  

2

  

3

  

›

  

GATE 0 ──▶ STAGE 1 ──▶ GATE 1 ──▶ STAGE 2 ──▶ GATE 2 ──▶ STAGE 3 ──▶ GATE 3 ──▶ STAGE 4 (DONE)

  

(prereq (scaffold) (one (views) (comparison (export/ (acceptance

  

check) record) works) polish) tests pass)

  

___

  

## GATE 0 — Prerequisite Readiness Check (DO NOT PASS without evidence)

  

**What must be true before writing a single line of code:**

  

|             Condition              |                                                                                                               Evidence Required                                                                                                                | Status Field |

|------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|

|       Subproject 1 complete        |                                                                  Frozen native VS Code Copilot/MCP evidence core specification document, with version number and freeze date                                                                   |      ☐       |

|       Subproject 2 complete        | At least one validated real-attempt dataset file (JSON or structured Markdown), with evaluator version stamped, containing all required fields: model, host, client, protocol, prompt version, tool surface, calls[], verdicts[], final_answer |      ☐       |

|       Subproject 3 complete        |                                                                  Model Rodeo comparison runner specification or output; at minimum, the schema that Subproject 4 must render                                                                   |      ☐       |

|      Attempt record validates      |                                         A single attempt record passes structural validation against the Subproject 2 schema — every field in the data model is present or explicitly marked optional                                          |      ☐       |

| Verdict-to-evidence linking exists |                                                          At least one verdict in the supplied record carries `evidence_refs` (line numbers or block IDs pointing back to raw evidence)                                                           |      ☐       |

  

**Gate 0 verdict:** If any condition fails, produce a **planning-only readiness assessment** listing what is present and what is missing. Do not proceed to Stage 1. If all conditions pass, produce an **implementation-ready** declaration and open Stage 1. AGENT\_TOOL\_EVID...OFF (1).md

  

___

  

## STAGE 1 — Scaffold: Safe Renderer + File Loader + Single-Pane Evidence Display

  

**Purpose:** Get one attempt record rendering safely in a browser. Nothing else matters until this works.

  

**Inputs:**

  

-   One validated attempt record (JSON)

-   The data model specification from Subproject 2

  

**Outputs:**

  

-   `index.html` — single static file containing all HTML, CSS, and vanilla JS

-   Functions: `escapeText()`, `renderEvidencePane()`, `loadFile()`, `parseRecord()`

-   A browser tab showing raw evidence with line numbers and syntax highlighting

-   No verdict panel, no navigation, no diff — those come later

  

**Verification method:**

  

1.  Open `index.html` via `file:///` in Chrome and Firefox

2.  Drag-drop a valid attempt record JSON file

3.  Confirm: all model-generated text is escaped (HTML tags appear as text, never rendered)

4.  Confirm: evidence pane shows line-numbered, monospace, syntax-colored output

5.  Confirm: no error in console for malformed JSON (graceful error message instead)

6.  Confirm: zero network requests in DevTools (proving no exfiltration)

  

**Progress goal:** A single attempt record renders safely in a browser with zero build steps, zero dependencies, and zero network activity.

  

___

  

## GATE 1 — Single-Record Rendering Check

  

|   Condition    |                                                  Check                                                  |

|----------------|---------------------------------------------------------------------------------------------------------|

| Safe rendering | Inject `<script>alert(1)</script>` into a field in the test record. It must appear as text, never execute |

|  File loading  |          Both drag-drop and file-picker work; malformed JSON shows an error, not a blank page           |

|   No network   |                                DevTools Network tab shows zero requests                                 |

| `file:///` works |                    Page functions when opened directly from disk, no server required                    |

| Line numbering |  Every displayed line of evidence carries a stable line number that verdict `evidence_refs` can point to  |

  

**If Gate 1 passes:** Stage 2 opens.

  

___

  

## STAGE 2 — Views: Verdict Panel + Navigation TOC + All Four Required Views

  

**Purpose:** Add the secondary panels that make the Explorer an _explorer_ rather than a viewer.

  

**Inputs:**

  

-   The working Stage 1 `index.html`

-   At least one attempt record with verdicts containing `evidence_refs`

  

**Outputs (four views, each justified by distinct value):** AGENT\_TOOL\_EVID...OFF (1).md

  

|  View  |                                                                                                           What it shows                                                                                                            |                                         Distinct value                                          |

|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|

|  **Map**   |            Attempt structure tree: metadata → tool_exposure → calls[] (with selection→arguments→emission→execution→delivery→interpretation chain) → verdicts[] → final_answer. Click a node, jump to that evidence line.             | Shows _relationships_ — which call produced which result, which verdict references which evidence |

| **Teach**  | Plain-language explanation of what happened in this attempt, with each claim carrying a citation link to the raw evidence line. Example: "The model selected `read_file` (line 42). The argument `file_path` was well-formed (line 44)." |       Makes the attempt legible to a non-technical auditor without obscuring the evidence       |

| **Debug**  |                          First point of divergence: where did the model's behavior depart from expected? Highlights the exact call, argument, or interpretation that failed the first reliability layer.                           |      Collapses an entire attempt into "here is where it went wrong, here is the evidence"       |

| **Govern** |                           Tool-policy compliance matrix: forbidden tool use (red), host-internal allowances used (amber), tool exposure completeness (green/grey), evidence completeness gaps (flagged).                           |      The compliance/audit view — answers "did this attempt violate policy?" in one glance       |

  

**Verdict panel behavior:**

  

-   Each verdict displays: category, determination (pass/fail/flag), and clickable evidence references

-   If a verdict contradicts raw evidence (e.g., says "pass" but evidence shows malformed argument), a red conflict banner appears: `⚠ Verdict contradicts evidence at line N`

-   Verdicts lacking `evidence_refs` are flagged: `⚠ Unmoored verdict — no evidence citation`

  

**Verification method:**

  

1.  Load a record with at least one pass verdict and one fail verdict

2.  Click each view tab — confirm distinct content in each

3.  In Map view, click a call node — confirm it scrolls the evidence pane to the correct line

4.  In Teach view, click a citation link — confirm it jumps to evidence

5.  In Govern view, confirm forbidden-use verdicts render red, compliant ones green

6.  Deliberately inject a contradictory verdict (pass where evidence shows failure) — confirm the conflict banner appears

  

**Progress goal:** All four views render correctly for a single record; every verdict-to-evidence link is navigable.

  

___

  

## GATE 2 — Single-Record Completeness Check

  

|         Condition         |                                       Check                                       |

|---------------------------|-----------------------------------------------------------------------------------|

|   All four views render   | Map, Teach, Debug, Govern each show distinct, correct content for the same record |

|   Verdict linking works   |     Every `evidence_refs` is clickable and scrolls to the correct evidence line     |

|    Conflict detection     |                Contradictory verdicts trigger the conflict banner                 |

| Unmoored verdict flagging |             Verdicts without `evidence_refs` show the unmoored warning              |

| No regression on Stage 1  | Safe rendering, file loading, `file:///` operation, and zero-network all still hold |

  

**If Gate 2 passes:** Stage 3 opens.

  

___

  

## STAGE 3 — Comparison View + Export

  

**Purpose:** Add the multi-record comparison capability and the export pipeline.

  

**Inputs:**

  

-   The working Stage 2 `index.html`

-   At least two attempt records (ideally one passing, one failing, for the same prompt)

  

**Outputs:**

  

**Comparison view — side-by-side diff:**

  

-   Two records loaded simultaneously

-   Columns aligned by: metadata, tool selection, argument construction, verdict compliance, final answer

-   Discrepancies highlighted: different tool chosen, different argument shape, different verdict outcome

-   Comparison dimensions drawn from the handoff spec: _model, model version, host, client, protocol, prompt version, tool surface, evaluator version, timestamp, cost, pricing band_ AGENT\_TOOL\_EVID...OFF (1).md

  

**Export:**

  

-   **Markdown export:** current view (any of the four views) rendered as clean Markdown with evidence citations preserved as footnotes

-   **JSON export:** the complete internal `ExperimentRecord` with all annotations (but no mutations to the original evidence)

  

**Verification method:**

  

1.  Load two records — confirm side-by-side columns align

2.  Confirm discrepancies are visually highlighted

3.  Export each view as Markdown — confirm citations survive

4.  Export as JSON — confirm structure matches the internal data model

5.  Re-import the exported JSON — confirm it renders identically

  

**Progress goal:** Two records can be compared side-by-side; any view can be exported as Markdown.

  

___

  

## GATE 3 — Full Acceptance Test (from the handoff spec)

  

**Required test cases from the spec:** AGENT\_TOOL\_EVID...OFF (1).md

  

|       Test Case       |                                                                     What to Verify                                                                     |

|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|

|         **Pass**          | A fully compliant attempt — all verdicts are "pass", evidence is complete, no conflicts. Explorer shows green across Govern view, no conflict banners. |

|         **Fail**          |        An attempt with a confirmed violation — verdict correctly says "fail", evidence supports it, Debug view identifies the divergence point.        |

| **Host-internal-visible** |      An attempt where a host-internal tool appeared in the tool exposure list. Govern view must flag it amber, not red (visible is not invoked).       |

| **Host-internal-invoked** |                                An attempt where a host-internal tool was actually called. Govern view must flag it red.                                |

|    **Forbidden-extra**    |                            An attempt where a tool not in the declared tool surface was used. Govern view must flag it red.                            |

|  **Incomplete-evidence**  |        An attempt record missing required fields (e.g., no `host_execution` block). Explorer must flag evidence-completeness gaps in Govern view.        |

  

**Gate 3 passes when:** All six test cases render correctly, all flags appear in the correct color/severity, and no false positives or false negatives occur.

  

___

  

## STAGE 4 — Polish & Handoff

  

**Only after Gate 3 passes:**

  

-   Inline documentation comments in the single `index.html`

-   A `README.md` with: what this is, how to open it, what files it accepts, how to interpret each view

-   The handoff prompt template (see below) filled out with the final state

-   A `CHANGELOG.md` listing what was built, what was deferred, and why

  

**Explicitly deferred (from the spec):** accounts, billing, multi-tenant hosting, vector search, autonomous remediation, generic dashboards, PDF export pipeline. AGENT\_TOOL\_EVID...OFF (1).md

  

___

  

# Progress Goals — Summary Milestones

  

Collapse

  

Run

  

Save Copy

  

9

  

1

  

2

  

3

  

4

  

5

  

6

  

›

  

M0: Gate 0 clears — prerequisites confirmed \[planning → build-ready\]

  

M1: Stage 1 done — safe evidence rendering in browser \[one file, zero deps\]

  

M2: Stage 2 done — all four views functional \[explorable, auditable\]

  

M3: Stage 3 done — comparison + export working \[multi-record, shareable\]

  

M4: Gate 3 clears — all six acceptance tests pass \[verified\]

  

M5: Stage 4 done — documented, handed off \[complete\]

  
  