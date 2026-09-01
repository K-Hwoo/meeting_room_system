import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID")
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "Asia/Tokyo"

_service = None  # 接続を使い回すためのキャッシュ


def _get_service():
    global _service
    if _service is None:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        _service = build("calendar", "v3", credentials=credentials)
    return _service


def _to_rfc3339(dt_str: str) -> str:
    return dt_str.replace(" ", "T") + "+09:00"


def create_event(title: str, start_time: str, end_time: str, description: str = None) -> dict:
    """
    Googleカレンダーにイベントを作成する。

    Returns:
        成功: {"success": true, "event_id": "..."}
        失敗: {"success": false, "error": "..."}
        (設定が無い場合は {"success": false, "error": "calendar_not_configured"})
    """
    if not SERVICE_ACCOUNT_FILE or not CALENDAR_ID:
        return {"success": False, "error": "calendar_not_configured"}

    try:
        service = _get_service()
        event = {
            "summary": title,
            "description": description or "",
            "start": {"dateTime": _to_rfc3339(start_time), "timeZone": TIMEZONE},
            "end": {"dateTime": _to_rfc3339(end_time), "timeZone": TIMEZONE},
        }
        created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return {"success": True, "event_id": created["id"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_event(event_id: str) -> dict:
    """予約削除時に対応するカレンダーイベントも削除する場合に使用。"""
    if not SERVICE_ACCOUNT_FILE or not CALENDAR_ID:
        return {"success": False, "error": "calendar_not_configured"}

    try:
        service = _get_service()
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}