@echo off
chcp 65001 >nul
title 智学方舟 - 一键启动

REM 双击即用：同时拉起后端(8000)与前端(5173)两个服务窗口
REM 停止服务：关闭对应窗口，或在窗口内按 Ctrl+C

start "后端 FastAPI (8000)" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --port 8000"
timeout /t 2 /nobreak >nul
start "前端 Vite (5173)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo   两个服务正在启动（约 5 秒就绪）：
echo     前端  http://localhost:5173   ← 平台入口，浏览器打开这个
echo     后端  http://127.0.0.1:8000/docs
echo.
echo   停止：关闭两个黑色服务窗口（或窗口内 Ctrl+C）
echo.
echo   本窗口可以随手关掉，不影响服务运行。
pause
