@echo off
rem ============================================================
rem LLMWiki PDF 鍮뚮뱶 ?ㅽ겕由쏀듃 (Windows)
rem ?ъ쟾 以鍮? MiKTeX(https://miktex.org) ?먮뒗 TeX Live ?ㅼ튂 ?꾩닔
rem MiKTeX ?ㅼ튂 ??"?먮룞 ?⑦궎吏 ?ㅼ튂: Yes" 沅뚯옣
rem ============================================================
chcp 65001 >nul
echo.
echo ============================================================
echo  LLMWiki Technical Specification PDF Build
echo ============================================================
echo.
rem 1) latexmk 議댁옱 ?뺤씤
where latexmk >nul 2>&1
if errorlevel 1 (
echo [?ㅻ쪟] latexmk瑜?李얠쓣 ???놁뒿?덈떎.
echo.
echo MiKTeX/TeX Live媛 ?ㅼ튂?섏뼱 ?덈뒗吏, PATH???ы븿?섏뼱 ?덈뒗吏 ?뺤씤?섏꽭??
echo MiKTeX: https://miktex.org/download
echo TeX Live: https://tug.org/texlive/
echo.
pause
exit /b 1
)
rem 2) LuaLaTeX ?붿쭊 ?뺤씤 (?고듃 泥섎━??媛???덉젙??
where lualatex >nul 2>&1
if errorlevel 1 (
echo [寃쎄퀬] lualatex 誘몃컻寃?- pdfLaTeX濡??쒕룄?⑸땲??(?고듃 ?먮윭 媛??.
set LATEX_ENGINE=-pdf
) else (
echo [?뺣낫] LuaLaTeX ?붿쭊 ?ъ슜 (沅뚯옣).
set LATEX_ENGINE=-lualatex
)
echo.
echo [1/3] ?고듃 罹먯떆 媛깆떊 (理쒖큹 1?뚮쭔 ?꾩슂)...
luaotfload-tool --update >nul 2>&1
echo [2/3] 硫붿씤 臾몄꽌 而댄뙆??(3-pass + bibtex)...
echo.
rem 鍮뚮뱶 ?붾젆?좊━ ?앹꽦
if not exist build mkdir build
rem latexmk ?ㅽ뻾
latexmk %LATEX_ENGINE% -interaction=nonstopmode -halt-on-error -file-line-error -synctex=1 -output-directory=build LLMWiki.tex
if errorlevel 1 (
echo.
echo [?ㅽ뙣: latexmk ?ㅽ뻾 以??ㅻ쪟 諛쒖깮.
echo 鍮뚮뱶 濡쒓렇瑜??뺤씤?섏꽭?? build/LLMWiki.log
pause
exit /b 1
)
echo.
echo [3/3] PDF 蹂듭궗 諛??꾨즺...
copy /y build\LLMWiki.pdf LLMWiki.pdf >nul
echo.
echo ============================================================
echo  鍮뚮뱶 ?깃났!  LLMWiki.pdf ?앹꽦??++ echo ============================================================
echo.
rem PDF ?먮룞 ?닿린 (?좏깮)
if "%1"=="--open" (
start "" LLMWiki.pdf
) else (
echo PDF ?닿린:  start LLMWiki.pdf
echo           ?먮뒗  .\build_pdf.bat --open
)
pause

