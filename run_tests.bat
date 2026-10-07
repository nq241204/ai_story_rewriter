@echo off
echo Running AI Story Rewriter tests...
python -m unittest discover tests -v
if %ERRORLEVEL% EQU 0 (
    echo.
    echo All tests passed!
) else (
    echo.
    echo Some tests failed!
)
pause
