# MCP 서버 자동 실행 스크립트
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$env:MCP_MODE="dify"
$env:PORT="8001"

$env:GOOGLE_SERVICE_ACCOUNT_FILE=Join-Path $scriptDir "calendar_credentials.json"
$env:GOOGLE_CALENDAR_ID="2fa6d138217a4549429b1bf0d716e78e6350cafb9db05f45f97deec32cfc5dfe@group.calendar.google.com"

python (Join-Path $scriptDir "mcp_server.py")
