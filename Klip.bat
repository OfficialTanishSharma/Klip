@echo off
title Klip — AI Clipboard Manager
cd /d "%~dp0"
python src\klip_panel.py
if %errorlevel% neq 0 pause
