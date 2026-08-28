cd C:\경로\회의실폴더
$env:MCP_MODE="dify"
$env:PORT="8001"
python mcp_server.py

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

npx @modelcontextprotocol/inspector
