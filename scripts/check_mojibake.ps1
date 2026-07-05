param(
  [Parameter(Mandatory = $true)]
  [string]$Root
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$doubleQuoted = [regex]::new('"(?:[^"\\]|\\.)*"')
$singleQuoted = [regex]::new('''(?:[^''\\]|\\.)*''')
$files = Get-ChildItem -Path $Root -Recurse -File -Include *.js,*.jsx,*.ts,*.tsx
$failures = New-Object System.Collections.Generic.List[string]

function Test-QuotedStrings {
  param(
    [string]$InputText,
    [regex]$Pattern
  )

  foreach ($match in $Pattern.Matches($InputText)) {
    $body = $match.Value.Substring(1, $match.Value.Length - 2)
    if ($body.IndexOf([char]0xFFFD) -ge 0) {
      return $true
    }
  }

  return $false
}

foreach ($file in $files) {
  $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
  $hasDouble = Test-QuotedStrings -InputText $content -Pattern $doubleQuoted
  $hasSingle = $false
  if (-not $hasDouble) {
    $hasSingle = Test-QuotedStrings -InputText $content -Pattern $singleQuoted
  }
  if ($hasDouble -or $hasSingle) {
    $failures.Add($file.FullName) | Out-Null
  }
}

if ($failures.Count -gt 0) {
  Write-Error "Mojibake-like quoted strings found:`n$($failures -join "`n")"
  exit 1
}

Write-Host "No mojibake-like quoted strings found in $Root"
