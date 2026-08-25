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

@mcp.tool()
def find_available_slots(
    date: str,
    duration_minutes: int,
    business_start: str = "09:00",
    business_end: str = "18:00",
) -> dict:
    """
    特定の日に空いている時間帯を探す。

    ユーザーが「空いてる時間ある?」と尋ねたら、暗算で予約の隙間を計算するのではなく
    このツールを使うこと。今日基準の相対的な日付(明日、来週火曜日など)は
    current_timeで確認した日付を基準に計算してから渡す。

    Args:
        date: 照会する日付, "YYYY-MM-DD" 形式
        duration_minutes: 必要な最小時間(分)。指定がなければ30を使う。
        business_start: 探索開始時刻, "HH:MM" 形式 (デフォルト 09:00)
        business_end: 探索終了時刻, "HH:MM" 形式 (デフォルト 18:00)

    Returns:
        {"success": true, "date": ..., "available_slots": [{"start":"HH:MM","end":"HH:MM","duration_minutes":N}, ...]}
        available_slots が空配列なら、その条件を満たす空き時間がないという意味。
    """
    conn = _get_conn()
    try:
        return db.find_available_slots(conn, date, duration_minutes, business_start, business_end)
    finally:
        conn.close()


@mcp.tool()
def count_reservations(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    予約件数を集計する。

    ユーザーが「今月会議何件?」「来週の予約いくつ?」のように件数を尋ねたら、
    list_reservationsで数を数えるのではなく、このツールで直接集計すること。

    Args:
        date: 特定の一日だけ集計, "YYYY-MM-DD"
        start_date, end_date: 期間集計, "YYYY-MM-DD"
        category: 特定のカテゴリだけ集計 ("接客"/"面接"/"会議"/"自由")

    Returns:
        {"success": true, "total": N, "by_category": {"会議": N, "接客": N, ...}}
    """
    conn = _get_conn()
    try:
        return db.count_reservations(conn, date=date, start_date=start_date, end_date=end_date, category=category)
    finally:
        conn.close()


@mcp.tool()
def get_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    予約データの詳細統計をまとめて取得する。「グラフで見せて」「傾向を教えて」
    「一番忙しい曜日は?」のような、単純な件数以上の分析が必要なときに使う
    (単純な件数だけなら count_reservations で十分)。

    Args:
        start_date, end_date: 集計期間, "YYYY-MM-DD"。両方省略すると全期間。
        category: 特定のカテゴリだけに絞りたい場合

    Returns:
        {
          "success": true, "total": N,
          "by_category": {"会議": N, ...},              カテゴリ別件数 → 円グラフ/棒グラフ向き
          "by_category_percent": {"会議": 45.5, ...},    カテゴリ別割合(%)
          "by_weekday": {"月": N, "火": N, ...},          曜日別件数 → 棒グラフ向き
          "by_hour": {"09:00": N, "10:00": N, ...},       開始時刻の時間帯別件数 → ピーク時間帯の把握、棒グラフ向き
          "daily_counts": {"2026-08-24": N, ...},         日別件数の推移 → 折れ線グラフ向き
          "average_duration_minutes": N                    平均所要時間(分)
        }
    """
    conn = _get_conn()
    try:
        return db.get_statistics(conn, start_date=start_date, end_date=end_date, category=category)
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