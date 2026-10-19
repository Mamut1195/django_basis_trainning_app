# Run from an external Windows PowerShell session. Uses only its own temporary DB.
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 55440,
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$runId = [Guid]::NewGuid().ToString('N')
$runDirectory = Join-Path $workspace ('.cache/arch06/' + $runId)
New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
$python = Join-Path $workspace '.venv-win/Scripts/python.exe'
$manifest = Get-Content -LiteralPath (Join-Path $workspace 'docs/architecture/ARCH-06-FILES.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$expectedTests = [int]$manifest.postgresql_tests
$expectedPureTests = [int]$manifest.pure_tests
if ($expectedTests -lt 158 -or $expectedPureTests -lt 61) { throw 'Invalid reviewed test counts.' }
$script:stepNumber = 0
$checks = [ordered]@{}

function Invoke-Captured {
    param([string]$Executable, [string[]]$Arguments, [string]$Label, [switch]$AllowFailure)
    # Every current argument is a simple token. Fail explicitly if future edits
    # introduce quoting needs rather than joining unsafe Windows command strings.
    foreach ($argument in $Arguments) {
        if ($argument -match '[\s"]') { throw "Argument requires explicit quoting: $Label" }
    }
    $script:stepNumber++
    $prefix = Join-Path $runDirectory ('{0:00}-{1}' -f $script:stepNumber, $Label)
    $stdout = $prefix + '.stdout.log'
    $stderr = $prefix + '.stderr.log'
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments `
        -WorkingDirectory $workspace -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $process.Refresh()
    if ($null -eq $process.ExitCode) { throw "No native exit code was available: $Label" }
    $result = [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output = [IO.File]::ReadAllText($stdout)
        ErrorOutput = [IO.File]::ReadAllText($stderr)
        StdoutLog = $stdout
        StderrLog = $stderr
    }
    if ($result.ExitCode -ne 0 -and -not $AllowFailure) {
        throw "$Label failed (exit $($result.ExitCode)). Logs: $prefix.*.log"
    }
    return $result
}

function Invoke-Check {
    param([string]$Executable, [string[]]$Arguments, [string]$Label)
    Write-Host "Checking $Label..."
    $result = Invoke-Captured -Executable $Executable -Arguments $Arguments -Label $Label
    $checks[$Label] = @{ status = 'VERIFIED'; exit_code = $result.ExitCode }
    return $result
}

function Get-SourceHashes {
    $manifest = Get-Content -LiteralPath (Join-Path $workspace 'docs/architecture/ARCH-06-FILES.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $hashes = [ordered]@{}
    foreach ($relative in $manifest.files) {
        if ($relative -match '\.(py|ini|ps1)$' -or $relative -eq '.github/workflows/checks.yml' -or $relative -eq 'docs/architecture/ARCH-06-FILES.json') {
            $hashes[$relative] = Get-TextHash (Join-Path $workspace $relative)
        }
    }
    return $hashes
}

function Get-TextHash {
    param([string]$Path)
    $utf8 = [Text.UTF8Encoding]::new($false, $true)
    $content = $utf8.GetString([IO.File]::ReadAllBytes($Path))
    if ($content.Length -gt 0 -and $content[0] -eq [char]0xFEFF) { $content = $content.Substring(1) }
    $content = $content.Replace("`r`n", "`n")
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash($utf8.GetBytes($content))).Replace('-', '') }
    finally { $hasher.Dispose() }
}

$savedEnvironment = @{}
foreach ($name in @('DATABASE_URL', 'DJANGO_SETTINGS_MODULE', 'PYTHONIOENCODING', 'DJANGO_DEBUG')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$containerId = $null
$receipt = [ordered]@{ status = 'FAILED'; run_id = $runId; checks = $checks }
try {
    $env:PYTHONIOENCODING = 'utf-8'
    if ($SelfTest) {
        $ok = Invoke-Captured -Executable $python -Arguments @('-m', 'unittest', 'discover', '-s', 'tests_architecture') -Label 'stderr-success'
        if ($ok.ErrorOutput -notmatch ('Ran ' + $expectedPureTests + ' tests\b') -or $ok.ErrorOutput -notmatch '\bOK\b') {
            throw 'Expected unittest progress on stderr with successful exit.'
        }
        $bad = Invoke-Captured -Executable $python -Arguments @('--deliberately-invalid-arch06-option') -Label 'nonzero-exit' -AllowFailure
        if ($bad.ExitCode -eq 0) { throw 'Expected nonzero process exit was not detected.' }
        Write-Host 'VERIFIED: native stderr is captured separately; real failing exit is detected.'
        return
    }

    $before = Get-SourceHashes
    $env:DJANGO_SETTINGS_MODULE = 'basis_trainning_app.test_settings'
    $env:DJANGO_DEBUG = '1'
    $env:DATABASE_URL = 'sqlite:///:memory:'
    Invoke-Check $python @('scripts/architecture_check.py') 'architecture' | Out-Null
    Invoke-Check $python @('-m', 'unittest', 'discover', '-s', 'tests_architecture') 'pure-tests' | Out-Null
    Invoke-Check $python @('-m', 'mypy', '--config-file', 'mypy-core.ini') 'core-types' | Out-Null
    Invoke-Check $python @('-m', 'mypy', '--config-file', 'mypy-django.ini') 'django-types' | Out-Null
    Invoke-Check (Join-Path $workspace '.venv-win/Scripts/lint-imports.exe') @('--no-cache') 'imports' | Out-Null
    Invoke-Check (Join-Path $workspace '.venv-win/Scripts/ruff.exe') @('check', '.') 'ruff' | Out-Null
    Invoke-Check $python @('manage.py', 'check') 'django-check' | Out-Null
    Invoke-Check $python @('manage.py', 'makemigrations', '--check', '--dry-run') 'migrations' | Out-Null

    $docker = (Get-Command docker -ErrorAction Stop).Source
    Invoke-Check $docker @('version') 'docker-access' | Out-Null
    $cidFile = Join-Path $runDirectory 'container.cid'
    # cidfile is relative so no argument contains whitespace from the workspace.
    $relativeCid = '.cache/arch06/' + $runId + '/container.cid'
    $name = 'basis-arch06-' + $runId
    $arguments = @('run', '--detach', '--rm', '--name', $name, '--cidfile', $relativeCid,
        '--label', ('basis.arch06.run=' + $runId), '--publish', ('127.0.0.1:' + $Port + ':5432'),
        '--env', 'POSTGRES_USER=basis_arch06', '--env', 'POSTGRES_PASSWORD=arch06-test-only',
        '--env', 'POSTGRES_DB=basis_arch06', 'postgres:18.4')
    try {
        Invoke-Check $docker $arguments 'postgres-start' | Out-Null
    }
    finally {
        if (Test-Path -LiteralPath $cidFile) {
            $candidateId = ([IO.File]::ReadAllText($cidFile)).Trim()
            if ($candidateId -match '^[a-f0-9]{64}$') { $containerId = $candidateId }
        }
    }
    if (-not $containerId) { throw 'Docker did not return a valid owned container ID.' }
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        $probe = Invoke-Captured $docker @('exec', $containerId, 'pg_isready', '-U', 'basis_arch06', '-d', 'basis_arch06') 'postgres-ready' -AllowFailure
        if ($probe.ExitCode -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Temporary PostgreSQL did not become ready.' }
    $mapping = Invoke-Check $docker @('port', $containerId, '5432/tcp') 'loopback-binding'
    if ($mapping.Output.Trim() -ne ('127.0.0.1:' + $Port)) { throw 'Unexpected database port binding.' }
    $version = Invoke-Check $docker @('exec', $containerId, 'postgres', '--version') 'postgres-version'
    if ($version.Output -notmatch 'PostgreSQL\) 18\.4') { throw 'Expected PostgreSQL 18.4.' }
    $image = Invoke-Check $docker @('inspect', '--format', '{{.Image}}', $containerId) 'image-id'
    $env:DATABASE_URL = 'postgresql://basis_arch06:arch06-test-only@127.0.0.1:' + $Port + '/basis_arch06'
    $tests = Invoke-Check $python @('manage.py', 'test', 'training.tests', 'basis.modules.training.adapters.tests', 'basis.modules.training.adapters.test_planning', 'basis.modules.training.adapters.test_metrics', 'basis.modules.training.adapters.test_progress', 'basis.modules.accounts.adapters.tests', 'basis.modules.billing.adapters', '--noinput') 'postgres-tests'
    $testOutput = $tests.Output + $tests.ErrorOutput
    if ($testOutput -notmatch ('Ran ' + $expectedTests + ' tests\b') -or $testOutput -notmatch '(?m)^OK\s*$' -or $testOutput -match 'skipped=') {
        throw 'Expected all $expectedTests Django tests to pass without concurrency skips.'
    }
    Invoke-Check $python @('manage.py', 'collectstatic', '--noinput') 'static-assets' | Out-Null
    $after = Get-SourceHashes
    foreach ($path in $before.Keys) {
        if ($after[$path] -ne $before[$path]) { throw "Candidate changed during verification: $path" }
    }
    $receipt.status = 'VERIFIED'
    $receipt['tests'] = $expectedTests
    $receipt['skipped'] = 0
    $receipt['engine'] = $version.Output.Trim()
    $receipt['image_id'] = $image.Output.Trim()
    $receipt['source_hashes'] = $after
    $receipt['hash_mode'] = 'SHA256 strict UTF-8 without BOM, CRLF normalized to LF'
}
catch {
    $receipt['error'] = $_.Exception.Message
}
finally {
    if ($containerId) {
        try {
            $stop = Invoke-Captured $docker @('stop', '--time', '10', $containerId) 'postgres-stop' -AllowFailure
            $receipt['container_stopped'] = ($stop.ExitCode -eq 0)
            if ($stop.ExitCode -ne 0) { throw 'Check the owned container ID in run logs.' }
        }
        catch {
            $receipt.status = 'FAILED'
            $receipt['cleanup_error'] = $_.Exception.Message
        }
    }
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    if (-not $SelfTest) {
        $receipt['verified_at'] = [DateTime]::UtcNow.ToString('o')
        $json = $receipt | ConvertTo-Json -Depth 8
        [IO.File]::WriteAllText((Join-Path $runDirectory 'receipt.json'), $json, [Text.UTF8Encoding]::new($false))
        if ($receipt.status -eq 'VERIFIED') {
            [IO.File]::WriteAllText((Join-Path $workspace 'docs/architecture/ARCH-06-RESULT.json'), $json, [Text.UTF8Encoding]::new($false))
        }
    }
}
if (-not $SelfTest) {
    if ($receipt.status -ne 'VERIFIED') { throw "Verification failed. $($receipt.error) Logs: $runDirectory" }
    Write-Host "VERIFIED: $expectedTests PostgreSQL tests, zero skips. Receipt: docs/architecture/ARCH-06-RESULT.json"
}
