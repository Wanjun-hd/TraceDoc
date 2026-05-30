@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动小溯医生系统...
python -m streamlit run web.py
pause
