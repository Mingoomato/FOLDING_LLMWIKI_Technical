<# 
.SYNOPSIS
LLMWiki ?쇳뀓??臾몄꽌瑜?PDF濡?鍮뚮뱶?⑸땲??
.DESCRIPTION
LuaLaTeX ?붿쭊???ъ슜??3-pass + bibtex + glossaries ?꾩쟾 鍮뚮뱶 ?섑뻾.
?ъ쟾 ?붽뎄?ы빆: MiKTeX ?먮뒗 TeX Live (latexmk, lualatex ?ы븿) ?ㅼ튂 ?꾩슂.
.PARAMETER Open
鍮뚮뱶 ??PDF ?먮룞 ?닿린
.PARAMETER Clean
鍮뚮뱶 ??build ?대뜑 ?뺣━
.EXAMPLE
.\Build-PDF.ps1
.EXAMPLE
.\Build-PDF.ps1 -Open
.EXAMPLE
.\Build-PDF.ps1 -Clean
#>
param(
[switch]$Open,
[switch]$Clean
)
$ErrorActionPreference = "Stop"
function Write-Step($msg) {
Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}
function Write-OK($msg) {
Write-Host "  [OK] $msg" -ForegroundColor Green
}
function Write-ErrorMsg($msg) {
Write-Host "  [ERROR] $msg" -ForegroundColor Red
}
Write-Host "`n============================================================"
Write-Host "  LLMWiki Technical Specification PDF Build (PowerShell)"
Write-Host "============================================================`n"
# 1) latexmk & lualatex ?뺤씤
Write-Step "?꾧뎄 ?뺤씤"
$latexmk = Get-Command latexmk -ErrorAction SilentlyContinue
$lualatex = Get-Command lualatex -ErrorAction SilentlyContinue
if (-not $latexmk) {
Write-ErrorMsg "latexmk瑜?李얠쓣 ???놁뒿?덈떎. MiKTeX/TeX Live ?ㅼ튂 ??PATH ?뺤씤 ?꾩슂."
Write-Host "  MiKTeX: https://miktex.org/download"
Write-Host "  TeX Live: https://tug.org/texlive/"
exit 1
}
Write-OK "latexmk: $($latexmk.Source)"
$engine = "-pdf"
if ($lualatex) {
Write-OK "lualatex: $($lualatex.Source)  ??LuaLaTeX ?붿쭊 ?ъ슜"
$engine = "-lualatex"
} else {
Write-Host "  [WARN] lualatex 誘몃컻寃???pdfLaTeX ?대갚 (?고듃 ?댁뒋 媛??" -ForegroundColor Yellow
}
# 2) ?고듃 罹먯떆 媛깆떊
Write-Step "?고듃 罹먯떆 媛깆떊 (理쒖큹 1??"
try {
& luaotfload-tool --update 2>$null
Write-OK "luaotfload-tool --update ?꾨즺"
} catch {
Write-Host "  [INFO] luaotfload-tool ?앸왂 (誘몄꽕移??먮뒗 沅뚰븳)" -ForegroundColor Yellow
}
# 3) 鍮뚮뱶 ?붾젆?좊━
$buildDir = "build"
if ($Clean -and (Test-Path $buildDir)) {
Write-Step "鍮뚮뱶 ?대뜑 ?뺣━"
Remove-Item -Recurse -Force $buildDir
Write-OK "build/ ??젣??
}
if (-not (Test-Path $buildDir)) { New-Item -ItemType Directory -Path $buildDir | Out-Null }
# 4) 而댄뙆??++ Write-Step "LaTeX 而댄뙆???쒖옉 (3-pass + bibtex + glossaries)"
$args = @(
$engine,
"-interaction=nonstopmode",
"-halt-on-error",
"-file-line-error",
"-synctex=1",
"-output-directory=build",
"LLMWiki.tex"
)
Write-Host "  ?ㅽ뻾: latexmk $($args -join ' ')"
$exitCode = & latexmk @args
if ($LASTEXITCODE -ne 0) {
Write-ErrorMsg "latexmk ?ㅽ뙣 (exit code: $LASTEXITCODE)"
Write-Host "  濡쒓렇 ?뺤씤: build/LLMWiki.log" -ForegroundColor Yellow
exit $LASTEXITCODE
}
# 5) PDF 蹂듭궗
Write-Step "寃곌낵 蹂듭궗"
Copy-Item -Path "build/LLMWiki.pdf" -Destination "LLMWiki.pdf" -Force
Write-OK "LLMWiki.pdf ?앹꽦??($(Get-Item LLMWiki.pdf).Length / 1KB KB)"
# 6) ?닿린
if ($Open) {
Write-Step "PDF ?닿린"
Invoke-Item "LLMWiki.pdf"
}
Write-Host "`n============================================================"
Write-Host "  鍮뚮뱶 ?꾨즺!" -ForegroundColor Green
Write-Host "============================================================`n"

