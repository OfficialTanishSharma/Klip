@echo off
title Klip — AI Clipboard Manager
cd /d "%~dp0"
start "" pythonw src\klip_panel.py
if %errorlevel% neq 0 (
    echo GUI failed to start, showing error...
    python src\klip_panel.py
    pause
)
