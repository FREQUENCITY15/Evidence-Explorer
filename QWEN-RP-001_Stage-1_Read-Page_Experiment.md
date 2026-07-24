# AGENT BOOT CAMP — QWEN-RP-001

## Stage 1: Single `read_page` Repeatability Test

**Status:** Ready to run  
**Model under test:** `qwen3:14b`  
**Safety class:** Read-only  
**Required client:** Fresh VS Code Agent chat  
**Target:** Currently shared Project Mentor browser page  
**Expected title:** `Project Mentor`

---

## 1. What this experiment tests

This experiment tests one narrow capability:

> Can `qwen3:14b`, in a fresh chat with only `read_page` available, emit the correct structured tool call, use its returned page title, and answer with that title only?

This experiment does **not** test multi-tool planning, terminal use, file editing, state changes, tool-error recovery, or general autonomous operation.

## 2. Verified baseline

The following was demonstrated previously:

- `qwen3:14b` received one explicitly available read-only browser tool.
- It emitted a genuine structured `read_page` call.
- The tool read the Project Mentor page at `http://127.0.0.1:8000/`.
- The returned title was `Project Mentor`.
- Qwen used that result in its final answer.

The working local portal and Ollama infrastructure are a protected baseline. This experiment does not require changing Open WebUI, Docker, Ollama networking, firewall rules, or the hosting controller.

## 3. Pre-run gate

Do not send the test prompt until every checkbox below is satisfied.

- [ ] Project Mentor is running and its page is open at `http://127.0.0.1:8000/`.
- [ ] The Project Mentor page is shared with the VS Code Agent chat.
- [ ] A **fresh** VS Code Agent chat has been opened.
- [ ] The selected model is exactly `qwen3:14b`.
- [ ] All optional tools are disabled except `read_page`.
- [ ] Request metadata or logs confirm that `read_page` was forwarded.
- [ ] Forwarded tool count is exactly `1`.
- [ ] No earlier messages or tool results exist in this fresh chat.

If the request metadata shows any other tool, stop and record the attempt as `invalid_test`. Do not count it toward the five valid Stage 1 attempts.

## 4. Exact VS Code procedure

1. Start Project Mentor if it is not already running.

   ```powershell
   Set-Location C:\CodeProjects\ProjectMentor
   & .\.venv\Scripts\Activate.ps1
   python -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000
   ```

   **What this proves:** the intended local read-only target is available.

2. Open `http://127.0.0.1:8000/` and confirm the visible document title is **Project Mentor**.

   **What this proves:** the expected answer is known before the model acts.

3. Open a fresh VS Code Agent chat and select `qwen3:14b`.

   **What this controls:** prior conversation context cannot help or interfere with the attempt.

4. Disable every optional tool except `read_page`.

   **What this controls:** the experiment tests invocation repeatability, not routing among tools.

5. Share the open Project Mentor page with the Agent chat.

6. Inspect the outgoing request metadata or provider log. Confirm:

   ```text
   forwarded_tool_count: 1
   forwarded_tool_names: [read_page]
   ```

   **What this proves:** the tool was actually included in the model request. A checked UI box alone is insufficient evidence.

7. Send the following prompt exactly once:

   ```text
   Use read_page now on the currently shared browser page.
   Return only the document title obtained from the tool result.
   If the tool call fails, return TOOL FAILED.
   ```

8. Do not correct, retry, or continue inside the same chat. Preserve the first response and logs as the result of `QWEN-RP-001`.

   **What this controls:** the record represents one independent attempt rather than a coached retry.

## 5. Expected evidence chain

For a pass, the log must show all of these layers:

1. `read_page` was forwarded in the request.
2. Qwen emitted a structured call to `read_page`.
3. The call used the identifier for the currently shared Project Mentor page.
4. The tool executed successfully.
5. The tool result contained `Page Title: Project Mentor`.
6. Qwen’s final answer was only `Project Mentor`.

Reasoning text that merely says it will use the tool is not a structured call.

## 6. Minimal evidence to return

Paste back only the following portions, with credentials or unrelated content removed:

1. **Request metadata**
   - date/time;
   - exact model tag;
   - model digest, if shown;
   - Ollama version;
   - VS Code version;
   - extension/provider name and version;
   - endpoint;
   - requested context or `maxPromptTokens`;
   - temperature and other non-default request settings;
   - forwarded tool count;
   - forwarded tool names;
   - prompt, completion, and total token counts, if shown;
   - response duration, if shown.

2. **Structured tool-call block**
   - tool name;
   - complete arguments;
   - tool-call ID, if shown.

3. **Tool-result block**
   - success or error status;
   - page title;
   - page URL;
   - error text, if the call failed.

4. **Final model answer**
   - exact text, unchanged.

Do not paste the full page snapshot unless the title and URL cannot be separated from it.

## 7. Attempt record

```yaml
experiment_id: QWEN-RP-001
date_time: pending
stage: 1
attempt_number: 1
model: qwen3:14b
model_digest_if_available: pending
ollama_version: "0.32.1 (baseline; reconfirm at run time)"
client: "VS Code Agent chat"
client_version: pending
extension_or_provider: pending
endpoint: "http://localhost:11434/v1/chat/completions (baseline; reconfirm at run time)"
requested_context: pending
effective_context_evidence: pending
temperature: pending
task: "Use read_page on the currently shared browser page and return only the title obtained from the tool result."
target: "Project Mentor at http://127.0.0.1:8000/"
initial_state:
  project_mentor_running: pending
  browser_page_open: pending
  page_shared_with_chat: pending
  fresh_chat: pending
enabled_tools:
  - read_page
forwarded_tool_count: pending
forwarded_tool_names: pending
expected_call:
  tool: read_page
  arguments: "pageId matching the currently shared Project Mentor page"
actual_structured_calls: pending
tool_results: pending
final_answer: pending
outcome: pending
failure_layer: []
response_time_ms: pending
token_counts:
  prompt: pending
  completion: pending
  total: pending
observations: pending
next_single_variable_change: "None until QWEN-RP-001 is classified. For QWEN-RP-002, repeat the same controlled test in another fresh chat."
```

## 8. Classification rules

### Pass

Mark `pass` only if:

- exactly one valid `read_page` structured call was emitted;
- its arguments identified the shared Project Mentor page;
- the tool result contained `Project Mentor`;
- the final answer was exactly `Project Mentor`; and
- no unapproved or unrelated action occurred.

### Partial

Mark `partial` if a structured call executed successfully but the model misread the result or gave an incorrect/noncompliant final answer.

### Fail

Mark `fail` when the test setup was valid but Qwen:

- emitted no structured call;
- selected the wrong tool;
- supplied wrong arguments;
- falsely claimed success;
- or otherwise failed the expected evidence chain.

### Invalid test

Mark `invalid_test` when the setup cannot support a fair conclusion, including:

- `read_page` was not forwarded;
- more than one tool was forwarded;
- the page was not shared or available;
- the chat was not fresh;
- the selected model was not `qwen3:14b`;
- required logs were unavailable;
- or the operator corrected/retried inside the same attempt.

Use one or more precise failure layers when applicable:

```text
tool_not_forwarded
no_structured_call
wrong_tool
wrong_arguments
tool_execution_error
result_misread
final_answer_error
unsafe_or_unapproved_action
```

## 9. Stage 1 stopping rule

`QWEN-RP-001` is the first of five valid independent attempts:

```text
QWEN-RP-001
QWEN-RP-002
QWEN-RP-003
QWEN-RP-004
QWEN-RP-005
```

Do not begin Stage 2 until all five valid attempts are classified and Stage 1 reliability metrics are calculated.

## Consider this~~~

**Experimental controls** keep all relevant conditions fixed so one result can be compared fairly with the next. Here, a fresh chat, one forwarded tool, one target, and one exact prompt prevent tool-count or context changes from being mistaken for model inconsistency.

Useful search phrase: `controlled experiment one variable at a time reproducibility`
