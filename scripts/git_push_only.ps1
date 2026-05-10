$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

function Write-Info {
    param([string]$Text)
    Write-Host "[INFO] $Text" -ForegroundColor Cyan
}

function Write-Warn {
    param([string]$Text)
    Write-Host "[WARN] $Text" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Text)
    Write-Host "[ERROR] $Text" -ForegroundColor Red
}

function Read-WithDefault {
    param(
        [string]$Prompt,
        [string]$Default
    )

    if ([string]::IsNullOrWhiteSpace($Default)) {
        return (Read-Host $Prompt).Trim()
    }

    $value = (Read-Host "$Prompt [$Default]").Trim()
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Get-ToolPath {
    param(
        [string]$Name,
        [string[]]$Fallbacks
    )

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    foreach ($path in $Fallbacks) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }

    return $null
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Add-LocalExclude {
    param([string]$Root)

    $excludePath = Join-Path $Root ".git\info\exclude"
    $excludeDir = Split-Path -Parent $excludePath
    if (-not (Test-Path -LiteralPath $excludeDir)) {
        New-Item -ItemType Directory -Force -Path $excludeDir | Out-Null
    }
    if (-not (Test-Path -LiteralPath $excludePath)) {
        New-Item -ItemType File -Force -Path $excludePath | Out-Null
    }

    $patterns = @(
        "node_modules/",
        ".env",
        ".env.*",
        "textbooks/",
        "*.zip",
        ".venv/",
        "venv/",
        "__pycache__/",
        "*.pyc",
        ".next/",
        "dist/",
        "build/",
        ".DS_Store"
    )

    $existing = Get-Content -LiteralPath $excludePath -ErrorAction SilentlyContinue
    foreach ($pattern in $patterns) {
        if ($existing -notcontains $pattern) {
            Add-Content -LiteralPath $excludePath -Value $pattern
        }
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

Write-Host ""
Write-Host "Git-only push helper" -ForegroundColor Green
Write-Host "Project folder: $projectRoot"
Write-Host ""
Write-Host "Before using this:" -ForegroundColor Yellow
Write-Host "1. Create an empty repository on https://github.com/new"
Write-Host "2. Copy its HTTPS URL, like https://github.com/yourname/project.git"
Write-Host ""

$git = Get-ToolPath -Name "git.exe" -Fallbacks @(
    "D:\Git\cmd\git.exe",
    "C:\Program Files\Git\cmd\git.exe",
    "C:\Program Files\Git\bin\git.exe"
)

if (-not $git) {
    Write-Fail "Git was not found."
    exit 1
}

Write-Info "Git: $git"

& $git rev-parse --is-inside-work-tree 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Info "This folder is not a Git repository yet. Initializing Git..."
    Invoke-Checked -FilePath $git -Arguments @("init") -FailureMessage "git init failed."
}

Add-LocalExclude -Root $projectRoot

$name = (& $git config user.name).Trim()
$email = (& $git config user.email).Trim()
if ([string]::IsNullOrWhiteSpace($name)) {
    $name = Read-WithDefault -Prompt "Git name" -Default $env:USERNAME
    Invoke-Checked -FilePath $git -Arguments @("config", "user.name", $name) -FailureMessage "Failed to set git user.name."
}
if ([string]::IsNullOrWhiteSpace($email)) {
    $email = Read-WithDefault -Prompt "Git email" -Default "you@example.com"
    Invoke-Checked -FilePath $git -Arguments @("config", "user.email", $email) -FailureMessage "Failed to set git user.email."
}

$origin = & $git remote get-url origin 2>$null
$hasOrigin = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($origin))
if (-not $hasOrigin) {
    $repoUrl = Read-WithDefault -Prompt "Paste GitHub HTTPS repo URL" -Default ""
    if ([string]::IsNullOrWhiteSpace($repoUrl)) {
        Write-Fail "No GitHub repo URL was provided."
        exit 1
    }
    Invoke-Checked -FilePath $git -Arguments @("remote", "add", "origin", $repoUrl) -FailureMessage "Failed to add origin remote."
}

$branch = (& $git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    $branch = "main"
    Invoke-Checked -FilePath $git -Arguments @("checkout", "-B", $branch) -FailureMessage "Failed to create main branch."
}

Invoke-Checked -FilePath $git -Arguments @("branch", "-M", "main") -FailureMessage "Failed to set main branch."
$branch = "main"

Write-Info "Staging files..."
Invoke-Checked -FilePath $git -Arguments @("add", "-A") -FailureMessage "git add failed."

$status = & $git status --short
$hasHead = $true
& $git rev-parse --verify HEAD 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    $hasHead = $false
}

if (-not [string]::IsNullOrWhiteSpace(($status -join ""))) {
    $message = Read-WithDefault -Prompt "Commit message" -Default "update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    Invoke-Checked -FilePath $git -Arguments @("commit", "-m", $message) -FailureMessage "git commit failed."
} elseif (-not $hasHead) {
    Write-Fail "No commit-ready files were found after safety excludes."
    exit 1
} else {
    Write-Info "No local changes to commit. Push will continue."
}

Write-Info "Pushing with git. If a browser login appears, finish it there."
Write-Warn "If Git asks for a password, use a GitHub token instead of your GitHub password."
Invoke-Checked -FilePath $git -Arguments @("push", "-u", "origin", $branch) -FailureMessage "git push failed."

$finalOrigin = (& $git remote get-url origin).Trim()
Write-Host ""
Write-Host "Done. Pushed to: $finalOrigin" -ForegroundColor Green
Write-Host ""
