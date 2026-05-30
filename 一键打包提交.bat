@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PROJECT_NAME=yuandaima"
set "TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "SRC_DIR=%~dp0."
set "TMP_ROOT=%TEMP%\%PROJECT_NAME%_pack_%RANDOM%%RANDOM%"
set "STAGE_DIR=%TMP_ROOT%\%PROJECT_NAME%"
set "ZIP_FILE=%~dp0%PROJECT_NAME%_submit_%TIMESTAMP%.zip"

echo ===== 一键打包开始 =====
echo.
echo [1/4] 创建临时目录...
if exist "%TMP_ROOT%" rmdir /s /q "%TMP_ROOT%"
mkdir "%STAGE_DIR%"
if errorlevel 1 (
    echo [ERROR] 无法创建临时目录：%STAGE_DIR%
    goto :END
)

echo [2/4] 复制项目文件...
robocopy "%SRC_DIR%" "%STAGE_DIR%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
    echo [ERROR] 文件复制失败，robocopy 错误码：%RC%
    goto :CLEANUP
)

echo [2.5/4] 删除不需要打包的缓存/临时文件...
for %%D in (__pycache__ .git .idea .pytest_cache .mypy_cache .ruff_cache .venv venv .cursor) do (
    if exist "%STAGE_DIR%\%%D" rmdir /s /q "%STAGE_DIR%\%%D"
)
for /r "%STAGE_DIR%" %%F in (*.pyc *.pyo *.log *.tmp *.bak) do del /f /q "%%F" >nul 2>nul
for %%F in (".DS_Store" "Thumbs.db" "desktop.ini" ".local_rag_index.pkl" "audit_log.jsonl") do (
    for /r "%STAGE_DIR%" %%G in (%%~F) do del /f /q "%%G" >nul 2>nul
)

echo [3/4] 生成 zip 压缩包...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Compress-Archive -Path '%STAGE_DIR%\*' -DestinationPath '%ZIP_FILE%' -Force; exit 0 } catch { Write-Host ('[ERROR] ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo [ERROR] 压缩失败，请检查 PowerShell 权限或文件占用。
    goto :CLEANUP
)

echo [4/4] 清理临时目录...

:CLEANUP
if exist "%TMP_ROOT%" rmdir /s /q "%TMP_ROOT%"

if exist "%ZIP_FILE%" (
    echo.
    echo [OK] 打包完成：%ZIP_FILE%
) else (
    echo.
    echo [FAIL] 未生成压缩包，请根据上面的错误信息排查。
)

:END
echo.
echo 按任意键退出...
pause >nul
endlocal
