@echo off
chcp 65001 > nul
echo ================================
echo  쿠팡 Ad Pipeline (전체 자동 실행)
echo  다운로드 + 데이터처리 + GitHub Push
echo ================================
echo.

where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python
) else (
    echo [ERROR] Python이 설치되지 않았거나 PATH에 등록되지 않았습니다.
    echo Python 설치 후 다시 실행해 주세요.
    pause
    exit /b 1
)

if not exist "%~dp0.env" (
    echo [ERROR] .env 파일이 없습니다. github_setup.bat 먼저 실행하세요.
    pause
    exit /b 1
)

for /f "usebackq tokens=1,2 delims==" %%a in ("%~dp0.env") do (
    set %%a=%%b
)

echo [1/3] 쿠팡 raw 데이터 자동 다운로드 중...
echo.
"%PYTHON%" "%~dp0coupang_download.py"
if errorlevel 1 (
    echo.
    echo [경고] 자동 다운로드 실패. raw 폴더를 직접 확인하세요.
    echo  계속 진행합니다...
    echo.
)

echo [2/3] data.csv 생성 중...
echo.
"%PYTHON%" "%~dp0coupang_pipeline.py"
if errorlevel 1 (
    echo [ERROR] data.csv 생성 실패.
    pause
    exit /b 1
)

echo.
echo [3/3] GitHub 업로드 중...
cd /d "%~dp0"

git config core.editor "true"
git stash -- index.html 2>nul
git pull origin main --allow-unrelated-histories -X ours 2>nul
git stash pop 2>nul

git add output\data.csv
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "data update %date% %time%"
    git push origin main
    if errorlevel 1 git push origin main --force-with-lease
    echo data.csv 업로드 완료
) else (
    echo data.csv 변경없음 - 건너뜀
)

git add index.html
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "index update %date% %time%"
    git push origin main
    if errorlevel 1 git push origin main --force-with-lease
    echo index.html 업로드 완료
) else (
    echo index.html 변경없음 - 건너뜀
)

echo.
echo ================================
echo  [완료] 모든 작업이 완료되었습니다.
echo ================================
echo.
pause
