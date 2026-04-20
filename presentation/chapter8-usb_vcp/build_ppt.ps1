$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$texFile = Join-Path $scriptDir 'stm32_usb_vcp_theory.tex'
$buildDir = Join-Path $scriptDir 'build'
$dotScript = Join-Path $scriptDir 'generate_dot_graphs.ps1'
$pdfName = 'stm32_usb_vcp_theory.pdf'
$buildPdf = Join-Path $buildDir $pdfName
$rootPdf = Join-Path $scriptDir $pdfName
$latexmk = 'latexmk.exe'

if (!(Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

& powershell -ExecutionPolicy Bypass -File $dotScript

$arguments = @(
    '-xelatex'
    '-interaction=nonstopmode'
    '-halt-on-error'
    '-file-line-error'
    "-outdir=$buildDir"
    $texFile
)

& $latexmk @arguments

if (!(Test-Path $buildPdf)) {
    throw "未找到编译输出文件: $buildPdf"
}

Copy-Item -LiteralPath $buildPdf -Destination $rootPdf -Force
