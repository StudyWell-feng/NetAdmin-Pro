@echo off
chcp 65001 >nul
echo ============================================
echo   NetAdmin Pro - 以管理员身份启动
echo ============================================
echo.
powershell -Command "Start-Process python -ArgumentList '\"%~dp0net_admin.py\"' -Verb RunAs"
