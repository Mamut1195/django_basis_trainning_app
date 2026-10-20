# Run in a normal PowerShell terminal. Includes ALL non-ignored changes.
# OpenSSL is selected per command; no global Git or TLS settings are changed.
[CmdletBinding()]
param(
    [string]$CommitMessage = 'refactor: complete BASIS architecture and presentation',
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot

function Invoke-CheckedGit {
    param(
        [Parameter(Mandatory = $true)][string[]]$GitArguments,
        [int[]]$AllowedExitCodes = @(0)
    )

    # Git writes normal progress to stderr. Judge success by its native exit code.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & git -c http.sslBackend=openssl @GitArguments
        $nativeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($AllowedExitCodes -notcontains $nativeExitCode) {
        throw "git $($GitArguments -join ' ') failed (exit $nativeExitCode)."
    }
}

Push-Location -LiteralPath $repository
try {
    Get-Command git -ErrorAction Stop | Out-Null
    $gitRoot = Invoke-CheckedGit -GitArguments @('rev-parse', '--show-toplevel')
    if ([IO.Path]::GetFullPath($gitRoot) -ne [IO.Path]::GetFullPath($repository)) {
        throw 'The script must operate on its containing repository.'
    }

    if (-not $VerifyOnly) {
        Invoke-CheckedGit -GitArguments @('switch', 'main')
        Invoke-CheckedGit -GitArguments @('add', '--all')
        Invoke-CheckedGit -GitArguments @('diff', '--cached', '--check')

        $stagedPaths = @(Invoke-CheckedGit -GitArguments @('diff', '--cached', '--name-only'))
        if ($stagedPaths.Count -gt 0) {
            Write-Host "Creating commit with $($stagedPaths.Count) changed paths..."
            Invoke-CheckedGit -GitArguments @('commit', '-m', $CommitMessage)
        }
        else {
            Write-Host 'No new changes to commit.'
        }

        Invoke-CheckedGit -GitArguments @('fetch', 'origin')
        Invoke-CheckedGit -GitArguments @('merge', '--no-edit', 'origin/main')
        Invoke-CheckedGit -GitArguments @('push', 'origin', 'main')
    }

    Invoke-CheckedGit -GitArguments @('fetch', 'origin')
    $branch = Invoke-CheckedGit -GitArguments @('branch', '--show-current')
    $localSha = Invoke-CheckedGit -GitArguments @('rev-parse', 'refs/heads/main')
    $trackingSha = Invoke-CheckedGit -GitArguments @('rev-parse', 'refs/remotes/origin/main')
    $remoteLine = @(Invoke-CheckedGit -GitArguments @('ls-remote', '--exit-code', 'origin', 'refs/heads/main'))
    if ($remoteLine.Count -ne 1) { throw 'Unexpected remote main response.' }
    $remoteSha = ($remoteLine[0] -split '\s+')[0]
    $pending = @(Invoke-CheckedGit -GitArguments @('status', '--porcelain', '--untracked-files=all'))

    if ($branch -ne 'main') { throw 'The current branch is not main.' }
    if ($localSha -ne $trackingSha -or $localSha -ne $remoteSha) {
        throw 'Local main, origin/main and remote main do not match.'
    }
    if ($pending.Count -ne 0) {
        throw 'Uncommitted or untracked changes remain. Synchronization is incomplete.'
    }

    Write-Host "VERIFIED: main local and remote match $localSha; working tree clean." -ForegroundColor Green
}
catch {
    Write-Host "INCOMPLETE: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Work is preserved. Resolve the error before running the script again.'
    throw
}
finally {
    Pop-Location
}
