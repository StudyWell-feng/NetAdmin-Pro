@echo off
chcp 65001 >nul
echo ============================================
echo   NetAdmin Pro 打包工具
echo ============================================
echo.
echo 正在安装 PyInstaller...
pip install pyinstaller -q

echo.
echo 正在打包为单文件 EXE...
pyinstaller --onefile --windowed --name "NetAdmin Pro" ^
    --add-data "config.json;." ^
    net_admin.py

echo.
if exist "dist\NetAdmin Pro.exe" (
    echo ✅ 打包成功！
    echo 输出文件: dist\NetAdmin Pro.exe
    explorer dist
) else (
    echo ❌ 打包失败，请查看错误信息
)
pause
