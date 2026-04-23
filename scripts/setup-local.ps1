param(
    [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([string]$Path)
    $repoRoot = Split-Path -Parent $PSScriptRoot
    return Join-Path -Path $repoRoot -ChildPath $Path
}

function Test-CommandExists {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

$repoRoot = Resolve-RepoPath "."
Set-Location $repoRoot

Write-Host "ALG local setup"
Write-Host "Repository: $repoRoot"

if (-not (Test-CommandExists "python")) {
    throw "Python was not found on PATH. Install Python 3.11+ before running setup."
}

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.11+ is required."
}

$pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
Write-Host "Python: $pythonVersion"

if (-not (Test-Path -LiteralPath $VenvDir)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv $VenvDir
}

$venvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment python not found at $venvPython"
}

Write-Host "Installing Python dependencies..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r "app\requirements.txt"

if (-not (Test-Path -LiteralPath ".env")) {
    Write-Host "No .env found. Create one locally with your LLM credentials."
} else {
    Write-Host ".env already exists; leaving it unchanged."
}

if (-not (Test-Path -LiteralPath "alg.settings.json")) {
    throw "Missing alg.settings.json in repo root."
} else {
    Write-Host "alg.settings.json found."
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Next:"
Write-Host "  1. notepad .env"
Write-Host "  2. Add ALG_LLM_API_KEY, ALG_LLM_BASE_URL, and ALG_LLM_MODEL"
Write-Host "  3. notepad alg.settings.json"
Write-Host "  4. powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1"
