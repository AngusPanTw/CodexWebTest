@echo off
chcp 65001 >nul
color 0B
title 台股創新高低比較查看器

REM 設定變數
set "PORT=8000"
set "URL=http://localhost:%PORT%"
set "PID_FILE=%~dp0.server_pid"

echo.
echo ================================================================
echo              台股創新高低比較查看器
echo              本地伺服器啟動工具
echo ================================================================
echo.

cd /d "%~dp0"

REM 檢查是否已有伺服器在執行
netstat -an | findstr ":%PORT%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [警告] 偵測到 Port %PORT% 已被使用
    echo.
    choice /c YN /m "是否要強制關閉現有伺服器並重新啟動？(Y/N)"
    if errorlevel 2 (
        echo 取消啟動
        pause
        exit /b 1
    )
    
    echo 正在關閉現有伺服器...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING"') do (
        taskkill /pid %%a /f >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

echo [步驟 1/4] 啟動 Python HTTP 伺服器...
echo 埠號: %PORT%
echo 路徑: %CD%

REM 啟動 Python 伺服器並記錄 PID
powershell -Command "& {$p = Start-Process -FilePath 'python' -ArgumentList '-m', 'http.server', '%PORT%' -WindowStyle Minimized -PassThru; $p.Id | Out-File -FilePath '%PID_FILE%' -Encoding ascii}"

if %errorlevel% neq 0 (
    echo [錯誤] 無法啟動 Python 伺服器
    echo 請確認已安裝 Python 並加入 PATH 環境變數
    pause
    exit /b 1
)

echo [步驟 2/4] 等待伺服器就緒...
timeout /t 3 /nobreak >nul

REM 驗證伺服器啟動
netstat -an | findstr ":%PORT%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 伺服器啟動失敗
    pause
    exit /b 1
)

echo [步驟 3/4] 轉換 Excel 檔案為 JSON...

REM 檢查 Excel 檔案
if not exist "output\*比較*.xlsx" (
    echo [警告] 找不到包含「比較」的 Excel 檔案
    echo 伺服器仍會啟動，但可能無法載入資料
    timeout /t 2 /nobreak >nul
    goto skip_convert
)

REM 執行轉換
python convert_excel_to_json.py

if %errorlevel% equ 0 (
    echo [成功] JSON 資料更新完成
) else (
    echo [警告] JSON 轉換遇到問題
    echo 建議檢查：
    echo - Excel 檔案是否存在
    echo - 檔案權限是否正確
    echo - Excel 檔案是否被其他程式開啟
    echo.
    echo 伺服器仍會啟動，但可能缺少資料
    timeout /t 3 /nobreak >nul
)

:skip_convert

echo [步驟 4/4] 開啟瀏覽器...
start "" "%URL%"

echo.
echo ================================================================
echo                     啟動成功！
echo ================================================================
echo 網址: %URL%
echo.
echo 功能說明:
echo - 查看台股創新高/創新低資料
echo - 支援日期篩選和股票代碼搜尋
echo - 點擊表格標題排序
echo - 自動計算漲跌幅
echo.
echo 操作說明:
echo - 按 Ctrl+C 或關閉視窗停止伺服器
echo - 重新執行此批次檔可重新載入資料
echo - 瀏覽器關閉後可重新開啟網址
echo ================================================================
echo.

REM 監控伺服器
if exist "%PID_FILE%" (
    for /f %%i in (%PID_FILE%) do set SERVER_PID=%%i
)

:monitor
echo [%date% %time:~0,8%] 伺服器運行中 (PID: %SERVER_PID%)
timeout /t 30 /nobreak >nul

REM 檢查伺服器狀態
tasklist /fi "pid eq %SERVER_PID%" 2>nul | findstr "%SERVER_PID%" >nul
if %errorlevel% neq 0 (
    echo [警告] 伺服器程序已結束
    goto cleanup
)
goto monitor

:cleanup
echo.
echo 正在清理資源...

REM 清理 PID 檔案並結束程序
if exist "%PID_FILE%" (
    for /f %%i in (%PID_FILE%) do (
        taskkill /pid %%i /f >nul 2>&1
    )
    del "%PID_FILE%" >nul 2>&1
)

REM 清理使用該埠的程序
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING" 2^>nul') do (
    taskkill /pid %%a /f >nul 2>&1
)

echo 伺服器已關閉
echo 謝謝使用！
echo.
pause
exit /b 0
