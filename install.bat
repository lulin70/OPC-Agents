@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo   OPC-Agents 一键安装脚本 (Windows)
echo ========================================
echo.

echo 📋 检查 Python 版本...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未找到 Python
    echo    请访问 https://www.python.org/downloads/ 下载安装
    echo    安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo    当前 Python 版本：%PYVER%

for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if %MAJOR% LSS 3 (
    echo ❌ 错误：需要 Python 3.9 或更高版本
    pause
    exit /b 1
)
if %MAJOR% EQU 3 if %MINOR% LSS 9 (
    echo ❌ 错误：需要 Python 3.9 或更高版本
    pause
    exit /b 1
)
echo ✓ Python 版本符合要求
echo.

echo 📦 创建 Python 虚拟环境...
if not exist "venv" (
    python -m venv venv
    echo ✓ 虚拟环境创建成功
) else (
    echo ⚠ 虚拟环境已存在，跳过
)
echo.

echo 🔌 激活虚拟环境...
call venv\Scripts\activate.bat
echo ✓ 虚拟环境已激活
echo.

echo ⬆️  升级 pip...
pip install --upgrade pip
echo ✓ pip 升级完成
echo.

echo 📥 安装 Python 依赖包...
if exist "requirements.txt" (
    pip install -r requirements.txt
    echo ✓ 依赖包安装完成
) else (
    echo ❌ 错误：找不到 requirements.txt
    pause
    exit /b 1
)
echo.

echo ⚙️  创建配置文件...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo ✓ 配置文件 .env 创建成功
        echo ⚠  请编辑 .env 配置 API 密钥
    ) else (
        echo ✓ 默认配置文件 .env 已创建
        echo ⚠  请编辑 .env 配置 API 密钥
    )
) else (
    echo ⚠  配置文件 .env 已存在，跳过
)
echo.

echo 📁 创建数据目录...
if not exist "deliverables" mkdir deliverables
if not exist "data" mkdir data
if not exist "data\schedules" mkdir data\schedules
if not exist "data\completions" mkdir data\completions
if not exist "data\context" mkdir data\context
if not exist "data\checkpoints" mkdir data\checkpoints
if not exist "data\loop_progress" mkdir data\loop_progress
if not exist "data\consensus_logs" mkdir data\consensus_logs
if not exist "data\marketplace" mkdir data\marketplace
if not exist "data\feedback" mkdir data\feedback
if not exist "data\knowledge" mkdir data\knowledge
if not exist "data\notifications" mkdir data\notifications
if not exist "data\custom_skills" mkdir data\custom_skills
if not exist "plugins" mkdir plugins
if not exist "data\workflows" mkdir data\workflows
if not exist "logs" mkdir logs
if not exist "output" mkdir output
echo ✓ 数据目录创建完成
echo.

echo ========================================
echo ✅ 安装完成！
echo ========================================
echo.
echo 📝 下一步操作：
echo.
echo 1. 配置 API 密钥（可选，不配置也能用模板模式）：
echo    notepad .env
echo.
echo 2. 启动服务：
echo    start.bat
echo.
echo 3. 访问系统：
echo    http://localhost:8501
echo.
echo ========================================
echo.

set /p REPLY="是否现在启动服务？(y/n) "
if /i "%REPLY%"=="y" (
    echo 🚀 启动 OPC-Agents...
    streamlit run frontend/app.py
)

pause
