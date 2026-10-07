@echo off
echo Starting AI Story Rewriter...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%
)
pause
