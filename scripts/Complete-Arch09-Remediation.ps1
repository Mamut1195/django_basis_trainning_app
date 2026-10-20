# Captured native launcher. Git changes occur only in the explicit complete mode.
[CmdletBinding()]
param([ValidateRange(1024, 65535)][int]$Port = 55440, [switch]$Resume)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$python = Join-Path $workspace '.venv-win/Scripts/python.exe'
$launchDirectory = Join-Path $workspace ('.cache/arch09-remediation-launch/' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $launchDirectory -Force | Out-Null
$arguments = @('scripts/arch09_remediation.py', 'complete', '--port', [string]$Port)
if ($Resume) { $arguments += '--resume' }
# Structured FilePath and WorkingDirectory preserve spaces; arguments are fixed tokens.
$stdout = Join-Path $launchDirectory 'stdout.log'
$stderr = Join-Path $launchDirectory 'stderr.log'
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $workspace `
    -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$process.Refresh()
if ($null -eq $process.ExitCode) { throw ('No native exit code; logs: ' + $launchDirectory) }
if (Test-Path -LiteralPath $stdout) { Get-Content -LiteralPath $stdout -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
if ($process.ExitCode -ne 0) { throw ('ARCH-09 remediation complete failed (exit ' + $process.ExitCode + '); logs: ' + $launchDirectory) }
