@echo off
echo Killing all Python servers on ports 8000-8016...

taskkill /F /PID 50940 2>nul
taskkill /F /PID 89048 2>nul
taskkill /F /PID 53192 2>nul
taskkill /F /PID 68300 2>nul
taskkill /F /PID 26256 2>nul
taskkill /F /PID 61492 2>nul
taskkill /F /PID 76400 2>nul
taskkill /F /PID 2932 2>nul
taskkill /F /PID 56520 2>nul
taskkill /F /PID 54524 2>nul
taskkill /F /PID 79424 2>nul
taskkill /F /PID 2496 2>nul
taskkill /F /PID 33596 2>nul
taskkill /F /PID 8668 2>nul
taskkill /F /PID 41080 2>nul
taskkill /F /PID 90756 2>nul
taskkill /F /PID 14344 2>nul

echo All servers stopped!
pause