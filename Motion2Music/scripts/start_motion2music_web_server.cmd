@echo off
setlocal

set PORT=%1
if "%PORT%"=="" set PORT=8132

set LOG_DIR=outputs\web_pipeline\server_logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set STDOUT_LOG=%LOG_DIR%\server_%PORT%_stdout.log
set STDERR_LOG=%LOG_DIR%\server_%PORT%_stderr.log

set PYTHONUNBUFFERED=1

echo [%date% %time%] starting Motion2Music web server on port %PORT%>> "%STDOUT_LOG%"
".\.venv\Scripts\python.exe" -u scripts\motion2music_web_server.py --host 127.0.0.1 --port %PORT% 1>> "%STDOUT_LOG%" 2>> "%STDERR_LOG%"
