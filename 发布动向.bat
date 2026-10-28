@echo off
cd /d "%~dp0"
title 发布产驹动向

echo.
echo  ================================
echo    发布产驹动向（次走 / 近况）
echo  ================================
echo.
echo  [1/3] 读取 Excel 里的「次走/近况」列 ...
echo.

py sync_moves.py
if errorlevel 1 goto err

echo.
echo  [2/3] 检查有没有新内容 ...
git add moves.js >nul 2>&1
git diff --cached --quiet
if not errorlevel 1 goto nochange

echo.
echo  [3/3] 正在发布到网站 ...
echo.
git pull --rebase --autostash
if errorlevel 1 goto err
git commit -m "update progeny moves"
if errorlevel 1 goto err
git push
if errorlevel 1 goto err

echo.
echo  ================================
echo    发布成功！
echo    网站大约 1 分钟后自动更新。
echo    网址：https://epimome.cn
echo  ================================
echo.
pause
exit /b 0

:nochange
echo.
echo  动向没有变化，不需要发布。
echo  （如果确实改了，检查一下是不是改在「次走/近况」这一列里）
echo.
pause
exit /b 0

:err
echo.
echo  ================================
echo    出错了 —— 把上面这段文字发给我
echo  ================================
echo.
pause
exit /b 1
