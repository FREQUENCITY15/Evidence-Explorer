const form = document.querySelector("#scan-form");
const pathInput = document.querySelector("#project-path");
const browseButton = document.querySelector("#browse-button");
const scanButton = document.querySelector("#scan-button");
const statusBox = document.querySelector("#status");
const results = document.querySelector("#results");
const fileFilter = document.querySelector("#file-filter");
const exportButton = document.querySelector("#export-button");
const traceSelect = document.querySelector("#trace-symbol-select");
const ollamaBadge = document.querySelector("#ollama-connection-badge");
const ollamaEndpoint = document.querySelector("#ollama-endpoint");
const ollamaModelSelect = document.querySelector("#ollama-model-select");
const ollamaRefreshButton = document.querySelector("#ollama-refresh-button");
const ollamaGuidance = document.querySelector("#ollama-guidance");
const aiExplainButton = document.querySelector("#ai-explain-button");
const aiQuestion = document.querySelector("#ai-question");
const aiStatus = document.querySelector("#ai-status");
const aiExportButton = document.querySelector("#ai-export-button");
const mapTab = document.querySelector("#map-tab");
const teachTab = document.querySelector("#teach-tab");
const teachView = document.querySelector("#teach-view");
const teachSymbolSelect = document.querySelector("#teach-symbol-select");
const teachBuildButton = document.querySelector("#teach-build-button");
const teachStatus = document.querySelector("#teach-status");
const teachLessonPanel = document.querySelector("#teach-lesson");
const teachExportJsonButton = document.querySelector("#teach-export-json-button");
const teachExportMarkdownButton = document.querySelector("#teach-export-markdown-button");
const teachAIQuestion = document.querySelector("#teach-ai-question");
const teachAIExplainButton = document.querySelector("#teach-ai-explain-button");
const teachAIStatus = document.querySelector("#teach-ai-status");
const teachAIExportButton = document.querySelector("#teach-ai-export-button");
const debugTab = document.querySelector("#debug-tab");
const debugView = document.querySelector("#debug-view");
const debugSymbolSelect = document.querySelector("#debug-symbol-select");
const debugFailureInput = document.querySelector("#debug-failure-input");
const debugBuildButton = document.querySelector("#debug-build-button");
const debugStatus = document.querySelector("#debug-status");
const debugInvestigationPanel = document.querySelector("#debug-investigation");
const debugExportJsonButton = document.querySelector("#debug-export-json-button");
const debugExportMarkdownButton = document.querySelector("#debug-export-markdown-button");

let currentFiles = [];
let currentAnalysis = null;
let currentView = null;
let currentScanId = null;
let ollamaConnected = false;
let currentMapAIResponse = null;
let currentTeachLesson = null;
let currentTeachAIResponse = null;
let currentDebugInvestigation = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setStatus(message, kind = "") {
  statusBox.textContent = message;
  statusBox.className = `status ${kind}`.trim();
}

function setBusy(isBusy) {
  scanButton.disabled = isBusy;
  browseButton.disabled = isBusy;
  scanButton.textContent = isBusy ? "Scanning…" : "Scan project";
}

function setAIStatus(message, kind = "") {
  aiStatus.textContent = message;
  aiStatus.className = `status ${kind}`.trim();
}

function setTeachStatus(message, kind = "") {
  teachStatus.textContent = message;
  teachStatus.className = `status ${kind}`.trim();
}

function setTeachAIStatus(message, kind = "") {
  teachAIStatus.textContent = message;
  teachAIStatus.className = `status ${kind}`.trim();
}

function setDebugStatus(message, kind = "") {
  debugStatus.textContent = message;
  debugStatus.className = `status ${kind}`.trim();
}

function updateAIAvailability() {
  const ready = Boolean(
    ollamaConnected
    && ollamaModelSelect.value
    && currentScanId
    && traceSelect.value
  );
  aiExplainButton.disabled = !ready;
  document.querySelector("#ai-selected-symbol").textContent = traceSelect.value || "Select a function above";
  const teachReady = Boolean(
    ollamaConnected
    && ollamaModelSelect.value
    && currentScanId
    && currentTeachLesson
    && currentTeachLesson.symbol_id === teachSymbolSelect.value
  );
  teachAIExplainButton.disabled = !teachReady;
}

async function refreshOllamaStatus() {
  ollamaRefreshButton.disabled = true;
  ollamaBadge.textContent = "Checking…";
  ollamaBadge.className = "connection-badge checking";
  ollamaGuidance.textContent = "Checking the configured Ollama endpoint. Deterministic scanning remains available.";
  try {
    const response = await fetch("/api/ollama/status", { cache: "no-store" });
    const data = await response.json();
    ollamaEndpoint.textContent = data.endpoint || "Not available";
    ollamaModelSelect.replaceChildren();
    ollamaConnected = Boolean(data.connected);
    if (!data.connected) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Ollama unavailable";
      ollamaModelSelect.append(option);
      ollamaModelSelect.disabled = true;
      ollamaBadge.textContent = "Unavailable";
      ollamaBadge.className = "connection-badge unavailable";
      const message = data.error && data.error.message
        ? data.error.message
        : "Project Mentor could not connect to Ollama.";
      ollamaGuidance.textContent = `${message} Start Ollama, confirm a model is installed, then select Retry / refresh.`;
    } else if (!data.models.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No installed models";
      ollamaModelSelect.append(option);
      ollamaModelSelect.disabled = true;
      ollamaBadge.textContent = "Connected · no models";
      ollamaBadge.className = "connection-badge warning";
      ollamaGuidance.textContent = "Ollama is running, but no model is installed. Pull a model in PowerShell, then refresh.";
    } else {
      data.models.forEach((model) => {
        const option = document.createElement("option");
        option.value = model.name;
        const details = [model.parameter_size, model.quantization_level].filter(Boolean).join(" · ");
        option.textContent = details ? `${model.name} (${details})` : model.name;
        ollamaModelSelect.append(option);
      });
      if (data.selected_model) ollamaModelSelect.value = data.selected_model;
      ollamaModelSelect.disabled = false;
      ollamaBadge.textContent = "Connected";
      ollamaBadge.className = "connection-badge connected";
      const notices = [
        `${data.models.length} installed model${data.models.length === 1 ? "" : "s"} found.`,
        data.default_warning,
        data.endpoint_risk,
      ].filter(Boolean);
      ollamaGuidance.textContent = notices.join(" ");
    }
  } catch (error) {
    ollamaConnected = false;
    ollamaModelSelect.disabled = true;
    ollamaBadge.textContent = "Unavailable";
    ollamaBadge.className = "connection-badge unavailable";
    ollamaGuidance.textContent = `${error.message} Deterministic scanning is still available.`;
  } finally {
    ollamaRefreshButton.disabled = false;
    updateAIAvailability();
  }
}

function emptyMessage(message) {
  return `<p class="empty-message">${escapeHtml(message)}</p>`;
}

function renderSummary(summary) {
  const values = [
    ["python_files", "Python files"],
    ["lines", "lines"],
    ["symbols", "symbols"],
    ["calls", "calls"],
    ["resolved_calls", "resolved calls"],
    ["unresolved_calls", "unresolved calls"],
    ["data_flows", "data flows"],
    ["mutations", "mutations"],
    ["raise_sites", "raise sites"],
    ["calls_with_error_evidence", "error-risk calls"],
    ["imports", "imports"],
    ["parse_errors", "parse errors"],
  ];

  document.querySelector("#summary-cards").innerHTML = values
    .map(([key, label]) => `
      <div class="summary-card">
        <strong>${Number(summary[key] || 0).toLocaleString()}</strong>
        <span>${escapeHtml(label)}</span>
      </div>
    `)
    .join("");
}

function renderEntryPoints(items) {
  const container = document.querySelector("#entry-points");
  if (!items.length) {
    container.innerHTML = emptyMessage(
      "No confident entry point was found. This may be a reusable library rather than a runnable application."
    );
    return;
  }

  container.innerHTML = items
    .map((item, index) => `
      <article class="entry-card">
        <div class="entry-title">
          <code>${index === 0 ? "Best match: " : "Candidate: "}${escapeHtml(item.path)}</code>
          <span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(item.confidence)} confidence</span>
        </div>
        <ul>${item.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>
      </article>
    `)
    .join("");
}

function renderLearningOrder(items) {
  const container = document.querySelector("#learning-order");
  if (!items.length) {
    container.innerHTML = emptyMessage("No Python files were found to arrange.");
    return;
  }

  container.innerHTML = items
    .map((item) => `
      <li>
        <code>${escapeHtml(item.path)}</code>
        <span>${escapeHtml(item.reason)}</span>
      </li>
    `)
    .join("");
}

function formatImport(item) {
  const aliases = new Map((item.aliases || []).map((alias) => [alias.imported_name, alias.bound_name]));
  const formatName = (name) => {
    const bound = aliases.get(name);
    return bound && bound !== name ? `${name} as ${bound}` : name;
  };
  if (item.module || item.level) {
    const prefix = ".".repeat(item.level || 0);
    return `from ${prefix}${item.module} import ${item.names.map(formatName).join(", ")}`;
  }
  return `import ${item.names.map(formatName).join(", ")}`;
}

function factList(items, formatter, emptyText) {
  if (!items.length) {
    return emptyMessage(emptyText);
  }
  return `<ul class="fact-list">${items
    .map((item) => `<li>${escapeHtml(formatter(item))}</li>`)
    .join("")}</ul>`;
}

function renderImports(items) {
  if (!items.length) {
    return emptyMessage("No imports");
  }
  return `<ul class="fact-list import-list">${items
    .map((item) => `
      <li>
        <span class="import-kind ${escapeHtml(item.classification)}">${escapeHtml(item.classification.replace("_", " "))}</span>
        <code>${escapeHtml(formatImport(item))}</code>
      </li>
    `)
    .join("")}</ul>`;
}

function renderImportGraph(data) {
  const container = document.querySelector("#import-graph");
  const orderedPaths = data.learning_order.map((item) => item.path);
  const pathSet = new Set(orderedPaths);
  data.files.forEach((file) => {
    if (!pathSet.has(file.path)) orderedPaths.push(file.path);
  });

  const limitedPaths = orderedPaths.slice(0, 30);
  if (!limitedPaths.length) {
    container.innerHTML = emptyMessage("No Python files were found for the map.");
    return;
  }

  const columns = Math.min(4, Math.ceil(Math.sqrt(limitedPaths.length)));
  const nodeWidth = 180;
  const nodeHeight = 48;
  const horizontalGap = 90;
  const verticalGap = 72;
  const margin = 35;
  const rows = Math.ceil(limitedPaths.length / columns);
  const width = margin * 2 + columns * nodeWidth + Math.max(0, columns - 1) * horizontalGap;
  const height = margin * 2 + rows * nodeHeight + Math.max(0, rows - 1) * verticalGap;
  const positions = new Map();

  limitedPaths.forEach((path, index) => {
    positions.set(path, {
      x: margin + (index % columns) * (nodeWidth + horizontalGap),
      y: margin + Math.floor(index / columns) * (nodeHeight + verticalGap),
    });
  });

  const edgeMarkup = data.import_edges
    .filter((edge) => positions.has(edge.source_path) && positions.has(edge.target_path))
    .map((edge) => {
      const source = positions.get(edge.source_path);
      const target = positions.get(edge.target_path);
      const sourceX = source.x + nodeWidth / 2;
      const sourceY = source.y + nodeHeight / 2;
      const targetX = target.x + nodeWidth / 2;
      const targetY = target.y + nodeHeight / 2;
      const distance = Math.hypot(targetX - sourceX, targetY - sourceY) || 1;
      const inset = 38;
      const unitX = (targetX - sourceX) / distance;
      const unitY = (targetY - sourceY) / distance;
      return `<line class="graph-edge" x1="${sourceX + unitX * inset}" y1="${sourceY + unitY * inset}" x2="${targetX - unitX * inset}" y2="${targetY - unitY * inset}" marker-end="url(#arrowhead)"><title>${escapeHtml(edge.source_path)} imports ${escapeHtml(edge.target_path)}</title></line>`;
    })
    .join("");

  const nodeMarkup = limitedPaths
    .map((path) => {
      const position = positions.get(path);
      const shortLabel = path.length > 25 ? `…${path.slice(-24)}` : path;
      return `
        <g class="graph-node" transform="translate(${position.x} ${position.y})">
          <rect width="${nodeWidth}" height="${nodeHeight}" rx="9"></rect>
          <text x="${nodeWidth / 2}" y="${nodeHeight / 2 + 4}" text-anchor="middle">${escapeHtml(shortLabel)}</text>
          <title>${escapeHtml(path)}</title>
        </g>
      `;
    })
    .join("");

  const limitNote = data.files.length > limitedPaths.length
    ? `<p class="graph-note">Showing the first ${limitedPaths.length} of ${data.files.length} files.</p>`
    : "";
  container.innerHTML = `
    <div class="graph-scroll">
      <svg class="import-graph" viewBox="0 0 ${width} ${height}" role="img" aria-label="Local Python import graph">
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6"></polygon>
          </marker>
        </defs>
        ${edgeMarkup}
        ${nodeMarkup}
      </svg>
    </div>
    ${limitNote}
  `;
}

function relationshipList(items, direction) {
  if (!items.length) {
    const message = direction === "incoming"
      ? "No resolved internal callers were found."
      : direction === "unresolved"
        ? "No unresolved calls originate in this symbol."
        : "No resolved internal calls originate in this symbol.";
    return emptyMessage(message);
  }
  return `<ul class="trace-list">${items.map((item) => {
    const target = direction === "incoming"
      ? item.caller_symbol_id
      : direction === "unresolved"
        ? item.target_expression
        : item.resolved_target_symbol_id;
    return `
      <li>
        <div class="trace-link-title">
          <code>${escapeHtml(target || "unresolved")}</code>
          <span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(item.confidence)}</span>
        </div>
        <span>${escapeHtml(item.file_path)}:${Number(item.line)}</span>
        <small>${escapeHtml(item.reason)}</small>
      </li>
    `;
  }).join("")}</ul>`;
}

function parameterEvidenceList(items) {
  if (!items.length) return emptyMessage("No explicit parameters.");
  return `<ul class="evidence-list">${items.map((item) => {
    const annotation = item.annotation ? `: ${item.annotation}` : "";
    const defaultValue = item.default !== null ? ` = ${item.default}` : "";
    return `
      <li>
        <div class="evidence-title"><code>${escapeHtml(item.name)}${escapeHtml(annotation)}${escapeHtml(defaultValue)}</code><span class="evidence-kind">${escapeHtml(item.kind.replaceAll("_", " "))}</span></div>
        <small>Declared on line ${Number(item.line)}. Annotations are source text, not inferred runtime types.</small>
      </li>
    `;
  }).join("")}</ul>`;
}

function outputEvidenceList(items) {
  if (!items.length) return emptyMessage("No explicit return or yield site.");
  return `<ul class="evidence-list">${items.map((item) => `
    <li>
      <div class="evidence-title"><code>${escapeHtml(item.kind)} ${escapeHtml(item.expression ?? "")}</code><span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(item.confidence)}</span></div>
      <span>line ${Number(item.line)}</span>
      <small>${escapeHtml(item.reason)}</small>
    </li>
  `).join("")}</ul>`;
}

function dataFlowEvidenceList(items) {
  if (!items.length) return emptyMessage("No straightforward assignment relationship was recorded.");
  return `<ul class="evidence-list">${items.map((item) => `
    <li>
      <div class="evidence-title"><code>${escapeHtml(item.source_expression)} → ${escapeHtml(item.target_expression)}</code><span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(item.confidence)}</span></div>
      <span>${escapeHtml(item.relationship_kind.replaceAll("_", " "))} · line ${Number(item.line)}${item.source_names.length ? ` · names: ${escapeHtml(item.source_names.join(", "))}` : ""}</span>
      <small>${escapeHtml(item.reason)}</small>
    </li>
  `).join("")}</ul>`;
}

function mutationEvidenceList(items) {
  if (!items.length) return emptyMessage("No state-mutation syntax was detected.");
  return `<ul class="evidence-list">${items.map((item) => `
    <li>
      <div class="evidence-title"><code>${escapeHtml(item.target_expression)}</code><span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(item.confidence)}</span></div>
      <span>${escapeHtml(item.mutation_kind.replaceAll("_", " "))} · line ${Number(item.line)}${item.value_expression ? ` · ${escapeHtml(item.value_expression)}` : ""}</span>
      <small>${escapeHtml(item.reason)}</small>
    </li>
  `).join("")}</ul>`;
}

function errorEvidenceList(raiseSites, paths, calls) {
  if (!raiseSites.length && !paths.length && !calls.length) {
    return emptyMessage("No explicit raise, try path, or call error evidence was recorded.");
  }
  const raises = raiseSites.map((item) => `
    <li>
      <div class="evidence-title"><code>raise ${escapeHtml(item.exception_expression ?? "(active exception)")}</code><span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(item.confidence)}</span></div>
      <span>raise site · line ${Number(item.line)}${item.cause_expression ? ` · from ${escapeHtml(item.cause_expression)}` : ""}</span>
      <small>${escapeHtml(item.reason)}</small>
    </li>
  `);
  const pathItems = paths.map((item) => `
    <li>
      <div class="evidence-title"><code>${escapeHtml(item.path_kind.replaceAll("_", " "))}${item.exception_expression ? ` ${escapeHtml(item.exception_expression)}` : ""}</code><span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(item.confidence)}</span></div>
      <span>try line ${Number(item.try_line)} · path starts line ${Number(item.line)}${item.bound_name ? ` · binds ${escapeHtml(item.bound_name)}` : ""}</span>
      <small>${escapeHtml(item.reason)}</small>
    </li>
  `);
  const callItems = calls.map((item) => `
    <li>
      <div class="evidence-title"><code>${escapeHtml(item.target_expression)}()${item.resolved_target_symbol_id ? ` → ${escapeHtml(item.resolved_target_symbol_id)}` : ""}</code><span class="confidence uncertain">uncertain</span></div>
      <span>${escapeHtml(item.propagation.replaceAll("_", " "))} · ${escapeHtml(item.context.replaceAll("_", " "))} · line ${Number(item.line)}</span>
      <small>${escapeHtml(item.reason)}</small>
    </li>
  `);
  return `<ul class="evidence-list">${[...raises, ...pathItems, ...callItems].join("")}</ul>`;
}

function renderSelectedTrace() {
  const container = document.querySelector("#function-trace");
  if (!currentView || !traceSelect.value) {
    container.innerHTML = emptyMessage("No function or method is available to trace.");
    updateAIAvailability();
    return;
  }
  const symbol = currentView.symbols.find((item) => item.symbol_id === traceSelect.value);
  if (!symbol) {
    container.innerHTML = emptyMessage("The selected symbol is no longer available.");
    updateAIAvailability();
    return;
  }
  const outgoing = currentView.call_relationships.filter(
    (item) => item.caller_symbol_id === symbol.symbol_id && item.resolved_target_symbol_id
  );
  const incoming = currentView.call_relationships.filter(
    (item) => item.resolved_target_symbol_id === symbol.symbol_id
  );
  const unresolved = currentView.call_relationships.filter(
    (item) => item.caller_symbol_id === symbol.symbol_id && !item.resolved_target_symbol_id
  );
  const evidence = (currentView.function_evidence || []).find(
    (item) => item.symbol_id === symbol.symbol_id
  ) || { parameters: [], output_sites: [], mutations: [], raise_sites: [], exception_paths: [] };
  const dataFlows = (currentView.data_flows || []).filter(
    (item) => item.function_symbol_id === symbol.symbol_id
  );
  const errorCalls = (currentView.error_propagation || []).filter(
    (item) => item.caller_symbol_id === symbol.symbol_id
  );
  container.innerHTML = `
    <div class="trace-definition">
      <div>
        <span class="symbol-kind">${escapeHtml(symbol.kind.replace("_", " "))}</span>
        <code>${escapeHtml(symbol.symbol_id)}</code>
      </div>
      <p><strong>Defined:</strong> ${escapeHtml(symbol.file_path)}:${Number(symbol.line)}${symbol.end_line ? `–${Number(symbol.end_line)}` : ""}</p>
      <p><strong>Signature:</strong> <code>${escapeHtml(symbol.signature || "not statically available")}</code></p>
      ${symbol.docstring_first_line ? `<p><strong>Docstring:</strong> ${escapeHtml(symbol.docstring_first_line)}</p>` : ""}
    </div>
    <div class="trace-evidence-grid">
      <section>
        <h4>Inputs (parameters)</h4>
        ${parameterEvidenceList(evidence.parameters)}
      </section>
      <section>
        <h4>Outputs (return and yield sites)</h4>
        ${outputEvidenceList(evidence.output_sites)}
      </section>
      <section>
        <h4>Detected state mutations</h4>
        ${mutationEvidenceList(evidence.mutations)}
      </section>
      <section>
        <h4>Error paths and propagation</h4>
        ${errorEvidenceList(evidence.raise_sites, evidence.exception_paths, errorCalls)}
      </section>
    </div>
    <section class="data-flow-trace">
      <h4>Straightforward assignment and data flow</h4>
      ${dataFlowEvidenceList(dataFlows)}
    </section>
    <div class="trace-columns">
      <section>
        <h4>Resolved calls from this symbol</h4>
        ${relationshipList(outgoing, "outgoing")}
      </section>
      <section>
        <h4>Resolved callers of this symbol</h4>
        ${relationshipList(incoming, "incoming")}
      </section>
      <section>
        <h4>Unresolved calls from this symbol</h4>
        ${relationshipList(unresolved, "unresolved")}
      </section>
    </div>
  `;
  updateAIAvailability();
}

function renderFunctionTrace(data) {
  const traceableKinds = new Set(["function", "async_function", "method", "async_method"]);
  const symbols = data.symbols.filter((item) => traceableKinds.has(item.kind));
  traceSelect.innerHTML = symbols.length
    ? symbols.map((item) => `<option value="${escapeHtml(item.symbol_id)}">${escapeHtml(item.symbol_id)}</option>`).join("")
    : '<option value="">No functions or methods</option>';
  traceSelect.disabled = !symbols.length;
  renderSelectedTrace();
}

function switchView(viewName) {
  const showTeach = viewName === "teach" && !teachTab.disabled;
  const showDebug = viewName === "debug" && !debugTab.disabled;
  mapTab.classList.toggle("active", !showTeach && !showDebug);
  teachTab.classList.toggle("active", showTeach);
  debugTab.classList.toggle("active", showDebug);
  results.classList.toggle("hidden", showTeach || showDebug || !currentAnalysis);
  teachView.classList.toggle("hidden", !showTeach);
  debugView.classList.toggle("hidden", !showDebug);
}

function populateTeachSymbols(data) {
  const traceableKinds = new Set(["function", "async_function", "method", "async_method"]);
  const symbols = data.symbols.filter((item) => traceableKinds.has(item.kind));
  teachSymbolSelect.innerHTML = symbols.length
    ? symbols.map((item) => `<option value="${escapeHtml(item.symbol_id)}">${escapeHtml(item.symbol_id)}</option>`).join("")
    : '<option value="">No functions or methods</option>';
  teachSymbolSelect.disabled = !symbols.length;
  teachBuildButton.disabled = !symbols.length || !currentScanId;
  teachTab.disabled = !symbols.length;
}

function populateDebugSymbols(data) {
  const traceableKinds = new Set(["function", "async_function", "method", "async_method"]);
  const symbols = data.symbols.filter((item) => traceableKinds.has(item.kind));
  debugSymbolSelect.innerHTML = symbols.length
    ? symbols.map((item) => `<option value="${escapeHtml(item.symbol_id)}">${escapeHtml(item.symbol_id)}</option>`).join("")
    : '<option value="">No functions or methods</option>';
  debugSymbolSelect.disabled = !symbols.length;
  debugBuildButton.disabled = !symbols.length || !currentScanId;
  debugTab.disabled = !symbols.length;
}

function lessonReferenceList(references) {
  if (!references || !references.length) {
    return emptyMessage("No source reference is available.");
  }
  return `<ul class="citation-list compact-citations">${references.map((reference) => {
    const location = reference.file_path
      ? `${reference.file_path}${reference.line_start ? `:${reference.line_start}${reference.line_end && reference.line_end !== reference.line_start ? `–${reference.line_end}` : ""}` : ""}`
      : "project-level evidence";
    return `<li><code>${escapeHtml(reference.evidence_id)}</code><span>${escapeHtml(reference.category.replaceAll("_", " "))} · ${escapeHtml(reference.kind.replaceAll("_", " "))} · ${escapeHtml(location)}</span></li>`;
  }).join("")}</ul>`;
}

function certaintyLabel(value) {
  const labels = {
    observed_source: "Observed source",
    project_mentor_inference: "PM inference",
    static_limit: "Static limit",
    mixed_static_evidence: "Observed + inferred",
    observed_source_with_runtime_uncertainty: "Observed · runtime unknown",
    observed_call_with_resolution_uncertainty: "Call observed · target uncertain",
  };
  return labels[value] || String(value).replaceAll("_", " ");
}

function certaintyClass(value) {
  if (value === "observed_source") return "high";
  if (value.includes("uncertainty") || value === "static_limit") return "uncertain";
  return "medium";
}

function lessonReferenceDisclosure(references) {
  if (!references || !references.length) return "";
  return `
    <details class="reference-disclosure">
      <summary>Show source references</summary>
      ${lessonReferenceList(references)}
    </details>
  `;
}

function renderTeachLesson(lesson) {
  currentTeachLesson = lesson;
  currentTeachAIResponse = null;
  document.querySelector("#teach-lesson-title").textContent = lesson.title;
  document.querySelector("#teach-objective").textContent = lesson.learning_objective;
  document.querySelector("#teach-location").textContent =
    `${lesson.symbol_id} · ${lesson.file_path}:${lesson.line_start}${lesson.line_end ? `–${lesson.line_end}` : ""} · lesson ${lesson.lesson_id}`;
  document.querySelector("#teach-ai-selected-symbol").textContent = lesson.symbol_id;

  const prerequisiteContainer = document.querySelector("#teach-prerequisites");
  prerequisiteContainer.innerHTML = lesson.prerequisites.length
    ? lesson.prerequisites.map((item) => `
        <article class="teach-card">
          <div class="evidence-title"><code>${escapeHtml(item.title)}</code><span class="confidence medium">${escapeHtml(item.relationship.replaceAll("_", " "))}</span></div>
          <p>${escapeHtml(item.reason)}</p>
          <p class="helper-text">${item.learning_position === null ? "No learning-order position recorded" : `Learning-order position ${Number(item.learning_position)}`}</p>
          ${lessonReferenceDisclosure(item.references)}
        </article>
      `).join("")
    : emptyMessage("No direct supporting project function was established as a prerequisite.");

  document.querySelector("#teach-stages").innerHTML = lesson.stages.map((stage) => `
    <li class="teach-stage">
      <div class="stage-number" aria-hidden="true">${Number(stage.number)}</div>
      <div class="stage-content">
        <div class="evidence-title"><h4>${escapeHtml(stage.title)}</h4><span class="confidence ${certaintyClass(stage.certainty)}">${escapeHtml(certaintyLabel(stage.certainty))}</span></div>
        <p>${escapeHtml(stage.explanation)}</p>
        ${lessonReferenceDisclosure(stage.references)}
      </div>
    </li>
  `).join("");

  document.querySelector("#teach-sections").innerHTML = lesson.sections.map((section) => `
    <article class="teach-card">
      <div class="evidence-title"><h4>${escapeHtml(section.heading)}</h4><span class="confidence ${certaintyClass(section.certainty)}">${escapeHtml(certaintyLabel(section.certainty))}</span></div>
      <p>${escapeHtml(section.body)}</p>
      ${lessonReferenceDisclosure(section.references)}
    </article>
  `).join("");

  document.querySelector("#teach-vocabulary").innerHTML = `<dl class="vocabulary-list">${lesson.vocabulary.map((item) => `
    <div><dt>${escapeHtml(item.term)}</dt><dd>${escapeHtml(item.definition)}</dd></div>
  `).join("")}</dl>`;

  const exercise = lesson.prediction_exercise;
  document.querySelector("#teach-exercise").innerHTML = `
    <p>${escapeHtml(exercise.prompt)}</p>
    <span class="confidence ${certaintyClass(exercise.certainty)}">${escapeHtml(certaintyLabel(exercise.certainty))}</span>
    <details class="answer-reveal">
      <summary>Reveal deterministic answer</summary>
      <p><strong>Answer:</strong> ${escapeHtml(exercise.expected_answer)}</p>
      <p>${escapeHtml(exercise.answer_explanation)}</p>
      ${lessonReferenceDisclosure(exercise.references)}
    </details>
  `;

  document.querySelector("#teach-quiz").innerHTML = lesson.quiz.map((question) => `
    <article class="teach-card quiz-question">
      <h4>${escapeHtml(question.question_id)}. ${escapeHtml(question.prompt)}</h4>
      <ul class="quiz-options">${question.options.map((option) => `<li><strong>${escapeHtml(option.option_id)}.</strong> ${escapeHtml(option.text)}</li>`).join("")}</ul>
      <details class="answer-reveal">
        <summary>Reveal answer and explanation</summary>
        <p><strong>Correct answer:</strong> ${escapeHtml(question.correct_option_id)}</p>
        <p>${escapeHtml(question.answer_explanation)}</p>
        ${lessonReferenceDisclosure(question.references)}
      </details>
    </article>
  `).join("");

  document.querySelector("#teach-uncertainty").innerHTML = lesson.uncertainty_labels
    .map((label) => `<li><span>${escapeHtml(label)}</span></li>`)
    .join("");

  document.querySelector("#teach-evidence-summary").textContent =
    `${lesson.teaching_evidence_count} key record(s) shape the beginner lesson. `
    + `${lesson.evidence_included_count} exact bounded record(s) remain below; `
    + `${lesson.evidence_omitted_count} were omitted by fixed technical limits.`;
  document.querySelector("#teach-evidence-details").innerHTML = lesson.evidence_groups.map((group) => `
    <details class="evidence-group">
      <summary><span>${escapeHtml(group.heading)}</span><span>${group.details.length.toLocaleString()} record(s)</span></summary>
      <p class="helper-text">${escapeHtml(group.summary)}</p>
      <div class="evidence-detail-list">
        ${group.details.map((detail) => {
          const reference = detail.reference;
          const location = reference.file_path
            ? `${reference.file_path}${reference.line_start ? `:${reference.line_start}${reference.line_end && reference.line_end !== reference.line_start ? `–${reference.line_end}` : ""}` : ""}`
            : "project-level evidence";
          return `
            <article class="evidence-detail">
              <div class="evidence-title"><code>${escapeHtml(reference.evidence_id)}</code><span class="evidence-kind">${escapeHtml(reference.kind.replaceAll("_", " "))}</span></div>
              <p class="helper-text">${escapeHtml(reference.category.replaceAll("_", " "))} · ${escapeHtml(location)}</p>
              <pre>${escapeHtml(detail.content)}</pre>
            </article>
          `;
        }).join("")}
      </div>
    </details>
  `).join("");
  teachLessonPanel.classList.remove("hidden");
  teachExportJsonButton.disabled = false;
  teachExportMarkdownButton.disabled = false;
  teachAIExportButton.disabled = true;
  document.querySelector("#teach-ai-answer-panel").classList.add("hidden");
  updateAIAvailability();
}

function renderDebugInvestigation(investigation) {
  currentDebugInvestigation = investigation;
  document.querySelector("#debug-investigation-title").textContent =
    `Investigation ${investigation.investigation_id}`;
  document.querySelector("#debug-location").textContent =
    `${investigation.symbol_id} · ${investigation.file_path}:${investigation.line_start}${investigation.line_end ? `–${investigation.line_end}` : ""} · schema ${investigation.debug_schema_version}`;
  document.querySelector("#debug-failure-statement").textContent = investigation.failure_statement;
  document.querySelector("#debug-boundary-notice").textContent = investigation.boundary_notice;

  document.querySelector("#debug-hypotheses").innerHTML = investigation.hypotheses.map((item) => `
    <article class="teach-card debug-hypothesis">
      <div class="evidence-title">
        <h4>${Number(item.rank)}. ${escapeHtml(item.title)}</h4>
        <span class="confidence uncertain">${escapeHtml(item.status)} · ${escapeHtml(item.confidence)}</span>
      </div>
      <p>${escapeHtml(item.rationale)}</p>
      ${lessonReferenceDisclosure(item.references)}
    </article>
  `).join("");

  document.querySelector("#debug-diagnostics").innerHTML = investigation.diagnostic_steps.map((step, index) => `
    <li class="teach-stage">
      <div class="stage-number" aria-hidden="true">${Number(index + 1)}</div>
      <div class="stage-content">
        <div class="evidence-title"><h4>${escapeHtml(step.title)}</h4><span class="confidence medium">manual observation</span></div>
        <p>${escapeHtml(step.instruction)}</p>
        <dl class="diagnostic-outcomes">
          <div><dt>Supports it when</dt><dd>${escapeHtml(step.supported_when)}</dd></div>
          <div><dt>Weakens it when</dt><dd>${escapeHtml(step.weakened_when)}</dd></div>
        </dl>
        ${lessonReferenceDisclosure(step.references)}
      </div>
    </li>
  `).join("");

  document.querySelector("#debug-evidence-summary").textContent =
    `${investigation.evidence_included_count} bounded record(s) are included; `
    + `${investigation.evidence_omitted_count} candidate record(s) were omitted by fixed limits. `
    + "No root cause is declared without a runtime observation.";
  document.querySelector("#debug-evidence-details").innerHTML = investigation.evidence_groups.map((group) => `
    <details class="evidence-group">
      <summary><span>${escapeHtml(group.heading)}</span><span>${group.details.length.toLocaleString()} record(s)</span></summary>
      <p class="helper-text">${escapeHtml(group.summary)}</p>
      <div class="evidence-detail-list">
        ${group.details.map((detail) => {
          const reference = detail.reference;
          const location = reference.file_path
            ? `${reference.file_path}${reference.line_start ? `:${reference.line_start}${reference.line_end && reference.line_end !== reference.line_start ? `–${reference.line_end}` : ""}` : ""}`
            : "project-level evidence";
          return `
            <article class="evidence-detail">
              <div class="evidence-title"><code>${escapeHtml(reference.evidence_id)}</code><span class="evidence-kind">${escapeHtml(reference.kind.replaceAll("_", " "))}</span></div>
              <p class="helper-text">${escapeHtml(reference.category.replaceAll("_", " "))} · ${escapeHtml(location)}</p>
              <pre>${escapeHtml(detail.content)}</pre>
            </article>
          `;
        }).join("")}
      </div>
    </details>
  `).join("");
  debugInvestigationPanel.classList.remove("hidden");
  debugExportJsonButton.disabled = false;
  debugExportMarkdownButton.disabled = false;
}

function renderProjectWarnings(data) {
  const external = document.querySelector("#external-dependencies");
  external.innerHTML = data.external_dependencies.length
    ? `<div class="tag-list">${data.external_dependencies.map((item) => `<code>${escapeHtml(item)}</code>`).join("")}</div>
       <p class="helper-text">These packages are not part of Python itself or this repository.</p>`
    : emptyMessage("No external Python packages were detected.");

  const unused = document.querySelector("#unused-files");
  unused.innerHTML = data.unused_files.length
    ? `<ul class="warning-list">${data.unused_files.map((item) => `
        <li><code>${escapeHtml(item.path)}</code><span>${escapeHtml(item.reason)}</span></li>
      `).join("")}</ul>`
    : emptyMessage("Every non-test file is imported or looks like an entry point.");

  const warnings = document.querySelector("#analysis-warnings");
  warnings.innerHTML = data.warnings
    .map((warning) => `<li><span>${escapeHtml(warning)}</span></li>`)
    .join("");
}

function renderFileCalls(file) {
  if (!file.calls.length) {
    return emptyMessage("No function calls");
  }
  return `<ul class="fact-list call-evidence-list">${file.calls.map((call) => {
    const relationship = currentView.call_relationships.find(
      (item) => item.file_path === file.path
        && item.line === call.line
        && item.column === call.column
        && item.target_expression === call.target
    );
    const target = relationship && relationship.resolved_target_symbol_id
      ? ` → ${relationship.resolved_target_symbol_id}`
      : " → unresolved";
    const confidence = relationship ? relationship.confidence : "unresolved";
    const reason = relationship ? relationship.reason : "No semantic relationship was recorded.";
    return `
      <li>
        <div><code>${escapeHtml(call.caller)} → ${escapeHtml(call.target)}()</code> <span class="confidence ${escapeHtml(confidence)}">${escapeHtml(confidence)}</span></div>
        <span>${escapeHtml(target)} · line ${Number(call.line)}</span>
        <small>${escapeHtml(reason)}</small>
      </li>
    `;
  }).join("")}</ul>`;
}

function fileCard(file) {
  const counts = `${file.imports.length} imports · ${file.calls.length} calls · ${file.functions.length} functions · ${file.classes.length} classes`;
  let detail;

  if (file.parse_error) {
    detail = `<div class="file-detail"><p class="error-message">${escapeHtml(file.parse_error)}</p></div>`;
  } else {
    detail = `
      <div class="file-detail">
        <div>
          <h4>Imports</h4>
          ${renderImports(file.imports)}
        </div>
        <div>
          <h4>Functions and methods</h4>
          ${factList(
            file.functions,
            (item) => `${item.is_async ? "async " : ""}${item.name}() — line ${item.line}`,
            "No functions"
          )}
        </div>
        <div>
          <h4>Classes</h4>
          ${factList(
            file.classes,
            (item) => `${item.name}${item.bases.length ? `(${item.bases.join(", ")})` : ""} — line ${item.line}`,
            "No classes"
          )}
        </div>
        <div>
          <h4>Call relationships</h4>
          ${renderFileCalls(file)}
        </div>
      </div>
    `;
  }

  return `
    <details class="file-card">
      <summary>
        <span class="file-title">
          <code>${escapeHtml(file.path)}</code>
          <small>Module: ${escapeHtml(file.module || "package root")} · ${file.line_count} lines${file.has_main_guard ? " · main guard" : ""}${file.possibly_unused ? " · possibly unused" : ""}</small>
        </span>
        <span class="file-counts">${escapeHtml(counts)}</span>
      </summary>
      ${detail}
    </details>
  `;
}

function renderFiles(files) {
  const query = fileFilter.value.trim().toLowerCase();
  const matching = files.filter((file) => file.path.toLowerCase().includes(query));
  document.querySelector("#file-list").innerHTML = matching.length
    ? matching.map(fileCard).join("")
    : emptyMessage("No files match that filter.");
}

function renderAnalysis(data) {
  currentAnalysis = data;
  const observed = data.observed_facts || { files: data.files || [], symbols: data.symbols || [] };
  const inferred = data.inferred_relationships || data;
  currentView = {
    ...data,
    ...observed,
    ...inferred,
    warnings: data.warnings || [],
  };
  document.querySelector("#result-root").textContent = data.project ? data.project.root : data.root;
  document.querySelector("#summary-description").textContent = data.summary.description;
  renderSummary(data.summary);
  renderImportGraph(currentView);
  renderFunctionTrace(currentView);
  populateTeachSymbols(currentView);
  populateDebugSymbols(currentView);
  renderEntryPoints(currentView.entry_points);
  renderLearningOrder(currentView.learning_order);
  renderProjectWarnings(currentView);
  currentFiles = currentView.files;
  fileFilter.value = "";
  renderFiles(currentFiles);
  results.classList.remove("hidden");
  switchView("map");
  updateAIAvailability();
}

browseButton.addEventListener("click", async () => {
  setStatus("Opening the Windows folder picker…");
  try {
    const response = await fetch("/api/pick-folder");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Folder picker failed.");
    }
    if (data.path) {
      pathInput.value = data.path;
      setStatus("Folder selected.", "success");
    } else {
      setStatus("No folder selected.");
    }
  } catch (error) {
    setStatus(`${error.message} You can type or paste the path instead.`, "error");
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const path = pathInput.value.trim();
  if (!path) {
    setStatus("Enter or select a project folder first.", "error");
    return;
  }

  setBusy(true);
  currentScanId = null;
  currentMapAIResponse = null;
  currentTeachLesson = null;
  currentTeachAIResponse = null;
  currentDebugInvestigation = null;
  teachTab.disabled = true;
  debugTab.disabled = true;
  teachLessonPanel.classList.add("hidden");
  teachView.classList.add("hidden");
  debugInvestigationPanel.classList.add("hidden");
  debugView.classList.add("hidden");
  aiExportButton.disabled = true;
  teachAIExportButton.disabled = true;
  debugExportJsonButton.disabled = true;
  debugExportMarkdownButton.disabled = true;
  setStatus("Reading Python files and building the project map…");
  try {
    const response = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    currentScanId = response.headers.get("X-Project-Mentor-Scan-ID");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "The project could not be scanned.");
    }
    renderAnalysis(data);
    setStatus("Scan complete. The selected project was not modified.", "success");
  } catch (error) {
    currentScanId = null;
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
});

fileFilter.addEventListener("input", () => renderFiles(currentFiles));
traceSelect.addEventListener("change", () => {
  renderSelectedTrace();
  currentMapAIResponse = null;
  aiExportButton.disabled = true;
  document.querySelector("#ai-answer-panel").classList.add("hidden");
});
ollamaModelSelect.addEventListener("change", updateAIAvailability);
ollamaRefreshButton.addEventListener("click", refreshOllamaStatus);
mapTab.addEventListener("click", () => switchView("map"));
teachTab.addEventListener("click", () => switchView("teach"));
debugTab.addEventListener("click", () => switchView("debug"));
teachSymbolSelect.addEventListener("change", () => {
  currentTeachLesson = null;
  currentTeachAIResponse = null;
  teachLessonPanel.classList.add("hidden");
  teachExportJsonButton.disabled = true;
  teachExportMarkdownButton.disabled = true;
  teachAIExportButton.disabled = true;
  teachBuildButton.disabled = !currentScanId || !teachSymbolSelect.value;
  setTeachStatus("Build a new lesson for the selected symbol.");
  updateAIAvailability();
});
debugSymbolSelect.addEventListener("change", () => {
  currentDebugInvestigation = null;
  debugInvestigationPanel.classList.add("hidden");
  debugExportJsonButton.disabled = true;
  debugExportMarkdownButton.disabled = true;
  debugBuildButton.disabled = !currentScanId || !debugSymbolSelect.value;
  setDebugStatus("Describe the observed failure for the selected symbol.");
});

function appendCitation(container, citation) {
  const item = document.createElement("li");
  const id = document.createElement("code");
  id.textContent = citation.evidence_id;
  const detail = document.createElement("span");
  const category = citation.category === "observed_fact"
    ? "observed fact"
    : "Project Mentor inference";
  const parts = [category, citation.kind, citation.location, citation.symbol_id].filter(Boolean);
  detail.textContent = parts.join(" · ");
  item.append(id, detail);
  container.append(item);
}

function safeArtifactName(value) {
  const cleaned = String(value || "project-mentor")
    .replaceAll(/[^A-Za-z0-9._-]+/g, "-")
    .replaceAll(/^-+|-+$/g, "")
    .slice(0, 100);
  return cleaned || "project-mentor";
}

function literalMarkdownBlock(value) {
  return String(value)
    .split(/\r?\n/)
    .map((line) => `    ${line}`)
    .join("\n");
}

async function saveTextArtifact(suggestedName, content, mimeType, extension, description) {
  if (typeof window.showSaveFilePicker === "function") {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName,
        types: [{ description, accept: { [mimeType]: [extension] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(content);
      await writable.close();
      return "saved";
    } catch (error) {
      if (error.name === "AbortError") return "cancelled";
      // Fall through to a normal browser download when the picker is unavailable.
    }
  }
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = suggestedName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return "downloaded";
}

function localModelMarkdown(workflow, symbolId, question, data) {
  const interpretation = data.local_model_interpretation;
  const answerAsLiteralText = literalMarkdownBlock(interpretation.answer);
  const citations = interpretation.citations.length
    ? interpretation.citations.map((citation) => {
        const parts = [citation.evidence_id, citation.category, citation.kind, citation.location, citation.symbol_id].filter(Boolean);
        return parts.join(" · ");
      }).join("\n")
    : "No supported citation was returned.";
  const warnings = [
    interpretation.grounding_warning,
    interpretation.rejected_citation_ids.length
      ? `Rejected citation IDs: ${interpretation.rejected_citation_ids.join(", ")}`
      : null,
  ].filter(Boolean).join(" ") || "None";
  return `# Project Mentor ${workflow} interpretation

## Request metadata

${literalMarkdownBlock(`Symbol: ${symbolId}\nModel requested: ${data.model.requested}\nModel reported: ${data.model.returned}\nEvidence insufficient: ${interpretation.evidence_insufficient ? "yes" : "no"}`)}

## Question

${literalMarkdownBlock(question)}

## Local-model interpretation

${answerAsLiteralText}

## Validated evidence citations

${literalMarkdownBlock(citations)}

## Grounding warning

${literalMarkdownBlock(warnings)}

The deterministic Project Mentor evidence remains the source of truth.
`;
}

function escapeMarkdownText(value) {
  return String(value)
    .replaceAll("\\", "\\\\")
    .replaceAll(/([`*_[\]<>#])/g, "\\$1")
    .replaceAll(/^([>+-]) /gm, "\\$1 ");
}

function deterministicLessonMarkdown(lesson) {
  const prerequisites = lesson.prerequisites.length
    ? lesson.prerequisites.map((item) =>
        `- ${escapeMarkdownText(item.title)} — ${escapeMarkdownText(item.reason)}`
      ).join("\n")
    : "No direct supporting project function was established as a prerequisite.";
  const stages = lesson.stages.map((stage) =>
    `${stage.number}. **${escapeMarkdownText(stage.title)}** — ${escapeMarkdownText(stage.explanation)}`
  ).join("\n");
  const sections = lesson.sections.map((section) =>
    `### ${escapeMarkdownText(section.heading)}\n\n${escapeMarkdownText(section.body)}`
  ).join("\n\n");
  const vocabulary = lesson.vocabulary.map((item) =>
    `- **${escapeMarkdownText(item.term)}:** ${escapeMarkdownText(item.definition)}`
  ).join("\n");
  const quiz = lesson.quiz.map((question) => {
    const options = question.options.map((option) =>
      `- ${escapeMarkdownText(option.option_id)}. ${escapeMarkdownText(option.text)}`
    ).join("\n");
    return `### ${escapeMarkdownText(question.question_id)}. ${escapeMarkdownText(question.prompt)}\n\n${options}\n\n**Answer:** ${escapeMarkdownText(question.correct_option_id)}\n\n${escapeMarkdownText(question.answer_explanation)}`;
  }).join("\n\n");
  const uncertainty = lesson.uncertainty_labels.map((label) =>
    `- ${escapeMarkdownText(label)}`
  ).join("\n");

  return `# ${escapeMarkdownText(lesson.title)}

${escapeMarkdownText(lesson.learning_objective)}

Source: ${escapeMarkdownText(lesson.file_path)}:${lesson.line_start}${lesson.line_end ? `–${lesson.line_end}` : ""}

## Helpful prerequisites

${prerequisites}

## Beginner walkthrough

${stages}

## Beginner lesson

${sections}

## Vocabulary

${vocabulary}

## Prediction exercise

${escapeMarkdownText(lesson.prediction_exercise.prompt)}

**Answer:** ${escapeMarkdownText(lesson.prediction_exercise.expected_answer)}

${escapeMarkdownText(lesson.prediction_exercise.answer_explanation)}

## Quiz and answer key

${quiz}

## Static-analysis boundaries

${uncertainty}

## Evidence summary

${lesson.teaching_evidence_count} key record(s) shaped this lesson. ${lesson.evidence_included_count} exact bounded record(s) remain in the deterministic JSON export; ${lesson.evidence_omitted_count} additional record(s) were omitted by fixed technical limits.

This Markdown file is a readable view derived from deterministic lesson schema ${escapeMarkdownText(lesson.lesson_schema_version)}. The JSON export remains the complete source of truth for exact evidence records and IDs.
`;
}

function deterministicDebugMarkdown(investigation) {
  const hypotheses = investigation.hypotheses.map((item) =>
    `${item.rank}. **${escapeMarkdownText(item.title)}** — ${escapeMarkdownText(item.rationale)} (${escapeMarkdownText(item.status)}, ${escapeMarkdownText(item.confidence)})`
  ).join("\n");
  const diagnostics = investigation.diagnostic_steps.map((step, index) =>
    `${index + 1}. **${escapeMarkdownText(step.title)}**\n   - Observe: ${escapeMarkdownText(step.instruction)}\n   - Supports it when: ${escapeMarkdownText(step.supported_when)}\n   - Weakens it when: ${escapeMarkdownText(step.weakened_when)}`
  ).join("\n");

  return `# Deterministic Debug investigation

Investigation: ${escapeMarkdownText(investigation.investigation_id)}

Source: ${escapeMarkdownText(investigation.file_path)}:${investigation.line_start}${investigation.line_end ? `–${investigation.line_end}` : ""}

## Reported failure

${escapeMarkdownText(investigation.failure_statement)}

## Ranked hypotheses

${hypotheses}

## Cheapest useful observations

${diagnostics}

## Current conclusion

${escapeMarkdownText(investigation.conclusion_status.replaceAll("_", " "))}. ${escapeMarkdownText(investigation.boundary_notice)}

## Evidence summary

${investigation.evidence_included_count} bounded record(s) are included in the deterministic JSON export; ${investigation.evidence_omitted_count} candidate record(s) were omitted by fixed limits.

This readable view is derived from Debug schema ${escapeMarkdownText(investigation.debug_schema_version)}. The JSON export remains the source of truth for exact evidence records and IDs.
`;
}

function renderAIResponse(data) {
  currentMapAIResponse = data;
  const interpretation = data.local_model_interpretation;
  const deterministic = data.deterministic_evidence;
  document.querySelector("#ai-observed-summary").textContent =
    `${deterministic.observed_facts.length} observed evidence item(s) were included in the bounded context.`;
  document.querySelector("#ai-inference-summary").textContent =
    `${deterministic.project_mentor_inferences.length} conservative inference item(s) were included; these are not runtime proof.`;
  document.querySelector("#ai-model-label").textContent =
    `Model requested: ${data.model.requested}. Model reported: ${data.model.returned}.`;
  // Model output is untrusted display text. textContent prevents it from becoming HTML.
  document.querySelector("#ai-answer-text").textContent = interpretation.answer;
  const warning = document.querySelector("#ai-grounding-warning");
  const warningParts = [
    interpretation.grounding_warning,
    interpretation.rejected_citation_ids.length
      ? `Unsupported IDs: ${interpretation.rejected_citation_ids.join(", ")}`
      : null,
  ].filter(Boolean);
  warning.textContent = warningParts.join(" ");
  warning.classList.toggle("hidden", !warningParts.length);
  const citations = document.querySelector("#ai-citations");
  citations.replaceChildren();
  interpretation.citations.forEach((citation) => appendCitation(citations, citation));
  if (!interpretation.citations.length) {
    const item = document.createElement("li");
    item.textContent = "No supported citation was returned. Treat the answer as insufficient.";
    citations.append(item);
  }
  const context = data.context;
  const contextParts = [
    `${context.included_evidence_count} evidence item(s), approximately ${context.approximate_chars.toLocaleString()} prompt characters.`,
    context.truncation_notice,
  ].filter(Boolean);
  document.querySelector("#ai-context-notice").textContent = contextParts.join(" ");
  document.querySelector("#ai-answer-panel").classList.remove("hidden");
  aiExportButton.disabled = false;
}

function renderTeachAIResponse(data) {
  currentTeachAIResponse = data;
  const interpretation = data.local_model_interpretation;
  document.querySelector("#teach-ai-model-label").textContent =
    `Model requested: ${data.model.requested}. Model reported: ${data.model.returned}.`;
  // Model output is untrusted display text. It must never be inserted as HTML.
  document.querySelector("#teach-ai-answer-text").textContent = interpretation.answer;
  const warning = document.querySelector("#teach-ai-grounding-warning");
  const warningParts = [
    interpretation.grounding_warning,
    interpretation.rejected_citation_ids.length
      ? `Unsupported IDs: ${interpretation.rejected_citation_ids.join(", ")}`
      : null,
  ].filter(Boolean);
  warning.textContent = warningParts.join(" ");
  warning.classList.toggle("hidden", !warningParts.length);
  const citations = document.querySelector("#teach-ai-citations");
  citations.replaceChildren();
  interpretation.citations.forEach((citation) => appendCitation(citations, citation));
  if (!interpretation.citations.length) {
    const item = document.createElement("li");
    item.textContent = "No supported lesson-evidence citation was returned. Treat the interpretation as insufficient.";
    citations.append(item);
  }
  const context = data.context;
  const contextParts = [
    `${context.included_evidence_count} lesson evidence item(s), approximately ${context.approximate_chars.toLocaleString()} prompt characters.`,
    context.truncation_notice,
  ].filter(Boolean);
  document.querySelector("#teach-ai-context-notice").textContent = contextParts.join(" ");
  document.querySelector("#teach-ai-answer-panel").classList.remove("hidden");
  teachAIExportButton.disabled = false;
}

aiExplainButton.addEventListener("click", async () => {
  const question = aiQuestion.value.trim();
  if (!question) {
    setAIStatus("Enter a question first.", "error");
    return;
  }
  aiExplainButton.disabled = true;
  setAIStatus("Building bounded evidence and waiting for the local model…");
  try {
    const response = await fetch("/api/ai/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scan_id: currentScanId,
        model: ollamaModelSelect.value,
        question,
        symbol_id: traceSelect.value,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail || {};
      throw new Error(detail.message || "The local-model request failed.");
    }
    renderAIResponse(data);
    setAIStatus("Grounded local-model response complete.", "success");
  } catch (error) {
    setAIStatus(`${error.message} Deterministic scan evidence is still available above.`, "error");
  } finally {
    updateAIAvailability();
  }
});

teachBuildButton.addEventListener("click", async () => {
  if (!currentScanId || !teachSymbolSelect.value) {
    setTeachStatus("Scan a project and select a function or method first.", "error");
    return;
  }
  teachBuildButton.disabled = true;
  setTeachStatus("Building a deterministic lesson without contacting Ollama…");
  try {
    const response = await fetch("/api/teach/lesson", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scan_id: currentScanId,
        symbol_id: teachSymbolSelect.value,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail || {};
      throw new Error(detail.message || "The deterministic lesson could not be built.");
    }
    renderTeachLesson(data);
    setTeachStatus("Deterministic lesson complete. Ollama was not required.", "success");
  } catch (error) {
    currentTeachLesson = null;
    teachLessonPanel.classList.add("hidden");
    setTeachStatus(error.message, "error");
  } finally {
    teachBuildButton.disabled = !currentScanId || !teachSymbolSelect.value;
    updateAIAvailability();
  }
});

debugBuildButton.addEventListener("click", async () => {
  const failureStatement = debugFailureInput.value.trim();
  if (!currentScanId || !debugSymbolSelect.value) {
    setDebugStatus("Scan a project and select a function or method first.", "error");
    return;
  }
  if (!failureStatement) {
    setDebugStatus("Describe the observed failure before building an investigation.", "error");
    return;
  }
  debugBuildButton.disabled = true;
  setDebugStatus("Ranking source-backed hypotheses without running code or contacting Ollama…");
  try {
    const response = await fetch("/api/debug/investigation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scan_id: currentScanId,
        symbol_id: debugSymbolSelect.value,
        failure_statement: failureStatement,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail || {};
      throw new Error(detail.message || "The deterministic investigation could not be built.");
    }
    renderDebugInvestigation(data);
    setDebugStatus("Deterministic investigation complete. No code, command, or model was run.", "success");
  } catch (error) {
    currentDebugInvestigation = null;
    debugInvestigationPanel.classList.add("hidden");
    setDebugStatus(error.message, "error");
  } finally {
    debugBuildButton.disabled = !currentScanId || !debugSymbolSelect.value;
  }
});

teachAIExplainButton.addEventListener("click", async () => {
  const question = teachAIQuestion.value.trim();
  if (!question) {
    setTeachAIStatus("Enter a question first.", "error");
    return;
  }
  if (!currentTeachLesson || currentTeachLesson.symbol_id !== teachSymbolSelect.value) {
    setTeachAIStatus("Build the deterministic lesson first.", "error");
    return;
  }
  teachAIExplainButton.disabled = true;
  setTeachAIStatus("Sending only allow-listed lesson evidence to the local model…");
  try {
    const response = await fetch("/api/teach/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scan_id: currentScanId,
        symbol_id: currentTeachLesson.symbol_id,
        model: ollamaModelSelect.value,
        question,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail || {};
      throw new Error(detail.message || "The local-model Teach request failed.");
    }
    if (data.lesson_id !== currentTeachLesson.lesson_id) {
      throw new Error("The lesson changed. Build it again before requesting an interpretation.");
    }
    renderTeachAIResponse(data.grounded_response);
    setTeachAIStatus("Grounded Teach interpretation complete.", "success");
  } catch (error) {
    setTeachAIStatus(`${error.message} The deterministic lesson remains available above.`, "error");
  } finally {
    updateAIAvailability();
  }
});

aiExportButton.addEventListener("click", async () => {
  if (!currentMapAIResponse) return;
  const filename = `${safeArtifactName(traceSelect.value)}-map-interpretation.md`;
  const result = await saveTextArtifact(
    filename,
    localModelMarkdown("Map", traceSelect.value, aiQuestion.value.trim(), currentMapAIResponse),
    "text/markdown",
    ".md",
    "Markdown document"
  );
  if (result !== "cancelled") setAIStatus("Interpretation export prepared.", "success");
});

teachAIExportButton.addEventListener("click", async () => {
  if (!currentTeachAIResponse || !currentTeachLesson) return;
  const filename = `${safeArtifactName(currentTeachLesson.symbol_id)}-teach-interpretation.md`;
  const result = await saveTextArtifact(
    filename,
    localModelMarkdown("Teach", currentTeachLesson.symbol_id, teachAIQuestion.value.trim(), currentTeachAIResponse),
    "text/markdown",
    ".md",
    "Markdown document"
  );
  if (result !== "cancelled") setTeachAIStatus("Interpretation export prepared.", "success");
});

teachExportJsonButton.addEventListener("click", async () => {
  if (!currentTeachLesson) return;
  const filename = `${safeArtifactName(currentTeachLesson.symbol_id)}-deterministic-lesson.json`;
  const result = await saveTextArtifact(
    filename,
    JSON.stringify(currentTeachLesson, null, 2),
    "application/json",
    ".json",
    "JSON document"
  );
  if (result !== "cancelled") setTeachStatus("Deterministic lesson export prepared.", "success");
});

teachExportMarkdownButton.addEventListener("click", async () => {
  if (!currentTeachLesson) return;
  const filename = `${safeArtifactName(currentTeachLesson.symbol_id)}-beginner-lesson.md`;
  const result = await saveTextArtifact(
    filename,
    deterministicLessonMarkdown(currentTeachLesson),
    "text/markdown",
    ".md",
    "Markdown document"
  );
  if (result !== "cancelled") setTeachStatus("Readable lesson export prepared.", "success");
});

debugExportJsonButton.addEventListener("click", async () => {
  if (!currentDebugInvestigation) return;
  const filename = `${safeArtifactName(currentDebugInvestigation.symbol_id)}-debug-investigation.json`;
  const result = await saveTextArtifact(
    filename,
    JSON.stringify(currentDebugInvestigation, null, 2),
    "application/json",
    ".json",
    "JSON document"
  );
  if (result !== "cancelled") setDebugStatus("Deterministic investigation export prepared.", "success");
});

debugExportMarkdownButton.addEventListener("click", async () => {
  if (!currentDebugInvestigation) return;
  const filename = `${safeArtifactName(currentDebugInvestigation.symbol_id)}-debug-investigation.md`;
  const result = await saveTextArtifact(
    filename,
    deterministicDebugMarkdown(currentDebugInvestigation),
    "text/markdown",
    ".md",
    "Markdown document"
  );
  if (result !== "cancelled") setDebugStatus("Readable investigation export prepared.", "success");
});

exportButton.addEventListener("click", () => {
  if (!currentAnalysis) return;
  const blob = new Blob([JSON.stringify(currentAnalysis, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const root = currentAnalysis.project ? currentAnalysis.project.root : currentAnalysis.root;
  const folderName = root.split(/[\\/]/).filter(Boolean).at(-1) || "project";
  link.href = url;
  link.download = `${folderName}-project-mentor-scan.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setStatus("JSON report exported.", "success");
});

refreshOllamaStatus();
