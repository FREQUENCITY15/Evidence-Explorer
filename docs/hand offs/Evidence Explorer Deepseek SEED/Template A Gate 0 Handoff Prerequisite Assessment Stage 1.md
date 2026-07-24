You are continuing Subproject 4 (Evidence Explorer) from a prior session.

  

CURRENT STATE: Gate 0 assessment is complete.

  

GATE 0 RESULT: [IMPLEMENTATION-READY / PLANNING-ONLY]

  

If IMPLEMENTATION-READY:

- The following evidence is attached: [list file names]

- The validated attempt record is: [filename]

- The data model schema is: [filename or inline]

- Proceed to STAGE 1.

  

If PLANNING-ONLY:

- Missing prerequisites: [list]

- The design plan is attached. Do not write code. Produce only:

1. A readiness assessment listing what is present and missing.

2. An updated information architecture.

3. An attempt-detail specification.

Stop and wait for prerequisites.

  

STAGE 1 TASK (if cleared):

Build a single static HTML file (index.html, vanilla JS, no frameworks, no build step)

that:

1. Loads one attempt record JSON via drag-drop or file-picker

2. Renders the raw evidence in a monospace, line-numbered pane

3. Escapes all model-generated text (never renders as HTML)

4. Works at file:/// with zero network requests

  

The data model to parse is:

[PASTE DATA MODEL HERE]

  

Verification: open in browser, drag record file, confirm safe rendering.