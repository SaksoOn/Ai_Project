@echo off
rem ASCII only -- see 0_진단.bat for why.
cd /d "%~dp0"

python run.py weekly %*
echo.
pause
