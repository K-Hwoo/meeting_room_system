"""
管理者用の meeting_room_manager.py(stdio, 全体 CRUD) とは別のサーバー。
同じDBを参照するが、書き込み系のツール(add/update/delete)は意図的に公開しない。

ローカルで実行：
    python read_mcp_server.py
    -> http://0.0.0.0:8001/mcp
"""

import os
from typing import Optional
from fastmcp import FastMCP
import db_logic as db

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.environ.get(
    "MEETING_ROOM_DB_PATH",
    os.path.join(_SCRIPT_DIR, "meeting_room.db"),
)
PORT = int(os.environ.get("PORT", "8001"))

mcp = FastMCP("meeting-room-read")

def _get_conn():
    return db.get_connection(DB_PATH)

@mcp.tool()
def list_reservations(
    # room_id: Optional[int] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    予約リストを取得する。フィルタはすべて任意で、指定しなければ全件取得する。

    ユーザーが "明日の午前10時から11時まで予約可能？"のように特定の時間帯を尋ねる場合、
    dateでその一日の予約を照会した後、その時間帯と重複するものがあるかどうかを直接比較して回答する。

    ユーザーが "来週の会議はいくつか？"のように期間を尋ねる場合、
    dateの代わりにstart_date/end_dateを使ってその期間の開始日と終了日を今日の日付を基準に
    計算して渡す。 (例: 今日が2026-08-19水曜日で"来週"と尋ねた場合
    start_date="2026-08-24"(来週月曜日), end_date="2026-08-30"(来週日曜日) のように)
    
    Args:
        room_id: 特定の会議室のみを照会したい場合
        date: 特定の一日のみを照会する場合, "YYYY-MM-DD" 形式
        start_date: 期間照会の開始日 "YYYY-MM-DD"
        end_date: 期間照会の終了日 "YYYY-MM-DD"
        category: 特定のカテゴリのみを照会したい場合 ("接客"/"面接"/"会議"/"自由")

    Returns:
        {"success": true, "reservations": [{"id":..,"title":..,
        "start_time":..,"end_time":..,"category":..,"description":..}, ...]}
        
        予約個数を知りたい場合は reservations リストの長さを数えて答える。
    """
    conn = _get_conn()
    try:
        return db.list_reservations(
            conn, date=date, start_date=start_date, end_date=end_date, category=category
        )
        
    finally:
        conn.close()

# @mcp.tool()
# def list_rooms() -> dict:
#     """
#     登録された会議室のリストを取得する。

#     Returns:
#         {"success": true, "rooms": [{"id":1,"name":"...","created_at":"..."}, ...]}
#     """
    
#     conn = _get_conn()
#     try:
#         return db.list_rooms(conn)
#     finally:
#         conn.close()


if __name__ == "__main__":
    mcp.run(transport="sse", port=PORT)