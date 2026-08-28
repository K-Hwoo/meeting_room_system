import os
import sys
import sqlite3
from typing import Optional
 
from fastmcp import FastMCP

import db_logic as db

DB_PATH = os.environ.get(
    "MEETING_ROOM_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "meeting_room.db"),
)

SQL_INIT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database_setting.sql")

def _init_db_if_needed():
    if os.path.exists(DB_PATH):
        return
    
    if not os.path.exists(SQL_INIT_PATH):
        print(f"[Warning] 初期化用SQLファイルがありません: {SQL_INIT_PATH}", file=sys.stderr)
        return
    
    with open(SQL_INIT_PATH, "r", encoding="utf-8") as f:
        sql_script = f.read()
        
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(sql_script)
        conn.commit()
        print(f"[Info] DBを初期化しました: {DB_PATH}", file=sys.stderr)
    finally:
        conn.close()

_init_db_if_needed()
mcp = FastMCP("meeting-room-manager")

def _get_conn() -> sqlite3.Connection:
    return db.get_connection(DB_PATH)


@mcp.tool()
def add_reservation(
    title: str,
    start_time: str,
    end_time: str,
    category: str,
    description: str = "",
) -> dict :
    """
    会議の予約を追加
    
    Args:
        title: 会議のタイトル
        start_time: 開始時間。 "YYYY-MM-DD HH:MM" 形式 (例: "2026-08-21 14:00")
        end_time: 終了時間。 start_timeと同じ形式。
        category: 必ず「会議」「接客」「面接」「自由」のいずれか。
                  チャット内容をもとに判断するが、どれであるか曖昧な場合は「自由」を使用する。
        description: 会議に関する追加説明。 (任意)
 
    Returns:
        成功時 {"success": true, "reservation": {...}}
        失敗時 {"success": false, "error": "エラーコード", ...関連情報}
        可能なエラーコード:
          - missing_fields: 必須項目ぬけ。
          - invalid_category: カテゴリが4つの値のうち一つではない。
          - invalid_datetime_format: 時間形式が間違っている。
          - end_before_start: 終了時間が開始時間より早い。
          - time_overlap: 会議室に重ねる時間帯の予約が既に存在する。
    """
    conn = _get_conn()
    try:
        return db.add_reservation(
            conn, title, start_time, end_time, category, description or None
        )
    finally:
        conn.close()

@mcp.tool()
def update_reservation(
    reservation_id: int,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """
    会議の予約を更新
    
    値を入力されたフィールドだけが更新され、入力されなかったフィールドはそのまま保持される。
 
    Args:
        reservation_id: 修正する予約のID (list_reservationsでまず確認してから修正すること)
        title: 新しいタイトル (変更する場合のみ)
        start_time: 新しい開始時間、"YYYY-MM-DD HH:MM" (変更する場合のみ)
        end_time: 新しい終了時間 (変更する場合のみ)
        category: 新しいカテゴリ、「会議」「接客」「面接」「自由」のいずれか (変更する場合のみ)
        description: 新しい説明 (変更する場合のみ)
 
    Returns:
        成功時 {"success": true, "reservation": {...}}
        失敗時 {"success": false, "error": "エラーコード", ...関連情報}
        エラーコードのリストは add_reservationと同じ (missing_fieldsは除く)。
        追加で reservation_not_found: 存在しない reservation_id
    """
    conn = _get_conn()
    try:
        return db.update_reservation(
            conn,
            reservation_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            category=category,
            description=description,
        )
    finally:
        conn.close()

@mcp.tool()
def delete_reservation(reservation_id: int) -> dict:
    """
    会議の予約をキャンセル
    
     Args:
        reservation_id: 削除する予約のID
 
    Returns:
        成功時 {"success": true, "deleted": {...削除された予約情報...}}
        失敗時 {"success": false, "error": "reservation_not_found", "reservation_id": ...}
    """
    conn = _get_conn()
    
    try:
        return db.delete_reservation(conn, reservation_id)
    finally:
        conn.close()

@mcp.tool()
def list_reservations(
    # room_id: Optional[int] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict :
    """
    すべての予約をみる
    
    フィルターはすべて選択項目であり、渡さなければ全体を照会する。
 
    Args:
        date: 特定の日だけ照会したいとき、"YYYY-MM-DD" 形式
        start_date: 照会開始日 "YYYY-MM-DD" (例: "今週", "来月" などの期間質問に使用.
                    終了日が分からない場合は end_date と同じ値として扱われる)
        end_date: 照会終了日 "YYYY-MM-DD" (start_date と組み合わせて範囲を形成する)
        category: 特定のカテゴリだけ照会したいとき (「会議」「接客」「面接」「自由」)
 
    Returns:
        {"success": true, "reservations": [予約リスト]}
 
    参考: dateを渡すとその日だけ照会され、start_date/end_dateは無視される。
          期間を尋ねる質問(例: "来週会議は何件ある?")には、
          dateの代わりにstart_date/end_dateでその期間の開始日/終了日を計算して渡すこと。
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
#     会議室のリストをみる
    
#     Returns:
#         {"success": true, "rooms": [{"id":1,"name":"...","created_at":"..."}, ...]}
#     """
#     conn = _get_conn()
    
#     try:
#         return db.list_rooms(conn)
#     finally:
#         conn.close()

if __name__ == "__main__":
    mcp.run(transport="stdio")