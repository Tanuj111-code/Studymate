$ErrorActionPreference = 'SilentlyContinue'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$runState = Join-Path $project '.run'

$backendPidFile = Join-Path $runState 'backend.pid'
if (Test-Path $backendPidFile) {
    $id = [int](Get-Content -LiteralPath $backendPidFile -Raw)
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $id"
    if ($process -and $process.ExecutablePath -eq (Join-Path $project 'backend\.venv\Scripts\python.exe')) {
        Stop-Process -Id $id -Force
        Write-Host 'Stopped the StudyMate backend.'
    }
    Remove-Item -LiteralPath $backendPidFile -Force
}

$frontendPidFile = Join-Path $runState 'frontend.pid'
if (Test-Path $frontendPidFile) {
    $id = [int](Get-Content -LiteralPath $frontendPidFile -Raw)
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $id"
    if ($process -and $process.Name -eq 'cmd.exe' -and $process.CommandLine -match 'npm run dev -- --host 127\.0\.0\.1') {
        & taskkill.exe /PID $id /T /F | Out-Null
        Write-Host 'Stopped the StudyMate frontend.'
    }
    Remove-Item -LiteralPath $frontendPidFile -Force
}
