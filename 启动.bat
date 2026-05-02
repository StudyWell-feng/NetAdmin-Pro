@echo off
chcp 65001 >nul
echo 正在启动 NetAdmin Pro...
python "%~dp0net_admin.py"
if errorlevel 1 (
    echo.
    echo 启动失败，请确保已安装 Python 和 customtkinter
    echo 运行: pip install customtkinter pillow
    pause
)
