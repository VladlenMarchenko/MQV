#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$TaskName = "QueueMailGenerator"
)

$ErrorActionPreference = "Stop"
$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$configPath = Join-Path $AppDir "server.json"
$port = 8000
if (Test-Path -LiteralPath $configPath) {
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.port) { $port = [int]$config.port }
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host ("Задача: {0} ({1}), последний запуск: {2}, результат: {3}" -f $TaskName, $task.State, $info.LastRunTime, $info.LastTaskResult)
} else {
    Write-Host "Задача '$TaskName' не установлена."
}

$PidFile = Join-Path $AppDir "logs\queuemail.pid"
if (Test-Path -LiteralPath $PidFile) {
    $procId = [int](Get-Content -LiteralPath $PidFile -Raw).Trim()
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "Процесс: PID $procId"
    } else {
        Write-Host "Файл PID есть, процесс $procId не найден."
    }
} else {
    Write-Host "Файл PID отсутствует."
}

$conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    Write-Host "Порт ${port} слушается (PID $($conn.OwningProcess))."
} else {
    Write-Host "Порт $port не слушается."
}
