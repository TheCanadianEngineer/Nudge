[console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$transcriptPath = Join-Path $env:TEMP "ps_session_transcript_$PID.txt"
if (-not $script:transcriptStarted) {
    Start-Transcript -Path $transcriptPath -Append -IncludeInvocationHeader | Out-Null
    $script:transcriptStarted = $true
}
$script:aiCheckScript = Join-Path $PSScriptRoot "nudge.py"
$script:lastCheckedId = -1
$script:ignoredCommands = @("grep", "findstr", "robocopy")
$script:nudgeEnabled = $true

function Test-InGitRepo {
    $dir = Get-Location
    while ($dir) {
        if (Test-Path (Join-Path $dir ".git")) { return $true }
        $parent = Split-Path $dir -Parent
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
    return $false
}

function chat {
    python $script:aiCheckScript chat
}

function lastfail {
    python $script:aiCheckScript last_fail
}

function nudgeoff {
    $script:nudgeEnabled = $false
    Write-Host "AI checks disabled." -ForegroundColor DarkGray
}

function nudgeon {
    $script:nudgeEnabled = $true
    Write-Host "AI checks enabled." -ForegroundColor DarkGray
}

function nudgehelp {
    Write-Host "Nudge commands:" -ForegroundColor Cyan
    Write-Host "  chat      - discuss the last failure with the AI"
    Write-Host "  lastfail  - show the last logged failure"
    Write-Host "  nudgeoff  - turn off automatic AI checks"
    Write-Host "  nudgeon   - turn automatic AI checks back on"
    Write-Host "  nudgehelp - show this list"
}

function prompt {
    $lastSucceeded = $?
    $lastExitCode = $LASTEXITCODE

    $currentPath = $executionContext.SessionState.Path.CurrentLocation.Path
    $shortPath = Split-Path $currentPath -Leaf
    if (-not $shortPath) { $shortPath = $currentPath }

    Write-Host "$shortPath" -NoNewline -ForegroundColor Cyan

    if (Test-InGitRepo) {
        $gitBranch = git rev-parse --abbrev-ref HEAD 2>$null
        if ($gitBranch) {
            $gitStatus = git status --porcelain 2>$null
            if ($gitStatus) {
                Write-Host " ($gitBranch *)" -NoNewline -ForegroundColor Yellow
            } else {
                Write-Host " ($gitBranch)" -NoNewline -ForegroundColor Green
            }
        }
    }
    Write-Host ""

    $failed = -not $lastSucceeded
    $lastHistoryItem = Get-History -Count 1

    if ($script:nudgeEnabled -and $failed -and $lastHistoryItem -and $lastHistoryItem.Id -ne $script:lastCheckedId) {
        $baseCommand = ($lastHistoryItem.CommandLine -split '\s+')[0]

        if ($script:ignoredCommands -notcontains $baseCommand) {
            $script:lastCheckedId = $lastHistoryItem.Id

            $recentOutput = Get-Content $transcriptPath -Tail 15 -ErrorAction SilentlyContinue
            $contextFile = Join-Path $env:TEMP "ai_error_context.txt"
            $recentOutput | Out-File -FilePath $contextFile -Encoding utf8

            $exitCodeForLog = if ($null -eq $lastExitCode) { 1 } else { $lastExitCode }

            try {
                $outputFile = Join-Path $env:TEMP "ai_check_output_$PID.txt"
                $proc = Start-Process -FilePath "python" -ArgumentList @($script:aiCheckScript, "log-failure", $lastHistoryItem.CommandLine, $exitCodeForLog, $contextFile) -RedirectStandardOutput $outputFile -RedirectStandardError "$outputFile.err" -NoNewWindow -PassThru

                $spinnerFrames = @(
                    [char]0x280B, [char]0x2819, [char]0x2839, [char]0x2838, [char]0x283C,
                    [char]0x2834, [char]0x2826, [char]0x2827, [char]0x2807, [char]0x280F
                )
                $i = 0
                $skipped = $false
                while (-not $proc.HasExited) {
                    if ([Console]::KeyAvailable) {
                        $key = [Console]::ReadKey($true)
                        if ($key.Key -eq 'Enter') {
                            $skipped = $true
                            break
                        }
                    }
                    Write-Host "`r$($spinnerFrames[$i % 10]) Checking error with local model... (press Enter to skip) " -NoNewline -ForegroundColor DarkGray
                    Start-Sleep -Milliseconds 100
                    $i++
                }
                Write-Host "`r$(' ' * 80)`r" -NoNewline

                if ($skipped) {
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                    Write-Host "Skipped AI check." -ForegroundColor DarkGray
                } else {
                    $explanation = Get-Content $outputFile -Raw -Encoding UTF8
                    Write-Host $explanation
                }
                Remove-Item $outputFile -ErrorAction SilentlyContinue
            } catch {
                Write-Host "`r[AI check crashed: $($_.Exception.Message)]" -ForegroundColor Red
            }
        }
    }

    $global:LASTEXITCODE = $lastExitCode

    return "> "
}