@echo off
rem Double-click to start the web UI, then open http://127.0.0.1:5000
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
rem Open the browser after a short delay so the server is up first
start "" /b cmd /c "timeout /t 2 >nul & start http://127.0.0.1:5000"
python -m ytconvert --web
