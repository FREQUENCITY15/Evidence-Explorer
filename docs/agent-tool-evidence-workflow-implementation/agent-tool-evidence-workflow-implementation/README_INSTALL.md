# Agent-Tool-Evidence workflow documentation overlay

This bundle adds only repository-maintainer documentation. It does not modify TypeScript source, tests, evidence, the Boot Camp trial agent, MCP configuration, dependencies, or Git history.

## Files added

- `.github/copilot-instructions.md`
- `docs/MAINTAINER_WORKFLOW.md`
- `docs/PROMPTING_PLAYBOOK.md`
- `docs/PROJECT_RESUME.md`
- `docs/templates/PROJECT_RESUME_TEMPLATE.md`

## Safe install

From PowerShell, extract this bundle and run:

```powershell
Set-Location <path-to-extracted-bundle>
.\INSTALL_WORKFLOW_DOCS.ps1 -Repo "C:\Projects\Active\Agent-Tool-Evidence"
```

The installer:

1. checks that the target resembles the expected project;
2. refuses to overwrite any destination file;
3. prints Git status before changes;
4. copies only the five documentation files;
5. runs `git --no-pager diff --check` and prints Git status afterward.

If your live repository still uses the older path/name, pass that path explicitly instead.

## After installation

Do not immediately commit. First inspect the new files and populate `docs/PROJECT_RESUME.md` using observed state from the live repository.

Recommended non-mutating observations:

```powershell
git status --short --branch
git --no-pager diff --check
Get-Content .\package.json
Get-ChildItem .\docs\handoffs\
```

Then run the repository-defined verification commands appropriate to the current checkpoint.
