@echo off
rem ASCII only -- see 0_진단.bat for why.
cd /d "%~dp0"

python run.py collect %*
if errorlevel 1 goto :fail

start "" "%~dp0queue"
echo.
pause
exit /b 0

:fail
echo.
python -c "print('\n  실패했습니다. [0_진단.bat] 을 실행하면 원인을 알려줍니다.\n')"
pause
exit /b 1
