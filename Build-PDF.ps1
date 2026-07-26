++ <# 
++ .SYNOPSIS
++     LLMWiki 라텍스 문서를 PDF로 빌드합니다.
++ .DESCRIPTION
++     LuaLaTeX 엔진을 사용해 3-pass + bibtex + glossaries 완전 빌드 수행.
++     사전 요구사항: MiKTeX 또는 TeX Live (latexmk, lualatex 포함) 설치 필요.
++ .PARAMETER Open
++     빌드 후 PDF 자동 열기
++ .PARAMETER Clean
++     빌드 전 build 폴더 정리
++ .EXAMPLE
++     .\Build-PDF.ps1
++ .EXAMPLE
++     .\Build-PDF.ps1 -Open
++ .EXAMPLE
++     .\Build-PDF.ps1 -Clean
++ #>
++ 
++ param(
++     [switch]$Open,
++     [switch]$Clean
++ )
++ 
++ $ErrorActionPreference = "Stop"
++ 
++ function Write-Step($msg) {
++     Write-Host "`n=== $msg ===" -ForegroundColor Cyan
++ }
++ 
++ function Write-OK($msg) {
++     Write-Host "  [OK] $msg" -ForegroundColor Green
++ }
++ 
++ function Write-ErrorMsg($msg) {
++     Write-Host "  [ERROR] $msg" -ForegroundColor Red
++ }
++ 
++ Write-Host "`n============================================================"
++ Write-Host "  LLMWiki Technical Specification PDF Build (PowerShell)"
++ Write-Host "============================================================`n"
++ 
++ # 1) latexmk & lualatex 확인
++ Write-Step "도구 확인"
++ $latexmk = Get-Command latexmk -ErrorAction SilentlyContinue
++ $lualatex = Get-Command lualatex -ErrorAction SilentlyContinue
++ 
++ if (-not $latexmk) {
++     Write-ErrorMsg "latexmk를 찾을 수 없습니다. MiKTeX/TeX Live 설치 후 PATH 확인 필요."
++     Write-Host "  MiKTeX: https://miktex.org/download"
++     Write-Host "  TeX Live: https://tug.org/texlive/"
++     exit 1
++ }
++ Write-OK "latexmk: $($latexmk.Source)"
++ 
++ $engine = "-pdf"
++ if ($lualatex) {
++     Write-OK "lualatex: $($lualatex.Source)  → LuaLaTeX 엔진 사용"
++     $engine = "-lualatex"
++ } else {
++     Write-Host "  [WARN] lualatex 미발견 → pdfLaTeX 폴백 (폰트 이슈 가능)" -ForegroundColor Yellow
++ }
++ 
++ # 2) 폰트 캐시 갱신
++ Write-Step "폰트 캐시 갱신 (최초 1회)"
++ try {
++     & luaotfload-tool --update 2>$null
++     Write-OK "luaotfload-tool --update 완료"
++ } catch {
++     Write-Host "  [INFO] luaotfload-tool 생략 (미설치 또는 권한)" -ForegroundColor Yellow
++ }
++ 
++ # 3) 빌드 디렉토리
++ $buildDir = "build"
++ if ($Clean -and (Test-Path $buildDir)) {
++     Write-Step "빌드 폴더 정리"
++     Remove-Item -Recurse -Force $buildDir
++     Write-OK "build/ 삭제됨"
++ }
++ if (-not (Test-Path $buildDir)) { New-Item -ItemType Directory -Path $buildDir | Out-Null }
++ 
++ # 4) 컴파일
++ Write-Step "LaTeX 컴파일 시작 (3-pass + bibtex + glossaries)"
++ $args = @(
++     $engine,
++     "-interaction=nonstopmode",
++     "-halt-on-error",
++     "-file-line-error",
++     "-synctex=1",
++     "-output-directory=build",
++     "LLMWiki.tex"
++ )
++ 
++ Write-Host "  실행: latexmk $($args -join ' ')"
++ $exitCode = & latexmk @args
++ 
++ if ($LASTEXITCODE -ne 0) {
++     Write-ErrorMsg "latexmk 실패 (exit code: $LASTEXITCODE)"
++     Write-Host "  로그 확인: build/LLMWiki.log" -ForegroundColor Yellow
++     exit $LASTEXITCODE
++ }
++ 
++ # 5) PDF 복사
++ Write-Step "결과 복사"
++ Copy-Item -Path "build/LLMWiki.pdf" -Destination "LLMWiki.pdf" -Force
++ Write-OK "LLMWiki.pdf 생성됨 ($(Get-Item LLMWiki.pdf).Length / 1KB KB)"
++ 
++ # 6) 열기
++ if ($Open) {
++     Write-Step "PDF 열기"
++     Invoke-Item "LLMWiki.pdf"
++ }
++ 
++ Write-Host "`n============================================================"
++ Write-Host "  빌드 완료!" -ForegroundColor Green
++ Write-Host "============================================================`n"
