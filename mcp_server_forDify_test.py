"""
read_mcp_server.py가 로컬에서 정상 응답하는지 확인하는 테스트 스크립트.

사용법:
  1. 터미널 A: python read_mcp_server.py         (서버 실행, 켜둔 채로 둠)
  2. 터미널 B: python test_read_mcp_client.py    (이 스크립트 실행)
"""

import asyncio
from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8001/mcp"

async def main():
    async with Client(SERVER_URL) as client:
        print("=== 사용 가능한 툴 목록 ===")
        tools = await client.list_tools()
        for t in tools:
            print("-", t.name)

        # print()
        # print("=== list_rooms 호출 ===")
        # result = await client.call_tool("list_rooms", {})
        # for room in result.data.get("rooms", []):
        #     print(room)

        print()
        print("=== list_reservations 호출 (전체) ===")
        result = await client.call_tool("list_reservations", {})
        for reservation in result.data.get("reservations", []):
            print(reservation)


if __name__ == "__main__":
    asyncio.run(main())