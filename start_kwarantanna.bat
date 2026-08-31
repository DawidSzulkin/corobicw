@echo off
title Kwarantanna PRO - Serwer Mapowania
echo ===================================================
echo  Uruchamianie serwera Kwarantanny PRO...
echo  Panel: http://localhost:8081
echo ===================================================
start http://localhost:8081
python scripts\tools\quarantine_server.py
pause
