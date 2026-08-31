@echo off
title CoRobićW - Serwer Testowy
echo ==================================================
echo  Uruchamianie lokalnego serwera (http://localhost:8080)
echo  Katalog bazowy: /public
echo  Zamknij to okno, aby wylaczyc serwer.
echo ==================================================
python -m http.server 8080 --directory public
pause
