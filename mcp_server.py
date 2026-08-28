"""
会議室管理システム - 統合MCPサーバー
"""

import os
import sys
import sqlite3
from typing import Optional

from fastmcp import FastMCP

import db_logic as db

MODE = os.environ.get("MCP_MODE", "admin")  # "admin" または "dify"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.environ.get(
    "MEETING_ROOM_DB_PATH",
    os.path.join(_SCRIPT_DIR, "meeting_room_dummy.db"),
)
SQL_INIT_PATH = os.path.join(_SCRIPT_DIR, "database_setting.sql")
PORT = int(os.environ.get("PORT", "8001"))

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

mcp = FastMCP("meeting-room-server")


def _get_conn() -> sqlite3.Connection:
    return db.get_connection(DB_PATH)


def tool_for(*modes):
    """
    指定したMODEのときだけ実際にmcp.tool()として登録するデコレータ。
    それ以外のMODEでは普通の関数のまま(登録されない)。
    """
    def decorator(func):
        if MODE in modes:
            return mcp.tool()(func)
        return func
    return decorator


@tool_for("dify")
def authenticate_employee(email: str) -> dict:
    """
    メールアドレスで本人確認を行う(完全一致のみ)。

    Args:
        email: 確認対象のメールアドレス
    """
    conn = _get_conn()
    try:
        return db.authenticate_employee(conn, email)
    finally:
        conn.close()


# ============================================================
# reservations - CRUD (adminは全て、difyは本人確認後のAgentにのみ接続)
# ============================================================
@tool_for("admin", "dify")
def add_reservation(
    title: str,
    start_time: str,
    end_time: str,
    category: str,
    description: str = "",
) -> dict:
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


@tool_for("admin", "dify")
def list_reservations_with_date (
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
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


# ============================================================
# 空き時間・統計 (dify専用。ユーザー向け問い合わせ機能)
# ============================================================
@tool_for("dify")
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


@tool_for("dify")
def get_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    予約データの詳細統計をまとめて取得する。「グラフで見せて」「傾向を教えて」
    「一番忙しい曜日は?」のような、単純な件数以上の分析が必要なときに使う。

    Args:
        start_date, end_date: 集計期間, "YYYY-MM-DD"。両方省略すると全期間。
        category: 特定のカテゴリだけに絞りたい場合

    Returns:
        {
          "success": true, "total": N,
          "by_category": {"会議": N, ...},
          "by_category_percent": {"会議": 45.5, ...},
          "by_weekday": {"月": N, "火": N, ...},
          "by_hour": {"09:00": N, "10:00": N, ...},
          "daily_counts": {"2026-08-24": N, ...},
          "average_duration_minutes": N
        }
    """
    conn = _get_conn()
    try:
        return db.get_statistics(conn, start_date=start_date, end_date=end_date, category=category)
    finally:
        conn.close()
        
@tool_for("admin", "dify")
def list_reservations_with_employee(
    email: str
) -> dict:
    """
    予約データの詳細統計をまとめて取得する。「グラフで見せて」「傾向を教えて」
    「一番忙しい曜日は?」のような、単純な件数以上の分析が必要なときに使う。

    Args:
        email: --
    """
    conn = _get_conn()
    try:
        return db.get_employee_reservations(conn, email=email)
    finally:
        conn.close()


if __name__ == "__main__":
    if MODE == "admin":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=PORT)