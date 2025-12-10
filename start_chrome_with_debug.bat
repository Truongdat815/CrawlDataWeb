@echo off
REM Script để khởi động Chrome với remote debugging port
REM Cho phép scraper kết nối đến Chrome đang chạy

echo 🚀 Đang khởi động Chrome với remote debugging port 9222...
echo 💡 Chrome sẽ chạy với các tab và profile hiện tại của bạn
echo 💡 Scraper có thể kết nối đến Chrome này để scrape

REM Tìm Chrome executable
set CHROME_PATH=
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
) else (
    echo ❌ Không tìm thấy Chrome!
    echo 💡 Vui lòng cài đặt Chrome từ https://www.google.com/chrome/
    pause
    exit /b 1
)

REM Khởi động Chrome với remote debugging port
start "" "%CHROME_PATH%" --remote-debugging-port=9222

echo ✅ Chrome đã được khởi động với remote debugging port 9222
echo 💡 Bây giờ bạn có thể chạy scraper: python main.py
echo 💡 Scraper sẽ kết nối đến Chrome này và dùng các tab đang mở
pause
