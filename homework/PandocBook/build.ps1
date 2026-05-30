param(
    [string]$Title = ([string]::Concat(
        [char]0x0053, [char]0x0054, [char]0x004D, [char]0x0033, [char]0x0032, [char]0x0020,
        [char]0x5D4C, [char]0x5165, [char]0x5F0F, [char]0x7CFB, [char]0x7EDF, [char]0x4F5C, [char]0x4E1A, [char]0x6C47, [char]0x7F16
    )),
    [string]$Subtitle = ([string]::Concat(
        [char]0x0030, [char]0x0031, [char]0x002D, [char]0x0031, [char]0x0033, [char]0x0020,
        [char]0x6587, [char]0x4EF6, [char]0x5939, [char]0x0020,
        [char]0x0052, [char]0x0045, [char]0x0041, [char]0x0044, [char]0x004D, [char]0x0045, [char]0x0020,
        [char]0x5408, [char]0x96C6
    )),
    [string]$Author = ([string]::Concat([char]0x5468, [char]0x8D24, [char]0x4E2D)),
    [string]$OutputName = "embedded_homework_book.pdf",
    [switch]$KeepTemp
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir '..')
$headerFile = Join-Path $scriptDir 'book-header.tex'
$authorLabel = ([string]::Concat([char]0x4F5C, [char]0x8005, [char]0xFF1A))
$tempFrontMatter = Join-Path $scriptDir '_pandoc_frontmatter.md'
$tempMergedMd = Join-Path $scriptDir '_merged.md'
$texFile = Join-Path $scriptDir '_book.tex'
$outputPdf = Join-Path $scriptDir $OutputName

if (-not (Test-Path -LiteralPath $headerFile)) {
    throw "Missing header file: $headerFile"
}

$moduleDirs = Get-ChildItem -LiteralPath $repoRoot -Directory |
    Where-Object { $_.Name -match '^(0[1-9]|1[0-3])' } |
    Sort-Object { [int]$_.Name.Substring(0, 2) }

$headingStripPatterns = @(
    '^\s*\u4F5C\u4E1A\d+[:\uFF1A]\s*',
    '^\s*\u4F5C\u4E1A[:\uFF1A]\s*',
    '^\s*\d+[A-Za-z0-9_]*\s*[\u2014\u2013-]\s*',
    '^\s*\u7B2C[\u4E00-\u9FFF0-9]+[\u7AE0\u8282\u90E8\u5206\u7BC7]?\s*',
    '^\s*[\u4E00-\u9FFF]+\u3001\s*',
    '^\s*\d+(?:[.\uFF0E\u3001]\d+)*[.\uFF0E\u3001]?\s*',
    '^\s*\u6B65\u9AA4\d+[:\uFF1A]\s*',
    '^\s*\u4EFB\u52A1\s*[A-Z]\s*[:\uFF1A]\s*',
    '^\s*\(\d+\)\s*',
    '^\s*\uFF08\d+\uFF09\s*'
)

function Normalize-MarkdownHeadings {
    param([string]$Text)

    $lines = $Text -split "`r?`n", -1
    $result = New-Object System.Collections.Generic.List[string]
    $inFence = $false

    foreach ($line in $lines) {
        if ($line -match '^\s*(```|~~~)') {
            $inFence = -not $inFence
            [void]$result.Add($line)
            continue
        }

        if (-not $inFence -and $line -match '^(#{1,6}\s+)(.+)$') {
            $prefix = $matches[1]
            $heading = $matches[2].Trim()

            foreach ($pattern in $headingStripPatterns) {
                $heading = [regex]::Replace($heading, $pattern, '')
            }

            $heading = $heading.Trim()
            if ([string]::IsNullOrWhiteSpace($heading)) {
                [void]$result.Add($line)
            } else {
                [void]$result.Add($prefix + $heading)
            }
        } else {
            [void]$result.Add($line)
        }
    }

    return ($result -join "`r`n")
}

function Add-ImageWidth {
    param([string]$Text)

    return [regex]::Replace(
        $Text,
        '^(?<indent>\s*)!\[(?<alt>[^\]]*)\]\((?<src>[^)\r\n]+)\)\s*$',
        {
            param($match)
            $indent = $match.Groups['indent'].Value
            $alt = $match.Groups['alt'].Value
            $src = $match.Groups['src'].Value
            return "${indent}![${alt}](${src}){ width=72% }"
        },
        [System.Text.RegularExpressions.RegexOptions]::Multiline
    )
}

function Normalize-UnicodeForLatex {
    param([string]$Text)

    $replacements = @{
        [string][char]0x2713 = '[OK]'
        [string][char]0x2717 = '[X]'
        [string][char]0x2605 = '*'
        [string][char]0x2248 = '~'
        [string][char]0x2194 = '<->'
        [string][char]0x03BC = 'u'
        [string][char]0x2265 = '>='
        [string][char]0x2014 = '--'
    }

    foreach ($pair in $replacements.GetEnumerator()) {
        $Text = $Text.Replace($pair.Key, $pair.Value)
    }

    return $Text
}

$readmes = foreach ($dir in $moduleDirs) {
    $readme = Join-Path $dir.FullName 'README.md'
    if (Test-Path -LiteralPath $readme) {
        $readme
    }
}

if (-not $readmes) {
    throw "No README.md files found under 01-13."
}

$frontMatter = @"
---
lang: zh-CN
title: $Title
subtitle: $Subtitle
author: $Author
date: $(Get-Date -Format 'yyyy-MM-dd')
documentclass: scrbook
classoption:
  - twoside
  - openany
  - headings=big
  - numbers=noenddot
geometry: margin=2.2cm
toc: false
numbersections: true
top-level-division: chapter
---

\begin{titlepage}
\centering
\vspace*{3.5cm}
{\Huge\bfseries $Title\par}
\vspace{1.2cm}
{\Large $Subtitle\par}
\vfill
{\Large $authorLabel$Author\par}
\vspace{0.3cm}
{\Large $(Get-Date -Format 'yyyy-MM-dd')\par}
\end{titlepage}

\frontmatter
\tableofcontents
\clearpage
\mainmatter
"@

Set-Content -LiteralPath $tempFrontMatter -Value $frontMatter -Encoding UTF8

$builder = [System.Text.StringBuilder]::new()
[void]$builder.AppendLine((Get-Content -LiteralPath $tempFrontMatter -Raw -Encoding UTF8))

foreach ($dir in $moduleDirs) {
    $readme = Join-Path $dir.FullName 'README.md'
    if (-not (Test-Path -LiteralPath $readme)) {
        continue
    }

    $text = Get-Content -LiteralPath $readme -Raw -Encoding UTF8
    $text = Normalize-MarkdownHeadings $text
    $text = Normalize-UnicodeForLatex $text
    $text = $text.Replace('\r\n', '\\r\\n')
    $prefix = $dir.Name
    $text = $text -replace '!\[([^\]]*)\]\(\.?/img/', "![$1]($prefix/img/"
    $text = $text -replace '!\[([^\]]*)\]\(img/', "![$1]($prefix/img/"
    $text = Add-ImageWidth $text
    [void]$builder.AppendLine($text.TrimEnd())
    [void]$builder.AppendLine()
}

Set-Content -LiteralPath $tempMergedMd -Value $builder.ToString() -Encoding UTF8

try {
    foreach ($ext in @('.aux', '.log', '.out', '.toc', '.xdv')) {
        Remove-Item -LiteralPath (Join-Path $scriptDir ($OutputName -replace '\.pdf$', $ext)) -ErrorAction SilentlyContinue
    }

    $resourcePaths = @($repoRoot.FullName) + @($moduleDirs.FullName)
    $resourcePathArg = ($resourcePaths | Select-Object -Unique) -join ';'

    $pandocArgs = @(
        $tempMergedMd
    ) + @(
        '-s',
        '-t', 'latex',
        '-o', $texFile,
        '--include-in-header', $headerFile,
        '--resource-path', $resourcePathArg
    )

    & pandoc @pandocArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pandoc failed with exit code $LASTEXITCODE"
    }

    $jobName = [IO.Path]::GetFileNameWithoutExtension($OutputName)

    & xelatex -interaction=nonstopmode -halt-on-error -jobname $jobName -output-directory $scriptDir $texFile
    if ($LASTEXITCODE -ne 0) {
        throw "xelatex pass 1 failed with exit code $LASTEXITCODE"
    }

    & xelatex -interaction=nonstopmode -halt-on-error -jobname $jobName -output-directory $scriptDir $texFile
    if ($LASTEXITCODE -ne 0) {
        throw "xelatex pass 2 failed with exit code $LASTEXITCODE"
    }

    if (Test-Path -LiteralPath $outputPdf) {
        Write-Host "Created: $outputPdf"
    } else {
        throw "Expected PDF not found: $outputPdf"
    }
}
finally {
    if (-not $KeepTemp) {
        Remove-Item -LiteralPath $tempFrontMatter -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tempMergedMd -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $texFile -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $scriptDir ($OutputName -replace '\.pdf$', '.aux')) -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $scriptDir ($OutputName -replace '\.pdf$', '.log')) -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $scriptDir ($OutputName -replace '\.pdf$', '.out')) -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $scriptDir ($OutputName -replace '\.pdf$', '.toc')) -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $scriptDir ($OutputName -replace '\.pdf$', '.xdv')) -ErrorAction SilentlyContinue
    }
}
