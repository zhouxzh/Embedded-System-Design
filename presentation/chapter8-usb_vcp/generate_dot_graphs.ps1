$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dotExe = 'dot.exe'
$imgDir = Join-Path $scriptDir 'img'

if (!(Test-Path $imgDir)) {
    New-Item -ItemType Directory -Path $imgDir | Out-Null
}

$dotFiles = Get-ChildItem -Path $imgDir -Filter *.dot | Sort-Object Name

foreach ($file in $dotFiles) {
    $outPdf = Join-Path $imgDir ($file.BaseName + '.pdf')
    & $dotExe -Tpdf $file.FullName -o $outPdf
}
