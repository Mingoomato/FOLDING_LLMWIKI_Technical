<# 
.SYNOPSIS
    LLMWiki Technical Specification PDF Build
.DESCRIPTION
    LuaLaTeX-based build with 3-pass + bibtex + glossaries.
    Requires: MiKTeX or TeX Live (latexmk, lualatex)
.PARAMETER Open
    Open PDF after build
.PARAMETER Clean
    Clean build directory first
.EXAMPLE
    .\Build-PDF-clean.ps1
.EXAMPLE
    .\Build-PDF-clean.ps1 -Open
.EXAMPLE
    .\Build-PDF-clean.ps1 -Clean
#>

param(
    [switch]$Open,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host "
=== $msg ===" -ForegroundColor Cyan
}

function Write-OK($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-ErrorMsg($msg) {
    Write-Host "  [ERROR] $msg" -ForegroundColor Red
}

Write-Host "
============================================================"
Write-Host "  LLMWiki Technical Specification PDF Build (PowerShell)"
Write-Host "============================================================
"

# 1) Check for latexmk & lualatex
Write-Step "Checking dependencies"
$latexmk = Get-Command latexmk -ErrorAction SilentlyContinue
$lualatex = Get-Command lualatex -ErrorAction SilentlyContinue

if (-not $latexmk) {
    Write-ErrorMsg "latexmk not found. Please install MiKTeX or TeX Live and add to PATH."
    Write-Host "  MiKTeX: https://miktex.org/download"
    Write-Host "  TeX Live: https://tug.org/texlive/"
    exit 1
}
Write-OK "latexmk: $($latexmk.Source)"

$engine = "-pdf"
if ($lualatex) {
    Write-OK "lualatex: $($lualatex.Source)  -> Using LuaLaTeX"
    $engine = "-lualatex"
} else {
    Write-Host "  [WARN] lualatex not found -> falling back to pdfLaTeX (fonts may not render correctly)" -ForegroundColor Yellow
}

# 2) Update luaotfload font database
Write-Step "Updating font database (luaotfload)"
try {
    & luaotfload-tool --update 2>$null
    Write-OK "luaotfload-tool --update completed"
} catch {
    Write-Host "  [INFO] luaotfload-tool skipped (may not be needed)" -ForegroundColor Yellow
}

# 3) Build directory setup
$buildDir = "build"
if ($Clean -and (Test-Path $buildDir)) {
    Write-Step "Cleaning build directory"
    Remove-Item -Recurse -Force $buildDir
    Write-OK "build/ cleaned"
}
if (-not (Test-Path $buildDir)) { New-Item -ItemType Directory -Path $buildDir | Out-Null }

# 4) LaTeX Build
Write-Step "LaTeX Build (3-pass + bibtex + glossaries)"
$args = @(
    $engine,
    "-interaction=nonstopmode",
    "-halt-on-error",
    "-file-line-error",
    "-synctex=1",
    "-output-directory=build",
    "LLMWiki.tex"
)

Write-Host "  Command: latexmk $($args -join ' ')"
$exitCode = & latexmk @args

if ($LASTEXITCODE -ne 0) {
    Write-ErrorMsg "latexmk failed (exit code: $LASTEXITCODE)"
    Write-Host "  Check log: build/LLMWiki.log" -ForegroundColor Yellow
    exit $LASTEXITCODE
}

# 5) Copy PDF
Write-Step "Copying PDF"
Copy-Item -Path "build/LLMWiki.pdf" -Destination "LLMWiki.pdf" -Force
Write-OK "LLMWiki.pdf created $( [math]::Round((Get-Item LLMWiki.pdf).Length / 1KB) ) KB"

# 6) Open if requested
if ($Open) {
    Write-Step "Opening PDF"
    Invoke-Item "LLMWiki.pdf"
}

Write-Host "
============================================================"
Write-Host "  Build completed successfully!" -ForegroundColor Green
Write-Host "============================================================
"
