@echo off
chcp 65001 > nul
echo ================================
echo  ì¿ íŒ¡ Ad Pipeline (?„ì²´ ?ë™ ?¤í–‰)
echo  ?¤ìš´ë¡œë“œ + ?°ì´?°ì²˜ë¦?+ GitHub Push
echo ================================
echo.

where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python
) else (
    echo [ERROR] Python???¤ì¹˜?˜ì? ?Šì•˜ê±°ë‚˜ PATH???±ë¡?˜ì? ?Šì•˜?µë‹ˆ??
    echo Python ?¤ì¹˜ ???¤ì‹œ ?¤í–‰??ì£¼ì„¸??
    pause
    exit /b 1
)

if not exist "%~dp0.env" (
    echo [ERROR] .env ?Œì¼???†ìŠµ?ˆë‹¤. github_setup.bat ë¨¼ì? ?¤í–‰?˜ì„¸??
    pause
    exit /b 1
)

for /f "usebackq tokens=1,2 delims==" %%a in ("%~dp0.env") do (
    set %%a=%%b
)

echo [1/3] ì¿ íŒ¡ raw ?°ì´???ë™ ?¤ìš´ë¡œë“œ ì¤?..
echo.
"%PYTHON%" "%~dp0coupang_download.py"
if errorlevel 1 (
    echo.
    echo [ê²½ê³ ] ?ë™ ?¤ìš´ë¡œë“œ ?¤íŒ¨. raw ?´ë”ë¥?ì§ì ‘ ?•ì¸?˜ì„¸??
    echo  ê³„ì† ì§„í–‰?©ë‹ˆ??..
    echo.
)

echo [2/3] data.csv ?ì„± ì¤?..
echo.
"%PYTHON%" "%~dp0coupang_pipeline.py"
if errorlevel 1 (
    echo [ERROR] data.csv ?ì„± ?¤íŒ¨.
    pause
    exit /b 1
)

echo.
echo [3/3] GitHub ?…ë¡œ??ì¤?..
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
    echo data.csv ?…ë¡œ???„ë£Œ
) else (
    echo data.csv ë³€ê²½ì—†??- ê±´ë„ˆ?€
)

git add index.html
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "index update %date% %time%"
    git push origin main
    if errorlevel 1 git push origin main --force-with-lease
    echo index.html ?…ë¡œ???„ë£Œ
) else (
    echo index.html ë³€ê²½ì—†??- ê±´ë„ˆ?€
)

echo.
echo ================================
echo  [?„ë£Œ] ëª¨ë“  ?‘ì—…???„ë£Œ?˜ì—ˆ?µë‹ˆ??
echo ================================
echo.
pause
