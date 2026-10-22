#Requires -Version 5.1
<#
.SYNOPSIS
  Removes the Queue Mail Generator startup task and firewall rule.
#>
[CmdletBinding()]
param(
    [string]$TaskName = "QueueMailGenerator",
    [switch]$RemoveVenv
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Запустите PowerShell от имени администратора."
}

& (Join-Path $PSScriptRoot "stop.ps1") -TaskName $TaskName

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Задача '$TaskName' удалена."
}

Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "Queue Mail Generator TCP *" } |
    Remove-NetFirewallRule

if ($RemoveVenv) {
    $VenvDir = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path ".venv"
    if (Test-Path -LiteralPath $VenvDir) {
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
        Write-Host "Виртуальное окружение удалено."
    }
}

Write-Host "Удаление завершено. Каталог приложения, np_rules.json и signature.txt оставлены на месте."
