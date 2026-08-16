# Installation & environment setup script for Windows PowerShell
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

python "$ScriptDir\install.py" $args
