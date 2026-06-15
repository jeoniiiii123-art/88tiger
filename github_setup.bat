@echo off
chcp 949 > nul
echo ================================
echo  GitHub 최초 설정 (1회만 실행)
echo ================================
echo.

if not exist "%~dp0.env" (
    echo [ERROR] .env 파일이 없습니다.
    echo .env 파일을 생성하고 GIT_USER, GIT_TOKEN, GIT_EMAIL, REPO_URL 을 입력하세요.
    pause
    exit /b
)

for /f "tokens=1,2 delims==" %%a in (%~dp0.env) do (
    set %%a=%%b
)

cd /d "%~dp0"

echo [1] git 초기화...
git init
git config user.email "%GIT_EMAIL%"
git config user.name  "%GIT_USER%"

echo [2] GitHub 원격 저장소 연결...
git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo [3] 첫 번째 commit & push...
git add .
git commit -m "init: coupang ad dashboard"
git branch -M main
git push -u origin main

echo.
echo [완료] GitHub 설정 완료.
echo 다음부터는 run_manual.bat 또는 run.bat 을 사용하세요.
echo.
pause