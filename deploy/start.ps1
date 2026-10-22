#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$TaskName = "QueueMailGenerator"
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Запустите PowerShell от имени администратора."
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    throw "Задача '$TaskName' не установлена. Сначала выполните deploy\install.ps1."
}

Start-ScheduledTask -TaskName $TaskName
Write-Host "Задача '$TaskName' запущена."
