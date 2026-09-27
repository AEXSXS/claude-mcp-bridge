# Pack extension files into a flat-structure .xpi (Firefox add-on = ZIP).
# Run:  powershell -ExecutionPolicy Bypass -File pack.ps1   (from extension/ dir)
# Files are listed individually so they land in the ZIP root (no subfolder).

$ErrorActionPreference = "Stop"
$files = @("manifest.json", "background.js", "content.js") | ForEach-Object {
    Join-Path $PSScriptRoot $_
}
$out = Join-Path $PSScriptRoot "..\claude-mcp-bridge-0.1.0.xpi"

Compress-Archive -Path $files -DestinationPath $out -Force
Write-Host "Packed: $out"

# Verify flat structure
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($out)
try {
    Write-Host "Contents:"
    $zip.Entries | ForEach-Object { Write-Host "  $($_.FullName)" }
}
finally {
    $zip.Dispose()
}
