@echo off
title MRX Bot Launcher
color 0A

:start
echo ===================================================
echo               MRX Bot is starting...
echo ===================================================
echo.

:: تثبيت المكتبات المطلوبة تلقائياً
echo [*] Checking and installing requirements...
py -m pip install -r requirements.txt --quiet
echo [+] Requirements ready!
echo.

:: مزامنة الأوامر (Slash Commands) تتم تلقائياً من داخل البوت
:: عند كل تشغيل البوت يعمل sync لأوامر السلاش

:: تشغيل البوت
echo [*] Starting bot...
echo.
py main.py

:: إذا وقف البوت (كراش أو خطأ) يعيد التشغيل تلقائياً بعد 5 ثواني
echo.
echo ===================================================
echo    [!] Bot stopped! Restarting in 5 seconds...
echo    [!] Press CTRL+C to cancel restart.
echo ===================================================
timeout /t 5 /nobreak >nul
goto start
