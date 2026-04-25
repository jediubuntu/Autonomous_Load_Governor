param(
    [int]$AppPort = 8000
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([string]$Path)
    $repoRoot = Split-Path -Parent $PSScriptRoot
    return Join-Path -Path $repoRoot -ChildPath $Path
}

function Read-DotEnv {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($key) {
            $values[$key] = $value
        }
    }
    return $values
}

function Assert-File {
    param(
        [string]$Path,
        [string]$Message
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw $Message
    }
}

function Start-AlgWindow {
    param(
        [string]$Title,
        [string[]]$Lines
    )

    $runDir = Resolve-RepoPath ".alg-run"
    if (-not (Test-Path -LiteralPath $runDir)) {
        New-Item -ItemType Directory -Path $runDir | Out-Null
    }

    $safeName = ($Title -replace "[^A-Za-z0-9_-]", "_").ToLowerInvariant()
    $scriptPath = Join-Path -Path $runDir -ChildPath "$safeName.ps1"
    $script = @(
        "`$Host.UI.RawUI.WindowTitle = '$($Title.Replace("'", "''"))'"
    ) + $Lines

    Set-Content -LiteralPath $scriptPath -Value $script -Encoding UTF8
    Start-Process powershell -ArgumentList "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $scriptPath
}

$repoRoot = Resolve-RepoPath "."
Set-Location $repoRoot

$venvActivate = Resolve-RepoPath ".venv\Scripts\Activate.ps1"
$envPath = Resolve-RepoPath ".env"

Assert-File $venvActivate "Missing .venv. Run scripts\setup-local.ps1 first."
Assert-File $envPath "Missing .env. Run scripts\setup-local.ps1 first, then fill in LLM values."

$envValues = Read-DotEnv $envPath
if (
    -not $envValues["ALG_LLM_API_KEY"] `
    -and -not $envValues["GEMINI_API_KEY"] `
    -and -not $envValues["GOOGLE_API_KEY"] `
    -and -not $envValues["OPENAI_API_KEY"]
) {
    throw "ALG_LLM_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY is required in .env."
}
if (-not $envValues["ALG_LLM_MODEL"]) {
    throw "ALG_LLM_MODEL is required in .env."
}

$targetUrl = "http://127.0.0.1:$AppPort"

Write-Host "Starting ALG local stack in separate PowerShell windows..."
Write-Host "FastAPI: $targetUrl"
Write-Host "Controller: Python + Locust in-process"
Write-Host ""

Start-AlgWindow "ALG FastAPI" @(
    "Set-Location -LiteralPath '$($repoRoot.Replace("'", "''"))'",
    ". '$($venvActivate.Replace("'", "''"))'",
    "python -m uvicorn app.main:app --host 127.0.0.1 --port $AppPort"
)
Start-Sleep -Seconds 3
Start-AlgWindow "ALG Controller" @(
    "Set-Location -LiteralPath '$($repoRoot.Replace("'", "''"))'",
    ". '$($venvActivate.Replace("'", "''"))'",
    "`$env:ALG_TARGET_URL = '$targetUrl'",
    "python controller\main.py"
)

Write-Host "Started. Close the spawned windows to stop each process."
