param(
    [Parameter(Mandatory = $false)]
    [string]$Repo = "C:\Projects\Active\Agent-Tool-Evidence"
)

$ErrorActionPreference = "Stop"
$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Agent-Tool-Evidence workflow-doc install preflight" -ForegroundColor Cyan
Write-Host "Target repo: $Repo"

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw "Repository path does not exist: $Repo"
}

$requiredRepoFiles = @(
    "package.json",
    "src\extraction\debug-log-extractor.ts",
    ".github\agents\boot-camp-trial.agent.md"
)

$missing = @()
foreach ($relative in $requiredRepoFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $Repo $relative))) {
        $missing += $relative
    }
}

if ($missing.Count -gt 0) {
    Write-Host "Preflight failed. Expected project markers are missing:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" }
    throw "Refusing to install into an unverified target."
}

$files = @(
    ".github\copilot-instructions.md",
    "docs\MAINTAINER_WORKFLOW.md",
    "docs\PROMPTING_PLAYBOOK.md",
    "docs\PROJECT_RESUME.md",
    "docs\templates\PROJECT_RESUME_TEMPLATE.md"
)

$conflicts = @()
foreach ($relative in $files) {
    $target = Join-Path $Repo $relative
    if (Test-Path -LiteralPath $target) {
        $conflicts += $relative
    }
}

if ($conflicts.Count -gt 0) {
    Write-Host "No files were changed." -ForegroundColor Yellow
    Write-Host "These destination files already exist and require manual review:" -ForegroundColor Yellow
    $conflicts | ForEach-Object { Write-Host "  - $_" }
    throw "Refusing to overwrite existing project documentation."
}

Write-Host "\nObserved Git state before copy:" -ForegroundColor Cyan
Push-Location $Repo
try {
    git status --short --branch
} finally {
    Pop-Location
}

foreach ($relative in $files) {
    $source = Join-Path $bundleRoot $relative
    $target = Join-Path $Repo $relative
    $targetDir = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -LiteralPath $source -Destination $target
    Write-Host "Added: $relative" -ForegroundColor Green
}

Write-Host "\nInstalled documentation only. No source, tests, evidence, agent, MCP config, or Git history changed." -ForegroundColor Green
Write-Host "\nGit state after copy:" -ForegroundColor Cyan
Push-Location $Repo
try {
    git status --short --branch
    Write-Host "\nDiff check:" -ForegroundColor Cyan
    git --no-pager diff --check
} finally {
    Pop-Location
}

Write-Host "\nNext: populate docs\PROJECT_RESUME.md from the live repository; do not copy current-state claims from chat history." -ForegroundColor Cyan
