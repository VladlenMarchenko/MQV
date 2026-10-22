#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$TaskName = "QueueMailGenerator",
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Запустите PowerShell от имени администратора."
}

$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PidFile = Join-Path $AppDir "logs\queuemail.pid"
$procId = $null
if (Test-Path -LiteralPath $PidFile) {
    $raw = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    if ($raw) { $procId = [int]$raw }
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}

if ($procId) {
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

$servePath = (Join-Path $AppDir "serve.py").ToLower()
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine.ToLower().Contains($servePath)
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

if (Test-Path -LiteralPath $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

if (-not $Quiet) {
    Write-Host "Сервис остановлен."
}
