param(
    [string]$RepoName = "",
    [string]$Message = "",
    [switch]$Private
)

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

function Get-RelativeGitPath {
    param(
        [string]$Root,
        [string]$Path
    )

    return ([System.IO.Path]::GetRelativePath($Root, $Path) -replace "\\", "/")
}

function Add-LocalExclude {
    param(
        [string]$GitRoot,
        [string[]]$Patterns
    )

    $excludePath = Join-Path $GitRoot ".git\info\exclude"
    $excludeDir = Split-Path -Parent $excludePath
    if (-not (Test-Path -LiteralPath $excludeDir)) {
        New-Item -ItemType Directory -Force -Path $excludeDir | Out-Null
    }
    if (-not (Test-Path -LiteralPath $excludePath)) {
        New-Item -ItemType File -Force -Path $excludePath | Out-Null
    }

    $existing = Get-Content -LiteralPath $excludePath -ErrorAction SilentlyContinue
    $toAdd = @()
    foreach ($pattern in $Patterns) {
        if ([string]::IsNullOrWhiteSpace($pattern)) {
            continue
        }
        if ($existing -notcontains $pattern) {
            $toAdd += $pattern
        }
    }

    if ($toAdd.Count -gt 0) {
        Add-Content -LiteralPath $excludePath -Value $toAdd
    }
}

function Get-DefaultRepoName {
    param([string]$Root)

    $leaf = Split-Path -Leaf $Root
    $name = $leaf.ToLowerInvariant() -replace "[^a-z0-9._-]", "-"
    $name = $name -replace "-+", "-"
    $name = $name.Trim("-._")
    if ($name.Length -lt 3) {
        return "ai-hackathon-project"
    }
    return $name
}

$scriptDir = Split-Path -Parent $PSCommandPath
$projectRoot = Split-Path -Parent $scriptDir
Set-Location -LiteralPath $projectRoot

Write-Host ""
Write-Host "GitHub one-click push helper" -ForegroundColor Green
Write-Host "Project folder: $projectRoot"
Write-Host ""

$git = Get-ToolPath -Name "git.exe" -Fallbacks @(
    "D:\Git\cmd\git.exe",
    "C:\Program Files\Git\cmd\git.exe",
    "C:\Program Files\Git\bin\git.exe"
)

$gh = Get-ToolPath -Name "gh.exe" -Fallbacks @(
    "C:\Program Files\GitHub CLI\gh.exe",
    "C:\Program Files (x86)\GitHub CLI\gh.exe",
    "$env:LOCALAPPDATA\GitHub CLI\gh.exe"
)

if (-not $git) {
    Write-Fail "Git was not found. Please install Git first."
    exit 1
}

Write-Info "Git: $git"
if ($gh) {
    Write-Info "GitHub CLI: $gh"
} else {
    Write-Warn "GitHub CLI was not found. Git-only mode will still work with an existing repo URL."
}

& $git rev-parse --is-inside-work-tree 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Info "This folder is not a Git repository yet. Initializing Git..."
    Invoke-Checked -FilePath $git -Arguments @("init") -FailureMessage "git init failed."
}

$commonExcludes = @(
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

$largeLimitBytes = 90MB
$gitDir = Join-Path $projectRoot ".git"
$largeFiles = Get-ChildItem -LiteralPath $projectRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notlike "$gitDir*" -and
        $_.Length -gt $largeLimitBytes
    }

$largeExcludes = @()
foreach ($file in $largeFiles) {
    $largeExcludes += Get-RelativeGitPath -Root $projectRoot -Path $file.FullName
}

if ($largeExcludes.Count -gt 0) {
    Write-Warn "Large files over 90MB were found. GitHub usually rejects files over 100MB."
    foreach ($item in $largeExcludes) {
        Write-Host "  excluded: $item"
    }
}

Add-LocalExclude -GitRoot $projectRoot -Patterns ($commonExcludes + $largeExcludes)

$hasCommit = $true
& $git rev-parse --verify HEAD 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    $hasCommit = $false
}

$statusBefore = & $git status --short
if ([string]::IsNullOrWhiteSpace(($statusBefore -join ""))) {
    Write-Info "No local changes to commit."
    if (-not $hasCommit) {
        Write-Fail "There are no commit-ready files in this folder after safety excludes."
        exit 1
    }
} else {
    Write-Info "Staging all code and document changes..."
    Invoke-Checked -FilePath $git -Arguments @("add", "-A") -FailureMessage "git add failed."

    $statusAfterAdd = & $git status --short
    if (-not [string]::IsNullOrWhiteSpace(($statusAfterAdd -join ""))) {
        if ([string]::IsNullOrWhiteSpace($Message)) {
            $defaultMessage = "update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
            $Message = Read-WithDefault -Prompt "Commit message" -Default $defaultMessage
        }

        Write-Info "Creating commit..."
        & $git commit -m $Message
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Commit failed. If Git asks for name/email, this helper can set them for this project."
            $setIdentity = Read-WithDefault -Prompt "Set Git name and email for this project now? Y/N" -Default "Y"
            if ($setIdentity -match "^(y|yes)$") {
                $gitName = Read-WithDefault -Prompt "Your Git name" -Default $env:USERNAME
                $gitEmail = Read-WithDefault -Prompt "Your Git email" -Default "you@example.com"
                Invoke-Checked -FilePath $git -Arguments @("config", "user.name", $gitName) -FailureMessage "Failed to set git user.name."
                Invoke-Checked -FilePath $git -Arguments @("config", "user.email", $gitEmail) -FailureMessage "Failed to set git user.email."
                Invoke-Checked -FilePath $git -Arguments @("commit", "-m", $Message) -FailureMessage "git commit failed again."
            } else {
                Write-Fail "Commit was not created."
                exit 1
            }
        }
    }
}

$origin = & $git remote get-url origin 2>$null
$hasOrigin = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($origin))
$createdRemote = $false

if (-not $hasOrigin) {
    Write-Warn "No GitHub remote is configured yet."
    Write-Host "Create an empty repository at https://github.com/new, then paste its HTTPS URL here." -ForegroundColor Yellow
    $repoUrl = Read-WithDefault -Prompt "Existing GitHub repo URL, or leave blank to try GitHub CLI auto-create" -Default ""

    if (-not [string]::IsNullOrWhiteSpace($repoUrl)) {
        Invoke-Checked -FilePath $git -Arguments @("remote", "add", "origin", $repoUrl) -FailureMessage "Failed to add origin remote."
    } else {
        if (-not $gh) {
            Write-Fail "GitHub CLI is unavailable. Please create a repo in your browser and paste its HTTPS URL."
            exit 1
        }

        & $gh auth status 1>$null 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "GitHub CLI login is invalid. Please create a repo in your browser and paste its HTTPS URL."
            exit 1
        }

        if ([string]::IsNullOrWhiteSpace($RepoName)) {
            $RepoName = Read-WithDefault -Prompt "GitHub repository name" -Default (Get-DefaultRepoName -Root $projectRoot)
        }

        if ($Private) {
            $visibility = "private"
        } else {
            $visibility = Read-WithDefault -Prompt "Repository visibility: public/private" -Default "public"
            if ($visibility -notmatch "^(public|private)$") {
                $visibility = "public"
            }
        }

        Write-Info "Creating GitHub repository: $RepoName ($visibility)"
        Invoke-Checked -FilePath $gh -Arguments @("repo", "create", $RepoName, "--$visibility", "--source", $projectRoot, "--remote", "origin") -FailureMessage "GitHub CLI repository creation failed."
    }
    $createdRemote = $true
}

$branch = (& $git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    $branch = "main"
    Invoke-Checked -FilePath $git -Arguments @("checkout", "-B", $branch) -FailureMessage "Failed to create main branch."
}

if ($createdRemote) {
    $branch = "main"
    Invoke-Checked -FilePath $git -Arguments @("branch", "-M", $branch) -FailureMessage "Failed to switch branch name to main."
}

Write-Info "Pushing to GitHub branch: $branch"
Invoke-Checked -FilePath $git -Arguments @("push", "-u", "origin", $branch) -FailureMessage "git push failed."

$finalOrigin = (& $git remote get-url origin).Trim()
Write-Host ""
Write-Host "Done. Your project was pushed to GitHub." -ForegroundColor Green
Write-Host "Remote: $finalOrigin"
Write-Host ""
