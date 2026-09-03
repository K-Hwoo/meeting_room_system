import os
import sys
import sqlite3

from typing import Optional, List
from fastmcp import FastMCP

import services.authentication as auth
import services.crud_service as crud
import services.request_service as rs
import services.utilize_service as us
import services.find_service as fs

from utils.database import get_connection

# "admin" または "dify"
MODE = os.environ.get("MCP_MODE", "admin")

# 현재 실행 중인 파이썬 스크립트 파일이 저장된 디렉터리의 절대 경로
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Databaseパス設定
DB_PATH = os.environ.get(
    "MEETING_ROOM_DB_PATH",
    os.path.join(_SCRIPT_DIR, "database", "meeting_room.db"),
)

# 初期化SQLファイルのパス設定
SQL_INIT_PATH = os.path.join(_SCRIPT_DIR, "database", "database_setting.sql")

# PORT設定
PORT = int(os.environ.get("PORT", "8001"))

def _init_db_if_needed():
    if os.path.exists(DB_PATH):
        return

    if not os.path.exists(SQL_INIT_PATH):
        print(f"[Warning] 初期化用SQLファイルがありません: {SQL_INIT_PATH}", file=sys.stderr)
        return

    with open(SQL_INIT_PATH, "r", encoding="utf-8") as f:
        sql_script = f.read()

    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
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
    return get_connection(DB_PATH)

def tool_for(*modes):
    """
    매개변수로 전달받은 모드(*modes)일 때만,
    이 함수를 AI(MCP)가 사용할 수 있는 '툴'로 등록하는 데코레이터
    """
    def decorator(func):
        if MODE in modes:
            return mcp.tool()(func)
        return func
    return decorator

# ========================================================
@tool_for("dify")
def authenticate_employee(email: str) -> dict:
    """
    【社員認証】
    メールアドレスで本人確認を行う(完全一致のみ)。

    Args:
        email: 確認対象のメールアドレス
    """
    conn = _get_conn()
    try:
        return auth.authenticate_employee(conn, email)
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
    特定の日付または期間内の会議室予約リストを照会。
    カテゴリを指定することもできる。

    Args:
        date: 照会したい特定の日 ("YYYY-MM-DD") 
        start_date: 照会開始日 ("YYYY-MM-DD") 
        end_date: 照会終了日 ("YYYY-MM-DD") 
        category: 特定のカテゴリを設定 (「会議」「接客」「面接」「自由」)

    Returns:
        {"success": true, "reservations": [予約リスト]}
    """
    conn = _get_conn()
    try:
        return crud.list_reservations(conn, date=date, start_date=start_date, end_date=end_date, category=category)
    
    finally:
        conn.close()


@tool_for("admin", "dify")
def add_reservation(
    title: str, start_time: str, end_time: str, 
    category: str, participants: list, description: str = "",
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
        participants: 参加させたい社員名のリスト。employeesに登録されている
                      名前のみ紐付けられ、見つからないものは無視される。

    Returns:
        成功時 {"success": true, "reservation": {...}}
        失敗時 {"success": false, "error": "エラーコード", ...関連情報}
        
        【可能なエラーコード】
        missing_fields ・ invalid_category ・ invalid_datetime_format ・ end_before_start ・ time_overlap
    """
    
    conn = _get_conn()
    try:
        return crud.create_reservation_integrated(
            conn=conn,
            title=title,
            start_time=start_time,
            end_time=end_time,
            category=category,
            participant=participants,
            description=description or None,
        )
    finally:
        conn.close()


# ============================================================
# 空き時間・統計 (dify専用。ユーザー向け問い合わせ機能)
# ============================================================
@tool_for("dify")
def find_available_slots(
    date: str,
    duration_minutes: int = 1, 
    business_start: str = "09:00",
    business_end: str = "18:00",
) -> dict:
    """
    特定の日付に指定した時間ほど会議室の予約可能な時間帯を照会できる

    Args:
        date: 照会したい特定の日 ("YYYY-MM-DD")
        duration_minutes: 必要な最小時間(分)。(デフォルト 1)
        business_start: 探索開始時刻 ("HH:MM") / (デフォルト 09:00)
        business_end: 探索終了時刻 ("HH:MM") / (デフォルト 18:00)

    Returns:
        {
            "success": true, 
            "date": ..., 
            "duration_minutes": ...,
            "available_slots": [{"start":"HH:MM","end":"HH:MM"}, ...]}
    
    available_slots が空配列なら、その条件を満たす空き時間がないという意味。
    """
    conn = _get_conn()
    try:
        return us.find_available_slots(conn, date, duration_minutes, business_start, business_end)
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
        return us.get_statistics(conn, start_date=start_date, end_date=end_date, category=category)
    finally:
        conn.close()
        
        
@tool_for("admin", "dify")
def list_reservations_with_employee(
    email: str
) -> dict:
    """
    指定されたメールアドレスの社員が参加する予約一覧を取得する。

    Args:
        email: 検索対象の社員のメールアドレス

    Returns:
        {"success": true, "reservations": [{"id":..,"title":..,"start_time":..,"end_time":..}, ...]}
    """
    conn = _get_conn()
    try:
        return fs.list_reservations_with_employee(conn, email=email)
    finally:
        conn.close()


@tool_for("dify")
def create_reservation_request(
    title: str,
    start_time: str,
    end_time: str,
    category: str,
    requester_email: str,
    participant_names: List[str],
    description: str = "",
) -> dict:
    """
    一般社員が会議室の予約をリクエストする。

    このツールは実際の予約を作らず、管理者の承認待ち状態として記録するだけ。
    一般社員向けAgentにのみ接続すること(管理者はadd_reservationで直接予約可能)。

    Args:
        title: 会議のタイトル
        start_time: 開始時間、"YYYY-MM-DD HH:MM" 形式
        end_time: 終了時間、同じ形式
        category: 「会議」「接客」「面接」「自由」のいずれか
        requester_email: リクエストする本人のメールアドレス
                         (本人確認済みのメールアドレスをそのまま使うこと)
        description: 補足説明(任意)
        participant_names: 参加させたい社員名のリスト(必須)。
                           承認された時点で実際の予約に紐付けられる。

    Returns:
        {"success": true, "request": {...}, "conflict_warning": bool}
        conflict_warning が true なら、その時間帯に既に他の予約があることを意味する。
        リクエスト自体は成功しているが、承認されない可能性が高いことをユーザーに伝えるとよい。
    """
    conn = _get_conn()
    try:
        return rs.create_reservation_request(
            conn=conn,
            title=title,
            start_time=start_time,
            end_time=end_time,
            category=category,
            requester_email=requester_email,
            participant_names=participant_names,
            description=description or None,
        )
    finally:
        conn.close()


@tool_for("admin", "dify")
def list_reservation_requests(status: Optional[str] = None) -> dict:
    """
    予約リクエストの一覧を取得する(管理者用)。

    Args:
        status: "pending"(承認待ち) / "approved"(承認済み) / "rejected"(却下済み)。
                指定しなければ全件。特に指示がなければ "pending" で確認するのが自然。

    Returns:
        {"success": true, "requests": [...]}
    """
    conn = _get_conn()
    try:
        return rs.list_reservation_requests(conn, status=status)
    finally:
        conn.close()


@tool_for("admin", "dify")
def approve_reservation_request(request_id: int) -> dict:
    """
    予約リクエストを承認して実際の予約を作成する(管理者用)。
    承認と同時にGoogleカレンダーへの登録も自動で行う。

    Args:
        request_id: 承認するリクエストのID (list_reservation_requestsで確認)

    Returns:
        成功時 {"success": true, "request": {...}, "reservation": {...},
                "calendar_sync": "success" | "failed" | "not_configured"}
        失敗時 {"success": false, "error": "エラーコード", ...}
        エラーコード:
          - request_not_found: 存在しないrequest_id
          - already_processed: 既に承認/却下済み
          - approve_failed: 承認時点で他の予約と重複する等の理由で失敗
                            (reasonに詳細。リクエストはpendingのまま維持される)
    """
    conn = _get_conn()
    try:
        return rs.approve_reservation_request(conn, request_id)
    finally:
        conn.close()


@tool_for("admin", "dify")
def reject_reservation_request(request_id: int, reason: Optional[str] = None) -> dict:
    """
    予約リクエストを却下する(管理者用)。実際の予約は作成しない。

    Args:
        request_id: 却下するリクエストのID
        reason: 却下理由(任意、あとで参照できるよう残しておくとよい)

    Returns:
        成功時 {"success": true, "request": {...}}
        失敗時 {"success": false, "error": "request_not_found" | "already_processed", ...}
    """
    conn = _get_conn()
    try:
        return rs.reject_reservation_request(conn, request_id, reason)
    finally:
        conn.close()


if __name__ == "__main__":
    if MODE == "admin":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=PORT)
