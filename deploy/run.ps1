$ErrorActionPreference = "Stop"
$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $AppDir ".venv\Scripts\python.exe"
$LogDir = Join-Path $AppDir "logs"
$StartupLog = Join-Path $LogDir "startup.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Startup([string]$Message) {
    $line = "{0} {1}{2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message, [Environment]::NewLine
    [System.IO.File]::AppendAllText($StartupLog, $line)
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Startup "Python venv not found: $Python"
    exit 1
}

Set-Location -LiteralPath $AppDir
Write-Startup "Starting $Python serve.py"
& $Python (Join-Path $AppDir "serve.py")
$code = $LASTEXITCODE
if ($null -eq $code) { $code = 0 }
Write-Startup "serve.py exited with code $code"
exit $code
