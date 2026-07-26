++ @echo off
++ rem ============================================================
++ rem LLMWiki PDF 빌드 스크립트 (Windows)
++ rem 사전 준비: MiKTeX(https://miktex.org) 또는 TeX Live 설치 필수
++ rem MiKTeX 설치 시 "자동 패키지 설치: Yes" 권장
++ rem ============================================================
++ 
++ chcp 65001 >nul
++ 
++ echo.
++ echo ============================================================
++ echo  LLMWiki Technical Specification PDF Build
++ echo ============================================================
++ echo.
++ 
++ rem 1) latexmk 존재 확인
++ where latexmk >nul 2>&1
++ if errorlevel 1 (
++     echo [오류] latexmk를 찾을 수 없습니다.
++     echo.
++     echo MiKTeX/TeX Live가 설치되어 있는지, PATH에 포함되어 있는지 확인하세요.
++     echo MiKTeX: https://miktex.org/download
++     echo TeX Live: https://tug.org/texlive/
++     echo.
++     pause
++     exit /b 1
++ )
++ 
++ rem 2) LuaLaTeX 엔진 확인 (폰트 처리에 가장 안정적)
++ where lualatex >nul 2>&1
++ if errorlevel 1 (
++     echo [경고] lualatex 미발견 - pdfLaTeX로 시도합니다 (폰트 에러 가능).
++     set LATEX_ENGINE=-pdf
++ ) else (
++     echo [정보] LuaLaTeX 엔진 사용 (권장).
++     set LATEX_ENGINE=-lualatex
++ )
++ 
++ echo.
++ echo [1/3] 폰트 캐시 갱신 (최초 1회만 필요)...
++ luaotfload-tool --update >nul 2>&1
++ 
++ echo [2/3] 메인 문서 컴파일 (3-pass + bibtex)...
++ echo.
++ 
++ rem 빌드 디렉토리 생성
++ if not exist build mkdir build
++ 
++ rem latexmk 실행
++ latexmk %LATEX_ENGINE% -interaction=nonstopmode -halt-on-error -file-line-error -synctex=1 -output-directory=build LLMWiki.tex
++ 
++ if errorlevel 1 (
++     echo.
++     echo [실패: latexmk 실행 중 오류 발생.
++     echo 빌드 로그를 확인하세요: build/LLMWiki.log
++     pause
++     exit /b 1
++ )
++ 
++ echo.
++ echo [3/3] PDF 복사 및 완료...
++ copy /y build\LLMWiki.pdf LLMWiki.pdf >nul
++ 
++ echo.
++ echo ============================================================
++ echo  빌드 성공!  LLMWiki.pdf 생성됨
++ echo ============================================================
++ echo.
++ 
++ rem PDF 자동 열기 (선택)
++ if "%1"=="--open" (
++     start "" LLMWiki.pdf
++ ) else (
++     echo PDF 열기:  start LLMWiki.pdf
++     echo           또는  .\build_pdf.bat --open
++ )
++ 
++ pause
