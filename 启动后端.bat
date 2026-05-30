@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动 TraceDoc 后端服务...
python -m uvicorn backend:app --host 127.0.0.1 --port 8000
pause
