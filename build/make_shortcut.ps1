# Generates a pinnable .lnk shortcut for the `lc` launcher on the Desktop.
#
# Deliberately NOT PyInstaller: one-file exes are a known Windows Defender
# false-positive pattern, and having the user's own tool quarantined
# mid-session is a worse failure than requiring Python + `lc` on PATH.
$ErrorActionPreference = "Stop"
$target  = (Get-Command lc).Source
$desktop = [Environment]::GetFolderPath("Desktop")
$link    = Join-Path $desktop "LeetGrind.lnk"

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($link)
$sc.TargetPath       = $target
$sc.WorkingDirectory = $env:USERPROFILE
$sc.Description      = "LeetGrind - LeetCode solve loop"
$sc.Save()

Write-Host "Created $link - right-click it and Pin to taskbar."
