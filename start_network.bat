@echo off
title CloakShare Multi-Device Server
chcp 65001 > nul
echo ========================================================
echo        CloakShare - Multi-Device Network Launcher
echo ========================================================
python scripts\start_network.py
echo.
pause
