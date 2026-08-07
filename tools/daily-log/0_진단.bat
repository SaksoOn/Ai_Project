@echo off
rem ASCII only. cmd reads .bat in the system OEM codepage (cp949 here), so any
rem Korean text saved as UTF-8 gets parsed as garbage commands. Korean output
rem comes from run.py instead, which handles the console codepage itself.
rem "cd /d" is required: plain "cd" does not switch drives in cmd.
cd /d "%~dp0"

python run.py doctor --verbose %*
echo.
pause
