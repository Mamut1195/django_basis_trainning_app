# External operator entry point: verify first, then integrate exactly the tested scope.
[CmdletBinding()]
param([ValidateRange(1024, 65535)][int]$Port = 55440)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $workspace 'docs/architecture/ARCH-04-FILES.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$operationId = [Guid]::NewGuid().ToString('N')
$logDirectory = Join-Path $workspace ('.cache/arch04-git/' + $operationId)
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$git = (Get-Command git -ErrorAction Stop).Source
$script:gitStep = 0

function Invoke-Git {
    param([string[]]$Arguments, [switch]$AllowFailure)
    foreach ($argument in $Arguments) {
        if ($argument -match '[\s"]') { throw 'Git argument needs explicit quoting.' }
    }
    $script:gitStep++
    $prefix = Join-Path $logDirectory ('git-{0:00}' -f $script:gitStep)
    $process = Start-Process -FilePath $git -ArgumentList $Arguments -WorkingDirectory $workspace `
        -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput ($prefix + '.out') `
        -RedirectStandardError ($prefix + '.err')
    $process.Refresh()
    if ($null -eq $process.ExitCode) { throw 'No native Git exit code was available.' }
    $result = [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output = [IO.File]::ReadAllText($prefix + '.out')
        ErrorOutput = [IO.File]::ReadAllText($prefix + '.err')
    }
    if ($result.ExitCode -ne 0 -and -not $AllowFailure) {
        throw "Git failed (exit $($result.ExitCode)); no destructive recovery was attempted. See $prefix.err"
    }
    return $result
}

function Assert-TestedSources {
    foreach ($entry in $receipt.source_hashes.PSObject.Properties) {
        if ($manifest.files -notcontains $entry.Name) { throw 'Receipt contains an unexpected file.' }
        $actual = Get-TextHash (Join-Path $workspace $entry.Name)
        if ($actual -ne $entry.Value) { throw "Source changed after verification: $($entry.Name)" }
    }
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

$branch = (Invoke-Git @('branch', '--show-current')).Output.Trim()
$base = (Invoke-Git @('rev-parse', 'HEAD')).Output.Trim()
if ($branch -ne 'main' -or -not $base.StartsWith($manifest.base_commit)) {
    throw 'Expected main at the reviewed ARCH-03 base. Reconcile changes before proceeding.'
}
$prepared = Invoke-Git @('diff', '--cached', '--quiet') -AllowFailure
if ($prepared.ExitCode -ne 0) { throw 'Existing staged changes must be reviewed first.' }
foreach ($path in $manifest.files) {
    if ($path -in @('seed.py', 'manage.py') -or $path -match '(^|/)\.\.(/|$)' -or [IO.Path]::IsPathRooted($path)) {
        throw 'Manifest contains an out-of-scope path.'
    }
}

& (Join-Path $PSScriptRoot 'Verify-Arch04.ps1') -SelfTest
& (Join-Path $PSScriptRoot 'Verify-Arch04.ps1') -Port $Port
$receiptPath = Join-Path $workspace 'docs/architecture/ARCH-04-RESULT.json'
$receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($receipt.status -ne 'VERIFIED' -or $receipt.tests -ne 148 -or $receipt.skipped -ne 0 -or -not $receipt.container_stopped) {
    throw 'A successful full PostgreSQL receipt and stopped test container are required.'
}
Assert-TestedSources
foreach ($path in $manifest.files) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspace $path) -PathType Leaf)) {
        throw "Missing candidate file: $path"
    }
}

Invoke-Git @('switch', '-c', 'arch/04-planning') | Out-Null
Invoke-Git (@('add', '--') + @($manifest.files)) | Out-Null
$stagedOutput = (Invoke-Git @('diff', '--cached', '--name-only')).Output.Trim()
foreach ($path in [regex]::Split($stagedOutput, '\r?\n')) {
    if ($manifest.files -notcontains $path) { throw "Unexpected staged file: $path" }
}
Invoke-Git @('-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol', 'diff', '--cached', '--check') | Out-Null
foreach ($path in $manifest.files) {
    Invoke-Git @('cat-file', '-e', (':' + $path)) | Out-Null
}
Assert-TestedSources
$messageRelative = '.cache/arch04-git/' + $operationId + '/message.txt'
[IO.File]::WriteAllText((Join-Path $workspace $messageRelative), "arch: migrate planning and versions to typed use cases`n", [Text.UTF8Encoding]::new($false))
Invoke-Git @('commit', '-F', $messageRelative) | Out-Null
$commit = (Invoke-Git @('rev-parse', 'HEAD')).Output.Trim()
Invoke-Git @('switch', 'main') | Out-Null
Invoke-Git @('merge', '--ff-only', 'arch/04-planning') | Out-Null
if ((Invoke-Git @('rev-parse', 'HEAD')).Output.Trim() -ne $commit) { throw 'Integration SHA mismatch.' }
foreach ($path in $manifest.files) {
    Invoke-Git @('cat-file', '-e', ('HEAD:' + $path)) | Out-Null
}
Assert-TestedSources
$integration = @{
    status = 'VERIFIED'; commit = $commit; base = $base; branch = 'main';
    verification_run = $receipt.run_id; source_hashes = $receipt.source_hashes;
    integrated_at = [DateTime]::UtcNow.ToString('o')
}
[IO.File]::WriteAllText((Join-Path $workspace '.cache/arch04-integration.json'), ($integration | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
Write-Host "VERIFIED: ARCH-04 integrated in main at $commit"
Write-Host (Invoke-Git @('status', '--short')).Output
Write-Host 'No push or production activation performed. Return this SHA to Codex for tracker reconciliation.'
