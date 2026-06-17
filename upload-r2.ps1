<#
  upload-r2.ps1 — Push Behold My Messenger audio to Cloudflare R2 via Wrangler.
  Auth is browser OAuth (NO secret/access key to paste — fixes the rclone signature problem).

  ONE-TIME SETUP (do this once):
      wrangler login            # opens a browser; authorize the Crowned Eagles Global account

  USAGE:
      .\upload-r2.ps1 -Book 5                 # upload every mp3 in audio\book-5  -> R2 beholdmymessenger-book5
      .\upload-r2.ps1 -Book 5 -Only "073-*"   # only files matching a pattern (e.g. one appendix's chapters)
      .\upload-r2.ps1 -Book all               # all five books

  Local audio\book-N\<file>.mp3  ->  R2  <bucket>/beholdmymessenger-bookN/<file>.mp3
#>
param(
  [Parameter(Mandatory = $true)][string]$Book,
  [string]$Only   = "*.mp3",
  [string]$Bucket = "crownedeaglesglobal-beholdmymessenger-series"
)
$ErrorActionPreference = "Stop"

# account id is public (it's in the dashboard URL); setting it avoids a multi-account prompt
$env:CLOUDFLARE_ACCOUNT_ID = "4e5aa7eb842d848eba4c95f133160e6a"

$wrangler = Join-Path $env:APPDATA "npm\wrangler.cmd"
if (-not (Test-Path $wrangler)) { $wrangler = "wrangler" }   # fall back to PATH

$repo  = $PSScriptRoot
$books = if ($Book -eq "all") { 1..5 } else { @([int]$Book) }
$ok = 0; $fail = 0

foreach ($n in $books) {
  $dir = Join-Path $repo "audio\book-$n"
  if (-not (Test-Path $dir)) { Write-Host "book-$n : no local audio dir ($dir) - skipped" -ForegroundColor Yellow; continue }
  $files = Get-ChildItem $dir -Filter $Only -File | Where-Object { $_.Extension -eq ".mp3" }
  Write-Host "`n=== book-$n : $($files.Count) file(s) -> $Bucket/beholdmymessenger-book$n ===" -ForegroundColor Cyan
  foreach ($f in $files) {
    $key = "$Bucket/beholdmymessenger-book$n/$($f.Name)"
    & $wrangler r2 object put $key --file="$($f.FullName)" --remote --content-type "audio/mpeg" | Out-Null
    if ($LASTEXITCODE -eq 0) { $ok++;  Write-Host ("  OK   " + $f.Name) }
    else                     { $fail++; Write-Host ("  FAIL " + $f.Name) -ForegroundColor Red }
  }
}
Write-Host "`nDone. uploaded=$ok failed=$fail" -ForegroundColor Green
if ($fail -gt 0) { Write-Host "If failures say 'not logged in', run:  wrangler login" -ForegroundColor Yellow }
