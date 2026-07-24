# Project Mentor — Phase 6 deterministic Debug investigation foundation

Project Mentor is a local FastAPI browser application that reads Python source
without importing or executing the scanned repository. Version `0.7.0` adds a
deterministic Debug workflow that ranks competing source-backed hypotheses and
proposes focused manual observations without running commands or contacting
Ollama.

The deterministic scan report remains schema `1.3.0`. Local-model text is a
separate interpretation layer: it may be wrong and never replaces scanner
facts or conservative Project Mentor inferences.

## What version 0.7.0 changes

- enables Debug for scanned functions and methods after a user describes an
  observed failure;
- returns byte-stable Debug schema `1.0.0` investigations through
  `POST /api/debug/investigation`;
- ranks up to four competing hypotheses from parameters, exceptions, calls,
  state/data flow, and output evidence while leaving every hypothesis
  explicitly unverified;
- proposes one focused manual observation per hypothesis and never runs that
  diagnostic automatically;
- refuses to claim a root cause from static evidence alone;
- limits each investigation to 12 allow-listed evidence records and validates
  every cited evidence ID;
- adds user-triggered JSON and readable Markdown investigation exports;
- does not add a Debug model endpoint and does not contact Ollama;
- preserves Map scan schema `1.3.0`, Teach lesson schema `1.1.0`, and all Phase 5
  behaviour.

Ollama's official API documentation identifies `http://localhost:11434/api` as
the default API base, `GET /api/tags` as the installed-model list, and `POST
/api/chat` as chat generation. Project Mentor disables streaming for the
reliable structured-output baseline:

- <https://docs.ollama.com/api/introduction>
- <https://docs.ollama.com/api/tags>
- <https://docs.ollama.com/api/chat>
- <https://docs.ollama.com/api/errors>

## Preserved deterministic behavior

The Phase 1.3 scanner still:

- uses Python's built-in `ast` parser and never imports scanned code;
- reports files, imports, symbols, calls, entry points, and learning order;
- records function parameters, explicit outputs, mutations, raises, try paths,
  cautious data flow, and cautious error propagation;
- separates observed facts from inferred relationships;
- uses deterministic ordering and produces no report timestamp;
- skips hidden/ignored directories, source-file symlinks, and Python files over
  1,000,000 bytes;
- refuses projects over 2,000 Python files;
- reports individual syntax/read errors without stopping the remaining scan;
- exports schema `1.3.0` JSON;
- keeps the FastAPI server bound to `127.0.0.1` in the supplied launch commands.

## Ollama preflight

Before optional local-model use or the live smoke test, confirm the local
Ollama installation in a normal PowerShell window:

```powershell
ollama --version
ollama list
Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags"
```

Interpret the results:

- If `ollama --version` is not recognized, install Ollama for Windows first.
- If the API command cannot connect, start Ollama and retry.
- If `ollama list` and the API `models` array are empty, install a model.
- If `gpt-oss:20b` appears in `ollama list`, Project Mentor prefers it by
  default unless an installed environment-configured model is selected.
- If it does not appear, Project Mentor does not assume or hard-code it. You may
  deliberately install it with `ollama pull gpt-oss:20b`, then rerun
  `ollama list` to confirm it actually completed.

The browser's Ollama panel repeats connection/no-model guidance. Map scanning
continues to work when Ollama is stopped.

## Windows 11 clean upgrade from version 0.6.1

Do not extract this release over an existing directory. Preserve the verified
v0.6.1 folder until the new release passes its tests and health check.

1. Stop Project Mentor with `Ctrl+C`.
2. Put `ProjectMentor-v0.7.0-source.zip` in Downloads.
3. Rename the stopped v0.6.1 directory, then extract into a new empty directory:

```powershell
cd C:\CodeProjects
Rename-Item .\ProjectMentor ProjectMentor-v0.6.1-verified
New-Item -ItemType Directory -Path .\ProjectMentor
Expand-Archive `
  -Path "$HOME\Downloads\ProjectMentor-v0.7.0-source.zip" `
  -DestinationPath "C:\CodeProjects\ProjectMentor"
```

4. Enter the new directory and run setup:

```powershell
cd C:\CodeProjects\ProjectMentor
.\setup_project.bat
```

5. Activate the new environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python --version
```

6. Run the complete offline test suite:

```powershell
python -m unittest discover -s tests -v
```

Expected result: `Ran 79 tests` followed by `OK (skipped=1)`. The skipped test
is the live Ollama smoke test. Normal tests do not require Ollama.

## Fresh installation

```powershell
cd C:\CodeProjects\ProjectMentor
py -3.14 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

`setup_project.bat` performs the environment creation and dependency steps if
preferred.

## Run and use Project Mentor

With `.venv` activated:

```powershell
python -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>.

1. Select or paste a Python project folder and choose **Scan project**. Map and
   deterministic Teach work when Ollama is unavailable.
2. In **Map**, choose a function in **Function evidence trace** and review the
   deterministic evidence.
3. Optionally choose an installed model and select **Explain selected evidence**.
4. After a valid response, use **Export interpretation (.md)**. Chromium-based
   browsers on localhost show a Save As picker for choosing the target folder;
   other browsers use their normal download behaviour.
5. Open **Teach**, choose a function or method, and select **Build deterministic
   lesson**.
6. Read the beginner walkthrough, short lesson sections, vocabulary, prediction
   exercise, quiz, and uncertainty labels.
7. Open **Expandable technical evidence** only when you want to inspect exact
   records, lines, categories, and evidence IDs.
8. Use **Export readable lesson (.md)** for a concise study file or **Export full
   evidence (.json)** for the complete deterministic lesson object.
9. Optionally select **Explain lesson evidence**. The model receives only the
   lesson's bounded evidence and cannot replace its exercise or quiz answers.
10. Use the Teach **Export interpretation (.md)** button to choose a destination
   for the validated local-model result.
11. Prefer deterministic evidence whenever it conflicts with model prose.

Double-clicking `start_project_mentor.bat` launches the same loopback-only
server. Press `Ctrl+C` to stop it.

## Optional configuration

Defaults need no `.env` file and no API key. Set overrides in the same
PowerShell window before launching Project Mentor:

```powershell
$env:PROJECT_MENTOR_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:PROJECT_MENTOR_OLLAMA_DEFAULT_MODEL = "an-installed-model-name"
$env:PROJECT_MENTOR_OLLAMA_CONNECT_TIMEOUT_SECONDS = "2"
$env:PROJECT_MENTOR_OLLAMA_GENERATION_TIMEOUT_SECONDS = "300"
$env:PROJECT_MENTOR_MAX_EVIDENCE_CHARS = "6000"
$env:PROJECT_MENTOR_OLLAMA_MAX_OUTPUT_TOKENS = "2048"
```

The default evidence budget is 6,000 characters because larger prompts caused
the confirmed local `gpt-oss:20b` setup to fail structured generation. The
output cap is intentionally conservative for short explanations; both values
can be overridden within validated bounds.

The configured default is selected only if `/api/tags` confirms it is
installed. Otherwise the UI warns and selects from actual installed models.

Remote Ollama origins are allowed only through the environment setting and are
visibly warned about. A remote endpoint receives bounded repository evidence,
so use only a server you trust. URLs with credentials, API paths, queries, or
fragments are rejected. Browser requests cannot choose an arbitrary proxy
destination.

## Optional live smoke test

First complete the three preflight commands. Then, in the activated environment:

```powershell
$env:PROJECT_MENTOR_RUN_LIVE_OLLAMA_TEST = "1"
python -m unittest tests.test_live_ollama -v
Remove-Item Env:PROJECT_MENTOR_RUN_LIVE_OLLAMA_TEST
```

This opt-in test lists real local models and performs one short generation. It
is intentionally skipped during normal tests.

## Security and grounding model

- Scanned repositories are read-only input. Project Mentor does not execute,
  import, install, or modify them.
- Source-file access is bounded by the original scan root, file limit, size
  limit, ignored directories, and symlink rules.
- Repository comments, docstrings, strings, filenames, and snippets are
  explicitly delimited as untrusted evidence.
- Ollama receives no tools. Model output cannot trigger a command, file change,
  install, or network action.
- Model output is untrusted display text and is inserted with browser
  `textContent`, never as raw model-generated HTML.
- Structured model output is validated. Only evidence IDs actually included in
  the bounded prompt resolve to server-generated path/line/symbol citations.
- Deterministic lessons are created before AI use. Teach interpretation rebuilds
  the trusted lesson server-side and accepts citations only from its evidence.
- Markdown and JSON exports require an explicit browser action. Ollama output
  cannot select a destination or write directly to the filesystem.
- Complete prompts, source text, and repositories are not logged by default.
- The in-memory scan ID expires and is not exported or persisted.
- Static scanner evidence wins whenever model output conflicts with it.

## Context limits and limitations

Project Mentor uses deterministic relevance selection, not embeddings or a
vector database. The Teach beginner view uses no more than 12 prioritised
records. Expandable groups retain exact bounded evidence separately. The
optional model receives only the small teaching allow-list, and items that do
not fit its character budget are omitted with a visible truncation notice.

Static analysis cannot prove full Python runtime behavior. Dynamic imports,
monkey patching, decorators, dependency injection, descriptors, runtime
dispatch, and external package behavior remain boundaries. Local-model output
adds another fallible layer and must be checked against cited evidence.

Teach does not yet store quiz attempts or learning progress. It does not prove
runtime types, path reachability, dynamic dispatch, or external-package
behaviour. Streaming, cloud models, embeddings, vector databases, browsing,
multi-agent execution, automatic commands, repository edits, persistent chat
memory, authentication, remote hosting, and plugin systems remain outside this
milestone.

The release suite was verified in the build environment on Python 3.12.13.
Thomas's required Python 3.14.6 verification is the local test command in the
upgrade steps above.

## Roll back to version 0.6.0

Stop the server and re-extract the preserved v0.6.0 source package over the
active source. This leaves `.venv` and local-only folders in place:

```powershell
cd C:\CodeProjects\ProjectMentor
Expand-Archive `
  -Path "$HOME\Downloads\ProjectMentor-v0.6.0-source.zip" `
  -DestinationPath "C:\CodeProjects\ProjectMentor" `
  -Force
```

The separate `ProjectMentor-failed-extract-backup` recovery folder is not used
or modified by either the upgrade or rollback procedure.
