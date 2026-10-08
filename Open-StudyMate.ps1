$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $project 'backend'
$frontend = Join-Path $project 'frontend'
$venv = Join-Path $backend '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
$runState = Join-Path $project '.run'
New-Item -ItemType Directory -Force -Path $runState | Out-Null

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python was not found. Install Python 3.10+ with the Windows py launcher, then run this script again.'
}
if (-not (Test-Path $python)) {
    & py -3 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the backend Python environment.' }
} else {
    $pipProbe = Start-Process -FilePath $python -ArgumentList @('-m', 'pip', '--version') `
        -WorkingDirectory $backend -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput (Join-Path $runState 'pip-check.out.log') `
        -RedirectStandardError (Join-Path $runState 'pip-check.err.log')
    if ($pipProbe.ExitCode -ne 0) {
        & py -3 -m venv --clear $venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not repair the backend Python environment.' }
    }
}

$dependencyProbe = Start-Process -FilePath $python -ArgumentList '-c "import flask, flask_cors, pypdf, dotenv, openai, fitz"' `
    -WorkingDirectory $backend -WindowStyle Hidden -Wait -PassThru `
    -RedirectStandardOutput (Join-Path $runState 'dependency-check.out.log') `
    -RedirectStandardError (Join-Path $runState 'dependency-check.err.log')
if ($dependencyProbe.ExitCode -ne 0) {
    Write-Host 'Installing backend packages (first run only)...'
    $savedErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $python -m pip install -r (Join-Path $backend 'requirements.txt')
    $installExitCode = $LASTEXITCODE
    $ErrorActionPreference = $savedErrorPreference
    if ($installExitCode -ne 0) { throw 'Backend dependency installation failed.' }
}

if (-not (Test-Path (Join-Path $frontend 'node_modules\vite'))) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Node.js 20.19+ and npm are required.' }
    Write-Host 'Installing frontend packages (first run only)...'
    Push-Location $frontend
    try {
        $savedErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        npm install
        $installExitCode = $LASTEXITCODE
        $ErrorActionPreference = $savedErrorPreference
        if ($installExitCode -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    finally { Pop-Location }
}

# Do not create duplicate server processes if the app is already running.
$backendReady = $false
try { $backendReady = (Invoke-RestMethod 'http://127.0.0.1:5000/api/health' -TimeoutSec 2).status -eq 'ok' } catch { }
if (-not $backendReady) {
    $backendProcess = Start-Process -FilePath $python -ArgumentList 'app.py' -WorkingDirectory $backend -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $backend 'server.out.log') `
        -RedirectStandardError (Join-Path $backend 'server.err.log') -PassThru
    Set-Content -LiteralPath (Join-Path $runState 'backend.pid') -Value $backendProcess.Id
}

$frontendReady = $false
try { $frontendReady = (Invoke-WebRequest 'http://127.0.0.1:5173' -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200 } catch { }
if (-not $frontendReady) {
    $frontendLog = Join-Path $frontend 'server.out.log'
    $frontendError = Join-Path $frontend 'server.err.log'
    $frontendProcess = Start-Process -FilePath $env:ComSpec -ArgumentList @('/c', 'npm run dev -- --host 127.0.0.1') `
        -WorkingDirectory $frontend -WindowStyle Hidden `
        -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendError -PassThru
    Set-Content -LiteralPath (Join-Path $runState 'frontend.pid') -Value $frontendProcess.Id
}

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $api = Invoke-RestMethod 'http://127.0.0.1:5000/api/health' -TimeoutSec 2
        $site = Invoke-WebRequest 'http://127.0.0.1:5173' -TimeoutSec 2 -UseBasicParsing
        if ($api.status -eq 'ok' -and $site.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    throw 'StudyMate did not start in time. Check backend\server.err.log and frontend\server.err.log.'
}

Start-Process 'http://127.0.0.1:5173'
Write-Host 'AI StudyMate is open at http://127.0.0.1:5173'
