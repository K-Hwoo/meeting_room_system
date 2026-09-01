import os
import sys
import sqlite3
from typing import Optional

from fastmcp import FastMCP

import db_logic as db
import google_calendar

# "admin" または "dify"
MODE = os.environ.get("MCP_MODE", "admin")

# 현재 실행 중인 파이썬 스크립트 파일이 저장된 디렉터리의 절대 경로
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Databaseパス設定
DB_PATH = os.environ.get(
    "MEETING_ROOM_DB_PATH",
    os.path.join(_SCRIPT_DIR, "meeting_room.db"),
)

# 初期化SQLファイルのパス設定
SQL_INIT_PATH = os.path.join(_SCRIPT_DIR, "database_setting.sql")

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
    メールアドレスで本人確認を行う(完全一致のみ)。

    Args:
        email: 確認対象のメールアドレス
    """
    conn = _get_conn()
    try:
        return db.authenticate_employee(conn, email)
    finally:
        conn.close()


@tool_for("admin", "dify")
def add_reservation(
    title: str,
    start_time: str,
    end_time: str,
    category: str,
    description: str = "",
    participants: list = None,
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
        participants: 参加させたい社員名のリスト(任意)。employeesに登録されている
                      名前のみ紐付けられ、見つからないものは無視される。

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
        result = db.add_reservation(
            conn, title, start_time, end_time, category, description or None
        )

        participant_result = None

        if result["success"]:

            reservation_id = result["reservation"]["id"]

            if participants:
                participant_result = db.add_participants(
                    conn,
                    reservation_id,
                    participants
                )

            calendar_result = google_calendar.create_event(
                title=title,
                start_time=result["reservation"]["start_time"],
                end_time=result["reservation"]["end_time"],
                description=description or None,
            )
            if calendar_result["success"]:
                db.set_calendar_event_id(conn, result["reservation"]["id"], calendar_result["event_id"])
                result["reservation"]["google_calendar_event_id"] = calendar_result["event_id"]
                result["calendar_sync"] = "success"
            elif calendar_result["error"] == "calendar_not_configured":
                result["calendar_sync"] = "not_configured"
            else:
                result["calendar_sync"] = "failed"
                result["calendar_error"] = calendar_result["error"]

            # 참가자 처리 결과도 반환
            if participant_result:
                result["participants"] = participant_result

        return result
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
    指定されたメールアドレスの社員が参加する予約一覧を取得する。

    Args:
        email: 検索対象の社員のメールアドレス

    Returns:
        {"success": true, "reservations": [{"id":..,"title":..,"start_time":..,"end_time":..}, ...]}
    """
    conn = _get_conn()
    try:
        return db.get_employee_reservations(conn, email=email)
    finally:
        conn.close()


@tool_for("dify")
def create_reservation_request(
    title: str,
    start_time: str,
    end_time: str,
    category: str,
    requester_email: str,
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

    Returns:
        {"success": true, "request": {...}, "conflict_warning": bool}
        conflict_warning が true なら、その時間帯に既に他の予約があることを意味する。
        リクエスト自体は成功しているが、承認されない可能性が高いことをユーザーに伝えるとよい。
    """
    conn = _get_conn()
    try:
        return db.create_reservation_request(
            conn, title, start_time, end_time, category, requester_email, description or None
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
        return db.list_reservation_requests(conn, status=status)
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
        result = db.approve_reservation_request(conn, request_id)

        if result["success"]:
            reservation = result["reservation"]
            calendar_result = google_calendar.create_event(
                title=reservation["title"],
                start_time=reservation["start_time"],
                end_time=reservation["end_time"],
                description=reservation.get("description"),
            )
            if calendar_result["success"]:
                db.set_calendar_event_id(conn, reservation["id"], calendar_result["event_id"])
                reservation["google_calendar_event_id"] = calendar_result["event_id"]
                result["calendar_sync"] = "success"
            elif calendar_result["error"] == "calendar_not_configured":
                result["calendar_sync"] = "not_configured"
            else:
                result["calendar_sync"] = "failed"
                result["calendar_error"] = calendar_result["error"]

        return result
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
        return db.reject_reservation_request(conn, request_id, reason)
    finally:
        conn.close()


if __name__ == "__main__":
    if MODE == "admin":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=PORT)