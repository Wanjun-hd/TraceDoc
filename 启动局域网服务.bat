@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在启动 TraceDoc 后端和前端（局域网模式）...
echo.
echo 后端监听: 0.0.0.0:8000
echo 前端监听: 0.0.0.0:8501
echo.
echo 如果局域网其他电脑无法访问，请检查 Windows 防火墙是否允许 Python / 8000 / 8501 端口入站。
echo.

start "TraceDoc Backend" cmd /k python -m uvicorn backend:app --host 0.0.0.0 --port 8000
timeout /t 3 >nul
start "TraceDoc Frontend" cmd /k python -m streamlit run web.py --server.address 0.0.0.0 --server.port 8501 --server.headless true

echo.
echo 已启动。请在本机运行 ipconfig 查看 IPv4 地址。
echo 局域网访问格式:
echo   前端: http://你的IPv4地址:8501
echo   后端: http://你的IPv4地址:8000
echo.
pause
