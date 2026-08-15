# Changelog

## 0.8.0 — Evidence Explorer public alpha — 2026-08-16

- Added canonical Agent-Tool-Evidence schema `1.0.0` validation with explicit
  completeness gaps, stable JSON Pointer citations, and null/false preservation.
- Added deterministic Govern classifications that separate tool-policy
  compliance from attempt reliability.
- Added safe line-addressable raw evidence rendering and user-triggered,
  byte-stable JSON and Markdown audit exports.
- Added validation-first append-only evidence import with flat identifiers,
  symlink protection, and a shared 1 MB record limit.
- Added bounded, ephemeral SHA-256 verification for explicitly selected raw
  artifacts without retaining their bytes or overstating audit assurance.
- Added the Evidence Explorer browser workflow inside Project Mentor while
  preserving Map, Teach, Debug, Phase 6 metadata, and existing schema contracts.
- Added a repeatable public pilot walkthrough and cross-platform setup guidance.
- Added GitHub Actions coverage on Python 3.12, 3.13, and 3.14.
- Added Apache-2.0 licensing, security and contribution guidance, issue
  templates, and public-alpha positioning.

## 0.7.0 — Phase 6 deterministic Debug investigation foundation — 2026-07-21

- Enabled an offline Debug tab for scanned functions and methods.
- Added isolated Debug schema `1.0.0` models without changing Map schema `1.3.0`
  or Teach schema `1.1.0`.
- Added byte-stable investigations with up to four competing, explicitly
  unverified hypotheses and one focused manual diagnostic observation each.
- Bounded investigation evidence to 12 records, reused stable evidence IDs, and
  validated every hypothesis and diagnostic citation against its allow-list.
- Added trusted-scan `POST /api/debug/investigation`; it never contacts Ollama,
  executes a command, imports scanned code, or modifies a scanned repository.
- Added user-triggered JSON and readable Markdown investigation exports with
  safe rendering of failure descriptions and repository evidence.
- Preserved loopback operation, opaque in-memory scan IDs, source-only scanning,
  deterministic ordering, existing Map/Teach behaviour, and optional Map/Teach
  Ollama interpretation.
- Expanded offline regression coverage for determinism, evidence bounds,
  citation validation, no-execution safety, API failures, UI safety, and exports.

## 0.6.1 — Teach readability repair — 2026-07-21

- Replaced record-by-record beginner paragraphs with stable purpose, input/output,
  relationship, and error summaries plus an ordered walkthrough.
- Added a deterministic 12-record teaching budget that prioritises explicit
  source facts and resolved internal project calls over unresolved built-ins.
- Preserved the exact bounded technical evidence in expandable groups and the
  JSON export while removing raw evidence IDs from default lesson prose.
- Grouped repeated data-flow and call-error explanations and stated the general
  AST/runtime boundary once instead of once per call.
- Replaced giant-expression prediction tasks and metadata-recognition quizzes
  with short source-backed exercises and understanding-focused answer keys.
- Restricted prerequisites to useful resolved internal calls; file imports and
  empty package markers remain technical context rather than required reading.
- Added a user-triggered readable deterministic lesson Markdown export. The
  lesson JSON remains the source of truth for exact records and evidence IDs.
- Added progressive disclosure for section references and technical evidence,
  plus grid, certainty-label, and long-text overflow fixes.
- Updated the Teach lesson schema from `1.0.0` to `1.1.0` while preserving Map
  scan schema `1.3.0`, offline Teach, loopback defaults, citation validation,
  safe model rendering, and the existing Map exports.
- Expanded regression coverage for prioritisation, stable grouping, bounded
  beginner prose, evidence preservation, meaningful quizzes/exercises, the
  small AI allow-list, progressive disclosure, layout wrapping, and exports.

## 0.6.0 — Phase 5 deterministic Teach foundation — 2026-07-20

- Enabled a functional Teach tab for scanned functions and methods.
- Added deterministic lesson models and a builder for objectives, direct
  prerequisites, source-backed sections, vocabulary, one prediction exercise,
  and a three-question quiz with fixed answers and explanations.
- Reused stable Map evidence IDs and added explicit observed, inferred, and
  static-limit labels without changing scan schema `1.3.0`.
- Added trusted-scan `/api/teach/lesson` and `/api/teach/explain` routes; lesson
  generation remains fully available when Ollama is stopped.
- Restricted optional Teach AI interpretation to the lesson's bounded
  allow-listed evidence while preserving model checks, citation validation,
  output limits, safe logging, and one malformed-response retry.
- Added user-triggered Markdown exports for Map and Teach model output, with a
  native Save As picker and download fallback, plus deterministic lesson JSON
  export. Model output remains text-only and cannot choose a filesystem path.
- Preserved loopback defaults, Map behaviour, static-analysis limits, and
  source-only scanning.
- Expanded the suite to 66 tests, with the live Ollama smoke test skipped unless
  explicitly enabled.

## 0.5.1 — Phase 4 reliability patch — 2026-07-20

- Reduced the default bounded evidence budget from 24,000 to 6,000 characters
  after confirming the larger local prompt caused structured generation failure.
- Added deterministic temperature, a validated 2,048-token output cap, typed
  output-limit failures, safe metadata logging, and one malformed-JSON retry.
- Strengthened offline and opt-in live tests to validate structured responses.

## 0.5.0 — Phase 4 local AI foundation — 2026-07-19

- Audited the supplied source and documented that version 0.4.0 implements
  Phase 1.3 Map only; Teach, Debug, and Govern remain disabled because their
  deterministic Phase 2/3 structures were not present.
- Added an isolated async Ollama client with environment-configured origin,
  separate connection/generation timeouts, model listing, non-streaming chat,
  and typed unavailable, timeout, HTTP, model, and malformed-response errors.
- Added installed-model selection that prefers `gpt-oss:20b` only when Ollama
  confirms it is installed, plus offline/no-model UI guidance and refresh.
- Added a shared deterministic context builder with stable evidence IDs,
  selected-symbol relevance, bounded source snippets, configurable evidence
  budget, deterministic ordering, and visible truncation notices.
- Added strong untrusted-repository delimiters and system instructions that
  prohibit following repository instructions, tool use, command execution,
  file modification, and raw HTML.
- Added structured local-model response validation, allow-listed citation
  resolution, invented-citation rejection, and explicit insufficient-evidence
  handling.
- Added a grounded Map explanation workflow that visibly separates observed
  facts, Project Mentor inference, and local-model interpretation.
- Added bounded in-memory scan IDs so AI requests reuse server-trusted scan
  objects while JSON report schema `1.3.0` remains unchanged.
- Preserved loopback FastAPI launch commands and all original scanner limits,
  deterministic behavior, no-execution guarantees, and 20 regression tests.
- Added focused configuration, client, offline, no-model, timeout, malformed
  response, context, citation, injection, traversal, UI-output, AI-service, and
  optional live-Ollama tests: 53 total tests, with one live test skipped unless
  explicitly enabled.
- Updated requirements, README, Windows upgrade/rollback instructions, Ollama
  preflight, configuration, security model, limitations, and test guidance.

## 0.4.0 — Phase 1.3 — 2026-07-19

- Added source-observed parameter evidence with parameter kinds, annotation
  text, and default expression text.
- Added explicit return, yield, yield-from, and raise sites with locations and
  path confidence.
- Added conservative function-local assignment/data-flow relationships with
  referenced names, expressions, confidence, and reasons.
- Added direct attribute, subscript, global, nonlocal, and deletion mutation
  evidence plus explicitly uncertain common mutator-method evidence.
- Added try-body, except-handler, try-else, and finally path evidence.
- Added explicitly uncertain call error-propagation evidence, lexical handler
  context, and resolved internal target raise lines when available.
- Expanded the browser function trace with inputs, outputs, data flow,
  mutations, error paths, and call propagation while preserving the Phase 1.2
  caller/callee/unresolved trace.
- Added report schema `1.3.0`, generator version `0.4.0`, new summary counts,
  and two additional static-analysis boundary warnings.
- Preserved AST-only scanning, deterministic JSON, ignored directories,
  source-file symlink and 1 MB file protections, the 2,000-file limit, and the
  `127.0.0.1` server binding.
- Preserved all 14 Phase 1.2 regression scenarios and added six focused Phase
  1.3 tests, for 20 passing tests total.
- Updated the README, changelog, Windows update/fresh-install instructions,
  self-scan guidance, and browser wording for Phase 1.3.

## 0.3.0 — Phase 1.2 — 2026-07-19

- Added stable symbol definitions for classes, functions, async functions,
  methods, and async methods.
- Documented the `module:qualified_name` symbol-ID format and conservative
  duplicate-definition handling.
- Added alias-aware resolution for same-module calls, `from` imports,
  module-qualified calls, class constructors, explicit class methods,
  `self`/`cls` methods, and simple constructor-assigned receivers.
- Added high, medium, and unresolved call confidence with a reason and source
  location for every detected call.
- Added the selectable function trace for outgoing calls, callers, and
  unresolved calls.
- Added report schema `1.2.0`, generator/project metadata, deterministic list
  ordering, separated observed facts and inferred relationships, and static
  analysis warnings.
- Refined learning order so production dependencies lead, test files generally
  follow production code, and empty package markers have low priority.
- Kept scanning source-only, ignored source-file symlinks, preserved file-size
  and ignored-directory limits, and kept the server on `127.0.0.1`.
- Preserved the five Phase 1.1 tests and added nine focused Phase 1.2 tests.
- Updated the application to version `0.3.0` and refreshed Windows setup,
  update, test, and run instructions.

## 0.2.0 — Phase 1.1

- Added a visual local-file import graph.
- Classified imports as internal, Python standard-library, or external.
- Added source-level function and method call relationships.
- Added high, medium, and low entry-point confidence.
- Added cautious “possibly unused” file detection.
- Added external dependency reporting.
- Added downloadable JSON scan reports.
- Expanded scanner regression tests.

## 0.1.0 — Phase 1

- Added local Python repository scanning.
- Extracted imports, functions, methods, and classes.
- Added likely entry-point detection and a recommended learning order.
- Added the local FastAPI browser interface and Windows launch helpers.
